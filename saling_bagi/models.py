# ============================================================
# models.py  ->  "M" di MVT. Mendefinisikan STRUKTUR TABEL database.
# Satu class = satu tabel. Satu atribut = satu kolom.
# ============================================================

from django.db import models                      # modul dasar ORM Django (Model, CharField, dll)
from django.contrib.auth.models import User       # model User bawaan Django (tabel auth_user)
from django.db.models import Q                    # Q = objek kondisi, dipakai di constraint bersyarat


class Makanan(models.Model):                      # tabel saling_bagi_makanan
    # Pilihan dropdown lokasi. Format tuple: (nilai_disimpan_di_DB, label_yang_tampil)
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
        ('lainnya', 'Lainnya'),                   # kalau dipilih, user wajib isi lokasi_lainnya
    ]

    nama_makanan = models.CharField(max_length=255)   # teks pendek, wajib diisi, maks 255 karakter
    deskripsi = models.TextField()                    # teks panjang tanpa batas, wajib diisi
    porsi = models.PositiveIntegerField(default=1)    # bilangan bulat >= 0, default 1
    foto = models.ImageField(
        upload_to='makanan/',                         # file disimpan di MEDIA_ROOT/makanan/
        null=True,                                    # null=True: di DATABASE boleh NULL
        blank=True                                    # blank=True: di FORM boleh dikosongkan
    )                                                 # (ImageField butuh library Pillow)

    lokasi_pengambilan = models.CharField(
        max_length=20,                                # cukup panjang untuk kode seperti 'kancil'
        choices=LOKASI_CHOICES,                       # dibatasi ke pilihan di atas (jadi dropdown)
        default='kancil'                              # nilai awal
    )

    lokasi_lainnya = models.CharField(
        max_length=255,
        blank=True,                                   # boleh kosong (hanya diisi jika pilih 'lainnya')
        default=''                                    # default string kosong, bukan NULL
    )

    batas_layak_konsumsi = models.DateTimeField()     # tanggal+jam kedaluwarsa, wajib diisi
    is_available = models.BooleanField(default=True)  # True = masih bisa diajukan, False = sudah dipesan/habis

    pemberi = models.ForeignKey(                      # relasi many-to-one: banyak makanan -> satu user
        User,
        on_delete=models.CASCADE,                     # kalau user dihapus, makanannya ikut terhapus
        related_name='makanan_dibagikan'              # akses balik: user.makanan_dibagikan.all()
    )

    def __str__(self):                                # teks yang tampil di admin / saat print(objek)
        return f"{self.nama_makanan} - {self.pemberi.username}"

    @property                                         # dipanggil seperti atribut: makanan.nama_lokasi (tanpa kurung)
    def nama_lokasi(self):
        if self.lokasi_pengambilan == 'lainnya':      # kalau user pilih 'Lainnya'
            return self.lokasi_lainnya or 'Lokasi lainnya'   # pakai teks ketikan, fallback kalau kosong

        return self.get_lokasi_pengambilan_display()  # method otomatis Django: ubah kode -> label choices


class JanjiTemu(models.Model):                        # tabel saling_bagi_janjitemu
    # Status janji. Alur: PENDING -> APPROVED -> COMPLETED, atau PENDING -> REJECTED
    STATUS_CHOICES = [
        ('PENDING', 'Menunggu Persetujuan'),
        ('APPROVED', 'Disetujui'),
        ('REJECTED', 'Ditolak'),
        ('COMPLETED', 'Selesai'),
    ]

    makanan = models.ForeignKey(
        Makanan,
        on_delete=models.CASCADE,                     # makanan dihapus -> janjinya ikut terhapus
        related_name='janji_temu'                     # akses balik: makanan.janji_temu.all()
    )

    pengambil = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='janji_temu_dibuat'              # akses balik: user.janji_temu_dibuat.all()
    )

    waktu_janji = models.DateTimeField()              # kapan pengambil akan datang

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING'                             # janji baru selalu mulai dari PENDING
    )

    created_at = models.DateTimeField(auto_now_add=True)   # diisi SEKALI saat objek dibuat
    updated_at = models.DateTimeField(auto_now=True)       # diisi ulang SETIAP kali save()

    class Meta:                                       # konfigurasi tambahan tabel
        ordering = ['-created_at']                    # default urutan: terbaru dulu ('-' = descending)
        constraints = [
            models.UniqueConstraint(                  # aturan keunikan di level DATABASE
                fields=['makanan'],                   # nilai kolom makanan tidak boleh kembar...
                condition=Q(status__in=['PENDING', 'APPROVED']),   # ...KHUSUS baris yang statusnya aktif
                name='unique_active_janji_per_makanan'
            )
            # Artinya: 1 makanan hanya boleh punya 1 janji aktif.
            # Janji REJECTED/COMPLETED tidak dihitung, jadi makanan bisa diajukan lagi setelah ditolak.
            # Ini pengaman terakhir saat dua orang mengajukan bersamaan (penting di SQLite).
        ]

    def __str__(self):
        return (
            f"Janji {self.makanan.nama_makanan} "
            f"- {self.pengambil.username}"
        )