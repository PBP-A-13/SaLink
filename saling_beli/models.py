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
