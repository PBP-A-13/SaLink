import calendar
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import BorrowItemForm, BorrowRequestForm
from .models import BorrowItem, BorrowRequest

HARI = ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu']
BULAN = [
    'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
    'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember',
]


def build_calendar(today):
    cal = calendar.Calendar(firstweekday=6)
    return [[
        {'date': day, 'in_month': day.month == today.month, 'is_today': day == today}
        for day in week
    ] for week in cal.monthdatescalendar(today.year, today.month)]


def item_list(request):
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
    my_requests = []
    if request.user.is_authenticated:
        my_requests = BorrowRequest.objects.filter(borrower=request.user).select_related('item')[:5]

    return render(request, 'saling_pinjam/item_list.html', {
        'items': items,
        'categories': BorrowItem.Category.choices,
        'selected_category': category,
        'query': query,
        'today_label': f'{HARI[today.weekday()]}, {today.day} {BULAN[today.month - 1]} {today.year}',
        'month_label': f'{BULAN[today.month - 1]} {today.year}',
        'calendar_weeks': build_calendar(today),
        'my_requests': my_requests,
    })


def item_detail(request, id):
    item = get_object_or_404(BorrowItem, id=id)
    return render(request, 'saling_pinjam/item_detail.html', {
        'item': item,
        'request_form': BorrowRequestForm(),
    })


@login_required
def item_create(request):
    form = BorrowItemForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        item = form.save(commit=False)
        item.owner = request.user
        item.save()
        messages.success(request, f'Barang "{item.name}" berhasil didaftarkan untuk dipinjamkan!')
        return redirect('saling_pinjam:item_detail', id=item.id)
    return render(request, 'saling_pinjam/item_form.html', {
        'form': form,
        'title': 'Pinjamkan Barang Anda',
    })


@login_required
def request_borrow(request, id):
    item = get_object_or_404(BorrowItem, id=id)
    if item.owner == request.user:
        messages.error(request, 'Anda tidak bisa meminjam barang milik Anda sendiri.')
        return redirect('saling_pinjam:item_detail', id=item.id)
    if item.status != BorrowItem.Status.AVAILABLE:
        messages.warning(request, 'Maaf, barang ini sedang tidak tersedia untuk dipinjam.')
        return redirect('saling_pinjam:item_detail', id=item.id)

    form = BorrowRequestForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        borrow_request = form.save(commit=False)
        borrow_request.item = item
        borrow_request.borrower = request.user
        borrow_request.save()
        messages.success(request, f'Pengajuan peminjaman "{item.name}" berhasil dikirim! Menunggu konfirmasi pemilik.')
        return redirect('saling_pinjam:my_borrows')
    return render(request, 'saling_pinjam/request_form.html', {'item': item, 'form': form})


@login_required
def my_borrows(request):
    context = {
        'as_borrower': BorrowRequest.objects.filter(borrower=request.user).select_related('item', 'item__owner'),
        'as_owner': BorrowRequest.objects.filter(item__owner=request.user).select_related('item', 'borrower'),
        'my_items': BorrowItem.objects.filter(owner=request.user),
    }
    return render(request, 'saling_pinjam/my_borrows.html', context)


@login_required
def update_request_status(request, request_id, new_status):
    borrow_request = get_object_or_404(BorrowRequest, id=request_id, item__owner=request.user)
    valid_statuses = [choice[0] for choice in BorrowRequest.Status.choices]
    if new_status in valid_statuses:
        borrow_request.status = new_status
        borrow_request.save()
        if new_status in (BorrowRequest.Status.APPROVED, BorrowRequest.Status.ONGOING):
            borrow_request.item.status = BorrowItem.Status.BORROWED
            borrow_request.item.save()
        elif new_status == BorrowRequest.Status.RETURNED:
            borrow_request.item.status = BorrowItem.Status.AVAILABLE
            borrow_request.item.save()
        messages.success(request, f'Status pengajuan diperbarui menjadi "{borrow_request.get_status_display()}".')
    else:
        messages.error(request, 'Status tidak valid.')
    return redirect('saling_pinjam:my_borrows')