import datetime
import json

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from .models import ItemListing

EDITABLE_FIELDS = {
	'title',
	'description',
	'category',
	'condition',
	'is_free',
	'price',
	'image_url',
	'pickup_location',
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

	context = {
		'items': items,
		'query': query,
		'session_views': session_views,
		'last_visit_cookie': last_visit_cookie,
		'last_login_cookie': last_login_cookie,
	}

	response = render(request, 'saling-beli.html', context)

	# Set cookie kunjungan terakhir untuk tracking user preference
	now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
	response.set_cookie('saling_beli_last_visit', now_str, max_age=60 * 60 * 24 * 7)

	return response


def item_detail(request, listing_id):
	"""
	Halaman detail barang prelove (HTML).
	Menyimpan riwayat barang yang baru dilihat ke dalam Session user.
	"""
	item = get_object_or_404(ItemListing, pk=listing_id)

	# Session: Tambahkan item ke daftar 'recently_viewed'
	recently_viewed = request.session.get('recently_viewed_items', [])
	item_id_str = str(item.id)
	if item_id_str in recently_viewed:
		recently_viewed.remove(item_id_str)
	recently_viewed.insert(0, item_id_str)
	request.session['recently_viewed_items'] = recently_viewed[:5]

	context = {
		'item': item,
	}
	return render(request, 'saling-beli-detail.html', context)


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
