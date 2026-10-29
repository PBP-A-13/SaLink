import uuid
from django.contrib.auth.models import User
from django.db import models


class ItemListing(models.Model):
    """Model data barang prelove atau gratis (hibah) yang ditawarkan pengguna."""
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
    image_url = models.URLField(max_length=500, blank=True, null=True, help_text="Tautan foto barang (opsional)")
    image = models.ImageField(upload_to='item_images/', blank=True, null=True, help_text="Upload foto barang dari perangkat")
    pickup_location = models.CharField(max_length=255, default='Perpustakaan Pusat UI', help_text="Titik temu / COD kampus")
    payout_method = models.CharField(max_length=50, blank=True, default='Bank BCA', help_text="Metode pencairan: Bank BCA, Mandiri, BRI, BNI, GoPay, OVO, ShopeePay, DANA")
    payout_account_name = models.CharField(max_length=150, blank=True, default='', help_text="Nama pemilik rekening / e-wallet penjual")
    payout_account_number = models.CharField(max_length=100, blank=True, default='', help_text="Nomor rekening bank atau e-wallet penjual")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AVAILABLE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def display_image(self):
        """Mengembalikan file upload jika ada, jika tidak kembalikan image_url"""
        if self.image:
            return self.image.url
        return self.image_url

    def __str__(self):
        return f"{self.title} ({'Gratis' if self.is_free else f'Rp{self.price:,}'})"


class PriceOffer(models.Model):
    """Model penawaran nego harga dari calon pembeli ke pemilik barang."""
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
    """Model tracker transaksi dan pembayaran QRIS escrow bertahap."""
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
    buyer_confirmed_at = models.DateTimeField(null=True, blank=True)
    seller_confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['item'],
                condition=~models.Q(stage__in=['BATAL', 'SELESAI']),
                name='uniq_active_order_per_item',
            ),
            models.UniqueConstraint(
                fields=['item', 'buyer'],
                condition=~models.Q(stage__in=['BATAL', 'SELESAI']),
                name='uniq_active_order_per_item_buyer',
            )
        ]

    def __str__(self):
        return f"Order #{str(self.id)[:8]} - {self.item.title} ({self.get_stage_display()})"


class Conversation(models.Model):
    """Ruang obrolan per item antara penjual dan pembeli agar thread tidak tercampur."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item = models.ForeignKey(ItemListing, on_delete=models.CASCADE, related_name='conversations')
    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='buyer_conversations')
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='seller_conversations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        constraints = [
            models.UniqueConstraint(
                fields=['item', 'buyer'],
                name='uniq_conversation_item_buyer',
            )
        ]

    def __str__(self):
        return f"Chat {self.item.title} - @{self.buyer.username} dengan @{self.seller.username}"


class ItemChatMessage(models.Model):
    """Pesan chat individual antara calon pembeli dan penjual."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages',
        null=True,
        blank=True,
        help_text="Thread percakapan; null hanya untuk data lama sebelum migrasi.",
    )
    item = models.ForeignKey(ItemListing, on_delete=models.CASCADE, related_name='chat_messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_chats')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_chats')
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Chat from {self.sender.username} to {self.recipient.username} on {self.item.title}"


class UserNotification(models.Model):
    """Model notifikasi in-app realtime untuk chat baru, penawaran nego, dan update order."""
    class NotifType(models.TextChoices):
        CHAT = 'CHAT', 'Pesan Baru'
        TRACKER_UPDATE = 'TRACKER_UPDATE', 'Pembaruan Status Tracker'
        OFFER = 'OFFER', 'Penawaran Nego'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=150)
    message = models.TextField()
    notification_type = models.CharField(max_length=30, choices=NotifType.choices, default=NotifType.TRACKER_UPDATE)
    link = models.CharField(max_length=255, blank=True, null=True, help_text="Tautan tujuan saat notifikasi diklik")
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notif for {self.user.username}: {self.title} ({'Read' if self.is_read else 'Unread'})"
