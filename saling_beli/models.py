import uuid

from django.contrib.auth.models import User
from django.db import models


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
    is_free = models.BooleanField(default=False, help_text='Centang jika barang dihibahkan secara gratis')
    price = models.DecimalField(max_digits=12, decimal_places=0, default=0, help_text='Harga dalam Rupiah (0 jika gratis)')
    image_url = models.URLField(max_length=500, blank=True, null=True, help_text='Tautan foto barang (opsional)')
    image = models.ImageField(upload_to='item_images/', blank=True, help_text='Upload foto barang dari perangkat')
    pickup_location = models.CharField(max_length=255, default='Perpustakaan Pusat UI', help_text='Titik temu / COD kampus')
    payout_method = models.CharField(max_length=50, blank=True, default='Bank BCA', help_text='Metode pencairan dana')
    payout_account_name = models.CharField(max_length=150, blank=True, default='', help_text='Nama pemilik rekening / e-wallet')
    payout_account_number = models.CharField(max_length=100, blank=True, default='', help_text='Nomor rekening bank atau e-wallet')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AVAILABLE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def display_image(self):
        if self.image:
            return self.image.url
        return self.image_url

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
    offered_price = models.DecimalField(max_digits=12, decimal_places=0)
    note = models.CharField(max_length=255, blank=True)
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
    payment_proof_note = models.CharField(max_length=255, blank=True)
    cod_meeting_time = models.CharField(max_length=150, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Order #{str(self.id)[:8]} - {self.item.title} ({self.get_stage_display()})"


class ItemChatMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item = models.ForeignKey(ItemListing, on_delete=models.CASCADE, related_name='chat_messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_chats')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_chats')
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'Chat from {self.sender.username} to {self.recipient.username} on {self.item.title}'


class UserNotification(models.Model):
    class NotifType(models.TextChoices):
        CHAT = 'CHAT', 'Pesan Baru'
        TRACKER_UPDATE = 'TRACKER_UPDATE', 'Pembaruan Status Tracker'
        OFFER = 'OFFER', 'Penawaran Nego'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=150)
    message = models.TextField()
    notification_type = models.CharField(max_length=30, choices=NotifType.choices, default=NotifType.TRACKER_UPDATE)
    link = models.CharField(max_length=255, blank=True, null=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notif for {self.user.username}: {self.title} ({'Read' if self.is_read else 'Unread'})"