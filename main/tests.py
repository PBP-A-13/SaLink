from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from django.contrib.auth.models import User
from saling_beli.models import ItemListing
from saling_tebeng.models import RideOffer, RideSchedule, Vehicle


class HomePageTests(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_home_only_shows_available_listings(self):
        seller = User.objects.create_user(username='seller', password='test-password')
        available = ItemListing.objects.create(user=seller, title='Available item', description='Available')
        ItemListing.objects.create(
            user=seller,
            title='Sold item',
            description='Sold',
            status=ItemListing.Status.SOLD,
        )
        response = self.client.get(reverse('main:show_main'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, available.title)
        self.assertNotContains(response, 'Sold item')

    def test_home_shows_empty_state_instead_of_sample_items(self):
        response = self.client.get(reverse('main:show_main'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Belum ada barang tersedia')
        self.assertContains(response, 'Lihat Semua (0)')
        self.assertNotContains(response, 'Buku Kalkulus Purcel')

# Create your tests here.
