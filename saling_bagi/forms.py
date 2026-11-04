# ============================================================
# forms.py  ->  membuat FORM HTML dari model + VALIDASI input user.
# Dipanggil dari views.py. Validasi jalan saat form.is_valid().
# ============================================================

from django import forms                              # modul form Django
from django.utils import timezone                     # timezone.now() = waktu sekarang (sadar zona waktu)
from django.core.exceptions import ValidationError    # exception untuk menolak input yang salah

from .models import Makanan, JanjiTemu


class MakananForm(forms.ModelForm):                   # ModelForm: field form dibuat otomatis dari model
    class Meta:                                       # konfigurasi form
        model = Makanan                               # form ini berdasarkan model Makanan
        fields = [                                    # HANYA field ini yang tampil/diterima
            'nama_makanan',                           # (pemberi & is_available sengaja tidak ada,
            'deskripsi',                              #  diisi otomatis di view, bukan oleh user)
            'porsi',
            'foto',
            'lokasi_pengambilan',
            'lokasi_lainnya',
            'batas_layak_konsumsi',
        ]

        labels = {                                    # teks label di samping input
            'nama_makanan': 'Nama Makanan',
            'deskripsi': 'Deskripsi',
            'porsi': 'Jumlah Porsi',
            'foto': 'Foto Makanan',
            'lokasi_pengambilan': 'Lokasi Pengambilan',
            'lokasi_lainnya': 'Tuliskan Lokasi',
            'batas_layak_konsumsi': 'Batas Layak Konsumsi',
        }

        widgets = {                                   # mengatur tampilan input HTML-nya
            'nama_makanan': forms.TextInput(attrs={   # <input type="text" placeholder="...">
                'placeholder': 'Contoh: Nasi ayam',
            }),
            'deskripsi': forms.Textarea(attrs={       # <textarea rows="4">
                'placeholder': 'Jelaskan kondisi makanan...',
                'rows': 4,
            }),
            'porsi': forms.NumberInput(attrs={        # <input type="number" min="1">
                'min': 1,                             # validasi sisi browser (bisa dilewati, jadi tetap ada clean_porsi)
            }),
            'foto': forms.ClearableFileInput(),       # input upload file
            'lokasi_pengambilan': forms.Select(),     # dropdown
            'lokasi_lainnya': forms.TextInput(attrs={
                'placeholder': 'Contoh: Selasar Gedung A',
            }),
            'batas_layak_konsumsi': forms.DateTimeInput(attrs={
                'type': 'datetime-local',             # pemilih tanggal+jam bawaan browser
            }),
        }

    # --- Validasi PER FIELD: method harus bernama clean_<nama_field> ---
    def clean_nama_makanan(self):
        nama = self.cleaned_data.get('nama_makanan', '').strip()   # ambil nilai, buang spasi pinggir

        if not nama:                                  # kalau hanya spasi -> kosong
            raise ValidationError('Nama makanan wajib diisi.')     # error muncul di bawah field ini

        return nama                                   # WAJIB return nilai bersih

    def clean_deskripsi(self):
        deskripsi = self.cleaned_data.get('deskripsi', '').strip()

        if not deskripsi:
            raise ValidationError('Deskripsi makanan wajib diisi.')

        return deskripsi

    def clean_porsi(self):
        porsi = self.cleaned_data.get('porsi')

        if porsi is None or porsi < 1:                # tolak kosong atau kurang dari 1
            raise ValidationError('Jumlah porsi minimal 1.')

        return porsi

    def clean_foto(self):
        foto = self.cleaned_data.get('foto')

        if foto:                                      # foto opsional, cek hanya kalau ada
            if foto.size > 5 * 1024 * 1024:           # ukuran dalam byte; 5 * 1024 * 1024 = 5 MB
                raise ValidationError(
                    'Ukuran foto maksimal 5 MB.'
                )

            content_type = getattr(foto, 'content_type', '')   # tipe MIME dari browser (aman kalau tidak ada)

            if content_type not in [                  # whitelist tipe yang diizinkan
                'image/jpeg',
                'image/png',
                'image/webp',
            ]:
                raise ValidationError(
                    'Format foto harus JPG, PNG, atau WebP.'
                )

        return foto

    def clean_batas_layak_konsumsi(self):
        batas = self.cleaned_data.get('batas_layak_konsumsi')

        if batas and batas <= timezone.now():         # tidak boleh waktu yang sudah lewat
            raise ValidationError(
                'Batas konsumsi harus berada di masa depan.'
            )

        return batas

    # --- Validasi LINTAS FIELD: clean() dipanggil SETELAH semua clean_<field> ---
    def clean(self):
        cleaned_data = super().clean()                # ambil data hasil validasi bawaan

        lokasi = cleaned_data.get('lokasi_pengambilan')
        lokasi_lainnya = (
            cleaned_data.get('lokasi_lainnya') or ''  # 'or ""' supaya None jadi string kosong
        ).strip()

        if lokasi == 'lainnya':                       # kalau pilih Lainnya...
            if not lokasi_lainnya:                    # ...tapi tidak mengetik lokasi
                self.add_error(                       # tempelkan error ke field tertentu
                    'lokasi_lainnya',
                    'Silakan tuliskan lokasi pengambilan.'
                )
            else:
                cleaned_data['lokasi_lainnya'] = lokasi_lainnya   # simpan versi yang sudah di-strip
        else:
            cleaned_data['lokasi_lainnya'] = ''       # bukan 'lainnya' -> bersihkan sisa ketikan lama

        return cleaned_data


class JanjiTemuForm(forms.ModelForm):
    class Meta:
        model = JanjiTemu
        fields = ['waktu_janji']                      # user hanya mengisi waktu; makanan & pengambil diisi di view

        labels = {
            'waktu_janji': 'Waktu Pengambilan',
        }

        widgets = {
            'waktu_janji': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
            }),
        }

    def __init__(self, *args, **kwargs):
        self.makanan = kwargs.pop('makanan', None)    # ambil kwarg 'makanan' dan BUANG dari kwargs
        super().__init__(*args, **kwargs)             # (harus di-pop dulu, kalau tidak ModelForm error karena tidak kenal 'makanan')

    def clean_waktu_janji(self):
        waktu = self.cleaned_data.get('waktu_janji')

        if waktu and waktu <= timezone.now():         # harus di masa depan
            raise ValidationError(
                'Waktu janji temu harus berada di masa depan.'
            )

        if (
            waktu
            and self.makanan                          # self.makanan tadi dikirim dari view
            and waktu >= self.makanan.batas_layak_konsumsi   # tidak boleh lewat batas kedaluwarsa
        ):
            raise ValidationError(
                'Waktu janji temu harus sebelum batas konsumsi.'
            )

        return waktu