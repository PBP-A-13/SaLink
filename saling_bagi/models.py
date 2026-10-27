from django.contrib.auth.models import User
from django.db import models


class Makanan(models.Model):
    nama_makanan = models.CharField(max_length=255)
    deskripsi = models.TextField()
    porsi = models.PositiveIntegerField(default=1)
    foto = models.ImageField(upload_to='makanan/', null=True, blank=True)
    lokasi_pengambilan = models.CharField(max_length=255)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    batas_layak_konsumsi = models.DateTimeField()
    is_available = models.BooleanField(default=True)
    pemberi = models.ForeignKey(User, on_delete=models.CASCADE, related_name='makanan_dibagikan')

    def __str__(self):
        return f'{self.nama_makanan} - {self.pemberi.username}'