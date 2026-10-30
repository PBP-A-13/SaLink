import json
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_time
from django.views.decorators.http import require_http_methods, require_POST

from .models import (
    RideBooking,
    RideChatMessage,
    RideConversation,
    RideOffer,
    RideRequest,
    RideSchedule,
    Vehicle,
)
from saling_beli.models import UserNotification
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

KURUN_WAKTU = 30
HARI_NAMES = [
    'Senin',
    'Selasa',
    'Rabu',
    'Kamis',
    'Jumat',
    'Sabtu',
    'Minggu',
]


def _minutes(t):
    return t.hour * 60 + t.minute


def evaluate_matched(
    schedule,
    origin,
    destination,
    requested_time,
    requested_date=None,
    occurrence_date=None,
):
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

    day_matched = (
        requested_date is None
        or occurrence_date is None
        or requested_date == occurrence_date
    )
    date_difference = (
        abs((occurrence_date - requested_date).days)
        if requested_date and occurrence_date else 0
    )
    reasons = []
    if not day_matched:
        reasons.append('Hari Berbeda')
    if not origin_matched:
        reasons.append('Asal Berbeda')
    if not destination_matched:
        reasons.append('Tujuan Berbeda')
    if not time_matched:
        reasons.append('Jam Berbeda')
    if not time_matched and not destination_matched and not origin_matched:
        reasons.append('Not Matched')

    match_rank = sum((
        not day_matched,
        not origin_matched,
        not destination_matched,
        not time_matched,
    ))
    if not origin_matched and not destination_matched:
        match_label = 'Beda Asal & Tujuan'
    elif not origin_matched:
        match_label = 'Beda Asal'
    elif not destination_matched:
        match_label = 'Beda Tujuan'
    elif origin and destination:
        match_label = 'Searah'
    else:
        match_label = ''

    return {
        'matched': match_rank == 0,
        'match_rank': match_rank,
        'match_label': match_label,
        'date_difference': date_difference,
        'day_matched': day_matched,
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


def _available_seats(schedule, ride_date):
    booked_seats = schedule.bookings.filter(
        ride_date=ride_date,
    ).exclude(status='cancelled').aggregate(total=Sum('seats'))['total'] or 0
    return max(0, schedule.total_seats - booked_seats)


def _create_booking(user, schedule_id, ride_date, seats=1):
    with transaction.atomic():
        schedule = (
            RideSchedule.objects.select_for_update()
            .select_related('ride_offer__driver')
            .get(pk=schedule_id)
        )
        if not schedule.is_active or not schedule.ride_offer.is_active:
            return None, 'Tebengan ini sudah tidak aktif.'
        if ride_date < schedule.date or ride_date.weekday() != schedule.date.weekday():
            return None, 'Jadwal ini tidak tersedia pada tanggal tersebut.'
        if schedule.ride_offer.driver_id == user.id:
            return None, 'Kamu tidak bisa menebeng tawaranmu sendiri.'
        if RideBooking.objects.filter(
            ride_schedule=schedule,
            ride_date=ride_date,
            passenger=user,
        ).exclude(status='cancelled').exists():
            return None, 'Kamu sudah bergabung di tebengan ini.'
        if seats < 1 or _available_seats(schedule, ride_date) < seats:
            return None, 'Kursi tidak mencukupi.'

        booking = RideBooking.objects.create(
            ride_schedule=schedule,
            ride_date=ride_date,
            passenger=user,
            seats=seats,
            status='confirmed',
        )
        RideConversation.objects.get_or_create(
            ride_schedule=schedule,
            passenger=user,
        )
        driver_chat_url = reverse(
            'saling_tebeng:ride_chat',
            args=[schedule.pk],
        )
        UserNotification.objects.create(
            user=schedule.ride_offer.driver,
            title='Penumpang bergabung',
            message=(
                f'@{user.username} bergabung ke tebenganmu '
                f'pada {ride_date:%d %b %Y}.'
            ),
            notification_type=UserNotification.NotifType.OFFER,
            link=(
                f'{driver_chat_url}?peer={user.pk}'
                f'&tanggal={ride_date.isoformat()}'
            ),
        )

        RideRequest.objects.filter(
            passenger=user,
            date=ride_date,
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
    today = timezone.localdate()
    form = RideSearchForm(
        request.GET or None,
        initial={'tanggal': today},
    )
    results = []

    asal = request.GET.get('asal', '').strip()
    tujuan = request.GET.get('tujuan', '').strip()
    jam_str = request.GET.get('jam', '').strip()
    tanggal_str = request.GET.get('tanggal', '').strip()

    req_time = parse_time(jam_str) if jam_str else None
    searched = bool(asal or tujuan or jam_str or tanggal_str)
    selected_date = parse_date(tanggal_str) if tanggal_str else today
    if selected_date is None:
        selected_date = today

    qs = (
        RideSchedule.objects.all()
        .select_related('ride_offer__driver', 'ride_offer__vehicle')
        .order_by('date', 'departure_time', 'pk')
    )

    schedule_slots = {}
    for schedule in qs:
        slot = (
            schedule.ride_offer.driver_id,
            schedule.departure_time,
            schedule.date.weekday(),
        )
        schedule_slots.setdefault(slot, []).append(schedule)

    occurrences = []
    for slot_schedules in schedule_slots.values():
        past_schedules = [
            schedule for schedule in slot_schedules
            if schedule.date <= selected_date
        ]
        if past_schedules:
            schedule = max(past_schedules, key=lambda item: item.date)
            if not schedule.is_active or not schedule.ride_offer.is_active:
                continue
        else:
            future_schedules = [
                schedule for schedule in slot_schedules
                if schedule.is_active and schedule.ride_offer.is_active
            ]
            if not future_schedules:
                continue
            schedule = min(future_schedules, key=lambda item: item.date)

        if schedule.date >= selected_date:
            occurrence_date = schedule.date
        else:
            days_until_schedule = (
                schedule.date.weekday() - selected_date.weekday()
            ) % 7
            occurrence_date = selected_date + timedelta(days=days_until_schedule)
        occurrences.append((schedule, occurrence_date))
    occurrences.sort(key=lambda item: (
        item[1],
        item[0].departure_time,
        item[0].pk,
    ))

    available_by_schedule = {
        (row['ride_schedule_id'], row['ride_date']): row['booked_seats'] or 0
        for row in RideBooking.objects.filter(
            ride_schedule__in=[schedule for schedule, _ in occurrences],
            ride_date__in=[occurrence_date for _, occurrence_date in occurrences],
        ).exclude(status='cancelled').values(
            'ride_schedule_id',
            'ride_date',
        ).annotate(
            booked_seats=Sum('seats'),
        )
    }

    booked_ids = set()
    if request.user.is_authenticated:
        booked_ids = set(
            RideBooking.objects.filter(
                passenger=request.user,
                ride_schedule__in=[
                    schedule for schedule, _ in occurrences
                ],
                ride_date__in=[
                    occurrence_date for _, occurrence_date in occurrences
                ],
            )
            .exclude(status='cancelled')
            .values_list('ride_schedule_id', 'ride_date')
        )

    for s, occurrence_date in occurrences:
        s.available_seats = max(
            0,
            s.total_seats - available_by_schedule.get(
                (s.id, occurrence_date),
                0,
            ),
        )
        if searched:
            info = evaluate_matched(
                s,
                asal,
                tujuan,
                req_time,
                selected_date,
                occurrence_date,
            )
        else:
            info = {
                'matched': True,
                'origin_matched': True,
                'destination_matched': True,
                'time_matched': True,
                'day_matched': True,
                'time_difference': 0,
                'date_difference': 0,
                'match_rank': 0,
                'match_label': '',
                'reasons': [],
            }
        info.update({
            'schedule': s,
            'driver': s.ride_offer.driver,
            'vehicle': s.ride_offer.vehicle,
            'already_booked': (s.id, occurrence_date) in booked_ids,
            'weekday': HARI_NAMES[occurrence_date.weekday()],
            'occurrence_date': occurrence_date,
        })
        results.append(info)

    if searched:
        results.sort(key=lambda r: (
            r['match_rank'],
            r['date_difference'],
            r['time_difference'],
            r['schedule'].origin.casefold(),
            r['schedule'].destination.casefold(),
            r['schedule'].departure_time,
        ))

    return render(request, 'saling_tebeng/saling_tebeng.html', {
        'form': form,
        'results': results,
        'searched': searched,
        'locations': sorted(LOCATIONS),
        'time_choices': TIME_CHOICES,
        'selected_asal': asal,
        'selected_tujuan': tujuan,
        'selected_jam': jam_str,
        'selected_date': selected_date,
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
                    total_seats=capacity,
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
    ride_date = parse_date(request.POST.get('ride_date', ''))
    if not ride_date:
        messages.error(request, 'Tanggal nebeng tidak valid.')
        return redirect('saling_tebeng:nebeng_list')

    _, err = _create_booking(request.user, schedule.id, ride_date, seats)
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
    ride_date = parse_date(request.GET.get('tanggal', '')) or schedule.date
    conversations = schedule.conversations.select_related('passenger').all()
    peer_id = request.GET.get('peer')
    if schedule.ride_offer.driver_id == request.user.id:
        conversation = None
        if peer_id:
            conversation = get_object_or_404(
                conversations,
                passenger_id=peer_id,
            )
        elif conversations:
            conversation = conversations.first()
    else:
        conversation, _ = RideConversation.objects.get_or_create(
            ride_schedule=schedule,
            passenger=request.user,
        )

    return render(request, 'saling_tebeng/ride_chat.html', {
        'schedule': schedule,
        'driver': schedule.ride_offer.driver,
        'ride_date': ride_date,
        'weekday': HARI_NAMES[ride_date.weekday()],
        'available_seats': _available_seats(schedule, ride_date),
        'conversation': conversation,
        'conversations': conversations,
        'peer': conversation.passenger if conversation else None,
    })


def _get_ride_conversation(schedule, user, peer_id=None):
    if schedule.ride_offer.driver_id == user.id:
        if not peer_id:
            return None
        return RideConversation.objects.filter(
            ride_schedule=schedule,
            passenger_id=peer_id,
        ).first()
    if peer_id and str(user.id) != str(peer_id):
        return None
    conversation, _ = RideConversation.objects.get_or_create(
        ride_schedule=schedule,
        passenger=user,
    )
    return conversation


@login_required
@require_http_methods(['GET', 'POST'])
def ride_chat_messages(request, schedule_id):
    schedule = get_object_or_404(
        RideSchedule.objects.select_related('ride_offer__driver'),
        pk=schedule_id,
    )
    peer_id = request.GET.get('peer') or request.POST.get('peer')
    conversation = _get_ride_conversation(schedule, request.user, peer_id)
    if conversation is None:
        return JsonResponse(
            {'error': 'Percakapan tidak ditemukan atau kamu tidak memiliki akses.'},
            status=404,
        )

    if request.method == 'POST':
        message = request.POST.get('message', '')
        if request.content_type == 'application/json':
            try:
                body = json.loads(request.body)
            except (json.JSONDecodeError, UnicodeDecodeError):
                return JsonResponse({'error': 'Format pesan tidak valid.'}, status=400)
            if not isinstance(body, dict):
                return JsonResponse({'error': 'Format pesan tidak valid.'}, status=400)
            message = body.get('message', '')
        if not isinstance(message, str):
            return JsonResponse({'error': 'Pesan harus berupa teks.'}, status=400)
        message = message.strip()
        if not message:
            return JsonResponse({'error': 'Pesan tidak boleh kosong.'}, status=400)
        if len(message) > 2000:
            return JsonResponse({'error': 'Pesan maksimal 2.000 karakter.'}, status=400)

        recipient = (
            conversation.passenger
            if request.user.id == schedule.ride_offer.driver_id
            else schedule.ride_offer.driver
        )
        chat_url = reverse(
            'saling_tebeng:ride_chat',
            args=[schedule.pk],
        )
        if recipient.id == schedule.ride_offer.driver_id:
            chat_url = (
                f'{chat_url}?peer={conversation.passenger_id}'
                f'&tanggal={schedule.date.isoformat()}'
            )
        else:
            chat_url = f'{chat_url}?tanggal={schedule.date.isoformat()}'
        with transaction.atomic():
            chat = RideChatMessage.objects.create(
                conversation=conversation,
                sender=request.user,
                message=message,
            )
            RideConversation.objects.filter(pk=conversation.pk).update(
                updated_at=timezone.now(),
            )
            UserNotification.objects.create(
                user=recipient,
                title=f'Pesan nebeng dari @{request.user.username}',
                message=message[:200],
                notification_type=UserNotification.NotifType.CHAT,
                link=chat_url,
            )
        return JsonResponse({
            'success': True,
            'chat': {
                'id': chat.pk,
                'sender': request.user.username,
                'is_me': True,
                'message': chat.message,
                'created_at': timezone.localtime(chat.created_at).strftime('%H:%M, %d %b'),
            },
        })

    chats = conversation.messages.select_related('sender').all()
    conversation.messages.filter(
        is_read=False,
    ).exclude(sender=request.user).update(is_read=True)
    return JsonResponse({
        'success': True,
        'chats': [
            {
                'id': chat.pk,
                'sender': chat.sender.username,
                'is_me': chat.sender_id == request.user.id,
                'message': chat.message,
                'created_at': timezone.localtime(chat.created_at).strftime('%H:%M, %d %b'),
            }
            for chat in chats
        ],
    })


@login_required
def ride_messages(request):
    conversations = RideConversation.objects.filter(
        Q(passenger=request.user)
        | Q(ride_schedule__ride_offer__driver=request.user)
    ).select_related(
        'passenger',
        'ride_schedule__ride_offer__driver',
    ).prefetch_related('messages').order_by('-updated_at')
    return render(request, 'saling_tebeng/ride_messages.html', {
        'conversations': conversations,
    })


@login_required
@require_POST
def join_from_chat(request, schedule_id):
    form = SeatsForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Kapasitas tidak valid.')
        return redirect('saling_tebeng:ride_chat', schedule_id=schedule_id)
    ride_date = parse_date(request.POST.get('ride_date', ''))
    if not ride_date:
        messages.error(request, 'Tanggal nebeng tidak valid.')
        return redirect('saling_tebeng:ride_chat', schedule_id=schedule_id)
    _, err = _create_booking(
        request.user,
        schedule_id,
        ride_date,
        form.cleaned_data['seats'],
    )
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
            booking.status = 'cancelled'
            booking.save(update_fields=['status'])
    messages.success(request, 'Booking dibatalkan.')
    return redirect('saling_tebeng:my_bookings')
