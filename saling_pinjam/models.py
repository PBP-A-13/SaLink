import uuid
from django.db import models
from django.contrib.auth.models import User

class BorrowItem(models.Model):
    """
    Barang yang ditawarkan atau didaftarkan untuk dipinjamkan kepada mahasiswa lain.
    """
    class Category(models.TextChoices):
        ACADEMIC = 'ACADEMIC', 'Akademik & Formal (Jas Almamater, Toga, Kemeja)'
        TRAVEL = 'TRAVEL', 'Travel & Koper (Koper, Carrier, Tas Gunung)'
        ELECTRONICS = 'ELECTRONICS', 'Elektronik & Aksesori (Kalkulator, Adapter, Kabel)'
        TOOLS = 'TOOLS', 'Peralatan & Hobi (Perkakas Kos, Alat Olahraga, Musik)'
        OTHER = 'OTHER', 'Lain-lain'

    class Condition(models.TextChoices):
        LIKE_NEW = 'LIKE_NEW', 'Sangat Baik (Mulus)'
        GOOD = 'GOOD', 'Baik / Layak Pakai'
        FAIR = 'FAIR', 'Ada Minus (Tetap Berfungsi)'

    class Status(models.TextChoices):
        AVAILABLE = 'AVAILABLE', 'Tersedia'
        BORROWED = 'BORROWED', 'Sedang Dipinjam'
        UNAVAILABLE = 'UNAVAILABLE', 'Tidak Tersedia'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='borrow_items')
    name = models.CharField(max_length=200, help_text="Nama barang yang dipinjamkan (misal: Jas Lab Kimia Ukuran L)")
    description = models.TextField(help_text="Deskripsi detail, kelengkapan, dan ketentuan khusus dari pemilik")
    category = models.CharField(max_length=30, choices=Category.choices, default=Category.OTHER)
    condition = models.CharField(max_length=30, choices=Condition.choices, default=Condition.GOOD)
    max_duration_days = models.PositiveIntegerField(default=7, help_text="Batas maksimal peminjaman (dalam hari)")
    deposit_fee = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        help_text="Uang jaminan/deposit dalam Rupiah (0 jika tanpa deposit)"
    )
    pickup_location = models.CharField(
        max_length=255,
        default='Perpustakaan Pusat UI',
        help_text="Titik temu serah-terima barang di area kampus UI"
    )
    image_url = models.URLField(max_length=500, blank=True, null=True, help_text="Tautan foto barang")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AVAILABLE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.get_status_display()} (Milik {self.owner.username})"


class BorrowRequest(models.Model):
    """
    Pengajuan pinjam-meminjam barang antar mahasiswa beserta jadwal dan status pengembaliannya.
    """
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Menunggu Persetujuan Pemilik'
        APPROVED = 'APPROVED', 'Disetujui'
        REJECTED = 'REJECTED', 'Ditolak'
        ONGOING = 'ONGOING', 'Sedang Berlangsung / Barang Sudah Diambil'
        RETURNED = 'RETURNED', 'Sudah Dikembalikan'
        CANCELLED = 'CANCELLED', 'Dibatalkan'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item = models.ForeignKey(BorrowItem, on_delete=models.CASCADE, related_name='requests')
    borrower = models.ForeignKey(User, on_delete=models.CASCADE, related_name='borrow_requests')
    start_date = models.DateField(help_text="Tanggal mulai peminjaman")
    end_date = models.DateField(help_text="Jadwal pengembalian yang diajukan")
    actual_return_date = models.DateField(blank=True, null=True, help_text="Tanggal aktual barang dikembalikan")
    notes = models.TextField(blank=True, help_text="Alasan peminjaman / pesan untuk pemilik barang")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Pengajuan {self.item.name} oleh {self.borrower.username} ({self.get_status_display()})"
