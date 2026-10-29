import datetime
import json
import time

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_http_methods
from PIL import Image, UnidentifiedImageError

from .forms import ItemListingForm
from .models import (
	Conversation,
	ItemChatMessage,
	ItemListing,
	PriceOffer,
	TransactionOrder,
	UserNotification,
)
from SaLink.cache_keys import HOME

EDITABLE_FIELDS = {
	'title',
	'description',
	'category',
	'condition',
	'is_free',
	'price',
	'image_url',
	'pickup_location',
	'payout_method',
	'payout_account_name',
	'payout_account_number',
}

MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp', '.gif')
ALLOWED_IMAGE_CONTENT_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}

# Transisi tahap yang sah. Urutan tracker tidak boleh dilompati (kecuali barang gratis bisa langsung atur COD).
STAGE_TRANSITIONS = {
	TransactionOrder.Stage.MENUNGGU_TRANSFER: {
		TransactionOrder.Stage.BUKTI_DIUNGGAH,
		TransactionOrder.Stage.BATAL,
	},
	TransactionOrder.Stage.BUKTI_DIUNGGAH: {
		TransactionOrder.Stage.DIKONFIRMASI,
	},
	TransactionOrder.Stage.DIKONFIRMASI: {
		TransactionOrder.Stage.JANJI_TEMU_COD,
	},
	TransactionOrder.Stage.JANJI_TEMU_COD: {
		TransactionOrder.Stage.SELESAI,
	},
	TransactionOrder.Stage.SELESAI: set(),
	TransactionOrder.Stage.BATAL: set(),
}

# Pihak yang boleh memindahkan order ke tahap tersebut.
STAGE_ACTORS = {
	TransactionOrder.Stage.BUKTI_DIUNGGAH: 'BUYER',
	TransactionOrder.Stage.DIKONFIRMASI: 'SELLER',
	TransactionOrder.Stage.JANJI_TEMU_COD: 'BOTH',
	TransactionOrder.Stage.SELESAI: 'BOTH',
	TransactionOrder.Stage.BATAL: 'BOTH',
}



def _listing_data(listing):
	return {
		'id': str(listing.id),
		'user_id': listing.user_id,
		'title': listing.title,
		'description': listing.description,
		'category': listing.category,
		'condition': listing.condition,
		'is_free': listing.is_free,
		'price': str(listing.price),
		'image_url': listing.image_url,
		'image': listing.image.url if listing.image else None,
		'display_image': listing.display_image,
		'pickup_location': listing.pickup_location,
		'status': listing.status,
		'created_at': listing.created_at.isoformat(),
		'updated_at': listing.updated_at.isoformat(),
	}


def _payload(request):
	try:
		data = json.loads(request.body)
	except (json.JSONDecodeError, UnicodeDecodeError):
		return None, JsonResponse({'error': 'Request body must contain valid JSON.'}, status=400)

	if not isinstance(data, dict):
		return None, JsonResponse({'error': 'Request body must be a JSON object.'}, status=400)

	unknown_fields = set(data) - EDITABLE_FIELDS
	if unknown_fields:
		return None, JsonResponse(
			{'error': 'Unknown fields.', 'fields': sorted(unknown_fields)},
			status=400,
		)

	return data, None


def _validation_errors(listing):
	if listing.is_free:
		listing.price = 0
	elif listing.payout_method == 'Bank BCA':
		# API clients may omit the field; keep the legacy model default but
		# normalize it to the value used by the form choices.
		listing.payout_method = 'BCA'
	try:
		listing.full_clean()
	except ValidationError as error:
		return error.message_dict
	if not listing.is_free:
		allowed_methods = {value for value, _label in ItemListingForm.PAYOUT_METHOD_CHOICES}
		if listing.payout_method not in allowed_methods:
			return {'payout_method': ['Pilih metode pembayaran yang tersedia.']}
		if listing.price <= 0:
			return {'price': ['Harga barang berbayar harus lebih besar dari Rp 0.']}
		if not (listing.payout_account_number or '').strip():
			return {'payout_account_number': ['Barang berbayar wajib memiliki nomor rekening/e-wallet.']}
	return None


def _invalidate_home():
	transaction.on_commit(lambda: cache.delete(HOME))


def _notification_data(notification):
	return {
		'id': str(notification.id),
		'title': notification.title,
		'message': notification.message,
		'type': notification.notification_type,
		'link': notification.link or '#',
		'is_read': notification.is_read,
		'created_at': notification.created_at.strftime('%H:%M, %d %b'),
	}


def _thread_summary(conversation):
	last = conversation.messages.order_by('-created_at').first()
	return {
		'buyer_id': conversation.buyer_id,
		'buyer': conversation.buyer.username,
		'last_message': last.message[:60] if last else '',
		'updated_at': conversation.updated_at.isoformat(),
	}


def _resolve_conversation(item, user, peer_id):
	"""
	Menentukan thread chat yang dituju.
	Pembeli memakai thread miliknya sendiri; penjual wajib memilih pembeli (peer).
	"""
	if user == item.user:
		if not peer_id:
			return None, 'Pilih pembeli yang ingin diajak chat.'
		buyer = get_object_or_404(User, pk=peer_id)
		if buyer == item.user:
			return None, 'Penjual tidak bisa memulai chat dengan dirinya sendiri.'
		if not Conversation.objects.filter(item=item, buyer=buyer).exists() and not (
			TransactionOrder.objects.filter(item=item, buyer=buyer).exists()
			or PriceOffer.objects.filter(item=item, buyer=buyer).exists()
		):
			return None, 'Pembeli ini belum pernah menghubungi atau memesan barang ini.'
	else:
		buyer = user

	conversation, _ = Conversation.objects.get_or_create(
		item=item,
		buyer=buyer,
		defaults={'seller': item.user},
	)
	return conversation, None


# ==========================================
# HTML Views (Menggunakan Session & Cookies)
# ==========================================

def index(request):
	"""
	Halaman utama katalog prelove Saling Beli (HTML).
	Mendukung pencarian (?q=...), filter kategori, kondisi fisik, dan pengurutan (A-Z, Z-A, terbaru, terlama).
	"""
	query = request.GET.get('q', '').strip()
	category = request.GET.get('category', '').strip()
	condition = request.GET.get('condition', '').strip()
	sort = request.GET.get('sort', 'newest').strip()

	show_sold = request.GET.get('show_sold', '').strip() == '1'
	# Katalog default hanya menampilkan barang yang benar-benar bisa dipesan.
	if show_sold:
		items = ItemListing.objects.all()
	else:
		items = ItemListing.objects.filter(status=ItemListing.Status.AVAILABLE)

	# Filter search query
	if query:
		items = items.filter(
			Q(title__icontains=query) |
			Q(description__icontains=query) |
			Q(pickup_location__icontains=query)
		)

	# Filter kategori barang
	if category and category in ItemListing.Category.values:
		items = items.filter(category=category)

	# Filter kondisi fisik barang
	if condition and condition in ItemListing.Condition.values:
		items = items.filter(condition=condition)

	# Sorting: A-Z, Z-A, terbaru, terlama
	if sort == 'name_asc':
		items = items.order_by('title')
	elif sort == 'name_desc':
		items = items.order_by('-title')
	elif sort == 'oldest':
		items = items.order_by('created_at')
	else:  # 'newest' default
		sort = 'newest'
		items = items.order_by('-created_at')

	# Session tracking: hitung berapa kali user membuka katalog saling_beli
	session_views = request.session.get('saling_beli_views', 0) + 1
	request.session['saling_beli_views'] = session_views

	# Cookie tracking: membaca cookie last_visit
	last_visit_cookie = request.COOKIES.get('saling_beli_last_visit', None)
	last_login_cookie = request.COOKIES.get('last_login', None)

	# Ambil data barang yang terakhir dilihat dari Session
	recently_viewed_ids = request.session.get('recently_viewed_items', [])
	recently_viewed_items = []
	if recently_viewed_ids:
		id_map = {str(item.id): item for item in ItemListing.objects.filter(id__in=recently_viewed_ids)}
		recently_viewed_items = [id_map[i_id] for i_id in recently_viewed_ids if i_id in id_map]

	context = {
		'items': items,
		'query': query,
		'category': category,
		'condition': condition,
		'sort': sort,
		'show_sold': show_sold,
		'categories': ItemListing.Category.choices,
		'conditions': ItemListing.Condition.choices,
		'session_views': session_views,
		'last_visit_cookie': last_visit_cookie,
		'last_login_cookie': last_login_cookie,
		'recently_viewed_items': recently_viewed_items,
	}

	response = render(request, 'saling_beli/saling-beli.html', context)

	now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
	response.set_cookie('saling_beli_last_visit', now_str, max_age=60 * 60 * 24 * 7)

	return response


@login_required
def item_create_page(request):
	"""
	Halaman Form Tambah Barang / Hibah bagi Penjual / Pemberi (HTML).
	Wajib login agar listing selalu tercatat atas nama pemilik yang sah.
	"""
	if request.method == 'POST':
		form = ItemListingForm(request.POST, request.FILES)
		if form.is_valid():
			listing = form.save(commit=False)
			listing.user = request.user

			if listing.is_free:
				listing.price = 0

			listing.save()
			_invalidate_home()
			return redirect('saling_beli:item_detail', listing_id=listing.id)
	else:
		form = ItemListingForm()

	context = {
		'form': form,
	}
	return render(request, 'saling_beli/saling-beli-form.html', context)

@login_required
def item_edit_page(request, listing_id):
	"""
	Halaman Form Edit Barang bagi Penjual / Pemilik Barang (HTML).
	"""
	listing = get_object_or_404(ItemListing, pk=listing_id, user=request.user)
	if listing.orders.exclude(stage__in=[TransactionOrder.Stage.BATAL, TransactionOrder.Stage.SELESAI]).exists():
		messages.error(request, 'Barang tidak dapat diedit selama transaksi masih berjalan.')
		return redirect('saling_beli:item_detail', listing_id=listing.id)

	if request.method == 'POST':
		form = ItemListingForm(request.POST, request.FILES, instance=listing)
		if form.is_valid():
			item = form.save(commit=False)
			if item.is_free:
				item.price = 0
			item.save()
			_invalidate_home()
			return redirect('saling_beli:item_detail', listing_id=item.id)
	else:
		form = ItemListingForm(instance=listing)

	context = {
		'form': form,
		'is_edit': True,
		'listing': listing,
	}
	return render(request, 'saling_beli/saling-beli-form.html', context)


@login_required
@require_http_methods(['POST'])
def item_delete_page(request, listing_id):
	"""
	Menghapus barang dagangan oleh pemiliknya (HTML Form POST).
	"""
	listing = get_object_or_404(ItemListing, pk=listing_id, user=request.user)
	if listing.orders.exclude(stage__in=[TransactionOrder.Stage.BATAL, TransactionOrder.Stage.SELESAI]).exists():
		messages.error(request, 'Barang tidak dapat dihapus selama transaksi masih berjalan.')
		return redirect('saling_beli:item_detail', listing_id=listing.id)
	listing.delete()
	_invalidate_home()
	return redirect('saling_beli:index')



def item_detail(request, listing_id):
	"""
	Halaman detail barang prelove (HTML).
	Menyimpan riwayat barang yang baru dilihat ke dalam Session user,
	serta menampilkan daftar tawaran nego dan tracker order.
	"""
	item = get_object_or_404(ItemListing, pk=listing_id)

	# Session: Tambahkan item ke daftar 'recently_viewed'
	recently_viewed = request.session.get('recently_viewed_items', [])
	item_id_str = str(item.id)
	if item_id_str in recently_viewed:
		recently_viewed.remove(item_id_str)
	recently_viewed.insert(0, item_id_str)
	request.session['recently_viewed_items'] = recently_viewed[:5]

	# Data transaksi bersifat privat: hanya penjual atau pembeli terkait yang boleh melihatnya.
	if request.user.is_authenticated:
		orders = item.orders.filter(
			Q(seller=request.user) | Q(buyer=request.user)
		).select_related('buyer', 'seller').all()
		if request.user == item.user:
			offers = item.offers.select_related('buyer').all()
		else:
			offers = item.offers.filter(buyer=request.user).select_related('buyer')
	else:
		orders = TransactionOrder.objects.none()
		offers = PriceOffer.objects.none()

	can_purchase = (
		request.user.is_authenticated
		and request.user != item.user
		and item.status == ItemListing.Status.AVAILABLE
		and (item.is_free or bool(item.payout_account_number))
	)
	can_negotiate = can_purchase and not item.is_free and item.price > 0

	context = {
		'item': item,
		'offers': offers,
		'orders': orders,
		'can_purchase': can_purchase,
		'can_negotiate': can_negotiate,
	}
	return render(request, 'saling_beli/saling-beli-detail.html', context)


@require_http_methods(['POST'])
def make_offer(request, listing_id):
	"""
	Mengajukan penawaran harga (nego) terhadap barang.
	"""
	if not request.user.is_authenticated:
		return JsonResponse({'error': 'Silakan login terlebih dahulu untuk menawar harga.'}, status=401)

	item = get_object_or_404(ItemListing, pk=listing_id)
	if item.status != ItemListing.Status.AVAILABLE:
		return JsonResponse({'error': 'Barang ini sedang dipesan atau sudah terjual.'}, status=400)

	if item.is_free or item.price <= 0:
		return JsonResponse({'error': 'Barang gratis tidak dapat dinego.'}, status=400)
	if not item.payout_account_number.strip():
		return JsonResponse({'error': 'Penjual belum menambahkan rekening pembayaran.'}, status=400)

	if item.user == request.user:
		return JsonResponse({'error': 'Anda tidak bisa menawar barang milik sendiri.'}, status=400)

	try:
		body = json.loads(request.body) if request.body else {}
		if not isinstance(body, dict):
			body = {}
		price_val = request.POST.get('offered_price') or body.get('offered_price')
		note = request.POST.get('note') or body.get('note', '')
		offered_price = int(price_val)
	except (ValueError, TypeError, json.JSONDecodeError):
		return JsonResponse({'error': 'Harga penawaran harus berupa angka valid.'}, status=400)

	if not isinstance(note, str):
		note = ''
	if offered_price <= 0:
		return JsonResponse({'error': 'Harga penawaran harus lebih besar dari Rp 0.'}, status=400)

	if offered_price >= item.price:
		return JsonResponse({'error': 'Harga penawaran harus lebih rendah dari harga asli. Gunakan tombol Pesan Sekarang jika ingin membeli dengan harga normal.'}, status=400)

	with transaction.atomic():
		item = ItemListing.objects.select_for_update().get(pk=listing_id)
		if item.status != ItemListing.Status.AVAILABLE:
			return JsonResponse({'error': 'Barang ini sedang dipesan atau sudah terjual.'}, status=400)
		if not item.payout_account_number.strip():
			return JsonResponse({'error': 'Penjual belum menambahkan rekening pembayaran.'}, status=400)
		if offered_price >= item.price:
			return JsonResponse({'error': 'Harga penawaran harus lebih rendah dari harga asli.'}, status=400)
		offer = PriceOffer.objects.create(
			item=item,
			buyer=request.user,
			offered_price=offered_price,
			note=note.strip()[:255],
		)
		UserNotification.objects.create(
			user=item.user,
			title=f'Tawaran Nego Baru dari @{request.user.username}',
			message=f'@{request.user.username} menawar "{item.title}" seharga Rp{offered_price:,}.',
			notification_type=UserNotification.NotifType.OFFER,
			link=f'/saling-beli/detail/{item.id}/',
		)

	return JsonResponse({
		'success': True,
		'message': 'Penawaran nego berhasil dikirim ke penjual!',
		'offer_id': str(offer.id),
		'buyer': offer.buyer.username,
		'offered_price': int(offer.offered_price),
		'status': offer.status,
	})


@require_http_methods(['POST'])
def respond_offer(request, offer_id):
	"""
	Penjual menerima atau menolak penawaran harga.
	Jika diterima, otomatis membuat TransactionOrder dengan harga yang disepakati.
	"""
	if not request.user.is_authenticated:
		return JsonResponse({'error': 'Authentication required.'}, status=401)

	try:
		body = json.loads(request.body) if request.body else {}
		if not isinstance(body, dict):
			body = {}
		action = request.POST.get('action') or body.get('action')
	except json.JSONDecodeError:
		action = request.POST.get('action')

	if action == 'accept':
		# Offer, order, status barang, dan notifikasi harus berhasil bersama.
		with transaction.atomic():
			offer_ref = get_object_or_404(PriceOffer.objects.only('pk', 'item_id'), pk=offer_id)
			item = ItemListing.objects.select_for_update().get(pk=offer_ref.item_id)
			offer = get_object_or_404(
				PriceOffer.objects.select_for_update().select_related('buyer'),
				pk=offer_id,
			)
			offer.item = item
			if offer.item.user_id != request.user.pk:
				return JsonResponse({'error': 'Hanya penjual barang yang dapat merespon nego ini.'}, status=403)
			if offer.status != PriceOffer.OfferStatus.PENDING:
				return JsonResponse({'error': 'Penawaran ini sudah direspons sebelumnya.'}, status=400)
			if item.status != ItemListing.Status.AVAILABLE:
				return JsonResponse({'error': 'Barang sudah dipesan atau terjual; penawaran tidak dapat diterima.'}, status=400)
			if not item.payout_account_number.strip():
				return JsonResponse({'error': 'Penjual belum menambahkan rekening pembayaran.'}, status=400)
			if TransactionOrder.objects.filter(item=item).exclude(
				stage__in=[TransactionOrder.Stage.BATAL, TransactionOrder.Stage.SELESAI],
			).exists():
				return JsonResponse({'error': 'Barang sudah memiliki pesanan aktif.'}, status=400)
			order = TransactionOrder.objects.create(
				item=item,
				buyer=offer.buyer,
				seller=item.user,
				agreed_price=offer.offered_price,
				stage=TransactionOrder.Stage.MENUNGGU_TRANSFER,
			)

			offer.status = PriceOffer.OfferStatus.ACCEPTED
			offer.save(update_fields=['status', 'updated_at'])

			# Tolak otomatis penawaran pending lain untuk barang ini agar pembeli lain mendapat kepastian
			other_offers = PriceOffer.objects.filter(
				item=item,
				status=PriceOffer.OfferStatus.PENDING
			).exclude(pk=offer.pk)
			for pending_offer in other_offers:
				pending_offer.status = PriceOffer.OfferStatus.REJECTED
				pending_offer.save(update_fields=['status', 'updated_at'])
				UserNotification.objects.create(
					user=pending_offer.buyer,
					title='Tawaran Nego Ditolak',
					message=f'Penjual @{request.user.username} telah menerima penawaran lain untuk "{item.title}".',
					notification_type=UserNotification.NotifType.OFFER,
					link=f'/saling-beli/detail/{item.id}/'
				)

			item.status = ItemListing.Status.RESERVED
			item.save(update_fields=['status', 'updated_at'])
			_invalidate_home()

			UserNotification.objects.create(
				user=offer.buyer,
				title='Tawaran Nego Anda Diterima!',
				message=f'Penjual @{request.user.username} menerima tawaran Rp{offer.offered_price:,} untuk "{item.title}". Transaksi COD dimulai.',
				notification_type=UserNotification.NotifType.TRACKER_UPDATE,
				link=f'/saling-beli/detail/{item.id}/'
			)

		return JsonResponse({
			'success': True,
			'status': 'ACCEPTED',
			'message': f'Penawaran Rp{offer.offered_price:,} diterima! Transaksi telah dimulai.',
			'order_id': str(order.id),
		})
	elif action == 'reject':
		with transaction.atomic():
			offer = get_object_or_404(PriceOffer.objects.select_for_update().select_related('item', 'buyer'), pk=offer_id)
			if offer.item.user_id != request.user.pk:
				return JsonResponse({'error': 'Hanya penjual barang yang dapat merespon nego ini.'}, status=403)
			if offer.status != PriceOffer.OfferStatus.PENDING:
				return JsonResponse({'error': 'Penawaran ini sudah direspons sebelumnya.'}, status=400)
			offer.status = PriceOffer.OfferStatus.REJECTED
			offer.save(update_fields=['status', 'updated_at'])
			UserNotification.objects.create(
				user=offer.buyer,
				title='Tawaran Nego Ditolak',
				message=f'Penjual @{request.user.username} menolak tawaran Anda untuk "{offer.item.title}".',
				notification_type=UserNotification.NotifType.OFFER,
				link=f'/saling-beli/detail/{offer.item.id}/',
			)
		return JsonResponse({
			'success': True,
			'status': 'REJECTED',
			'message': 'Penawaran ditolak.',
		})

	return JsonResponse({'error': 'Aksi tidak valid (gunakan accept atau reject).'}, status=400)


@require_http_methods(['POST'])
def create_order(request, listing_id):
	"""
	Membuat pesanan langsung (Buy Now) dengan harga normal barang.
	"""
	if not request.user.is_authenticated:
		return JsonResponse({'error': 'Silakan login untuk memesan barang.'}, status=401)

	# Kunci baris barang agar dua pembeli tidak bisa memesan bersamaan.
	with transaction.atomic():
		item = get_object_or_404(ItemListing.objects.select_for_update(), pk=listing_id)

		if item.user == request.user:
			return JsonResponse({'error': 'Anda tidak bisa membeli barang Anda sendiri.'}, status=400)

		existing_order = TransactionOrder.objects.filter(
			item=item,
			buyer=request.user,
		).exclude(
			stage__in=[TransactionOrder.Stage.BATAL, TransactionOrder.Stage.SELESAI],
		).first()
		if existing_order:
			return JsonResponse({
				'success': True,
				'order_id': str(existing_order.id),
				'message': 'Anda sudah memiliki pesanan aktif untuk barang ini. Lanjutkan di tracker.',
				'already_exists': True,
			})

		if TransactionOrder.objects.filter(item=item).exclude(
			stage__in=[TransactionOrder.Stage.BATAL, TransactionOrder.Stage.SELESAI],
		).exists():
			return JsonResponse({'error': 'Barang sedang dipesan pembeli lain.'}, status=400)

		if item.status != ItemListing.Status.AVAILABLE:
			return JsonResponse({'error': 'Barang ini sedang dipesan atau sudah tidak tersedia.'}, status=400)
		if not item.is_free and not item.payout_account_number.strip():
			return JsonResponse({'error': 'Penjual belum menambahkan rekening pembayaran.'}, status=400)

		order = TransactionOrder.objects.create(
			item=item,
			buyer=request.user,
			seller=item.user,
			agreed_price=item.price,
			stage=TransactionOrder.Stage.MENUNGGU_TRANSFER,
		)

		# Barang dikunci selama transaksi berjalan.
		item.status = ItemListing.Status.RESERVED
		item.save(update_fields=['status', 'updated_at'])
		_invalidate_home()

		# Tolak otomatis penawaran pending untuk barang ini karena sudah dipesan
		other_offers = PriceOffer.objects.filter(
			item=item,
			status=PriceOffer.OfferStatus.PENDING
		)
		for pending_offer in other_offers:
			pending_offer.status = PriceOffer.OfferStatus.REJECTED
			pending_offer.save(update_fields=['status', 'updated_at'])
			UserNotification.objects.create(
				user=pending_offer.buyer,
				title='Tawaran Nego Ditolak',
				message=f'Barang "{item.title}" telah dipesan oleh pembeli lain.',
				notification_type=UserNotification.NotifType.OFFER,
				link=f'/saling-beli/detail/{item.id}/'
			)

		# Notifikasi ke Penjual
		UserNotification.objects.create(
			user=item.user,
			title=f'Pesanan Baru dari @{request.user.username}!',
			message=f'@{request.user.username} telah memesan "{item.title}". Menunggu konfirmasi transfer/COD.',
			notification_type=UserNotification.NotifType.TRACKER_UPDATE,
			link=f'/saling-beli/detail/{item.id}/'
		)

	return JsonResponse({
		'success': True,
		'order_id': str(order.id),
		'message': 'Pesanan berhasil dibuat! Silakan lakukan transfer dan pantau status COD di tracker.',
	})


@require_http_methods(['POST'])
def update_order_stage(request, order_id):
	"""
	Memperbarui tahapan status transaksi / tracker COD dan mengirimkan notifikasi.
	"""
	if not request.user.is_authenticated:
		return JsonResponse({'error': 'Authentication required.'}, status=401)

	try:
		body = json.loads(request.body) if request.body else {}
		if not isinstance(body, dict):
			body = {}
		stage = request.POST.get('stage') or body.get('stage')
		note = request.POST.get('note') or body.get('note', '')
		cod_time = request.POST.get('cod_meeting_time') or body.get('cod_meeting_time', '')
	except json.JSONDecodeError:
		stage = request.POST.get('stage')
		note = request.POST.get('note', '')
		cod_time = request.POST.get('cod_meeting_time', '')
	if not isinstance(note, str):
		note = ''
	if not isinstance(cod_time, str):
		cod_time = ''

	if stage not in TransactionOrder.Stage.values:
		return JsonResponse({'error': 'Tahapan status tidak valid.'}, status=400)

	with transaction.atomic():
		order = get_object_or_404(
			TransactionOrder.objects.select_for_update().select_related('item'),
			pk=order_id,
		)

		if request.user not in [order.buyer, order.seller]:
			return JsonResponse({'error': 'Anda tidak memiliki akses ke pesanan ini.'}, status=403)

		if stage == TransactionOrder.Stage.SELESAI:
			if order.stage == TransactionOrder.Stage.SELESAI:
				return JsonResponse({
					'success': True,
					'stage': order.stage,
					'stage_display': order.get_stage_display(),
					'awaiting_confirmation': False,
					'message': 'Transaksi sudah selesai.',
				})
			if order.stage != TransactionOrder.Stage.JANJI_TEMU_COD:
				return JsonResponse({'error': 'Barang hanya dapat dikonfirmasi setelah jadwal COD dibuat.'}, status=400)
			confirmation_field = 'buyer_confirmed_at' if request.user == order.buyer else 'seller_confirmed_at'
			if getattr(order, confirmation_field) is not None:
				return JsonResponse({
					'success': True,
					'stage': order.stage,
					'stage_display': order.get_stage_display(),
					'awaiting_confirmation': True,
					'message': 'Konfirmasi Anda sudah tersimpan. Menunggu pihak lain.',
				})
			setattr(order, confirmation_field, timezone.now())
			order.save(update_fields=[confirmation_field, 'updated_at'])
			if order.buyer_confirmed_at and order.seller_confirmed_at:
				order.stage = TransactionOrder.Stage.SELESAI
				order.save(update_fields=['stage', 'updated_at'])
				order.item.status = ItemListing.Status.SOLD
				order.item.save(update_fields=['status', 'updated_at'])
				_invalidate_home()
				message = 'Kedua pihak telah mengonfirmasi serah terima. Transaksi selesai.'
			else:
				message = 'Konfirmasi Anda tersimpan. Transaksi selesai setelah pihak lain mengonfirmasi serah terima.'
			recipient = order.seller if request.user == order.buyer else order.buyer
			UserNotification.objects.create(
				user=recipient,
				title=f'Konfirmasi Serah Terima: {order.item.title}',
				message=f'@{request.user.username} telah mengonfirmasi serah terima barang.',
				notification_type=UserNotification.NotifType.TRACKER_UPDATE,
				link=f'/saling-beli/detail/{order.item.id}/',
			)
			return JsonResponse({
				'success': True,
				'stage': order.stage,
				'stage_display': order.get_stage_display(),
				'awaiting_confirmation': order.stage != TransactionOrder.Stage.SELESAI,
				'message': message,
			})

		if stage == order.stage:
			return JsonResponse({
				'success': True,
				'stage': order.stage,
				'stage_display': order.get_stage_display(),
				'message': 'Status pesanan sudah berada di tahap ini.',
			})

		valid_transitions = STAGE_TRANSITIONS.get(order.stage, set())
		if (
			order.item.is_free
			and order.stage == TransactionOrder.Stage.MENUNGGU_TRANSFER
		):
			valid_transitions = valid_transitions | {TransactionOrder.Stage.JANJI_TEMU_COD}
		if stage not in valid_transitions:
			return JsonResponse({
				'error': (
					f'Tahap tidak dapat berpindah dari "{order.get_stage_display()}" '
					f'ke "{TransactionOrder.Stage(stage).label}".'
				),
			}, status=400)
		if order.item.status == ItemListing.Status.SOLD:
			return JsonResponse({'error': 'Barang ini sudah terjual.'}, status=400)

		required_actor = STAGE_ACTORS.get(stage, 'BOTH')
		if required_actor == 'BUYER' and request.user != order.buyer:
			return JsonResponse({'error': 'Tahap ini hanya dapat diubah oleh pembeli.'}, status=403)
		if required_actor == 'SELLER' and request.user != order.seller:
			return JsonResponse({'error': 'Tahap ini hanya dapat diubah oleh penjual.'}, status=403)
		if stage == TransactionOrder.Stage.BUKTI_DIUNGGAH and not str(note).strip():
			return JsonResponse({'error': 'Masukkan nomor referensi atau catatan transfer.'}, status=400)
		if stage == TransactionOrder.Stage.JANJI_TEMU_COD and not str(cod_time).strip():
			return JsonResponse({'error': 'Masukkan waktu pertemuan COD yang disepakati.'}, status=400)
		if len(str(note)) > 255 or len(str(cod_time)) > 150:
			return JsonResponse({'error': 'Catatan terlalu panjang.'}, status=400)

		order.stage = stage
		if note:
			order.payment_proof_note = note
		if cod_time:
			order.cod_meeting_time = cod_time
		order.save()

		# Jika batal, lepaskan kunci barang bila tidak ada order aktif lain
		if stage == TransactionOrder.Stage.BATAL:
			other_active = TransactionOrder.objects.filter(
				item=order.item,
			).exclude(pk=order.pk).exclude(
				stage__in=[TransactionOrder.Stage.BATAL, TransactionOrder.Stage.SELESAI],
			).exists()
			if not other_active and order.item.status == ItemListing.Status.RESERVED:
				order.item.status = ItemListing.Status.AVAILABLE
				order.item.save(update_fields=['status', 'updated_at'])
				_invalidate_home()

		# Kirim Notifikasi ke pihak lawan (jika pembeli update -> kirim ke penjual, vice versa)
		recipient = order.seller if request.user == order.buyer else order.buyer
		UserNotification.objects.create(
			user=recipient,
			title=f'Update Tracker: {order.item.title}',
			message=f'Status pesanan #{str(order.id)[:8]} diubah menjadi: "{order.get_stage_display()}" oleh @{request.user.username}.',
			notification_type=UserNotification.NotifType.TRACKER_UPDATE,
			link=f'/saling-beli/detail/{order.item.id}/'
		)

		return JsonResponse({
			'success': True,
			'stage': order.stage,
			'stage_display': order.get_stage_display(),
			'message': f'Status transaksi berhasil diperbarui menjadi {order.get_stage_display()}',
		})



# ==========================================
# REST / JSON API Views
# ==========================================

@require_http_methods(['GET', 'POST'])
def listings(request):
	if request.method == 'GET':
		return JsonResponse([_listing_data(item) for item in ItemListing.objects.all()], safe=False)

	return _create_listing(request)


@require_http_methods(['GET'])
def listings_json(request):
	"""Endpoint khusus pengembalian JSON semua listing"""
	return JsonResponse([_listing_data(item) for item in ItemListing.objects.all()], safe=False)


@require_http_methods(['POST'])
def listing_create(request):
	return _create_listing(request)


def _create_listing(request):
	if not request.user.is_authenticated:
		return JsonResponse({'error': 'Authentication required.'}, status=401)

	data, error_response = _payload(request)
	if error_response:
		return error_response

	listing = ItemListing(user=request.user, **data)
	errors = _validation_errors(listing)
	if errors:
		return JsonResponse({'errors': errors}, status=400)

	listing.save()
	_invalidate_home()
	return JsonResponse(_listing_data(listing), status=201)


@require_http_methods(['PUT', 'PATCH'])
def listing_update(request, listing_id):
	return _update_listing(request, listing_id)


@require_http_methods(['DELETE'])
def listing_delete(request, listing_id):
	if not request.user.is_authenticated:
		return JsonResponse({'error': 'Authentication required.'}, status=401)

	listing = get_object_or_404(ItemListing, pk=listing_id, user=request.user)
	if listing.orders.exclude(stage__in=[TransactionOrder.Stage.BATAL, TransactionOrder.Stage.SELESAI]).exists():
		return JsonResponse({'error': 'Barang tidak dapat dihapus selama transaksi masih berjalan.'}, status=409)
	listing.delete()
	_invalidate_home()
	return HttpResponse(status=204)


@require_http_methods(['GET', 'PUT', 'PATCH', 'DELETE'])
def listing_detail(request, listing_id):
	if request.method == 'GET':
		listing = get_object_or_404(ItemListing, pk=listing_id)
		return JsonResponse(_listing_data(listing))

	if request.method == 'DELETE':
		return listing_delete(request, listing_id)

	return _update_listing(request, listing_id)


def _update_listing(request, listing_id):
	if not request.user.is_authenticated:
		return JsonResponse({'error': 'Authentication required.'}, status=401)

	listing = get_object_or_404(ItemListing, pk=listing_id, user=request.user)
	if listing.orders.exclude(stage__in=[TransactionOrder.Stage.BATAL, TransactionOrder.Stage.SELESAI]).exists():
		return JsonResponse({'error': 'Barang tidak dapat diedit selama transaksi masih berjalan.'}, status=409)

	data, error_response = _payload(request)
	if error_response:
		return error_response

	for field, value in data.items():
		setattr(listing, field, value)

	errors = _validation_errors(listing)
	if errors:
		return JsonResponse({'errors': errors}, status=400)

	listing.save()
	_invalidate_home()
	return JsonResponse(_listing_data(listing))


@require_http_methods(['POST'])
def upload_item_image(request, listing_id):
	"""
	Endpoint untuk mengupload foto barang dari perangkat ke server/media
	"""
	if not request.user.is_authenticated:
		return JsonResponse({'error': 'Authentication required.'}, status=401)

	listing = get_object_or_404(ItemListing, pk=listing_id, user=request.user)

	if 'image' not in request.FILES:
		return JsonResponse({'error': 'No image file provided in multipart/form-data.'}, status=400)

	uploaded_file = request.FILES['image']

	if uploaded_file.size > MAX_IMAGE_BYTES:
		return JsonResponse({
			'error': f'Ukuran foto maksimal {MAX_IMAGE_BYTES // (1024 * 1024)} MB.',
		}, status=400)

	if not uploaded_file.name.lower().endswith(ALLOWED_IMAGE_EXTENSIONS):
		return JsonResponse({'error': 'Format file harus berupa gambar (JPG, PNG, WEBP, GIF).'}, status=400)

	content_type = (uploaded_file.content_type or '').lower()
	if content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
		return JsonResponse({'error': 'Content-Type berkas bukan gambar yang didukung.'}, status=400)

	# Pastikan isi berkas benar-benar gambar, bukan hanya ekstensinya.
	try:
		with Image.open(uploaded_file) as image:
			image.verify()
	except (UnidentifiedImageError, OSError, ValueError):
		return JsonResponse({'error': 'Berkas tidak dapat dibaca sebagai gambar.'}, status=400)

	uploaded_file.seek(0)
	listing.image = uploaded_file
	listing.save()
	_invalidate_home()

	return JsonResponse({
		'success': True,
		'message': 'Foto barang berhasil diunggah!',
		'image_url': listing.image.url,
		'listing': _listing_data(listing),
	})


# ==========================================
# Chat & Realtime In-App Notification Views
# ==========================================

@require_http_methods(['GET', 'POST'])
def item_chats(request, listing_id):
	"""
	Riwayat chat atau kirim pesan baru. Satu thread per pasangan barang-pembeli.
	Penjual wajib menyertakan peer (id pembeli) untuk memilih thread.
	"""
	if not request.user.is_authenticated:
		return JsonResponse({'error': 'Silakan login untuk menggunakan fitur chat.'}, status=401)

	item = get_object_or_404(ItemListing, pk=listing_id)

	if request.method == 'GET':
		peer_id = request.GET.get('peer')

		threads = []
		if request.user == item.user:
			conversations = item.conversations.select_related('buyer').all()
			threads = [_thread_summary(c) for c in conversations]

			# Calon pembeli dari order/offer yang belum punya thread tetap bisa dipilih.
			known = {t['buyer_id'] for t in threads}
			for buyer in User.objects.filter(
				Q(orders_bought__item=item) | Q(price_offers__item=item)
			).distinct():
				if buyer.pk not in known and buyer.pk != item.user_id:
					threads.append({
						'buyer_id': buyer.pk,
						'buyer': buyer.username,
						'last_message': '',
						'updated_at': '',
					})

			# Tanpa parameter peer, penjual diarahkan ke thread pertama.
			if not peer_id and threads:
				peer_id = threads[0]['buyer_id']

		conversation, error = _resolve_conversation(item, request.user, peer_id)
		if error:
			return JsonResponse({
				'success': True,
				'chats': [],
				'threads': threads,
				'peer': None,
				'error': error,
			})

		chats = conversation.messages.select_related('sender').order_by('created_at')
		data = [
			{
				'id': str(chat.id),
				'sender': chat.sender.username,
				'is_me': chat.sender == request.user,
				'message': chat.message,
				'created_at': chat.created_at.strftime('%H:%M, %d %b'),
			}
			for chat in chats
		]

		if request.user == item.user:
			peer = {'id': conversation.buyer_id, 'username': conversation.buyer.username}
		else:
			peer = {'id': conversation.seller_id, 'username': conversation.seller.username}
		conversation.messages.filter(recipient=request.user, is_read=False).update(is_read=True)

		return JsonResponse({
			'success': True,
			'chats': data,
			'threads': threads,
			'peer': peer,
			'conversation_id': str(conversation.id),
		})

	# POST: Kirim pesan
	try:
		body = json.loads(request.body) if request.body else {}
		if not isinstance(body, dict):
			return JsonResponse({'error': 'Request body must be a JSON object.'}, status=400)
		message_text = request.POST.get('message') or body.get('message', '')
		peer_id = request.POST.get('peer') or body.get('peer')
	except (json.JSONDecodeError, UnicodeDecodeError):
		message_text = request.POST.get('message', '')
		peer_id = request.POST.get('peer')

	if not isinstance(message_text, str):
		return JsonResponse({'error': 'Pesan harus berupa teks.'}, status=400)
	message_text = message_text.strip()
	if not message_text:
		return JsonResponse({'error': 'Pesan tidak boleh kosong.'}, status=400)
	if len(message_text) > 2000:
		return JsonResponse({'error': 'Pesan maksimal 2.000 karakter.'}, status=400)

	conversation, error = _resolve_conversation(item, request.user, peer_id)
	if error:
		return JsonResponse({'error': error}, status=400)

	recipient = conversation.seller if request.user == conversation.buyer else conversation.buyer

	with transaction.atomic():
		chat = ItemChatMessage.objects.create(
			conversation=conversation,
			item=item,
			sender=request.user,
			recipient=recipient,
			message=message_text,
		)
		Conversation.objects.filter(pk=conversation.pk).update(updated_at=timezone.now())

		# Tautan notifikasi membuka thread yang tepat.
		if recipient == item.user:
			link = f'/saling-beli/detail/{item.id}/?peer={request.user.pk}#chat'
		else:
			link = f'/saling-beli/detail/{item.id}/#chat'

		UserNotification.objects.create(
			user=recipient,
			title=f'Pesan baru dari @{request.user.username}',
			message=f'@{request.user.username} mengirim pesan tentang "{item.title}": "{message_text[:60]}"',
			notification_type=UserNotification.NotifType.CHAT,
			link=link,
		)

	return JsonResponse({
		'success': True,
		'message': 'Pesan berhasil terkirim!',
		'chat': {
			'id': str(chat.id),
			'sender': chat.sender.username,
			'is_me': True,
			'message': chat.message,
			'created_at': chat.created_at.strftime('%H:%M, %d %b'),
		},
		'peer': {
			'id': recipient.pk,
			'username': recipient.username,
		},
	})


@require_http_methods(['GET'])
def user_notifications(request):
	"""
	Endpoint daftar notifikasi (awal pemuatan dan saat dropdown dibuka).
	"""
	if not request.user.is_authenticated:
		return JsonResponse({'notifications': [], 'unread_count': 0, 'cursor': None})

	notifs = UserNotification.objects.filter(user=request.user)[:10]
	unread_count = UserNotification.objects.filter(user=request.user, is_read=False).count()
	latest = UserNotification.objects.filter(user=request.user).order_by('-created_at').first()

	return JsonResponse({
		'success': True,
		'unread_count': unread_count,
		'notifications': [_notification_data(notification) for notification in notifs],
		'cursor': latest.created_at.isoformat() if latest else None,
	})


@require_http_methods(['GET'])
def notification_stream(request):
	"""
	Long-polling: menahan request sampai ada notifikasi baru atau 20 detik habis.
	Menghilangkan jeda tetap 5 detik pada polling biasa.
	"""
	if not request.user.is_authenticated:
		return JsonResponse({'notifications': [], 'unread_count': 0, 'cursor': None, 'timeout': False})

	after_raw = request.GET.get('after')
	after = None
	if after_raw:
		try:
			after = parse_datetime(after_raw)
		except ValueError:
			after = None

	deadline = time.monotonic() + 20
	new_notifications = []

	while True:
		queryset = UserNotification.objects.filter(user=request.user)
		if after:
			queryset = queryset.filter(created_at__gt=after)
		new_notifications = list(queryset.order_by('created_at')[:10])
		if new_notifications or time.monotonic() >= deadline:
			break
		time.sleep(1)

	latest = UserNotification.objects.filter(user=request.user).order_by('-created_at').first()
	unread_count = UserNotification.objects.filter(user=request.user, is_read=False).count()

	return JsonResponse({
		'success': True,
		'unread_count': unread_count,
		'notifications': [_notification_data(notification) for notification in new_notifications],
		'cursor': latest.created_at.isoformat() if latest else None,
		'timeout': not new_notifications,
	})


@require_http_methods(['POST'])
def mark_notifications_read(request):
	"""
	Menandai semua notifikasi user sebagai terbaca.
	"""
	if not request.user.is_authenticated:
		return JsonResponse({'error': 'Authentication required.'}, status=401)

	UserNotification.objects.filter(user=request.user, is_read=False).update(is_read=True)
	return JsonResponse({'success': True, 'message': 'Semua notifikasi ditandai sebagai terbaca.'})
