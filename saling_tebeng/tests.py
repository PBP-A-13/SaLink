from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from saling_beli.models import UserNotification

from .models import RideOffer, RideSchedule, Vehicle


class RideSearchTests(TestCase):
    def create_schedule(self, username, date, departure_time, origin, destination):
        driver = User.objects.create_user(username=username)
        vehicle = Vehicle.objects.create(
            owner=driver,
            vehicle_type='motor',
            brand='Honda',
            model='Vario',
            license_plate=f'{username[:3]}-123',
        )
        offer = RideOffer.objects.create(driver=driver, vehicle=vehicle)
        return RideSchedule.objects.create(
            ride_offer=offer,
            date=date,
            departure_time=departure_time,
            origin=origin,
            destination=destination,
        )

    def test_authenticated_nebeng_page_loads_notification_controls(self):
        user = User.objects.create_user(username='notif_user')
        self.client.force_login(user)

        response = self.client.get(reverse('saling_tebeng:index'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="notif-dropdown"')
        self.assertContains(response, reverse('saling_beli:user-notifications'))
        self.assertContains(response, reverse('saling_beli:notification-stream'))

    def test_search_prioritizes_selected_date_then_route_and_time(self):
        today = timezone.localdate()
        origin_and_time = self.create_schedule(
            'origin_time_driver', today, '08:30', 'Stasiun UI', 'Fakultas Hukum',
        )
        destination_and_time = self.create_schedule(
            'destination_time_driver', today, '08:30', 'Fakultas Teknik', 'Perpusat UI',
        )
        same_route_different_time = self.create_schedule(
            'different_time_driver', today, '09:00', 'Stasiun UI', 'Perpusat UI',
        )
        other_same_day = self.create_schedule(
            'other_same_day_driver', today, '10:00', 'Fakultas Teknik', 'Fakultas Hukum',
        )
        different_day = self.create_schedule(
            'day_driver',
            today + timedelta(days=1),
            '08:00',
            'Stasiun UI',
            'Perpusat UI',
        )

        response = self.client.get(reverse('saling_tebeng:index'), {
            'asal': 'Stasiun UI',
            'tujuan': 'Perpusat UI',
            'jam': '08:00',
            'tanggal': today.isoformat(),
        })

        results = response.context['results']
        self.assertEqual(
            [result['schedule'].id for result in results],
            [
                origin_and_time.id,
                destination_and_time.id,
                same_route_different_time.id,
                other_same_day.id,
                different_day.id,
            ],
        )
        self.assertEqual(
            [result['match_label'] for result in results],
            [
                'Beda Tujuan',
                'Beda Asal',
                'Beda Jam',
                'Beda Asal & Tujuan',
                'Searah',
            ],
        )
        self.assertEqual(
            [result['day_matched'] for result in results],
            [True, True, True, True, False],
        )
        self.assertEqual(
            [result['match_priority'] for result in results],
            [0, 1, 2, 3, 4],
        )
        self.assertContains(response, 'ride-card__badge--day-match')
        self.assertContains(response, 'ride-card__badge--day-different')
        self.assertContains(response, 'BEDA ASAL')
        self.assertContains(response, 'BEDA TUJUAN')
        self.assertContains(response, 'BEDA JAM')
        self.assertContains(response, 'ride-card--different-date')
        self.assertContains(response, '08.30')

    def test_date_only_search_does_not_label_offers_as_searah(self):
        today = timezone.localdate()
        self.create_schedule(
            'date_only_driver', today, '08:00', 'Depok', 'Salemba',
        )

        response = self.client.get(reverse('saling_tebeng:index'), {
            'tanggal': today.isoformat(),
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['results'][0]['match_label'], '')

    def test_same_route_thirty_minutes_later_is_still_searah(self):
        today = timezone.localdate()
        self.create_schedule(
            'thirty_minute_driver',
            today,
            '08:30',
            'Stasiun UI',
            'Perpusat UI',
        )

        response = self.client.get(reverse('saling_tebeng:index'), {
            'asal': 'Stasiun UI',
            'tujuan': 'Perpusat UI',
            'jam': '08:00',
            'tanggal': today.isoformat(),
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['results'][0]['match_label'], 'Searah')
        self.assertTrue(response.context['results'][0]['time_matched'])

    def test_schedule_repeats_on_its_weekday_for_a_later_date(self):
        selected_date = timezone.localdate() + timedelta(days=10)
        schedule_date = selected_date - timedelta(days=7)
        schedule = self.create_schedule(
            'weekly_driver',
            schedule_date,
            '08:00',
            'Stasiun UI',
            'Perpusat UI',
        )

        response = self.client.get(reverse('saling_tebeng:index'), {
            'tanggal': selected_date.isoformat(),
        })

        self.assertEqual(response.status_code, 200)
        result = response.context['results'][0]
        self.assertEqual(result['schedule'].id, schedule.id)
        self.assertEqual(result['weekday'], [
            'Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu',
        ][selected_date.weekday()])

    def test_booking_capacity_is_tracked_per_recurring_date(self):
        driver = User.objects.create_user(username='weekly_driver')
        passenger = User.objects.create_user(username='weekly_passenger')
        vehicle = Vehicle.objects.create(
            owner=driver,
            vehicle_type='motor',
            brand='Honda',
            model='Vario',
            license_plate='WKL-123',
            capacity=2,
        )
        offer = RideOffer.objects.create(driver=driver, vehicle=vehicle)
        ride_date = timezone.localdate() + timedelta(days=7)
        schedule = RideSchedule.objects.create(
            ride_offer=offer,
            date=ride_date - timedelta(days=7),
            departure_time='08:00',
            origin='Stasiun UI',
            destination='Perpusat UI',
            available_seats=2,
            total_seats=2,
        )

        self.client.force_login(passenger)
        response = self.client.post(
            reverse('saling_tebeng:join_ride', args=[schedule.id]),
            {'ride_date': ride_date.isoformat(), 'seats': 1},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            schedule.bookings.get(passenger=passenger).ride_date,
            ride_date,
        )
        notification = UserNotification.objects.get(user=driver)
        self.assertEqual(
            notification.notification_type,
            UserNotification.NotifType.OFFER,
        )
        self.assertIn(f'peer={passenger.pk}', notification.link)
        self.assertIn(f'tanggal={ride_date.isoformat()}', notification.link)

        next_occurrence = ride_date + timedelta(days=7)
        next_response = self.client.get(reverse('saling_tebeng:index'), {
            'tanggal': next_occurrence.isoformat(),
        })
        self.assertEqual(
            next_response.context['results'][0]['schedule'].available_seats,
            2,
        )

        next_booking = self.client.post(
            reverse('saling_tebeng:join_ride', args=[schedule.id]),
            {'ride_date': next_occurrence.isoformat(), 'seats': 1},
        )
        self.assertEqual(next_booking.status_code, 302)
        self.assertEqual(schedule.bookings.filter(passenger=passenger).count(), 2)

    def test_ride_chat_allows_passenger_and_driver_to_exchange_messages(self):
        ride_date = timezone.localdate() + timedelta(days=1)
        schedule = self.create_schedule(
            'chat_driver',
            ride_date,
            '08:00',
            'Stasiun UI',
            'Perpusat UI',
        )
        passenger = User.objects.create_user(username='chat_passenger')
        chat_url = reverse(
            'saling_tebeng:ride_chat_messages',
            args=[schedule.id],
        )

        self.client.force_login(passenger)
        response = self.client.post(
            chat_url,
            data='{"message":"Halo, masih ada kursi?"}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        driver_notification = UserNotification.objects.get(
            user=schedule.ride_offer.driver,
        )
        self.assertEqual(
            driver_notification.notification_type,
            UserNotification.NotifType.CHAT,
        )
        self.assertIn(f'peer={passenger.pk}', driver_notification.link)

        self.client.force_login(schedule.ride_offer.driver)
        response = self.client.get(chat_url, {'peer': passenger.id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['chats'][0]['message'], 'Halo, masih ada kursi?')
        self.assertFalse(response.json()['chats'][0]['is_me'])

        response = self.client.post(
            f'{chat_url}?peer={passenger.id}',
            data='{"message":"Ya, masih ada."}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        passenger_notification = UserNotification.objects.get(user=passenger)
        self.assertEqual(
            passenger_notification.notification_type,
            UserNotification.NotifType.CHAT,
        )
        self.assertNotIn('peer=', passenger_notification.link)

        self.client.force_login(passenger)
        response = self.client.get(chat_url)
        self.assertEqual(response.json()['chats'][-1]['message'], 'Ya, masih ada.')
        self.assertFalse(response.json()['chats'][-1]['is_me'])
