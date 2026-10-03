import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import ItemListing


class ListingApiTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(username='seller', password='test-password')
		self.collection_url = reverse('saling_beli:listing-list')

	def test_collection_returns_listings(self):
		ItemListing.objects.create(
			user=self.user,
			title='Desk',
			description='Study desk',
		)

		response = self.client.get(self.collection_url)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(len(response.json()), 1)
		self.assertEqual(response.json()[0]['title'], 'Desk')

	def test_authenticated_user_can_create_listing(self):
		self.client.force_login(self.user)

		response = self.client.post(
			self.collection_url,
			data=json.dumps({'title': 'Lamp', 'description': 'Desk lamp'}),
			content_type='application/json',
		)

		self.assertEqual(response.status_code, 201)
		self.assertEqual(ItemListing.objects.get().user, self.user)

	def test_anonymous_user_cannot_create_listing(self):
		response = self.client.post(
			self.collection_url,
			data=json.dumps({'title': 'Lamp', 'description': 'Desk lamp'}),
			content_type='application/json',
		)

		self.assertEqual(response.status_code, 401)

	def test_explicit_create_update_and_delete_routes(self):
		self.client.force_login(self.user)
		create_response = self.client.post(
			reverse('saling_beli:listing-create'),
			data=json.dumps({'title': 'Lamp', 'description': 'Desk lamp'}),
			content_type='application/json',
		)
		listing_id = create_response.json()['id']

		update_response = self.client.patch(
			reverse('saling_beli:listing-update', args=[listing_id]),
			data=json.dumps({'title': 'Reading lamp'}),
			content_type='application/json',
		)
		delete_response = self.client.delete(
			reverse('saling_beli:listing-delete', args=[listing_id]),
		)

		self.assertEqual(create_response.status_code, 201)
		self.assertEqual(update_response.status_code, 200)
		self.assertEqual(update_response.json()['title'], 'Reading lamp')
		self.assertEqual(delete_response.status_code, 204)
		self.assertFalse(ItemListing.objects.filter(pk=listing_id).exists())
