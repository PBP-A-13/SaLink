"""
Serializer modul Saling Pinjam untuk web service DRF.

Serializer ini ngubah model (BorrowItem, BorrowRequest) jadi JSON buat aplikasi Flutter,
dan sebaliknya: memeriksa JSON yang dikirim aplikasi sebelum disimpan ke database.
Aturan validasinya sengaja dibuat sama dengan form di forms.py supaya hasilnya
konsisten antara situs web dan aplikasi.
"""

from datetime import date

from rest_framework import serializers

from .forms import conflicting_bookings
from .models import BorrowItem, BorrowRequest
from .views import ALLOWED_TRANSITIONS

# Pesan error bawaan DRF berbahasa Inggris, jadi yang sering muncul diganti di sini.
WAJIB = {
    'required': 'Bagian ini wajib diisi.',
    'blank': 'Bagian ini wajib diisi.',
    'null': 'Bagian ini wajib diisi.',
}

# Batas uang jaminan = max_digits=12 di model BorrowItem
MAKS_JAMINAN = 999_999_999_999


class BorrowItemSerializer(serializers.ModelSerializer):
    """
    Barang yang dipinjamkan. Dipakai untuk daftar, detail, dan juga untuk
    membaca isian form tambah/edit barang dari aplikasi.
    """

    owner = serializers.CharField(source='owner.username', read_only=True)
    is_owner = serializers.SerializerMethodField()
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    condition_display = serializers.CharField(source='get_condition_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    # Dijadikan integer biasa (di model bertipe Decimal) biar gampang dibaca Flutter
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
        # status dan owner diatur server, jadi kalau aplikasi mengirimnya akan diabaikan
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
    """Ringkasan barang yang ditempel di dalam data pengajuan, supaya daftar pengajuan nggak kepanjangan."""

    owner = serializers.CharField(source='owner.username', read_only=True)

    class Meta:
        model = BorrowItem
        fields = ['id', 'name', 'image_url', 'pickup_location', 'category', 'status', 'owner']


class BorrowRequestSerializer(serializers.ModelSerializer):
    """
    Pengajuan pinjam untuk ditampilkan. `next_statuses` dan `can_cancel` dihitung
    di server memakai aturan yang sama dengan situs web, jadi aplikasi cukup
    menampilkan tombol yang diizinkan tanpa menyalin aturannya sendiri.
    """

    item = BorrowItemRingkasSerializer(read_only=True)
    borrower = serializers.CharField(source='borrower.username', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    next_statuses = serializers.SerializerMethodField()
    can_cancel = serializers.SerializerMethodField()

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
            'next_statuses',
            'can_cancel',
            'created_at',
            'updated_at',
        ]

    def get_next_statuses(self, obj):
        """Status tujuan yang boleh dipilih pemilik barang dari status sekarang."""
        return [status.value for status in ALLOWED_TRANSITIONS.get(obj.status, [])]

    def get_can_cancel(self, obj):
        return obj.status in (BorrowRequest.Status.PENDING, BorrowRequest.Status.APPROVED)


class BorrowRequestCreateSerializer(serializers.ModelSerializer):
    """
    Isian form "Ajukan pinjam". Barang yang dipinjam dikirim lewat context
    (context={'item': item}) karena aturan durasi dan jadwalnya bergantung pada barang itu.
    """

    class Meta:
        model = BorrowRequest
        fields = ['start_date', 'end_date', 'notes']
        extra_kwargs = {
            'start_date': {'error_messages': {**WAJIB, 'invalid': 'Format tanggal tidak valid (YYYY-MM-DD).'}},
            'end_date': {'error_messages': {**WAJIB, 'invalid': 'Format tanggal tidak valid (YYYY-MM-DD).'}},
        }

    def validate(self, attrs):
        # Urutan dan pesannya mengikuti BorrowRequestForm.clean di forms.py
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
    """Isian untuk mengubah status pengajuan: {"status": "APPROVED"}."""

    status = serializers.ChoiceField(
        choices=BorrowRequest.Status.choices,
        error_messages={**WAJIB, 'invalid_choice': 'Status tidak valid.'},
    )