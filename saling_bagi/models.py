from django.db import models
from django.contrib.auth.models import User

class Makanan(models.Model):
    nama_makanan = models.CharField(max_length=255)
    deskripsi = models.TextField()
    lokasi_pengambilan = models.CharField(max_length=255)
    batas_layak_konsumsi = models.DateTimeField()
    is_available = models.BooleanField(default=True)
    # Menghubungkan data makanan dengan user yang membagikan
    pemberi = models.ForeignKey(User, on_delete=models.CASCADE, related_name='makanan_dibagikan')

    def __str__(self):
        return f"{self.nama_makanan} - {self.pemberi.username}"