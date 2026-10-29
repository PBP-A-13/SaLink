import io
import json
from unittest import mock

from django.contrib.auth.models import User
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from .models import (
	Conversation,
	ItemChatMessage,
	ItemListing,
	PriceOffer,
	TransactionOrder,
	UserNotification,
)


class ListingPageTests(TestCase):
	def test_catalog_only_shows_available_items_by_default(self):
		seller = User.objects.create_user(username='seller', password='test-password')
		ItemListing.objects.create(user=seller, title='Available item', description='Available')
		ItemListing.objects.create(
			user=seller,
			title='Reserved item',
			description='Reserved',
			status=ItemListing.Status.RESERVED,
		)
		ItemListing.objects.create(
			user=seller,
			title='Sold item',
			description='Sold',
			status=ItemListing.Status.SOLD,
		)

		response = self.client.get(reverse('saling_beli:index'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Available item')
		self.assertNotContains(response, 'Reserved item')
		self.assertNotContains(response, 'Sold item')


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

	def test_public_listing_api_does_not_expose_payment_account(self):
		ItemListing.objects.create(
			user=self.user,
			title='Desk',
			description='Study desk',
			payout_method='BCA',
			payout_account_name='Seller Name',
			payout_account_number='1234567890',
		)
		response = self.client.get(self.collection_url)
		self.assertEqual(response.status_code, 200)
		self.assertNotIn('payout_account_number', response.json()[0])
		self.assertNotIn('payout_account_name', response.json()[0])

	def test_paid_listing_requires_payment_destination(self):
		self.client.force_login(self.user)
		response = self.client.post(
			self.collection_url,
			data=json.dumps({'title': 'Lamp', 'description': 'Desk lamp', 'price': 20000}),
			content_type='application/json',
		)
		self.assertEqual(response.status_code, 400)
		self.assertFalse(ItemListing.objects.exists())

	def test_paid_listing_rejects_unknown_payment_method(self):
		self.client.force_login(self.user)
		response = self.client.post(
			self.collection_url,
			data=json.dumps({
				'title': 'Lamp',
				'description': 'Desk lamp',
				'price': 20000,
				'payout_method': 'Unknown wallet',
				'payout_account_number': '08123456789',
			}),
			content_type='application/json',
		)
		self.assertEqual(response.status_code, 400)
		self.assertIn('payout_method', response.json()['errors'])

	def test_authenticated_user_can_create_listing(self):
		self.client.force_login(self.user)

		response = self.client.post(
			self.collection_url,
			data=json.dumps({'title': 'Lamp', 'description': 'Desk lamp', 'is_free': True}),
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
			data=json.dumps({'title': 'Lamp', 'description': 'Desk lamp', 'is_free': True}),
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


class OrderFlowTests(TestCase):
	def setUp(self):
		self.seller = User.objects.create_user(username='penjual', password='test-password')
		self.buyer = User.objects.create_user(username='pembeli', password='test-password')
		self.other = User.objects.create_user(username='pembeli-lain', password='test-password')
		self.item = ItemListing.objects.create(
			user=self.seller,
			title='Kalkulator',
			description='Mulus, lengkap',
			price=100000,
			payout_account_number='1234567890',
		)
		self.offer_url = reverse('saling_beli:make-offer', args=[self.item.id])
		self.order_url = reverse('saling_beli:create-order', args=[self.item.id])

	def _make_offer(self, price=75000):
		self.client.force_login(self.buyer)
		response = self.client.post(
			self.offer_url,
			data=json.dumps({'offered_price': price}),
			content_type='application/json',
		)
		return response, PriceOffer.objects.get(item=self.item, buyer=self.buyer)

	def _accept_offer(self, offer):
		self.client.force_login(self.seller)
		return self.client.post(
			reverse('saling_beli:respond-offer', args=[offer.id]),
			data=json.dumps({'action': 'accept'}),
			content_type='application/json',
		)

	def _set_stage(self, order, user, stage, **extra):
		self.client.force_login(user)
		payload = {'stage': stage}
		payload.update(extra)
		return self.client.post(
			reverse('saling_beli:update-order-stage', args=[order.id]),
			data=json.dumps(payload),
			content_type='application/json',
		)

	def test_accept_offer_creates_order_and_reserves_item(self):
		_, offer = self._make_offer()
		response = self._accept_offer(offer)

		self.assertEqual(response.status_code, 200)
		order = TransactionOrder.objects.get(item=self.item)
		self.assertEqual(order.agreed_price, 75000)
		self.item.refresh_from_db()
		self.assertEqual(self.item.status, ItemListing.Status.RESERVED)

	def test_accepting_twice_does_not_create_second_order(self):
		_, offer = self._make_offer()
		first = self._accept_offer(offer)
		second = self._accept_offer(offer)

		self.assertEqual(first.status_code, 200)
		self.assertEqual(second.status_code, 400)
		self.assertEqual(TransactionOrder.objects.filter(item=self.item).count(), 1)

	def test_second_buyer_cannot_order_reserved_item(self):
		self.client.force_login(self.buyer)
		first = self.client.post(self.order_url)

		self.client.force_login(self.other)
		second = self.client.post(self.order_url)

		self.assertEqual(first.status_code, 200)
		self.assertEqual(second.status_code, 400)
		self.assertEqual(TransactionOrder.objects.filter(item=self.item).count(), 1)

	def test_sold_item_cannot_be_ordered_again(self):
		self.item.status = ItemListing.Status.SOLD
		self.item.save(update_fields=['status'])
		self.client.force_login(self.buyer)

		response = self.client.post(self.order_url)

		self.assertEqual(response.status_code, 400)
		self.assertFalse(TransactionOrder.objects.filter(item=self.item).exists())

	def test_paid_item_without_account_cannot_be_ordered(self):
		self.item.payout_account_number = ''
		self.item.save(update_fields=['payout_account_number'])
		self.client.force_login(self.buyer)

		response = self.client.post(self.order_url)

		self.assertEqual(response.status_code, 400)
		self.assertFalse(TransactionOrder.objects.filter(item=self.item).exists())

	def test_same_buyer_order_is_idempotent(self):
		self.client.force_login(self.buyer)
		first = self.client.post(self.order_url)
		second = self.client.post(self.order_url)

		self.assertEqual(second.status_code, 200)
		self.assertEqual(first.json()['order_id'], second.json()['order_id'])
		self.assertTrue(second.json()['already_exists'])
		self.assertEqual(TransactionOrder.objects.filter(item=self.item).count(), 1)

	def test_accept_offer_rejected_when_item_reserved_by_other(self):
		self.client.force_login(self.buyer)
		self.client.post(self.order_url)

		offer = PriceOffer.objects.create(
			item=self.item,
			buyer=self.other,
			offered_price=50000,
		)
		response = self._accept_offer(offer)

		self.assertEqual(response.status_code, 400)
		self.assertEqual(TransactionOrder.objects.filter(item=self.item).count(), 1)

	def test_stage_cannot_be_skipped(self):
		order = TransactionOrder.objects.create(
			item=self.item,
			buyer=self.buyer,
			seller=self.seller,
			agreed_price=100000,
		)

		response = self._set_stage(order, self.buyer, 'SELESAI')

		self.assertEqual(response.status_code, 400)
		order.refresh_from_db()
		self.assertEqual(order.stage, TransactionOrder.Stage.MENUNGGU_TRANSFER)

	def test_paid_order_cannot_skip_transfer_confirmation_for_cod(self):
		order = TransactionOrder.objects.create(
			item=self.item,
			buyer=self.buyer,
			seller=self.seller,
			agreed_price=100000,
		)
		response = self._set_stage(
			order,
			self.buyer,
			'JANJI_TEMU_COD',
			cod_meeting_time='Jumat 10.00',
		)
		self.assertEqual(response.status_code, 400)
		order.refresh_from_db()
		self.assertEqual(order.stage, TransactionOrder.Stage.MENUNGGU_TRANSFER)

	def test_free_order_can_schedule_cod_without_payment(self):
		free_item = ItemListing.objects.create(
			user=self.seller,
			title='Buku gratis',
			description='Silakan ambil',
			is_free=True,
		)
		order = TransactionOrder.objects.create(
			item=free_item,
			buyer=self.buyer,
			seller=self.seller,
			agreed_price=0,
		)
		free_item.status = ItemListing.Status.RESERVED
		free_item.save(update_fields=['status'])

		response = self._set_stage(
			order,
			self.buyer,
			'JANJI_TEMU_COD',
			cod_meeting_time='Jumat 10.00',
		)
		self.assertEqual(response.status_code, 200)
		order.refresh_from_db()
		self.assertEqual(order.stage, TransactionOrder.Stage.JANJI_TEMU_COD)

	def test_only_buyer_can_upload_payment_proof(self):
		order = TransactionOrder.objects.create(
			item=self.item,
			buyer=self.buyer,
			seller=self.seller,
			agreed_price=100000,
		)

		seller_response = self._set_stage(order, self.seller, 'BUKTI_DIUNGGAH')
		buyer_response = self._set_stage(
			order,
			self.buyer,
			'BUKTI_DIUNGGAH',
			note='BCA 12345',
		)

		self.assertEqual(seller_response.status_code, 403)
		self.assertEqual(buyer_response.status_code, 200)
		order.refresh_from_db()
		self.assertEqual(order.payment_proof_note, 'BCA 12345')

	def test_full_flow_marks_item_sold(self):
		order = TransactionOrder.objects.create(
			item=self.item,
			buyer=self.buyer,
			seller=self.seller,
			agreed_price=100000,
		)
		self.item.status = ItemListing.Status.RESERVED
		self.item.save(update_fields=['status'])

		self.assertEqual(self._set_stage(order, self.buyer, 'BUKTI_DIUNGGAH', note='REF-1').status_code, 200)
		self.assertEqual(self._set_stage(order, self.seller, 'DIKONFIRMASI').status_code, 200)
		self.assertEqual(self._set_stage(
			order, self.seller, 'JANJI_TEMU_COD', cod_meeting_time='Jumat 10.00, Perpusat'
		).status_code, 200)
		first_confirmation = self._set_stage(order, self.buyer, 'SELESAI')
		self.assertTrue(first_confirmation.json()['awaiting_confirmation'])
		order.refresh_from_db()
		self.item.refresh_from_db()
		self.assertEqual(order.stage, TransactionOrder.Stage.JANJI_TEMU_COD)
		self.assertEqual(self.item.status, ItemListing.Status.RESERVED)
		self.assertEqual(self._set_stage(order, self.seller, 'SELESAI').status_code, 200)

		order.refresh_from_db()
		self.item.refresh_from_db()
		self.assertEqual(order.stage, TransactionOrder.Stage.SELESAI)
		self.assertEqual(self.item.status, ItemListing.Status.SOLD)

	def test_transfer_order_cannot_be_cancelled_after_payment_proof(self):
		order = TransactionOrder.objects.create(
			item=self.item,
			buyer=self.buyer,
			seller=self.seller,
			agreed_price=100000,
			stage=TransactionOrder.Stage.BUKTI_DIUNGGAH,
		)
		self.item.status = ItemListing.Status.RESERVED
		self.item.save(update_fields=['status'])
		response = self._set_stage(order, self.buyer, 'BATAL')
		self.assertEqual(response.status_code, 400)
		order.refresh_from_db()
		self.item.refresh_from_db()
		self.assertEqual(order.stage, TransactionOrder.Stage.BUKTI_DIUNGGAH)
		self.assertEqual(self.item.status, ItemListing.Status.RESERVED)

	def test_offer_cannot_be_accepted_after_item_is_sold(self):
		_, offer = self._make_offer()
		self.item.status = ItemListing.Status.SOLD
		self.item.save(update_fields=['status'])
		response = self._accept_offer(offer)
		self.assertEqual(response.status_code, 400)
		self.assertFalse(TransactionOrder.objects.filter(item=self.item).exists())

	def test_cancel_releases_reserved_item(self):
		self.client.force_login(self.buyer)
		self.client.post(self.order_url)
		order = TransactionOrder.objects.get(item=self.item)

		response = self._set_stage(order, self.buyer, 'BATAL')

		self.assertEqual(response.status_code, 200)
		self.item.refresh_from_db()
		self.assertEqual(self.item.status, ItemListing.Status.AVAILABLE)


class ChatThreadTests(TestCase):
	def setUp(self):
		self.seller = User.objects.create_user(username='penjual', password='test-password')
		self.buyer_a = User.objects.create_user(username='pembeli-a', password='test-password')
		self.buyer_b = User.objects.create_user(username='pembeli-b', password='test-password')
		self.item = ItemListing.objects.create(
			user=self.seller,
			title='Buku Kalkulus',
			description='Edisi 14',
			price=120000,
			payout_account_number='1234567890',
		)
		self.chat_url = reverse('saling_beli:item-chats', args=[self.item.id])

	def _send(self, user, message, peer=None):
		self.client.force_login(user)
		payload = {'message': message}
		if peer is not None:
			payload['peer'] = peer
		return self.client.post(
			self.chat_url,
			data=json.dumps(payload),
			content_type='application/json',
		)

	def test_each_buyer_gets_own_thread(self):
		self._send(self.buyer_a, 'Halo, masih ada?')
		self._send(self.buyer_b, 'Saya mau beli')

		self.client.force_login(self.seller)
		response_a = self.client.get(self.chat_url, {'peer': self.buyer_a.id})
		response_b = self.client.get(self.chat_url, {'peer': self.buyer_b.id})

		messages_a = [c['message'] for c in response_a.json()['chats']]
		messages_b = [c['message'] for c in response_b.json()['chats']]
		self.assertEqual(messages_a, ['Halo, masih ada?'])
		self.assertEqual(messages_b, ['Saya mau beli'])

	def test_seller_reply_goes_to_selected_buyer(self):
		self._send(self.buyer_a, 'Halo')
		self._send(self.seller, 'Halo juga, ada yang bisa dibantu?', peer=self.buyer_a.id)

		chat = ItemChatMessage.objects.filter(sender=self.seller).get()
		self.assertEqual(chat.recipient, self.buyer_a)
		self.assertEqual(chat.conversation.buyer, self.buyer_a)

	def test_buyer_only_sees_own_messages(self):
		self._send(self.buyer_a, 'Pesan A')
		self._send(self.buyer_b, 'Pesan B')

		self.client.force_login(self.buyer_b)
		response = self.client.get(self.chat_url)

		messages = [c['message'] for c in response.json()['chats']]
		self.assertEqual(messages, ['Pesan B'])

	def test_seller_must_choose_buyer_without_threads(self):
		self.client.force_login(self.seller)
		response = self.client.post(
			self.chat_url,
			data=json.dumps({'message': 'Halo'}),
			content_type='application/json',
		)

		self.assertEqual(response.status_code, 400)
		self.assertEqual(Conversation.objects.count(), 0)

	def test_chat_rejects_non_object_json_without_server_error(self):
		self.client.force_login(self.buyer_a)
		response = self.client.post(
			self.chat_url,
			data=json.dumps(['not', 'an', 'object']),
			content_type='application/json',
		)
		self.assertEqual(response.status_code, 400)
		self.assertFalse(ItemChatMessage.objects.exists())


class NotificationStreamTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(username='pembeli', password='test-password')
		self.stream_url = reverse('saling_beli:notification-stream')

	def test_returns_new_notifications_immediately(self):
		self.client.force_login(self.user)
		UserNotification.objects.create(
			user=self.user,
			title='Tawaran masuk',
			message='Ada yang menawar barangmu.',
			notification_type=UserNotification.NotifType.OFFER,
		)

		response = self.client.get(self.stream_url)
		payload = response.json()

		self.assertEqual(response.status_code, 200)
		self.assertEqual(len(payload['notifications']), 1)
		self.assertEqual(payload['notifications'][0]['title'], 'Tawaran masuk')
		self.assertIsNotNone(payload['cursor'])

	def test_anonymous_gets_empty_payload(self):
		response = self.client.get(self.stream_url)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json()['notifications'], [])


class UploadValidationTests(TestCase):
	def setUp(self):
		self.seller = User.objects.create_user(username='penjual', password='test-password')
		self.item = ItemListing.objects.create(
			user=self.seller,
			title='Lampu',
			description='Lampu belajar',
			price=35000,
		)
		self.upload_url = reverse('saling_beli:upload-image', args=[self.item.id])
		self.client.force_login(self.seller)

	def _upload(self, name, content, content_type):
		return self.client.post(
			self.upload_url,
			data={'image': SimpleUploadedFile(name, content, content_type=content_type)},
		)

	def test_valid_png_is_accepted(self):
		buffer = io.BytesIO()
		Image.new('RGB', (16, 16), 'white').save(buffer, format='PNG')

		# Penyimpanan fisik diganti mock agar tes tidak menulis ke disk.
		with mock.patch.object(FileSystemStorage, '_save', return_value='item_images/foto.png'):
			response = self._upload('foto.png', buffer.getvalue(), 'image/png')

		self.assertEqual(response.status_code, 200)
		self.assertTrue(response.json()['success'])

	def test_oversized_file_is_rejected(self):
		response = self._upload('besar.png', b'x' * (5 * 1024 * 1024 + 1), 'image/png')

		self.assertEqual(response.status_code, 400)
		self.assertIn('maksimal', response.json()['error'])

	def test_fake_image_is_rejected(self):
		response = self._upload('palsu.jpg', b'bukan gambar sama sekali', 'image/jpeg')

		self.assertEqual(response.status_code, 400)

	def test_wrong_content_type_is_rejected(self):
		response = self._upload('dokumen.pdf', b'%PDF-1.4', 'application/pdf')

		self.assertEqual(response.status_code, 400)


class CreatePageAuthTests(TestCase):
	def test_anonymous_redirected_to_login(self):
		response = self.client.get(reverse('saling_beli:item_create'))

		self.assertEqual(response.status_code, 302)
		self.assertIn('/akun/login/', response.url)


class PageRenderTests(TestCase):
	def setUp(self):
		self.seller = User.objects.create_user(username='penjual', password='test-password')
		self.buyer = User.objects.create_user(username='pembeli', password='test-password')
		self.item = ItemListing.objects.create(
			user=self.seller,
			title='Meja Belajar',
			description='Kayu minimalis',
			price=45000,
		)

	def test_detail_page_renders_for_buyer(self):
		self.client.force_login(self.buyer)
		response = self.client.get(reverse('saling_beli:item_detail', args=[self.item.id]))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Chat Penjual')

	def test_transaction_is_hidden_from_anonymous_and_unrelated_users(self):
		order = TransactionOrder.objects.create(
			item=self.item,
			buyer=self.buyer,
			seller=self.seller,
			agreed_price=45000,
		)

		anonymous_response = self.client.get(reverse('saling_beli:item_detail', args=[self.item.id]))
		self.client.force_login(User.objects.create_user(username='pengunjung-lain'))
		unrelated_response = self.client.get(reverse('saling_beli:item_detail', args=[self.item.id]))

		for response in (anonymous_response, unrelated_response):
			self.assertEqual(response.status_code, 200)
			self.assertNotContains(response, str(order.id)[:8])
			self.assertNotContains(response, 'Tracker Transaksi COD')

		self.client.force_login(self.buyer)
		buyer_response = self.client.get(reverse('saling_beli:item_detail', args=[self.item.id]))
		self.assertContains(buyer_response, str(order.id)[:8])

	def test_reserved_item_hides_buy_and_nego_actions(self):
		self.item.status = ItemListing.Status.RESERVED
		self.item.save(update_fields=['status'])
		self.client.force_login(self.buyer)

		response = self.client.get(reverse('saling_beli:item_detail', args=[self.item.id]))

		self.assertEqual(response.status_code, 200)
		self.assertNotContains(response, 'Beli Sekarang')
		self.assertNotContains(response, 'Ajukan Nego')
		self.assertContains(response, 'Barang sedang diproses')

	def test_detail_page_renders_seller_peer_selector(self):
		self.client.force_login(self.seller)
		response = self.client.get(reverse('saling_beli:item_detail', args=[self.item.id]))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'chat-peer-select')

	def test_create_page_renders_for_logged_in_user(self):
		self.client.force_login(self.seller)
		response = self.client.get(reverse('saling_beli:item_create'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Form Penjual')

	def test_anonymous_detail_page_offers_login_instead_of_chat_compose(self):
		response = self.client.get(reverse('saling_beli:item_detail', args=[self.item.id]))
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Masuk untuk Chat')
		self.assertNotContains(response, 'id="chat-form"')
