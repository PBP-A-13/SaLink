"""
Serializer modul Saling Pinjam untuk web service DRF.
"""

from datetime import date
from rest_framework import serializers

from .forms import conflicting_bookings
from .models import BorrowItem, BorrowRequest
from .views import ALLOWED_TRANSITIONS

WAJIB = {
    'required': 'Bagian ini wajib diisi.',
    'blank': 'Bagian ini wajib diisi.',
    'null': 'Bagian ini wajib diisi.',
}

MAKS_JAMINAN = 999_999_999_999


class BorrowItemSerializer(serializers.ModelSerializer):
    owner = serializers.CharField(source='owner.username', read_only=True)
    is_owner = serializers.SerializerMethodField()
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    condition_display = serializers.CharField(source='get_condition_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    max_duration_days = serializers.IntegerField(
        min_value=1,
        error_messages={**WAJIB, 'invalid': 'Isi dengan angka.', 'min_value': 'Minimal 1 hari.'},
    )
    deposit_fee = serializers.IntegerField(
        min_value=0,
        max_value=MAKS_JAMINAN,
        required=False,
        default=0,
        error_messages={
            **WAJIB,
            'invalid': 'Isi dengan angka.',
            'min_value': 'Uang jaminan tidak boleh minus.',
            'max_value': 'Nominalnya terlalu besar.',
        },
    )
    image_url = serializers.URLField(
        max_length=500,
        required=False,
        allow_blank=True,
        allow_null=True,
        error_messages={'invalid': 'Link tidak valid. Pastikan diawali https://'},
    )

    class Meta:
        model = BorrowItem
        fields = [
            'id',
            'name',
            'description',
            'category',
            'category_display',
            'condition',
            'condition_display',
            'max_duration_days',
            'deposit_fee',
            'pickup_location',
            'image_url',
            'status',
            'status_display',
            'owner',
            'is_owner',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'status', 'created_at', 'updated_at']
        extra_kwargs = {
            'name': {'error_messages': {**WAJIB, 'max_length': 'Maksimal 200 karakter.'}},
            'description': {'error_messages': WAJIB},
            'pickup_location': {'error_messages': {**WAJIB, 'max_length': 'Maksimal 255 karakter.'}},
            'category': {'error_messages': {**WAJIB, 'invalid_choice': 'Pilihan kategori tidak valid.'}},
            'condition': {'error_messages': {**WAJIB, 'invalid_choice': 'Pilihan kondisi tidak valid.'}},
        }

    def get_is_owner(self, obj):
        request = self.context.get('request')
        return bool(request and request.user.is_authenticated and obj.owner_id == request.user.id)


class BorrowItemRingkasSerializer(serializers.ModelSerializer):
    owner = serializers.CharField(source='owner.username', read_only=True)

    class Meta:
        model = BorrowItem
        fields = ['id', 'name', 'image_url', 'pickup_location', 'category', 'status', 'owner']


class BorrowRequestSerializer(serializers.ModelSerializer):
    item = BorrowItemRingkasSerializer(read_only=True)
    borrower = serializers.CharField(source='borrower.username', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    next_statuses = serializers.SerializerMethodField()
    can_cancel = serializers.SerializerMethodField()

    can_confirm_handover = serializers.SerializerMethodField()
    can_confirm_return = serializers.SerializerMethodField()
    handover_status_display = serializers.SerializerMethodField()
    return_status_display = serializers.SerializerMethodField()

    class Meta:
        model = BorrowRequest
        fields = [
            'id',
            'item',
            'borrower',
            'start_date',
            'end_date',
            'actual_return_date',
            'notes',
            'status',
            'status_display',
            'owner_handover_confirmed',
            'borrower_handover_confirmed',
            'borrower_return_confirmed',
            'owner_return_confirmed',
            'can_confirm_handover',
            'can_confirm_return',
            'handover_status_display',
            'return_status_display',
            'next_statuses',
            'can_cancel',
            'created_at',
            'updated_at',
        ]

    def get_next_statuses(self, obj):
        return [status.value for status in ALLOWED_TRANSITIONS.get(obj.status, [])]

    def get_can_cancel(self, obj):
        return obj.status in (BorrowRequest.Status.PENDING, BorrowRequest.Status.APPROVED)

    def get_can_confirm_handover(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        if obj.status != BorrowRequest.Status.APPROVED:
            return False
        if request.user == obj.item.owner:
            return not obj.owner_handover_confirmed
        if request.user == obj.borrower:
            return not obj.borrower_handover_confirmed
        return False

    def get_can_confirm_return(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        if obj.status != BorrowRequest.Status.ONGOING:
            return False
        if request.user == obj.borrower:
            return not obj.borrower_return_confirmed
        if request.user == obj.item.owner:
            return not obj.owner_return_confirmed
        return False

    def get_handover_status_display(self, obj):
        if obj.status == BorrowRequest.Status.APPROVED:
            if obj.owner_handover_confirmed and not obj.borrower_handover_confirmed:
                return 'Pemilik telah menyerahkan barang. Menunggu konfirmasi penerimaan oleh peminjam.'
            elif not obj.owner_handover_confirmed and obj.borrower_handover_confirmed:
                return 'Peminjam telah menerima barang. Menunggu konfirmasi penyerahan oleh pemilik.'
            elif not obj.owner_handover_confirmed and not obj.borrower_handover_confirmed:
                return 'Menunggu serah-terima fisik barang oleh kedua belah pihak.'
        return ''

    def get_return_status_display(self, obj):
        if obj.status == BorrowRequest.Status.ONGOING:
            if obj.borrower_return_confirmed and not obj.owner_return_confirmed:
                return 'Peminjam telah mengembalikan barang. Menunggu konfirmasi pemilik bahwa barang telah diterima.'
            elif not obj.borrower_return_confirmed and obj.owner_return_confirmed:
                return 'Pemilik telah menerima kembali barang. Menunggu konfirmasi pengembalian oleh peminjam.'
            elif not obj.borrower_return_confirmed and not obj.owner_return_confirmed:
                return 'Barang sedang aktif dipinjam. Harap konfirmasi saat pengembalian barang.'
        return ''


class BorrowRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = BorrowRequest
        fields = ['start_date', 'end_date', 'notes']
        extra_kwargs = {
            'start_date': {'error_messages': {**WAJIB, 'invalid': 'Format tanggal tidak valid (YYYY-MM-DD).'}},
            'end_date': {'error_messages': {**WAJIB, 'invalid': 'Format tanggal tidak valid (YYYY-MM-DD).'}},
        }

    def validate(self, attrs):
        start_date = attrs['start_date']
        end_date = attrs['end_date']
        item = self.context.get('item')
        errors = {}

        if start_date < date.today():
            errors['start_date'] = 'Tanggal mulai tidak boleh sebelum hari ini.'

        if end_date < start_date:
            errors['end_date'] = 'Tanggal pengembalian tidak boleh mendahului tanggal mulai.'
        elif item is not None:
            days = (end_date - start_date).days + 1
            if days > item.max_duration_days:
                errors['end_date'] = f'Barang ini maksimal dipinjam {item.max_duration_days} hari.'
            elif conflicting_bookings(item, start_date, end_date).exists():
                errors['non_field_errors'] = (
                    'Barang ini sudah dipinjam orang lain di sebagian tanggal itu. Coba tanggal lain.'
                )

        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class StatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=BorrowRequest.Status.choices,
        error_messages={**WAJIB, 'invalid_choice': 'Status tidak valid.'},
    )
