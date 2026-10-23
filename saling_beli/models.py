import uuid
from django.db import models
from django.contrib.auth.models import User

class ItemListing(models.Model):
    class Category(models.TextChoices):
        FURNITURE = 'FURNITURE', 'Furnitur & Perabot Kos'
        ELECTRONICS = 'ELECTRONICS', 'Elektronik & Gadget'
        BOOKS = 'BOOKS', 'Buku & Alat Tulis'
        CLOTHING = 'CLOTHING', 'Pakaian & Aksesori'
        KITCHEN = 'KITCHEN', 'Peralatan Dapur'
        OTHER = 'OTHER', 'Lain-lain'

    class Condition(models.TextChoices):
        BRAND_NEW = 'BRAND_NEW', 'Baru / Belum Pernah Dipakai'
        LIKE_NEW = 'LIKE_NEW', 'Seperti Baru (Mulus)'
        GOOD = 'GOOD', 'Layak Pakai'
        FAIR = 'FAIR', 'Ada Minus (Berfungsi)'

    class Status(models.TextChoices):
        AVAILABLE = 'AVAILABLE', 'Tersedia'
        RESERVED = 'RESERVED', 'Dipesan'
        SOLD = 'SOLD', 'Terjual / Diberikan'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='item_listings')
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=30, choices=Category.choices, default=Category.OTHER)
    condition = models.CharField(max_length=30, choices=Condition.choices, default=Condition.GOOD)
    is_free = models.BooleanField(default=False, help_text="Centang jika barang dihibahkan secara gratis")
    price = models.DecimalField(max_digits=12, decimal_places=0, default=0, help_text="Harga dalam Rupiah (0 jika gratis)")
    image_url = models.URLField(max_length=500, blank=True, null=True, help_text="Tautan foto barang")
    pickup_location = models.CharField(max_length=255, default='Perpustakaan Pusat UI', help_text="Titik temu / COD kampus")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AVAILABLE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']


    def __str__(self):
        return f"{self.title} ({'Gratis' if self.is_free else f'Rp{self.price:,}'})"


class PriceOffer(models.Model):
    class OfferStatus(models.TextChoices):
        PENDING = 'PENDING', 'Menunggu Respon'
        ACCEPTED = 'ACCEPTED', 'Diterima'
        REJECTED = 'REJECTED', 'Ditolak'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item = models.ForeignKey(ItemListing, on_delete=models.CASCADE, related_name='offers')
    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='price_offers')
    offered_price = models.DecimalField(max_digits=12, decimal_places=0, help_text="Harga penawaran nego dalam Rupiah")
    note = models.CharField(max_length=255, blank=True, help_text="Pesan/alasan nego (opsional)")
    status = models.CharField(max_length=20, choices=OfferStatus.choices, default=OfferStatus.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Nego Rp{self.offered_price:,} untuk {self.item.title} oleh {self.buyer.username} [{self.status}]"


class TransactionOrder(models.Model):
    class Stage(models.TextChoices):
        MENUNGGU_TRANSFER = 'MENUNGGU_TRANSFER', 'Menunggu Transfer'
        BUKTI_DIUNGGAH = 'BUKTI_DIUNGGAH', 'Bukti Terkirim / Verifikasi'
        DIKONFIRMASI = 'DIKONFIRMASI', 'Dikonfirmasi Penjual'
        JANJI_TEMU_COD = 'JANJI_TEMU_COD', 'Janji Temu COD Kampus'
        SELESAI = 'SELESAI', 'Transaksi Selesai'
        BATAL = 'BATAL', 'Dibatalkan'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item = models.ForeignKey(ItemListing, on_delete=models.CASCADE, related_name='orders')
    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders_bought')
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders_sold')
    agreed_price = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    stage = models.CharField(max_length=30, choices=Stage.choices, default=Stage.MENUNGGU_TRANSFER)
    payment_proof_note = models.CharField(max_length=255, blank=True, help_text="Catatan transfer atau nomor referensi bank")
    cod_meeting_time = models.CharField(max_length=150, blank=True, help_text="Waktu pertemuan COD yang disepakati")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Order #{str(self.id)[:8]} - {self.item.title} ({self.get_stage_display()})"
