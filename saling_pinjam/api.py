"""
Web service (Django REST Framework) modul Saling Pinjam untuk aplikasi Flutter.
Mendukung autentikasi Session dan Token DRF.
Mendukung mekanisme konfirmasi serah-terima dua arah (Two-Way Handover & Return Confirmation).
"""

from datetime import date

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status as http
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
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
# Helper Response
# ---------------------------------------------------------------------------

def sukses(data=None, message='', code=http.HTTP_200_OK):
    return Response({'status': 'success', 'message': message, 'data': data}, status=code)


def gagal(message, code=http.HTTP_400_BAD_REQUEST, errors=None):
    body = {'status': 'error', 'message': message}
    if errors:
        body['errors'] = errors
    return Response(body, status=code)


def gagal_validasi(serializer, message=None):
    errors = serializer.errors
    form_wide = errors.get('non_field_errors')
    if message is None:
        message = str(form_wide[0]) if form_wide else 'Isian belum benar. Cek bagian yang ditandai.'
    return gagal(message, http.HTTP_400_BAD_REQUEST, errors)


class SessionTanpaCSRF(SessionAuthentication):
    def enforce_csrf(self, request):
        if request.method in SAFE_METHODS:
            return
        if not (request.content_type and request.content_type.startswith('application/json')):
            raise PermissionDenied('Request harus berformat JSON.')


class JSONUtf8Renderer(JSONRenderer):
    charset = 'utf-8'


class PinjamAPIView(APIView):
    authentication_classes = [TokenAuthentication, SessionTanpaCSRF]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]
    renderer_classes = [JSONUtf8Renderer]

    def handle_exception(self, exc):
        if isinstance(exc, NotAuthenticated):
            exc = NotAuthenticated('Silakan login dulu.')
        response = super().handle_exception(exc)
        if isinstance(response.data, dict) and 'detail' in response.data:
            response.data = {'status': 'error', 'message': str(response.data['detail'])}
        return response

    def serializer_context(self):
        return {'request': self.request}


def cari_barang(id):
    return BorrowItem.objects.select_related('owner').filter(id=id).first()


# ---------------------------------------------------------------------------
# Endpoint Barang (Katalog, Tambah, Detail, Edit, Hapus)
# ---------------------------------------------------------------------------

class ItemListCreateView(PinjamAPIView):
    """
    GET  /saling-pinjam/api/items/       daftar barang (bisa filter ?q= & ?category=)
    POST /saling-pinjam/api/items/       tambah barang baru
    """

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [AllowAny()]
        return [IsAuthenticated()]

    def get(self, request):
        qs = BorrowItem.objects.select_related('owner').all()
        q = request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))

        category = request.GET.get('category', '').strip()
        if category:
            qs = qs.filter(category=category)

        data = BorrowItemSerializer(qs, many=True, context=self.serializer_context()).data
        return sukses(data)

    def post(self, request):
        serializer = BorrowItemSerializer(data=request.data, context=self.serializer_context())
        if not serializer.is_valid():
            return gagal_validasi(serializer)
        item = serializer.save(owner=request.user)
        return sukses(
            BorrowItemSerializer(item, context=self.serializer_context()).data,
            f'Barang "{item.name}" berhasil ditambahkan.',
            code=http.HTTP_201_CREATED,
        )


class ItemDetailView(PinjamAPIView):
    """GET /saling-pinjam/api/items/<id>/ detail satu barang."""

    permission_classes = [AllowAny]

    def get(self, request, id):
        item = cari_barang(id)
        if item is None:
            return gagal('Barang tidak ditemukan.', http.HTTP_404_NOT_FOUND)
        return sukses(BorrowItemSerializer(item, context=self.serializer_context()).data)


class ItemUpdateView(PinjamAPIView):
    """POST /saling-pinjam/api/items/<id>/update/ edit barang milik sendiri."""

    def post(self, request, id):
        item = cari_barang(id)
        if item is None:
            return gagal('Barang tidak ditemukan.', http.HTTP_404_NOT_FOUND)
        if item.owner != request.user:
            return gagal('Kamu bukan pemilik barang ini.', http.HTTP_403_FORBIDDEN)

        serializer = BorrowItemSerializer(
            item, data=request.data, partial=True, context=self.serializer_context()
        )
        if not serializer.is_valid():
            return gagal_validasi(serializer)
        item = serializer.save()
        return sukses(
            BorrowItemSerializer(item, context=self.serializer_context()).data,
            f'Perubahan barang "{item.name}" disimpan.',
        )


class ItemDeleteView(PinjamAPIView):
    """POST /saling-pinjam/api/items/<id>/delete/ hapus barang milik sendiri."""

    def post(self, request, id):
        item = cari_barang(id)
        if item is None:
            return gagal('Barang tidak ditemukan.', http.HTTP_404_NOT_FOUND)
        if item.owner != request.user:
            return gagal('Kamu bukan pemilik barang ini.', http.HTTP_403_FORBIDDEN)

        nama = item.name
        item.delete()
        return sukses(message=f'Barang "{nama}" berhasil dihapus.')


# ---------------------------------------------------------------------------
# Endpoint Pengajuan & Riwayat Pinjam
# ---------------------------------------------------------------------------

class BorrowCreateView(PinjamAPIView):
    """POST /saling-pinjam/api/items/<id>/request/ ajukan pinjam barang."""

    def post(self, request, id):
        item = cari_barang(id)
        if item is None:
            return gagal('Barang tidak ditemukan.', http.HTTP_404_NOT_FOUND)
        if item.owner == request.user:
            return gagal('Tidak bisa meminjam barang milik sendiri.')
        if item.status != BorrowItem.Status.AVAILABLE:
            return gagal('Barang sedang tidak tersedia untuk dipinjam.')

        active_count = BorrowRequest.objects.filter(
            borrower=request.user, status__in=ACTIVE_STATUSES
        ).count()
        if active_count >= MAX_ACTIVE_BORROWS:
            return gagal(
                f'Kamu masih punya {active_count} pinjaman yang belum selesai. '
                f'Maksimal {MAX_ACTIVE_BORROWS} pinjaman sekaligus.',
                http.HTTP_409_CONFLICT,
            )

        serializer = BorrowRequestCreateSerializer(data=request.data, context={'item': item})
        if not serializer.is_valid():
            return gagal_validasi(serializer)

        borrow_req = serializer.save(item=item, borrower=request.user)
        return sukses(
            BorrowRequestSerializer(borrow_req, context=self.serializer_context()).data,
            f'Pengajuan pinjam "{item.name}" terkirim ke {item.owner.username}.',
            code=http.HTTP_201_CREATED,
        )


class MyBorrowsView(PinjamAPIView):
    """GET /saling-pinjam/api/my-borrows/ semua pinjaman & pengajuan user."""

    def get(self, request):
        user = request.user
        as_borrower = (
            BorrowRequest.objects.select_related('item', 'item__owner')
            .filter(borrower=user)
            .order_by('-created_at')
        )
        as_owner = (
            BorrowRequest.objects.select_related('item', 'borrower')
            .filter(item__owner=user)
            .order_by('-created_at')
        )
        my_items = BorrowItem.objects.filter(owner=user).order_by('-created_at')

        return sukses({
            'as_borrower': BorrowRequestSerializer(
                as_borrower, many=True, context=self.serializer_context()
            ).data,
            'as_owner': BorrowRequestSerializer(
                as_owner, many=True, context=self.serializer_context()
            ).data,
            'my_items': BorrowItemSerializer(
                my_items, many=True, context=self.serializer_context()
            ).data,
            'active_count': as_borrower.filter(status__in=ACTIVE_STATUSES).count(),
            'max_active': MAX_ACTIVE_BORROWS,
        })


class CancelRequestView(PinjamAPIView):
    """POST /saling-pinjam/api/requests/<id>/cancel/ peminjam membatalkan pengajuan."""

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
            BorrowRequestSerializer(borrow_req, context=self.serializer_context()).data,
            f'Pengajuan "{borrow_req.item.name}" dibatalkan.',
        )


class UpdateRequestStatusView(PinjamAPIView):
    """
    POST /saling-pinjam/api/requests/<id>/status/
    Persetujuan awal pemilik: APPROVED atau REJECTED.
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
                return gagal('Transisi status tidak valid.', http.HTTP_409_CONFLICT)

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

        message = f'Status pengajuan diperbarui menjadi "{borrow_req.get_status_display()}".'
        if auto_rejected:
            message += f' {auto_rejected} pengajuan lain di tanggal yang sama otomatis ditolak.'
        return sukses(
            {
                'request': BorrowRequestSerializer(
                    borrow_req, context=self.serializer_context()
                ).data,
                'auto_rejected': auto_rejected,
            },
            message,
        )


# ---------------------------------------------------------------------------
# Endpoint Konfirmasi Serah-Terima Dua Arah (Two-Way Handover & Return)
# ---------------------------------------------------------------------------

class ConfirmHandoverView(PinjamAPIView):
    """
    POST /saling-pinjam/api/requests/<id>/confirm-handover/
    Kedua belah pihak mengonfirmasi penyerahan barang di awal peminjaman.
    Saat kedua pihak telah konfirmasi: status pengajuan berubah jadi ONGOING,
    dan status barang berubah jadi BORROWED.
    """

    def post(self, request, request_id):
        with transaction.atomic():
            borrow_req = (
                BorrowRequest.objects.select_for_update()
                .select_related('item', 'item__owner', 'borrower')
                .filter(id=request_id)
                .first()
            )
            if not borrow_req:
                return gagal('Pengajuan tidak ditemukan.', http.HTTP_404_NOT_FOUND)

            if request.user != borrow_req.item.owner and request.user != borrow_req.borrower:
                return gagal('Kamu bukan pihak dalam peminjaman ini.', http.HTTP_403_FORBIDDEN)

            if borrow_req.status != BorrowRequest.Status.APPROVED:
                return gagal('Pengajuan belum disetujui atau sudah tidak dalam tahap serah-terima.', http.HTTP_409_CONFLICT)

            if request.user == borrow_req.item.owner:
                borrow_req.owner_handover_confirmed = True
            elif request.user == borrow_req.borrower:
                borrow_req.borrower_handover_confirmed = True

            msg = 'Konfirmasi serah-terima Anda berhasil dicatat.'
            # Cek apakah kedua pihak telah konfirmasi
            if borrow_req.handover_ready:
                borrow_req.status = BorrowRequest.Status.ONGOING
                borrow_req.item.status = BorrowItem.Status.BORROWED
                borrow_req.item.save()
                msg = 'Kedua pihak telah mengonfirmasi! Barang resmi sedang dipinjam (Berlangsung).'
            else:
                pihak_lain = 'peminjam' if request.user == borrow_req.item.owner else 'pemilik'
                msg += f' Menunggu konfirmasi dari {pihak_lain}.'

            borrow_req.save()

        return sukses(
            BorrowRequestSerializer(borrow_req, context=self.serializer_context()).data,
            msg,
        )


class ConfirmReturnView(PinjamAPIView):
    """
    POST /saling-pinjam/api/requests/<id>/confirm-return/
    Kedua belah pihak mengonfirmasi pengembalian barang di akhir peminjaman.
    Saat kedua pihak telah konfirmasi: status pengajuan berubah jadi RETURNED,
    dan status barang kembali jadi AVAILABLE.
    """

    def post(self, request, request_id):
        with transaction.atomic():
            borrow_req = (
                BorrowRequest.objects.select_for_update()
                .select_related('item', 'item__owner', 'borrower')
                .filter(id=request_id)
                .first()
            )
            if not borrow_req:
                return gagal('Pengajuan tidak ditemukan.', http.HTTP_404_NOT_FOUND)

            if request.user != borrow_req.item.owner and request.user != borrow_req.borrower:
                return gagal('Kamu bukan pihak dalam peminjaman ini.', http.HTTP_403_FORBIDDEN)

            if borrow_req.status != BorrowRequest.Status.ONGOING:
                return gagal('Pinjaman tidak sedang berlangsung.', http.HTTP_409_CONFLICT)

            if request.user == borrow_req.borrower:
                borrow_req.borrower_return_confirmed = True
            elif request.user == borrow_req.item.owner:
                borrow_req.owner_return_confirmed = True

            msg = 'Konfirmasi pengembalian Anda berhasil dicatat.'
            if borrow_req.return_ready:
                borrow_req.status = BorrowRequest.Status.RETURNED
                borrow_req.actual_return_date = timezone.now().date()
                borrow_req.item.status = BorrowItem.Status.AVAILABLE
                borrow_req.item.save()
                msg = 'Kedua pihak telah mengonfirmasi! Barang resmi selesai dikembalikan.'
            else:
                pihak_lain = 'pemilik' if request.user == borrow_req.borrower else 'peminjam'
                msg += f' Menunggu konfirmasi pengembalian dari {pihak_lain}.'

            borrow_req.save()

        return sukses(
            BorrowRequestSerializer(borrow_req, context=self.serializer_context()).data,
            msg,
        )
