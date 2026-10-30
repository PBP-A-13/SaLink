from datetime import timedelta

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from django.contrib.auth.models import User
from saling_bagi.models import Makanan
from saling_beli.models import ItemListing


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
        self.assertContains(response, 'Saling Nebeng')
        self.assertNotContains(response, 'Saling Tebeng')

    def test_saling_nebeng_uses_new_url_and_redirects_legacy_url(self):
        canonical_url = reverse('saling_tebeng:index')
        self.assertEqual(canonical_url, '/saling-nebeng/')

        legacy_response = self.client.get('/saling-tebeng/nebeng/')
        self.assertRedirects(
            legacy_response,
            '/saling-nebeng/nebeng/',
            fetch_redirect_response=False,
        )

    def test_home_hides_expired_food(self):
        giver = User.objects.create_user(username='pemberi', password='test-password')
        Makanan.objects.create(
            nama_makanan='Makanan Kedaluwarsa QA',
            deskripsi='Sudah lewat batas',
            porsi=1,
            pemberi=giver,
            batas_layak_konsumsi=timezone.now() - timedelta(hours=1),
            is_available=True,
        )

        response = self.client.get(reverse('main:show_main'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Makanan Kedaluwarsa QA')

# Create your tests here.
