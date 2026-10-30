from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

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

    def test_initial_page_shows_all_available_schedules_on_today(self):
        today = timezone.localdate()
        today_schedule = self.create_schedule(
            'today_driver', today, '08:00', 'Depok', 'Salemba',
        )
        tomorrow_schedule = self.create_schedule(
            'tomorrow_driver', today + timedelta(days=1), '08:00', 'Depok', 'Salemba',
        )

        response = self.client.get(reverse('saling_tebeng:index'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [result['schedule'].id for result in response.context['results']],
            [today_schedule.id],
        )
        self.assertContains(response, f'value="{today:%Y-%m-%d}"')
        self.assertNotContains(response, tomorrow_schedule.ride_offer.driver.username)
        self.assertNotContains(response, 'SEARAH')

    def test_search_shows_and_orders_matching_and_mismatching_routes(self):
        today = timezone.localdate()
        matching = self.create_schedule(
            'matching_driver', today, '08:00', 'Stasiun UI', 'Perpusat UI',
        )
        different_origin = self.create_schedule(
            'origin_driver', today, '08:30', 'Fakultas Teknik', 'Perpusat UI',
        )
        different_destination = self.create_schedule(
            'destination_driver', today, '09:00', 'Stasiun UI', 'Fakultas Hukum',
        )
        different_both = self.create_schedule(
            'both_driver', today, '09:30', 'Fakultas Teknik', 'Fakultas Hukum',
        )

        response = self.client.get(reverse('saling_tebeng:index'), {
            'asal': 'Stasiun UI',
            'tujuan': 'Perpusat UI',
            'tanggal': today.isoformat(),
        })

        results = response.context['results']
        self.assertEqual(
            [result['schedule'].id for result in results],
            [
                matching.id,
                different_origin.id,
                different_destination.id,
                different_both.id,
            ],
        )
        self.assertEqual(
            [result['match_label'] for result in results],
            ['Searah', 'Beda Asal', 'Beda Tujuan', 'Beda Asal & Tujuan'],
        )
        self.assertContains(response, 'ride-card__badge--matched')
        self.assertContains(response, 'ride-card__badge--different')
