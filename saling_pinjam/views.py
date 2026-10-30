import calendar
from datetime import date, timedelta

from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Min, Q
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from .models import BorrowItem, BorrowRequest
from .forms import BorrowItemForm, BorrowRequestForm, BOOKED_STATUSES, conflicting_bookings

HARI = ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu']
BULAN = [
    'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
    'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember',
]
BULAN_SINGKAT = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']

# Pengajuan yang masih "memakan" slot peminjam
ACTIVE_STATUSES = [
    BorrowRequest.Status.PENDING,
    BorrowRequest.Status.APPROVED,
    BorrowRequest.Status.ONGOING,
]
MAX_ACTIVE_BORROWS = 2

# Perubahan status yang boleh dilakukan pemilik barang: status sekarang -> status tujuan
ALLOWED_TRANSITIONS = {
    BorrowRequest.Status.PENDING: [BorrowRequest.Status.APPROVED, BorrowRequest.Status.REJECTED],
    BorrowRequest.Status.APPROVED: [BorrowRequest.Status.ONGOING],
    BorrowRequest.Status.ONGOING: [BorrowRequest.Status.RETURNED],
}

# Batas pilihan tanggal kembali di kartu kalender, supaya dropdown tidak kepanjangan
MAX_END_OPTIONS = 31


def format_label(day):
    return f'{HARI[day.weekday()]}, {day.day} {BULAN[day.month - 1]} {day.year}'


def parse_date(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def add_months(first_of_month, months):
    index = first_of_month.year * 12 + first_of_month.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def redirect_back(request, fallback, *args, **kwargs):
    """Balik ke halaman asal (dikirim lewat input `next`), kalau aman. Kalau tidak, ke `fallback`."""
    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(next_url)
    return redirect(fallback, *args, **kwargs)


def build_calendar(month_start, today, selected, bookings):
    """
    Susun kalender satu bulan (minggu dimulai hari Minggu, sesuai desain).
    `bookings` = pinjaman aktif user, ditampilkan sebagai label di tanggalnya.
    """
    cal = calendar.Calendar(firstweekday=6)  # 6 = Minggu
    weeks = []
    for week in cal.monthdatescalendar(month_start.year, month_start.month):
        weeks.append([
            {
                'date': day,
                'in_month': day.month == month_start.month,
                'is_today': day == today,
                'is_past': day < today,
                'is_selected': day == selected,
                'bookings': [b for b in bookings if b.start_date <= day <= b.end_date],
            }
            for day in week
        ])
    return weeks


def end_date_options(item, start, next_booking_start):
    """Pilihan tanggal kembali: dibatasi max_duration_days dan jadwal pinjaman berikutnya."""
    last = start + timedelta(days=min(item.max_duration_days, MAX_END_OPTIONS) - 1)
    if next_booking_start:
        last = min(last, next_booking_start - timedelta(days=1))

    options = []
    day = start
    while day <= last:
        days = (day - start).days + 1
        options.append({
            'value': day.isoformat(),
            'label': f's/d {day.day} {BULAN_SINGKAT[day.month - 1]} ({days} hari)',
        })
        day += timedelta(days=1)
    return options


def item_list(request):
    """
    Halaman utama Pinjam: kalender, barang yang bebas dipinjam di tanggal terpilih,
    katalog barang, dan slot pinjaman aktif milik user.
    """
    category = request.GET.get('category', '')
    query = request.GET.get('q', '')

    items = BorrowItem.objects.all()

    if category:
        items = items.filter(category=category)
    if query:
        items = items.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(pickup_location__icontains=query)
        )

    today = date.today()

    # Tanggal yang diklik di kalender (?tanggal=2026-11-03). Tanggal lewat dianggap hari ini.
    selected = parse_date(request.GET.get('tanggal')) or today
    if selected < today:
        selected = today

    month_start = selected.replace(day=1)
    this_month = today.replace(day=1)
    prev_month_date = None
    if month_start > this_month:
        prev_month_date = max(add_months(month_start, -1), today)
    next_month_date = add_months(month_start, 1)

    # Pinjaman aktif user: isi slot di panel kanan + label di kalender
    my_active = []
    if request.user.is_authenticated:
        my_active = list(
            BorrowRequest.objects
            .filter(borrower=request.user, status__in=ACTIVE_STATUSES)
            .select_related('item')
            .order_by('start_date')
        )
    shown = my_active[:MAX_ACTIVE_BORROWS]
    active_slots = shown + [None] * (MAX_ACTIVE_BORROWS - len(shown))

    # Barang yang bebas di tanggal terpilih
    booked_on_selected = (
        BorrowRequest.objects
        .filter(status__in=BOOKED_STATUSES, start_date__lte=selected, end_date__gte=selected)
        .values('item_id')
    )
    available = (
        BorrowItem.objects
        .exclude(status=BorrowItem.Status.UNAVAILABLE)
        .exclude(id__in=booked_on_selected)
        .select_related('owner')
    )
    if request.user.is_authenticated:
        available = available.exclude(owner=request.user)
    busy_items = BorrowItem.objects.filter(id__in=booked_on_selected)

    # Jadwal pinjaman berikutnya tiap barang, supaya pilihan tanggal kembali tidak menabrak
    next_bookings = dict(
        BorrowRequest.objects
        .filter(item__in=available, status__in=BOOKED_STATUSES, start_date__gt=selected)
        .order_by()
        .values('item_id')
        .annotate(first_start=Min('start_date'))
        .values_list('item_id', 'first_start')
    )
    my_item_ids = {req.item_id for req in my_active}

    available = list(available)
    for item in available:
        item.end_options = end_date_options(item, selected, next_bookings.get(item.id))
        item.already_requested = item.id in my_item_ids

    context = {
        'items': items,
        'categories': BorrowItem.Category.choices,
        'selected_category': category,
        'query': query,
        # Bagian kalender
        'today_label': format_label(today),
        'month_label': f'{BULAN[month_start.month - 1]} {month_start.year}',
        'calendar_weeks': build_calendar(month_start, today, selected, my_active),
        'prev_month_date': prev_month_date,
        'next_month_date': next_month_date,
        # Bagian "Barang bebas dipinjam"
        'selected_date': selected,
        'selected_label': format_label(selected),
        'available_items': available,
        'busy_items': busy_items,
        # Bagian "Pinjaman Saya"
        'active_slots': active_slots,
        'active_count': len(my_active),
        'max_active': MAX_ACTIVE_BORROWS,
        'slots_full': len(my_active) >= MAX_ACTIVE_BORROWS,
    }
    return render(request, 'saling_pinjam/item_list.html', context)


def item_detail(request, id):
    """
    Detail barang pinjaman dan form pengajuan pinjam.
    """
    item = get_object_or_404(BorrowItem, id=id)
    request_form = BorrowRequestForm()

    context = {
        'item': item,
        'request_form': request_form,
    }

    # Untuk pemilik: info yang dipakai di bagian "Hapus barang ini"
    if request.user == item.owner:
        context['locked_count'] = item.requests.filter(status__in=BOOKED_STATUSES).count()
        context['pending_count'] = item.requests.filter(status=BorrowRequest.Status.PENDING).count()

    return render(request, 'saling_pinjam/item_detail.html', context)


@login_required
def item_create(request):
    """
    Menambahkan barang baru yang ingin dipinjamkan ke mahasiswa lain.
    """
    if request.method == 'POST':
        form = BorrowItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.owner = request.user
            item.save()
            messages.success(request, f'Barang "{item.name}" berhasil didaftarkan untuk dipinjamkan!')
            return redirect('saling_pinjam:item_detail', id=item.id)
    else:
        form = BorrowItemForm()

    return render(request, 'saling_pinjam/tambah_barang.html', {'form': form, 'title': 'Pinjamkan Barang Anda'})


@login_required
def item_edit(request, id):
    """
    Mengubah data barang. Hanya pemilik barang yang bisa membuka halaman ini.
    Form dan template-nya sama dengan tambah barang, bedanya form diisi data lama (instance).
    """
    item = get_object_or_404(BorrowItem, id=id, owner=request.user)

    if request.method == 'POST':
        form = BorrowItemForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, f'Perubahan pada "{item.name}" sudah disimpan.')
            return redirect('saling_pinjam:item_detail', id=item.id)
    else:
        form = BorrowItemForm(instance=item)

    return render(request, 'saling_pinjam/tambah_barang.html', {'form': form, 'title': 'Edit Barang', 'item': item})


@login_required
@require_POST
def item_delete(request, id):
    """
    Menghapus barang milik user.
    Ditolak kalau barang sedang dipinjam atau sudah disetujui untuk dipinjam,
    supaya pinjaman yang sedang jalan tidak ikut hilang.
    """
    item = get_object_or_404(BorrowItem, id=id, owner=request.user)

    if item.requests.filter(status__in=BOOKED_STATUSES).exists():
        messages.error(
            request,
            f'"{item.name}" belum bisa dihapus karena sedang dipinjam atau sudah disetujui untuk dipinjam. '
            'Selesaikan pinjamannya dulu.',
        )
        return redirect_back(request, 'saling_pinjam:item_detail', id=item.id)

    name = item.name
    item.delete()  # pengajuan yang masih menunggu untuk barang ini ikut terhapus (on_delete=CASCADE)
    messages.success(request, f'Barang "{name}" sudah dihapus.')
    return redirect(reverse('saling_pinjam:my_borrows') + '#barang-saya')


@login_required
def request_borrow(request, id):
    """
    Mengajukan permohonan pinjam atas suatu barang.
    Bisa dari halaman detail, atau dari kartu di bawah kalender (bawa input `next`).
    """
    item = get_object_or_404(BorrowItem, id=id)

    if item.owner == request.user:
        messages.error(request, 'Anda tidak bisa meminjam barang milik Anda sendiri.')
        return redirect('saling_pinjam:item_detail', id=item.id)

    if item.status == BorrowItem.Status.UNAVAILABLE:
        messages.warning(request, 'Maaf, barang ini sedang tidak tersedia untuk dipinjam.')
        return redirect_back(request, 'saling_pinjam:item_detail', id=item.id)

    if request.method == 'POST':
        my_active = BorrowRequest.objects.filter(borrower=request.user, status__in=ACTIVE_STATUSES)

        if my_active.filter(item=item).exists():
            messages.warning(request, f'Kamu sudah punya pengajuan aktif untuk "{item.name}".')
            return redirect_back(request, 'saling_pinjam:item_detail', id=item.id)

        if my_active.count() >= MAX_ACTIVE_BORROWS:
            messages.warning(
                request,
                f'Slot pinjaman kamu penuh ({MAX_ACTIVE_BORROWS} barang). '
                'Selesaikan atau batalkan salah satu dulu.',
            )
            return redirect_back(request, 'saling_pinjam:item_detail', id=item.id)

        form = BorrowRequestForm(request.POST, item=item)
        if form.is_valid():
            borrow_req = form.save(commit=False)
            borrow_req.item = item
            borrow_req.borrower = request.user
            borrow_req.save()
            messages.success(request, f'Pengajuan peminjaman "{item.name}" berhasil dikirim! Menunggu konfirmasi pemilik.')
            return redirect_back(request, 'saling_pinjam:my_borrows')
    else:
        form = BorrowRequestForm(item=item)

    return render(request, 'saling_pinjam/request_form.html', {'item': item, 'form': form})


@login_required
@require_POST
def cancel_request(request, request_id):
    """
    Peminjam membatalkan pengajuannya sendiri (selama barang belum diambil),
    supaya slot pinjamannya kosong lagi.
    """
    borrow_req = get_object_or_404(
        BorrowRequest.objects.select_related('item'), id=request_id, borrower=request.user
    )

    if borrow_req.status in (BorrowRequest.Status.PENDING, BorrowRequest.Status.APPROVED):
        borrow_req.status = BorrowRequest.Status.CANCELLED
        borrow_req.save()
        messages.success(request, f'Pengajuan "{borrow_req.item.name}" dibatalkan.')
    else:
        messages.error(request, 'Pengajuan ini sudah tidak bisa dibatalkan.')

    return redirect_back(request, 'saling_pinjam:my_borrows')


@login_required
def my_borrows(request):
    """
    Dashboard untuk melihat:
    1. Pengajuan yang diajukan oleh user (sebagai peminjam)
    2. Pengajuan yang masuk atas barang-barang milik user (sebagai pemilik)
    """
    as_borrower = BorrowRequest.objects.filter(borrower=request.user).select_related('item', 'item__owner')
    as_owner = BorrowRequest.objects.filter(item__owner=request.user).select_related('item', 'borrower')
    my_items = BorrowItem.objects.filter(owner=request.user)

    context = {
        'as_borrower': as_borrower,
        'as_owner': as_owner,
        'my_items': my_items,
    }
    return render(request, 'saling_pinjam/my_borrows.html', context)


@login_required
@require_POST
def update_request_status(request, request_id, new_status):
    """
    Aksi persetujuan (Approve/Reject/Return) oleh pemilik barang.
    """
    with transaction.atomic():
        borrow_req = get_object_or_404(
            BorrowRequest.objects.select_for_update().select_related('item'),
            id=request_id,
            item__owner=request.user,
        )
        item = borrow_req.item

        if new_status not in ALLOWED_TRANSITIONS.get(borrow_req.status, []):
            messages.error(request, 'Status tidak valid.')
            return redirect('saling_pinjam:my_borrows')

        if new_status == BorrowRequest.Status.APPROVED and conflicting_bookings(
            item, borrow_req.start_date, borrow_req.end_date, exclude_id=borrow_req.id
        ).exists():
            messages.error(request, 'Tidak bisa disetujui: tanggalnya bentrok dengan pinjaman lain yang sudah disetujui.')
            return redirect('saling_pinjam:my_borrows')

        if new_status == BorrowRequest.Status.APPROVED and item.status == BorrowItem.Status.UNAVAILABLE:
            messages.error(request, 'Barang sedang dinonaktifkan pemilik sehingga tidak bisa disetujui.')
            return redirect('saling_pinjam:my_borrows')

        borrow_req.status = new_status
        borrow_req.save()

        auto_rejected = 0
        if new_status == BorrowRequest.Status.APPROVED:
            # Pengajuan lain di tanggal yang bentrok otomatis ditolak, supaya slot peminjamnya kosong lagi
            auto_rejected = (
                BorrowRequest.objects
                .filter(
                    item=item,
                    status=BorrowRequest.Status.PENDING,
                    start_date__lte=borrow_req.end_date,
                    end_date__gte=borrow_req.start_date,
                )
                .exclude(id=borrow_req.id)
                .update(status=BorrowRequest.Status.REJECTED, updated_at=timezone.now())
            )
        elif new_status == BorrowRequest.Status.ONGOING:
            # Status barang baru berubah saat benar-benar diambil, bukan saat disetujui
            item.status = BorrowItem.Status.BORROWED
            item.save()
        elif new_status == BorrowRequest.Status.RETURNED:
            item.status = BorrowItem.Status.AVAILABLE
            item.save()

    message = f'Status pengajuan diperbarui menjadi "{borrow_req.get_status_display()}".'
    if auto_rejected:
        message += f' {auto_rejected} pengajuan lain di tanggal yang sama otomatis ditolak.'
    messages.success(request, message)

    return redirect('saling_pinjam:my_borrows')