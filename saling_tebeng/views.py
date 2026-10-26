from django.shortcuts import render, get_object_or_404, redirect
from datetime import date as date_cls, datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_time
from django.views.decorators.http import require_POST
from .models import RideBooking, RideOffer, RideRequest, RideSchedule, Vehicle


LOCATIONS = {
    'Fakultas Teknik',
    'Fakultas Ilmu Komputer, Gedung Baru',
    'Fakultas Ilmu Komputer, Gedung Lama',
    'Fakultas Matematika dan Ilmu Pengetahuan Alam',
    'Fakultas Ekonomi dan Bisnis',
    'Fakultas Ilmu Budaya',
    'Fakultas Ilmu Administrasi',
    'Fakultas Kesehatan Masyarakat',
    'Fakultas Ilmu Keperawatan',
    'Fakultas Hukum',
    'Fakultas Psikologi',
    'Fakultas Kedokteran',
    'Vokasi',
    'Fakultas Ilmu Politik dan Sosial',
    'Balairung',
    'Perpusat UI',
    'Sarana Olahraga',
    'RSUI',
    'Pusat Kegiatan Mahassiswa',
    'Kutek',
    'Kukel',
    'Stasiun UI',
    'Stasiun Pondok Cina',
    'Rumpun Ilmu Kesehatan',
}

PRICE_BY_TYPE = {'motor': 5000, 'mobil' : 7000}
KURUN_WAKTU = 30
HARI = ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumta', 'Sabtu', 'Minggu']

def _minutes(t):
    return t.hour * 60 + t.minute

def evaluate_matched(schedule, origin, destination, requested_time):
    origin_matched = schedule.origin.strip().lower() == origin.strip().lower()
    destination_matched = schedule.destination.strip().lower() == destination.strip().lower()
    time_difference = _minutes(schedule.departure_time) - _minutes(requested_time)
    time_matched = 0 <= time_difference <= KURUN_WAKTU

    reasons = []
    if not origin_matched:
        reasons.append('Asal Berbeda')
    elif not destination_matched:
        reasons.append('Tujuan Berbeda')
    if not time_matched:
        reasons.append('Jam Berbeda')
    if not time_matched and not destination_matched and not origin_matched:
        reasons.append('Not Matched')

    return {
        'matched' : origin_matched and destination_matched and time_matched,
        'origin_matched': origin_matched,
        'destination_matched': destination_matched,
        'time_matched': time_matched,
        'time_difference': abs(time_difference),
        'reasons': reasons,
    }

def _week_days():
    today = timezone.localdate()
    return [
        {
            'date': today + timedelta(days=i),
            'name': HARI[(today + timedelta(days=i)).weekday()],
        }
        for i in range(7)
    ]


#gabung tebengan
def _create_booking(user, schedule_id, seats=1):
    with transaction.atomic():
        schedule = (
            RideSchedule.objects.select_for_update()
            .select_related('ride_offer__driver')
            .get(pk=schedule_id)
        )
        if not schedule.is_active or not schedule.ride_offer.is_active:
            return None, 'Tebengan ini sudah tidak aktif.'
        if schedule.ride_offer.driver_id == user.id:
            return None, 'Kamu tidak bisa menebeng tawaranmu sendiri.'
        if RideBooking.objects.filter(
            ride_schedule=schedule, passenger=user
        ).exclude(status='cancelled').exists():
            return None, 'Kamu sudah bergabung di tebengan ini.'
        if seats < 1 or schedule.available_seats < seats:
            return None, 'Kursi tidak mencukupi.'

        booking = RideBooking.objects.create(
            ride_schedule=schedule, passenger=user,
            seats=seats, status='confirmed',
        )
        schedule.available_seats -= seats
        schedule.save(update_fields=['available_seats'])

        RideRequest.objects.filter(
            passenger=user, date=schedule.date, status='searching',
            origin__iexact=schedule.origin,
            destination__iexact=schedule.destination,
        ).update(status='matched')
        return booking, None


# ---------------------------------------------------------------------------
# Cari tebengan
# ---------------------------------------------------------------------------

@login_required
def nebeng_list(request):
    """
    Halaman utama NEBENG. Input: asal, tujuan, jam (+ tanggal, default hari ini).
    Hasil: tawaran dengan status matched / tidak (beserta alasannya).
    """
    origin = request.GET.get('asal', '').strip()
    destination = request.GET.get('tujuan', '').strip()
    req_time = parse_time(request.GET.get('jam', ''))
    req_date = parse_date(request.GET.get('tanggal', '')) or timezone.localdate()

    results = []
    searched = bool(origin and destination and req_time)

    if searched:
        o_lat, o_lng = LOCATIONS.get(origin, (None, None))
        d_lat, d_lng = LOCATIONS.get(destination, (None, None))
        RideRequest.objects.get_or_create(
            passenger=request.user, date=req_date, requested_time=req_time,
            origin=origin, destination=destination, status='searching',
            defaults={
                'origin_latitude': o_lat, 'origin_longitude': o_lng,
                'destination_latitude': d_lat, 'destination_longitude': d_lng,
            },
        )

        qs = (
            RideSchedule.objects
            .filter(date=req_date, is_active=True, available_seats__gt=0,
                    ride_offer__is_active=True)
            .exclude(ride_offer__driver=request.user)
            .filter(Q(origin__iexact=origin) | Q(destination__iexact=destination))
            .select_related('ride_offer__driver', 'ride_offer__vehicle')
        )
        if req_date == timezone.localdate():
            qs = qs.filter(departure_time__gte=timezone.localtime().time())

        booked_ids = set(
            RideBooking.objects.filter(passenger=request.user)
            .exclude(status='cancelled')
            .values_list('ride_schedule_id', flat=True)
        )

        for s in qs:
            info = evaluate_matched(s, origin, destination, req_time)
            info.update({
                'schedule': s,
                'driver': s.ride_offer.driver,
                'vehicle': s.ride_offer.vehicle,
                'already_booked': s.id in booked_ids,
            })
            results.append(info)

        # matched dulu, lalu yang selisih jamnya paling kecil
        results.sort(key=lambda r: (not r['matched'], len(r['reasons']), r['time_diff']))

    return render(request, 'nebeng/nebeng_list.html', {
        'locations': list(LOCATIONS.keys()),
        'results': results,
        'searched': searched,
        'asal': origin, 'tujuan': destination,
        'jam': request.GET.get('jam', ''), 'tanggal': req_date,
    })


# ---------------------------------------------------------------------------
# Tawarkan tebengan
# ---------------------------------------------------------------------------

class _SlotError(Exception):
    def __init__(self, errors):
        self.errors = errors

#tawarkan tebengan
@login_required
def tawarkan_tebengan(request):
    """
    Halaman jadwal mingguan. Per hari bisa ada banyak baris (jam, asal, tujuan,
    harga) lewat tombol "tambah jam". Di kanan: jenis kendaraan + kapasitas.

    Nama field POST per hari (tanggal ISO):
        time_<YYYY-MM-DD>[], origin_<..>[], destination_<..>[], price_<..>[]
    price: 'paid' (tarif standar) atau 'free'.
    """
    days = _week_days()
    existing = RideSchedule.objects.filter(
        ride_offer__driver=request.user, is_active=True,
        date__gte=days[0]['date'], date__lte=days[-1]['date'],
    ).order_by('date', 'departure_time')

    ctx = {
        'days': days,
        'locations': list(LOCATIONS.keys()),
        'vehicle_types': Vehicle.VEHICLE_TYPE_CHOICES,
        'existing': existing,
        'posted': request.POST,
    }
    if request.method != 'POST':
        return render(request, 'nebeng/offer_ride.html', ctx)

    errors = []
    vehicle_type = request.POST.get('vehicle_type', '')
    if vehicle_type not in PRICE_BY_TYPE:
        errors.append('Pilih jenis kendaraan.')
    try:
        capacity = int(request.POST.get('capacity', ''))
        if capacity < 1:
            raise ValueError
    except ValueError:
        capacity = 0
        errors.append('Kapasitas minimal 1.')

    # kumpulkan slot per hari
    slots = []
    for d in days:
        iso = d['date'].isoformat()
        rows = zip(
            request.POST.getlist(f'time_{iso}'),
            request.POST.getlist(f'origin_{iso}'),
            request.POST.getlist(f'destination_{iso}'),
            request.POST.getlist(f'price_{iso}') or ['paid'] * 50,
        )
        for t, o, dest, p in rows:
            if not (t or o or dest):
                continue  # baris kosong
            label = f'{d["name"]} {d["date"]:%d/%m}'
            tm = parse_time(t)
            if not tm or o not in LOCATIONS or dest not in LOCATIONS:
                errors.append(f'{label}: jam, asal, dan tujuan wajib diisi.')
            elif o == dest:
                errors.append(f'{label}: asal dan tujuan tidak boleh sama.')
            else:
                slots.append((d['date'], tm, o, dest, p))

    if not slots and not errors:
        errors.append('Isi minimal satu jadwal.')

    if not errors:
        try:
            with transaction.atomic():
                vehicle = Vehicle.objects.filter(
                    owner=request.user, vehicle_type=vehicle_type, is_active=True
                ).first()
                if vehicle:
                    vehicle.capacity = capacity
                    vehicle.save(update_fields=['capacity'])
                else:
                    vehicle = Vehicle.objects.create(
                        owner=request.user, vehicle_type=vehicle_type,
                        capacity=capacity,
                        brand=request.POST.get('brand', '').strip(),
                        model=request.POST.get('model', '').strip(),
                        license_plate=request.POST.get('license_plate', '').strip(),
                    )
                offer = RideOffer.objects.create(driver=request.user, vehicle=vehicle)

                slot_errors = []
                for dt, tm, o, dest, p in slots:
                    label = f'{dt:%d/%m} {tm:%H:%M}'
                    if RideSchedule.objects.filter(
                        ride_offer__driver=request.user, date=dt,
                        departure_time=tm, is_active=True,
                    ).exists():
                        slot_errors.append(f'{label}: jadwal di jam ini sudah ada.')
                        continue
                    (olat, olng), (dlat, dlng) = LOCATIONS[o], LOCATIONS[dest]
                    sched = RideSchedule(
                        ride_offer=offer, date=dt, departure_time=tm,
                        origin=o, destination=dest,
                        origin_latitude=olat, origin_longitude=olng,
                        destination_latitude=dlat, destination_longitude=dlng,
                        available_seats=capacity,
                        price=0 if p == 'free' else PRICE_BY_TYPE[vehicle_type],
                    )
                    try:
                        sched.full_clean()
                    except ValidationError as e:
                        slot_errors.extend(f'{label}: {m}' for m in e.messages)
                        continue
                    sched.save()
                if slot_errors:
                    raise _SlotError(slot_errors)
        except _SlotError as e:
            errors.extend(e.errors)

    if errors:
        for e in errors:
            messages.error(request, e)
        return render(request, 'nebeng/tawarkan_tebengan.html', ctx)

    messages.success(request, 'Tawaran tebengan berhasil disimpan.')
    return redirect('nebeng_list')


@login_required
@require_POST
def cancel_schedule(request, schedule_id):
    schedule = get_object_or_404(
        RideSchedule, pk=schedule_id, ride_offer__driver=request.user
    )
    schedule.is_active = False
    schedule.save(update_fields=['is_active'])
    schedule.bookings.exclude(status='completed').update(status='cancelled')
    messages.success(request, 'Jadwal dibatalkan.')
    return redirect('offer_ride')


# ---------------------------------------------------------------------------
# Gabung & chat
# ---------------------------------------------------------------------------

@login_required
@require_POST
def join_ride(request, schedule_id):
    """
    Gabung langsung dari daftar. HANYA boleh jika matched
    (dicek ulang di server, bukan hanya dari tombol di UI).
    Jika tidak matched -> arahkan ke chat untuk menyesuaikan.
    """
    schedule = get_object_or_404(RideSchedule, pk=schedule_id)
    origin = request.POST.get('asal', '')
    destination = request.POST.get('tujuan', '')
    req_time = parse_time(request.POST.get('jam', ''))
    seats = int(request.POST.get('seats', 1) or 1)

    if not (origin and destination and req_time):
        messages.error(request, 'Data pencarian tidak lengkap.')
        return redirect('nebeng_list')

    if not evaluate_matched(schedule, origin, destination, req_time)['matched']:
        messages.info(request, 'Belum cocok, sesuaikan dulu lewat chat.')
        return redirect('ride_chat', schedule_id=schedule.id)

    booking, err = _create_booking(request.user, schedule.id, seats)
    if err:
        messages.error(request, err)
        return redirect('nebeng_list')
    messages.success(request, 'Berhasil bergabung ke tebengan!')
    return redirect('my_bookings')


@login_required
def ride_chat(request, schedule_id):
    """
    Halaman chat dengan driver ("Sesuaikan" / "Chat"). Tombol "Gabung
    Tebengan" ada di sini untuk kasus yang tidak matched, setelah sepakat.

    CATATAN: model pesan belum ada. Tambahkan model ChatMessage lalu
    simpan/tampilkan di view ini. Sementara hanya konteks jadwalnya.
    """
    schedule = get_object_or_404(
        RideSchedule.objects.select_related('ride_offer__driver', 'ride_offer__vehicle'),
        pk=schedule_id,
    )
    return render(request, 'nebeng/ride_chat.html', {
        'schedule': schedule,
        'driver': schedule.ride_offer.driver,
        'asal': request.GET.get('asal', ''),
        'tujuan': request.GET.get('tujuan', ''),
        'jam': request.GET.get('jam', ''),
    })


@login_required
@require_POST
def join_from_chat(request, schedule_id):
    """Gabung setelah sepakat di chat (tanpa syarat matched)."""
    seats = int(request.POST.get('seats', 1) or 1)
    booking, err = _create_booking(request.user, schedule_id, seats)
    if err:
        messages.error(request, err)
        return redirect('ride_chat', schedule_id=schedule_id)
    messages.success(request, 'Berhasil bergabung ke tebengan!')
    return redirect('my_bookings')


@login_required
def my_bookings(request):
    bookings = (
        RideBooking.objects.filter(passenger=request.user)
        .select_related('ride_schedule__ride_offer__driver',
                        'ride_schedule__ride_offer__vehicle')
        .order_by('-booked_at')
    )
    return render(request, 'nebeng/my_bookings.html', {'bookings': bookings})


@login_required
@require_POST
def cancel_booking(request, booking_id):
    with transaction.atomic():
        booking = get_object_or_404(
            RideBooking.objects.select_for_update(),
            pk=booking_id, passenger=request.user,
        )
        if booking.status in ('pending', 'confirmed'):
            schedule = RideSchedule.objects.select_for_update().get(
                pk=booking.ride_schedule_id)
            schedule.available_seats += booking.seats
            schedule.save(update_fields=['available_seats'])
            booking.status = 'cancelled'
            booking.save(update_fields=['status'])
    messages.success(request, 'Booking dibatalkan.')
    return redirect('my_bookings')