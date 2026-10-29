
from django.db import models
from django.contrib.auth.models import User


class Makanan(models.Model):
    LOKASI_CHOICES = [
        ('Kantin Fasilkom', 'Kantin Fasilkom'),
        ('Perpusat UI', 'Perpustakaan Pusat UI'),
        ('Stasiun UI', 'Stasiun UI'),
        ('Asrama UI', 'Asrama UI'),
        ('Kantin RIK', 'Kantin RIK'),
        ('Lainnya', 'Lainnya'),
    ]

    nama_makanan = models.CharField(max_length=255)
    deskripsi = models.TextField()
    porsi = models.PositiveIntegerField(default=1)
    foto = models.ImageField(
        upload_to='makanan/',
        null=True,
        blank=True
    )
    lokasi_pengambilan = models.CharField(
        max_length=50,
        choices=LOKASI_CHOICES,
        default='Kantin Fasilkom'
    )
    batas_layak_konsumsi = models.DateTimeField()
    is_available = models.BooleanField(default=True)
    pemberi = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='makanan_dibagikan'
    )

    def __str__(self):
        return f"{self.nama_makanan} - {self.pemberi.username}"
