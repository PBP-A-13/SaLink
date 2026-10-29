from datetime import date as date_cls, datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_time
from django.views.decorators.http import require_POST

from .forms import (
    DAY_NAMES,
    LOCATIONS,
    PRICE_BY_TYPE,
    TIME_CHOICES,
    JoinRideForm,
    OfferVehicleForm,
    RideSearchForm,
    SeatsForm,
)
from .models import RideBooking, RideOffer, RideRequest, RideSchedule, Vehicle

KURUN_WAKTU = 30


def _minutes(t):
    return t.hour * 60 + t.minute


def evaluate_matched(schedule, origin, destination, requested_time):
    origin_matched = True
    if origin:
        origin_matched = schedule.origin.strip().lower() == origin.strip().lower()

    destination_matched = True
    if destination:
        destination_matched = schedule.destination.strip().lower() == destination.strip().lower()

    time_matched = True
    time_difference = 0
    if requested_time:
        time_difference = _minutes(schedule.departure_time) - _minutes(requested_time)
        time_matched = 0 <= time_difference <= KURUN_WAKTU

    reasons = []
    if not origin_matched:
        reasons.append('Asal Berbeda')
    if not destination_matched:
        reasons.append('Tujuan Berbeda')
    if not time_matched:
        reasons.append('Jam Berbeda')
    if not time_matched and not destination_matched and not origin_matched:
        reasons.append('Not Matched')

    return {
        'matched': origin_matched and destination_matched and time_matched,
        'origin_matched': origin_matched,
        'destination_matched': destination_matched,
        'time_matched': time_matched,
        'time_difference': abs(time_difference),
        'reasons': reasons,
    }


def _week_days():
    today = timezone.localdate()
    # Jika akhir pekan (Sabtu=5, Minggu=6), ambil Senin minggu depan
    if today.weekday() >= 5:
        monday = today + timedelta(days=(7 - today.weekday()))
    else:
        monday = today - timedelta(days=today.weekday())

    names = ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat']
    return [
        {
            'date': monday + timedelta(days=i),
            'iso': (monday + timedelta(days=i)).isoformat(),
            'name': names[i],
            'is_today': (monday + timedelta(days=i)) == today,
        }
        for i in range(5)
    ]


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
            ride_schedule=schedule,
            passenger=user,
            seats=seats,
            status='confirmed',
        )
        schedule.available_seats -= seats
        schedule.save(update_fields=['available_seats'])

        RideRequest.objects.filter(
            passenger=user,
            date=schedule.date,
            status='searching',
            origin__iexact=schedule.origin,
            destination__iexact=schedule.destination,
        ).update(status='matched')
        return booking, None


# ---------------------------------------------------------------------------
# Cari tebengan (Halaman Utama Nebeng)
# ---------------------------------------------------------------------------

def nebeng_list(request):
    """
    Halaman utama NEBENG. Input: asal, tujuan, jam (semua dropdown).
    Menampilkan tebengan yang tersedia beserta rute, kapasitas, harga, & status SEARAH.
    Dapat diakses oleh publik tanpa harus login.
    """
    form = RideSearchForm(request.GET or None)
    results = []

    asal = request.GET.get('asal', '').strip()
    tujuan = request.GET.get('tujuan', '').strip()
    jam_str = request.GET.get('jam', '').strip()
    tanggal_str = request.GET.get('tanggal', '').strip()

    req_time = parse_time(jam_str) if jam_str else None
    searched = bool(asal or tujuan or jam_str)

    qs = (
        RideSchedule.objects.filter(
            is_active=True,
            available_seats__gt=0,
            ride_offer__is_active=True,
        )
        .select_related('ride_offer__driver', 'ride_offer__vehicle')
    )

    if request.user.is_authenticated:
        qs = qs.exclude(ride_offer__driver=request.user)

    if tanggal_str:
        req_date = parse_date(tanggal_str)
        if req_date:
            qs = qs.filter(date=req_date)
    else:
        qs = qs.filter(date__gte=timezone.localdate())

    if searched:
        if asal:
            qs = qs.filter(origin__icontains=asal)
        if tujuan:
            qs = qs.filter(destination__icontains=tujuan)

    booked_ids = set()
    if request.user.is_authenticated:
        booked_ids = set(
            RideBooking.objects.filter(passenger=request.user)
            .exclude(status='cancelled')
            .values_list('ride_schedule_id', flat=True)
        )

    for s in qs:
        if searched:
            info = evaluate_matched(s, asal, tujuan, req_time)
        else:
            info = {
                'matched': True,
                'origin_matched': True,
                'destination_matched': True,
                'time_matched': True,
                'time_difference': 0,
                'reasons': [],
            }
        info.update({
            'schedule': s,
            'driver': s.ride_offer.driver,
            'vehicle': s.ride_offer.vehicle,
            'already_booked': s.id in booked_ids,
        })
        results.append(info)

    # Matched tebengan diutamakan
    results.sort(key=lambda r: (not r['matched'], len(r.get('reasons', [])), r.get('time_difference', 0)))

    return render(request, 'saling_tebeng/saling_tebeng.html', {
        'form': form,
        'results': results,
        'searched': searched,
        'locations': sorted(LOCATIONS),
        'time_choices': TIME_CHOICES,
        'selected_asal': asal,
        'selected_tujuan': tujuan,
        'selected_jam': jam_str,
    })


# ---------------------------------------------------------------------------
# Tawarkan tebengan
# ---------------------------------------------------------------------------

class _SlotError(Exception):
    def __init__(self, errors):
        self.errors = errors


@login_required
def tawarkan_tebengan(request):
    """
    Halaman jadwal mingguan tawarkan tebeng.
    Tiap isi jadwal pada suatu hari, user bisa menekan tombol tambah (+)
    sehingga jadwal tersimpan di list hari itu, lalu bisa menambah jadwal lain.
    Di kanan: Kendaraan (Jenis & Kapasitas dropdown).
    Di ujung kanan bawah: Tombol Save dan Cancel.
    """
    days = _week_days()
    vehicle_form = OfferVehicleForm(request.POST or None)

    existing = (
        RideSchedule.objects.filter(
            ride_offer__driver=request.user,
            is_active=True,
            date__gte=days[0]['date'],
            date__lte=days[-1]['date'],
        )
        .select_related('ride_offer__vehicle')
        .order_by('date', 'departure_time')
    )

    ctx = {
        'days': days,
        'vehicle_form': vehicle_form,
        'existing': existing,
        'locations': sorted(LOCATIONS),
        'time_choices': TIME_CHOICES,
    }

    if request.method != 'POST':
        return render(request, 'saling_tebeng/tawarkan_tebengan.html', ctx)

    vehicle_type = request.POST.get('vehicle_type', '').strip()
    capacity_raw = request.POST.get('capacity', '1').strip()
    try:
        capacity = int(capacity_raw)
    except ValueError:
        capacity = 1

    slot_dates = request.POST.getlist('slot_date[]') or request.POST.getlist('slot_date')
    slot_origins = request.POST.getlist('slot_origin[]') or request.POST.getlist('slot_origin')
    slot_destinations = request.POST.getlist('slot_destination[]') or request.POST.getlist('slot_destination')
    slot_times = request.POST.getlist('slot_time[]') or request.POST.getlist('slot_time')

    has_error = False
    if not vehicle_type:
        messages.error(request, 'Pilih jenis kendaraan terlebih dahulu.')
        has_error = True

    if not slot_origins:
        messages.error(request, 'Isi jadwal dan klik tombol tambah (+) untuk menambahkan minimal satu jadwal tebengan.')
        has_error = True

    if has_error:
        return render(request, 'saling_tebeng/tawarkan_tebengan.html', ctx)

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
                    owner=request.user,
                    vehicle_type=vehicle_type,
                    capacity=capacity,
                    brand='Kendaraan',
                    model=vehicle_type.capitalize(),
                    license_plate='B 1234 UI',
                )

            offer = RideOffer.objects.create(driver=request.user, vehicle=vehicle)
            price = PRICE_BY_TYPE.get(vehicle_type, 5000)

            saved_count = 0
            for d_str, o, dest, t_str in zip(slot_dates, slot_origins, slot_destinations, slot_times):
                if not (d_str and o and dest and t_str):
                    continue
                dt = parse_date(d_str)
                tm = parse_time(t_str)
                if not dt or not tm:
                    continue

                if RideSchedule.objects.filter(
                    ride_offer__driver=request.user,
                    date=dt,
                    departure_time=tm,
                    is_active=True,
                ).exists():
                    continue

                sched = RideSchedule(
                    ride_offer=offer,
                    date=dt,
                    departure_time=tm,
                    origin=o,
                    destination=dest,
                    available_seats=capacity,
                    price=price,
                )
                sched.save()
                saved_count += 1

            if saved_count == 0 and not existing.exists():
                messages.error(request, 'Tidak ada jadwal baru yang berhasil disimpan (mungkin jadwal di jam yang sama sudah ada).')
                return render(request, 'saling_tebeng/tawarkan_tebengan.html', ctx)

        messages.success(request, f'Tawaran tebengan berhasil disimpan ({saved_count} jadwal baru ditambahkan).')
        return redirect('saling_tebeng:nebeng_list')

    except Exception as e:
        messages.error(request, f'Terjadi kesalahan saat menyimpan jadwal: {e}')
        return render(request, 'saling_tebeng/tawarkan_tebengan.html', ctx)


@login_required
@require_POST
def cancel_schedule(request, schedule_id):
    schedule = get_object_or_404(
        RideSchedule, pk=schedule_id, ride_offer__driver=request.user
    )
    schedule.is_active = False
    schedule.save(update_fields=['is_active'])
    schedule.bookings.exclude(status='completed').update(status='cancelled')
    messages.success(request, 'Jadwal berhasil dibatalkan.')
    return redirect('saling_tebeng:tawarkan_tebengan')


# ---------------------------------------------------------------------------
# Gabung & chat
# ---------------------------------------------------------------------------

@login_required
@require_POST
def join_ride(request, schedule_id):
    schedule = get_object_or_404(RideSchedule, pk=schedule_id)
    seats = int(request.POST.get('seats', 1) or 1)

    booking, err = _create_booking(request.user, schedule.id, seats)
    if err:
        messages.error(request, err)
        return redirect('saling_tebeng:nebeng_list')
    messages.success(request, 'Berhasil bergabung ke tebengan!')
    return redirect('saling_tebeng:my_bookings')


@login_required
def ride_chat(request, schedule_id):
    schedule = get_object_or_404(
        RideSchedule.objects.select_related('ride_offer__driver', 'ride_offer__vehicle'),
        pk=schedule_id,
    )
    return render(request, 'saling_tebeng/ride_chat.html', {
        'schedule': schedule,
        'driver': schedule.ride_offer.driver,
        'asal': request.GET.get('asal', ''),
        'tujuan': request.GET.get('tujuan', ''),
        'jam': request.GET.get('jam', ''),
    })


@login_required
@require_POST
def join_from_chat(request, schedule_id):
    form = SeatsForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Kapasitas tidak valid.')
        return redirect('saling_tebeng:ride_chat', schedule_id=schedule_id)
    booking, err = _create_booking(request.user, schedule_id, form.cleaned_data['seats'])
    if err:
        messages.error(request, err)
        return redirect('saling_tebeng:ride_chat', schedule_id=schedule_id)
    messages.success(request, 'Berhasil bergabung ke tebengan!')
    return redirect('saling_tebeng:my_bookings')


@login_required
def my_bookings(request):
    bookings = (
        RideBooking.objects.filter(passenger=request.user)
        .select_related(
            'ride_schedule__ride_offer__driver',
            'ride_schedule__ride_offer__vehicle',
        )
        .order_by('-booked_at')
    )
    return render(request, 'saling_tebeng/my_bookings.html', {'bookings': bookings})


@login_required
@require_POST
def cancel_booking(request, booking_id):
    with transaction.atomic():
        booking = get_object_or_404(
            RideBooking.objects.select_for_update(),
            pk=booking_id,
            passenger=request.user,
        )
        if booking.status in ('pending', 'confirmed'):
            schedule = RideSchedule.objects.select_for_update().get(
                pk=booking.ride_schedule_id
            )
            schedule.available_seats += booking.seats
            schedule.save(update_fields=['available_seats'])
            booking.status = 'cancelled'
            booking.save(update_fields=['status'])
    messages.success(request, 'Booking dibatalkan.')
    return redirect('saling_tebeng:my_bookings')
