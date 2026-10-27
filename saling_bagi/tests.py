from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Makanan


class SalingBagiAuthTests(TestCase):
	def setUp(self):
		self.giver = User.objects.create_user(username='giver', password='test-password')
		self.claimant = User.objects.create_user(username='claimant', password='test-password')
		self.food = Makanan.objects.create(
			nama_makanan='Snack box',
			deskripsi='Makanan berlebih acara kampus',
			porsi=2,
			lokasi_pengambilan='Perpusat UI',
			batas_layak_konsumsi=timezone.now() + timedelta(hours=4),
			pemberi=self.giver,
		)

	def test_guest_can_browse_food_listings(self):
		response = self.client.get(reverse('saling_bagi:index'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Snack box')
		self.assertContains(response, 'Masuk untuk ambil')

	def test_guest_claim_redirects_to_shared_login_and_back_to_list(self):
		response = self.client.post(reverse('saling_bagi:ambil_makanan', args=[self.food.id]))

		self.assertEqual(response.status_code, 302)
		self.assertEqual(response['Location'], '/akun/login/?next=/saling-bagi/')

	def test_logged_in_user_can_claim_food(self):
		self.client.force_login(self.claimant)

		response = self.client.post(reverse('saling_bagi:ambil_makanan', args=[self.food.id]))

		self.assertRedirects(response, reverse('saling_bagi:index'))
		self.food.refresh_from_db()
		self.assertFalse(self.food.is_available)
