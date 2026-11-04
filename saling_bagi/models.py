from django.db import models
from django.contrib.auth.models import User
from django.db.models import Q


class Makanan(models.Model):
    LOKASI_CHOICES = [
        ('kanmer', 'Kanmer (Kantin FH)'),
        ('kanvok', 'Kanvok (Kantin Vokasi)'),
        ('kancil', 'Kancil (Kantin Fasilkom)'),
        ('dallas', 'Dallas (Kantin FMIPA)'),
        ('kansas', 'Kansas (Kantin FIB)'),
        ('kanrik', 'Kanrik (Kantin RIK)'),
        ('kantek', 'Kantek (Kantin Teknik)'),
        ('bamen', 'Bamen (Kantin FIA)'),
        ('takor', 'Takor (Kantin FISIP)'),
        ('lainnya', 'Lainnya'),
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
        max_length=20,
        choices=LOKASI_CHOICES,
        default='kancil'
    )

    lokasi_lainnya = models.CharField(
        max_length=255,
        blank=True,
        default=''
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

    @property
    def nama_lokasi(self):
        if self.lokasi_pengambilan == 'lainnya':
            return self.lokasi_lainnya or 'Lokasi lainnya'

        return self.get_lokasi_pengambilan_display()


class JanjiTemu(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Menunggu Persetujuan'),
        ('APPROVED', 'Disetujui'),
        ('REJECTED', 'Ditolak'),
        ('COMPLETED', 'Selesai'),
    ]

    makanan = models.ForeignKey(
        Makanan,
        on_delete=models.CASCADE,
        related_name='janji_temu'
    )

    pengambil = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='janji_temu_dibuat'
    )

    waktu_janji = models.DateTimeField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['makanan'],
                condition=Q(status__in=['PENDING', 'APPROVED']),
                name='unique_active_janji_per_makanan'
            )
        ]

    def __str__(self):
        return (
            f"Janji {self.makanan.nama_makanan} "
            f"- {self.pengambil.username}"
        )