import datetime
import json

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .forms import ItemListingForm
from .models import ItemChatMessage, ItemListing, PriceOffer, TransactionOrder, UserNotification

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
	'status',
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
		'payout_method': listing.payout_method,
		'payout_account_name': listing.payout_account_name,
		'payout_account_number': listing.payout_account_number,
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
	try:
		listing.full_clean()
	except ValidationError as error:
		return error.message_dict
	return None


# ==========================================
# HTML Views (Menggunakan Session & Cookies)
# ==========================================

def index(request):
	"""
	Halaman utama katalog prelove Saling Beli (HTML).
	Mendukung pencarian (?q=...), session view count, dan pembacaan cookie.
	"""
	query = request.GET.get('q', '').strip()
	items = ItemListing.objects.all()

	if query:
		items = items.filter(
			Q(title__icontains=query) |
			Q(description__icontains=query) |
			Q(pickup_location__icontains=query)
		)

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
		# Preserve order of recently viewed
		id_map = {str(item.id): item for item in ItemListing.objects.filter(id__in=recently_viewed_ids)}
		recently_viewed_items = [id_map[i_id] for i_id in recently_viewed_ids if i_id in id_map]

	context = {
		'items': items,
		'query': query,
		'session_views': session_views,
		'last_visit_cookie': last_visit_cookie,
		'last_login_cookie': last_login_cookie,
		'recently_viewed_items': recently_viewed_items,
	}

	response = render(request, 'saling_beli/saling-beli.html', context)

	# Set cookie kunjungan terakhir untuk tracking user preference
	now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
	response.set_cookie('saling_beli_last_visit', now_str, max_age=60 * 60 * 24 * 7)

	return response


def item_create_page(request):
	"""
	Halaman Form Tambah Barang / Hibah bagi Penjual / Pemberi (HTML).
	Mendukung upload foto dari galeri/perangkat dan integrasi OpenStreetMap.
	"""
	from django.contrib.auth.models import User

	if request.method == 'POST':
		form = ItemListingForm(request.POST, request.FILES)
		if form.is_valid():
			listing = form.save(commit=False)
			if request.user.is_authenticated:
				listing.user = request.user
			else:
				# Fallback ke user pertama atau buat default jika guest
				listing.user = User.objects.first() or User.objects.create_user('penjual_ui', 'penjual@ui.ac.id')

			if listing.is_free:
				listing.price = 0

			listing.save()
			return redirect('saling_beli:item_detail', listing_id=listing.id)
	else:
		form = ItemListingForm()

	context = {
		'form': form,
	}
	return render(request, 'saling_beli/saling-beli-form.html', context)


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

	# Ambil daftar penawaran (nego) untuk barang ini
	offers = item.offers.select_related('buyer').all()
	# Ambil tracker transaksi pemesanan terkait barang ini
	orders = item.orders.select_related('buyer', 'seller').all()

	context = {
		'item': item,
		'offers': offers,
		'orders': orders,
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
	if item.is_free or item.price <= 0:
		return JsonResponse({'error': 'Barang gratis tidak dapat dinego.'}, status=400)

	if item.user == request.user:
		return JsonResponse({'error': 'Anda tidak bisa menawar barang milik sendiri.'}, status=400)

	try:
		price_val = request.POST.get('offered_price') or json.loads(request.body).get('offered_price')
		note = request.POST.get('note', '') or (json.loads(request.body).get('note', '') if request.body else '')
		offered_price = int(price_val)
	except (ValueError, TypeError, json.JSONDecodeError):
		return JsonResponse({'error': 'Harga penawaran harus berupa angka valid.'}, status=400)

	offer = PriceOffer.objects.create(
		item=item,
		buyer=request.user,
		offered_price=offered_price,
		note=note.strip()
	)

	# Kirim Notifikasi ke Penjual
	UserNotification.objects.create(
		user=item.user,
		title=f'Tawaran Nego Baru dari @{request.user.username}',
		message=f'@{request.user.username} menawar "{item.title}" seharga Rp{offered_price:,}.',
		notification_type=UserNotification.NotifType.OFFER,
		link=f'/saling-beli/detail/{item.id}/'
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

	offer = get_object_or_404(PriceOffer, pk=offer_id)
	if offer.item.user != request.user:
		return JsonResponse({'error': 'Hanya penjual barang yang dapat merespon nego ini.'}, status=403)

	try:
		body = json.loads(request.body) if request.body else {}
		action = request.POST.get('action') or body.get('action')
	except json.JSONDecodeError:
		action = request.POST.get('action')

	if action == 'accept':
		offer.status = PriceOffer.OfferStatus.ACCEPTED
		offer.save()
		# Buat TransactionOrder
		order, created = TransactionOrder.objects.get_or_create(
			item=offer.item,
			buyer=offer.buyer,
			seller=offer.item.user,
			defaults={'agreed_price': offer.offered_price}
		)
		# Kirim Notifikasi ke Pembeli
		UserNotification.objects.create(
			user=offer.buyer,
			title='Tawaran Nego Anda Diterima!',
			message=f'Penjual @{request.user.username} menerima tawaran Rp{offer.offered_price:,} untuk "{offer.item.title}". Transaksi COD dimulai.',
			notification_type=UserNotification.NotifType.TRACKER_UPDATE,
			link=f'/saling-beli/detail/{offer.item.id}/'
		)
		return JsonResponse({
			'success': True,
			'status': 'ACCEPTED',
			'message': f'Penawaran Rp{offer.offered_price:,} diterima! Transaksi telah dimulai.',
			'order_id': str(order.id),
		})
	elif action == 'reject':
		offer.status = PriceOffer.OfferStatus.REJECTED
		offer.save()
		UserNotification.objects.create(
			user=offer.buyer,
			title='Tawaran Nego Ditolak',
			message=f'Penjual @{request.user.username} menolak tawaran Anda untuk "{offer.item.title}".',
			notification_type=UserNotification.NotifType.OFFER,
			link=f'/saling-beli/detail/{offer.item.id}/'
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

	item = get_object_or_404(ItemListing, pk=listing_id)
	if item.user == request.user:
		return JsonResponse({'error': 'Anda tidak bisa membeli barang Anda sendiri.'}, status=400)

	order = TransactionOrder.objects.create(
		item=item,
		buyer=request.user,
		seller=item.user,
		agreed_price=item.price,
		stage=TransactionOrder.Stage.MENUNGGU_TRANSFER,
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

	order = get_object_or_404(TransactionOrder, pk=order_id)
	if request.user not in [order.buyer, order.seller]:
		return JsonResponse({'error': 'Anda tidak memiliki akses ke pesanan ini.'}, status=403)

	try:
		body = json.loads(request.body) if request.body else {}
		stage = request.POST.get('stage') or body.get('stage')
		note = request.POST.get('note') or body.get('note', '')
		cod_time = request.POST.get('cod_meeting_time') or body.get('cod_meeting_time', '')
	except json.JSONDecodeError:
		stage = request.POST.get('stage')
		note = request.POST.get('note', '')
		cod_time = request.POST.get('cod_meeting_time', '')

	if stage in TransactionOrder.Stage.values:
		order.stage = stage
		if note:
			order.payment_proof_note = note
		if cod_time:
			order.cod_meeting_time = cod_time
		order.save()

		# Jika selesai, tandai barang sebagai SOLD
		if stage == TransactionOrder.Stage.SELESAI:
			order.item.status = ItemListing.Status.SOLD
			order.item.save()

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

	return JsonResponse({'error': 'Tahapan status tidak valid.'}, status=400)



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
	return JsonResponse(_listing_data(listing), status=201)


@require_http_methods(['PUT', 'PATCH'])
def listing_update(request, listing_id):
	return _update_listing(request, listing_id)


@require_http_methods(['DELETE'])
def listing_delete(request, listing_id):
	if not request.user.is_authenticated:
		return JsonResponse({'error': 'Authentication required.'}, status=401)

	listing = get_object_or_404(ItemListing, pk=listing_id, user=request.user)
	listing.delete()
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

	data, error_response = _payload(request)
	if error_response:
		return error_response

	for field, value in data.items():
		setattr(listing, field, value)

	errors = _validation_errors(listing)
	if errors:
		return JsonResponse({'errors': errors}, status=400)

	listing.save()
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
	# Validasi ekstensi
	allowed_extensions = ('.jpg', '.jpeg', '.png', '.webp', '.gif')
	if not uploaded_file.name.lower().endswith(allowed_extensions):
		return JsonResponse({'error': 'Format file harus berupa gambar (JPG, PNG, WEBP, GIF).'}, status=400)

	listing.image = uploaded_file
	listing.save()

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
	Mengambil riwayat chat atau mengirim pesan baru terkait barang.
	Ketika pesan terkirim, otomatis mengirimkan notifikasi ke penerima.
	"""
	if not request.user.is_authenticated:
		return JsonResponse({'error': 'Silakan login untuk menggunakan fitur chat.'}, status=401)

	item = get_object_or_404(ItemListing, pk=listing_id)

	if request.method == 'GET':
		# Tampilkan riwayat chat yang melibatkan user saat ini
		chats = ItemChatMessage.objects.filter(
			item=item
		).filter(
			Q(sender=request.user) | Q(recipient=request.user)
		).select_related('sender', 'recipient').order_by('created_at')

		data = [
			{
				'id': str(c.id),
				'sender': c.sender.username,
				'is_me': c.sender == request.user,
				'message': c.message,
				'created_at': c.created_at.strftime('%H:%M, %d %b'),
			}
			for c in chats
		]
		return JsonResponse({'success': True, 'chats': data})

	# POST: Kirim pesan
	try:
		body = json.loads(request.body) if request.body else {}
		message_text = request.POST.get('message') or body.get('message', '')
	except json.JSONDecodeError:
		message_text = request.POST.get('message', '')

	message_text = message_text.strip()
	if not message_text:
		return JsonResponse({'error': 'Pesan tidak boleh kosong.'}, status=400)

	# Tentukan penerima: jika yang kirim pembeli -> penerimanya penjual; jika penjual -> kirim ke pembeli
	recipient = item.user if request.user != item.user else (
		# Jika penjual mengirim pesan balasan, cari user pembeli yang sedang bertransaksi / chat terakhir
		item.orders.exclude(buyer=request.user).values_list('buyer', flat=True).first() or
		item.offers.exclude(buyer=request.user).values_list('buyer', flat=True).first()
	)
	if not recipient:
		return JsonResponse({'error': 'Belum ada calon pembeli yang memulai percakapan.'}, status=400)

	if isinstance(recipient, int):
		from django.contrib.auth.models import User
		recipient = User.objects.get(pk=recipient)

	chat = ItemChatMessage.objects.create(
		item=item,
		sender=request.user,
		recipient=recipient,
		message=message_text
	)

	# Buat Notifikasi ke Penerima Pesan
	UserNotification.objects.create(
		user=recipient,
		title=f'Pesan baru dari @{request.user.username}',
		message=f'@{request.user.username} mengirim pesan tentang "{item.title}": "{message_text[:60]}"',
		notification_type=UserNotification.NotifType.CHAT,
		link=f'/saling-beli/detail/{item.id}/'
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
		}
	})


@require_http_methods(['GET'])
def user_notifications(request):
	"""
	Endpoint untuk mengecek notifikasi user secara berkala (polling / badge).
	"""
	if not request.user.is_authenticated:
		return JsonResponse({'notifications': [], 'unread_count': 0})

	notifs = UserNotification.objects.filter(user=request.user)[:10]
	unread_count = UserNotification.objects.filter(user=request.user, is_read=False).count()

	data = [
		{
			'id': str(n.id),
			'title': n.title,
			'message': n.message,
			'type': n.notification_type,
			'link': n.link or '#',
			'is_read': n.is_read,
			'created_at': n.created_at.strftime('%H:%M, %d %b'),
		}
		for n in notifs
	]

	return JsonResponse({'success': True, 'unread_count': unread_count, 'notifications': data})


@require_http_methods(['POST'])
def mark_notifications_read(request):
	"""
	Menandai semua notifikasi user sebagai terbaca.
	"""
	if not request.user.is_authenticated:
		return JsonResponse({'error': 'Authentication required.'}, status=401)

	UserNotification.objects.filter(user=request.user, is_read=False).update(is_read=True)
	return JsonResponse({'success': True, 'message': 'Semua notifikasi ditandai sebagai terbaca.'})
