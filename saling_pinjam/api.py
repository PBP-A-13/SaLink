"""
Web service (Django REST Framework) modul Saling Pinjam, dipakai aplikasi Flutter.

Bentuk balasan semua endpoint sama, supaya aplikasi cukup memeriksa field `status`:

    berhasil: {"status": "success", "message": "...", "data": ...}
    gagal   : {"status": "error", "message": "...", "errors": {"nama_field": ["..."]}}

`errors` hanya ada kalau isian form-nya yang salah. Kode HTTP-nya juga tetap benar
(201, 400, 403, 404, 409), tapi pbp_django_auth di sisi Flutter cuma mengembalikan body,
jadi `status` di body-lah yang dibaca aplikasi.

Semua perubahan data memakai POST dengan body JSON. CookieRequest di Flutter
memang hanya punya GET dan POST, jadi tidak ada PUT/DELETE.

Aturan bisnisnya (maksimal 2 pinjaman aktif, alur status, bentrok jadwal) sama dengan
views.py yang melayani situs web. Konstantanya diambil dari sana.
"""

from datetime import date

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status as http
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import NotAuthenticated, PermissionDenied
from rest_framework.parsers import JSONParser
from rest_framework.permissions import SAFE_METHODS, AllowAny, IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from .forms import BOOKED_STATUSES, conflicting_bookings
from .models import BorrowItem, BorrowRequest
from .serializers import (
    BorrowItemSerializer,
    BorrowRequestCreateSerializer,
    BorrowRequestSerializer,
    StatusUpdateSerializer,
)
from .views import ACTIVE_STATUSES, ALLOWED_TRANSITIONS, MAX_ACTIVE_BORROWS, parse_date


# ---------------------------------------------------------------------------
# Dasar bersama semua endpoint
# ---------------------------------------------------------------------------

def sukses(data=None, message='', code=http.HTTP_200_OK):
    return Response({'status': 'success', 'message': message, 'data': data}, status=code)


def gagal(message, code=http.HTTP_400_BAD_REQUEST, errors=None):
    body = {'status': 'error', 'message': message}
    if errors:
        body['errors'] = errors
    return Response(body, status=code)


def gagal_validasi(serializer, message=None):
    """Ubah error serializer jadi balasan gagal: satu pesan ringkas + rincian per field."""
    errors = serializer.errors
    form_wide = errors.get('non_field_errors')
    if message is None:
        message = str(form_wide[0]) if form_wide else 'Isian belum benar. Cek bagian yang ditandai.'
    return gagal(message, http.HTTP_400_BAD_REQUEST, errors)


class SessionTanpaCSRF(SessionAuthentication):
    """
    Login lewat cookie session seperti situs web, tapi tanpa token CSRF.

    pbp_django_auth di Flutter cuma menyimpan cookie `sessionid` dan tidak mengirim
    header X-CSRFToken, jadi pengecekan CSRF bawaan DRF akan menolak semua POST dari aplikasi.
    Sebagai gantinya, request yang mengubah data wajib bertipe application/json.
    Browser tidak bisa mengirim tipe itu dari situs lain tanpa izin CORS (yang tidak kita buka),
    jadi form jebakan dari situs lain tetap tidak bisa menembus endpoint ini.
    """

    def enforce_csrf(self, request):
        if request.method in SAFE_METHODS:
            return
        if not request.content_type.startswith('application/json'):
            raise PermissionDenied('Request harus berformat JSON.')


class JSONUtf8Renderer(JSONRenderer):
    """
    JSONRenderer biasa, tapi header Content-Type-nya menyebut charset=utf-8.
    Tanpa itu, package http di Flutter membaca body sebagai Latin-1, sehingga
    huruf non-ASCII (é, emoji) di nama atau catatan barang tampil rusak.
    """

    charset = 'utf-8'


class PinjamAPIView(APIView):
    """Dasar semua endpoint modul ini: auth session, body JSON saja, dan format error yang seragam."""

    authentication_classes = [SessionTanpaCSRF]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]
    renderer_classes = [JSONUtf8Renderer]

    def handle_exception(self, exc):
        # Pesan "belum login" dari DRF berbahasa Inggris, jadi diganti.
        if isinstance(exc, NotAuthenticated):
            exc = NotAuthenticated('Silakan login dulu.')
        # Error bawaan DRF (belum login, method salah, JSON rusak) berbentuk {"detail": "..."}.
        # Dibungkus ulang supaya sama dengan balasan gagal yang lain.
        response = super().handle_exception(exc)
        if isinstance(response.data, dict) and 'detail' in response.data:
            response.data = {'status': 'error', 'message': str(response.data['detail'])}
        return response

    def serializer_context(self):
        return {'request': self.request}


def cari_barang(id):
    return BorrowItem.objects.select_related('owner').filter(id=id).first()


# ---------------------------------------------------------------------------
# Barang
# ---------------------------------------------------------------------------

class ItemListCreateView(PinjamAPIView):
    """
    GET  /saling-pinjam/api/items/   daftar barang, terbuka untuk tamu.
         Filter opsional: ?category=ACADEMIC  ?q=kata  ?tanggal=2026-11-20
         (tanggal = hanya barang yang bebas dipinjam di tanggal itu, tanpa barang milik sendiri)
    POST /saling-pinjam/api/items/   tambah barang baru, wajib login.
    """

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [AllowAny()]
        return super().get_permissions()

    def get(self, request):
        items = BorrowItem.objects.select_related('owner')

        category = request.query_params.get('category', '')
        query = request.query_params.get('q', '').strip()
        if category:
            items = items.filter(category=category)
        if query:
            items = items.filter(
                Q(name__icontains=query)
                | Q(description__icontains=query)
                | Q(pickup_location__icontains=query)
            )

        raw_date = request.query_params.get('tanggal')
        if raw_date:
            tanggal = parse_date(raw_date)
            if tanggal is None:
                return gagal('Format tanggal tidak valid. Pakai YYYY-MM-DD.')
            booked = BorrowRequest.objects.filter(
                status__in=BOOKED_STATUSES, start_date__lte=tanggal, end_date__gte=tanggal
            ).values('item_id')
            items = items.exclude(status=BorrowItem.Status.UNAVAILABLE).exclude(id__in=booked)
            if request.user.is_authenticated:
                items = items.exclude(owner=request.user)

        data = BorrowItemSerializer(items, many=True, context=self.serializer_context()).data
        return sukses(data)

    def post(self, request):
        serializer = BorrowItemSerializer(data=request.data, context=self.serializer_context())
        if not serializer.is_valid():
            return gagal_validasi(serializer)
        item = serializer.save(owner=request.user)
        return sukses(
            BorrowItemSerializer(item, context=self.serializer_context()).data,
            f'Barang "{item.name}" berhasil didaftarkan untuk dipinjamkan!',
            http.HTTP_201_CREATED,
        )


class ItemDetailView(PinjamAPIView):
    """
    GET /saling-pinjam/api/items/<id>/   detail barang, terbuka untuk tamu.

    Selain data barang, ada tambahan:
      booked_ranges      tanggal yang sudah terkunci (disetujui/berlangsung), untuk memilih tanggal di form
      my_active_request  pengajuan aktif milik user yang login untuk barang ini (atau null)
      locked_count, pending_count   hanya untuk pemilik, dipakai pada keterangan hapus barang
    """

    permission_classes = [AllowAny]

    def get(self, request, id):
        item = cari_barang(id)
        if item is None:
            return gagal('Barang tidak ditemukan.', http.HTTP_404_NOT_FOUND)

        context = self.serializer_context()
        data = dict(BorrowItemSerializer(item, context=context).data)

        booked = item.requests.filter(
            status__in=BOOKED_STATUSES, end_date__gte=date.today()
        ).order_by('start_date')
        data['booked_ranges'] = [
            {'start_date': req.start_date.isoformat(), 'end_date': req.end_date.isoformat()}
            for req in booked
        ]

        data['my_active_request'] = None
        if request.user.is_authenticated and item.owner_id != request.user.id:
            mine = (
                item.requests.filter(borrower=request.user, status__in=ACTIVE_STATUSES)
                .select_related('item', 'item__owner', 'borrower')
                .first()
            )
            if mine:
                data['my_active_request'] = BorrowRequestSerializer(mine).data

        if request.user.is_authenticated and item.owner_id == request.user.id:
            data['locked_count'] = item.requests.filter(status__in=BOOKED_STATUSES).count()
            data['pending_count'] = item.requests.filter(status=BorrowRequest.Status.PENDING).count()

        return sukses(data)


class ItemUpdateView(PinjamAPIView):
    """
    POST /saling-pinjam/api/items/<id>/update/   ubah data barang, hanya pemilik.
    Boleh mengirim sebagian field saja, field lain tetap seperti sebelumnya.
    """

    def post(self, request, id):
        item = cari_barang(id)
        if item is None:
            return gagal('Barang tidak ditemukan.', http.HTTP_404_NOT_FOUND)
        if item.owner_id != request.user.id:
            return gagal('Hanya pemilik yang bisa mengubah barang ini.', http.HTTP_403_FORBIDDEN)

        serializer = BorrowItemSerializer(
            item, data=request.data, partial=True, context=self.serializer_context()
        )
        if not serializer.is_valid():
            return gagal_validasi(serializer)
        item = serializer.save()
        return sukses(
            BorrowItemSerializer(item, context=self.serializer_context()).data,
            f'Perubahan pada "{item.name}" sudah disimpan.',
        )


class ItemDeleteView(PinjamAPIView):
    """
    POST /saling-pinjam/api/items/<id>/delete/   hapus barang, hanya pemilik.
    Ditolak kalau barangnya sedang dipinjam atau sudah disetujui untuk dipinjam.
    """

    def post(self, request, id):
        item = cari_barang(id)
        if item is None:
            return gagal('Barang tidak ditemukan.', http.HTTP_404_NOT_FOUND)
        if item.owner_id != request.user.id:
            return gagal('Hanya pemilik yang bisa menghapus barang ini.', http.HTTP_403_FORBIDDEN)

        if item.requests.filter(status__in=BOOKED_STATUSES).exists():
            return gagal(
                f'"{item.name}" belum bisa dihapus karena sedang dipinjam atau sudah disetujui '
                'untuk dipinjam. Selesaikan pinjamannya dulu.',
                http.HTTP_409_CONFLICT,
            )

        name = item.name
        item.delete()  # pengajuan yang masih menunggu ikut terhapus (on_delete=CASCADE)
        return sukses(None, f'Barang "{name}" sudah dihapus.')


# ---------------------------------------------------------------------------
# Pengajuan pinjam
# ---------------------------------------------------------------------------

class BorrowCreateView(PinjamAPIView):
    """
    POST /saling-pinjam/api/items/<id>/request/   ajukan pinjam, wajib login.
    Body: {"start_date": "2026-11-20", "end_date": "2026-11-22", "notes": "..."}
    """

    def post(self, request, id):
        item = cari_barang(id)
        if item is None:
            return gagal('Barang tidak ditemukan.', http.HTTP_404_NOT_FOUND)

        if item.owner_id == request.user.id:
            return gagal('Anda tidak bisa meminjam barang milik Anda sendiri.', http.HTTP_403_FORBIDDEN)

        if item.status == BorrowItem.Status.UNAVAILABLE:
            return gagal('Maaf, barang ini sedang tidak tersedia untuk dipinjam.', http.HTTP_409_CONFLICT)

        my_active = BorrowRequest.objects.filter(borrower=request.user, status__in=ACTIVE_STATUSES)

        if my_active.filter(item=item).exists():
            return gagal(f'Kamu sudah punya pengajuan aktif untuk "{item.name}".', http.HTTP_409_CONFLICT)

        if my_active.count() >= MAX_ACTIVE_BORROWS:
            return gagal(
                f'Slot pinjaman kamu penuh ({MAX_ACTIVE_BORROWS} barang). '
                'Selesaikan atau batalkan salah satu dulu.',
                http.HTTP_409_CONFLICT,
            )

        serializer = BorrowRequestCreateSerializer(data=request.data, context={'item': item})
        if not serializer.is_valid():
            return gagal_validasi(serializer)

        borrow_req = serializer.save(item=item, borrower=request.user)
        return sukses(
            BorrowRequestSerializer(borrow_req).data,
            f'Pengajuan peminjaman "{item.name}" berhasil dikirim! Menunggu konfirmasi pemilik.',
            http.HTTP_201_CREATED,
        )


class MyBorrowsView(PinjamAPIView):
    """
    GET /saling-pinjam/api/my-borrows/   isi halaman "Pinjaman Saya", wajib login.

    data:
      as_borrower   pengajuan yang aku buat
      as_owner      pengajuan yang masuk ke barang milikku
      my_items      barang milikku
      active_count, max_active   pemakaian slot pinjaman aktif
    """

    def get(self, request):
        as_borrower = BorrowRequest.objects.filter(borrower=request.user).select_related(
            'item', 'item__owner', 'borrower'
        )
        as_owner = BorrowRequest.objects.filter(item__owner=request.user).select_related(
            'item', 'item__owner', 'borrower'
        )
        my_items = BorrowItem.objects.filter(owner=request.user).select_related('owner')

        return sukses({
            'as_borrower': BorrowRequestSerializer(as_borrower, many=True).data,
            'as_owner': BorrowRequestSerializer(as_owner, many=True).data,
            'my_items': BorrowItemSerializer(
                my_items, many=True, context=self.serializer_context()
            ).data,
            'active_count': as_borrower.filter(status__in=ACTIVE_STATUSES).count(),
            'max_active': MAX_ACTIVE_BORROWS,
        })


class CancelRequestView(PinjamAPIView):
    """
    POST /saling-pinjam/api/requests/<id>/cancel/   peminjam membatalkan pengajuannya sendiri,
    selama statusnya masih Menunggu atau Disetujui.
    """

    def post(self, request, request_id):
        borrow_req = (
            BorrowRequest.objects.select_related('item', 'item__owner', 'borrower')
            .filter(id=request_id, borrower=request.user)
            .first()
        )
        if borrow_req is None:
            return gagal('Pengajuan tidak ditemukan.', http.HTTP_404_NOT_FOUND)

        if borrow_req.status not in (BorrowRequest.Status.PENDING, BorrowRequest.Status.APPROVED):
            return gagal('Pengajuan ini sudah tidak bisa dibatalkan.', http.HTTP_409_CONFLICT)

        borrow_req.status = BorrowRequest.Status.CANCELLED
        borrow_req.save()
        return sukses(
            BorrowRequestSerializer(borrow_req).data,
            f'Pengajuan "{borrow_req.item.name}" dibatalkan.',
        )


class UpdateRequestStatusView(PinjamAPIView):
    """
    POST /saling-pinjam/api/requests/<id>/status/   pemilik barang mengubah status pengajuan.
    Body: {"status": "APPROVED"}  (APPROVED, REJECTED, ONGOING, atau RETURNED)

    Alur yang diizinkan: Menunggu -> Disetujui/Ditolak, Disetujui -> Berlangsung,
    Berlangsung -> Dikembalikan. Kalau disetujui, pengajuan lain yang masih menunggu
    di tanggal bentrok otomatis ditolak.
    """

    def post(self, request, request_id):
        serializer = StatusUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return gagal_validasi(serializer, 'Status tidak valid.')
        new_status = serializer.validated_data['status']

        with transaction.atomic():
            borrow_req = (
                BorrowRequest.objects.select_for_update()
                .select_related('item', 'item__owner', 'borrower')
                .filter(id=request_id, item__owner=request.user)
                .first()
            )
            if borrow_req is None:
                return gagal('Pengajuan tidak ditemukan.', http.HTTP_404_NOT_FOUND)
            item = borrow_req.item

            if new_status not in ALLOWED_TRANSITIONS.get(borrow_req.status, []):
                return gagal('Status tidak valid.', http.HTTP_409_CONFLICT)

            if new_status == BorrowRequest.Status.APPROVED:
                if conflicting_bookings(
                    item, borrow_req.start_date, borrow_req.end_date, exclude_id=borrow_req.id
                ).exists():
                    return gagal(
                        'Tidak bisa disetujui: tanggalnya bentrok dengan pinjaman lain yang sudah disetujui.',
                        http.HTTP_409_CONFLICT,
                    )
                if item.status == BorrowItem.Status.UNAVAILABLE:
                    return gagal(
                        'Barang sedang dinonaktifkan pemilik sehingga tidak bisa disetujui.',
                        http.HTTP_409_CONFLICT,
                    )

            borrow_req.status = new_status
            borrow_req.save()

            auto_rejected = 0
            if new_status == BorrowRequest.Status.APPROVED:
                # Pengajuan lain di tanggal yang bentrok otomatis ditolak, supaya slot peminjamnya kosong lagi
                auto_rejected = (
                    BorrowRequest.objects.filter(
                        item=item,
                        status=BorrowRequest.Status.PENDING,
                        start_date__lte=borrow_req.end_date,
                        end_date__gte=borrow_req.start_date,
                    )
                    .exclude(id=borrow_req.id)
                    .update(status=BorrowRequest.Status.REJECTED, updated_at=timezone.now())
                )
            elif new_status == BorrowRequest.Status.ONGOING:
                # Status barang baru berubah saat benar-benar diambil, bukan saat disetujui
                item.status = BorrowItem.Status.BORROWED
                item.save()
            elif new_status == BorrowRequest.Status.RETURNED:
                item.status = BorrowItem.Status.AVAILABLE
                item.save()

        message = f'Status pengajuan diperbarui menjadi "{borrow_req.get_status_display()}".'
        if auto_rejected:
            message += f' {auto_rejected} pengajuan lain di tanggal yang sama otomatis ditolak.'
        return sukses(
            {'request': BorrowRequestSerializer(borrow_req).data, 'auto_rejected': auto_rejected},
            message,
        )