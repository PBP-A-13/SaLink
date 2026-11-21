from django import forms
from django.utils import timezone
from django.core.exceptions import ValidationError

from .models import Makanan, JanjiTemu


class MakananForm(forms.ModelForm):
    class Meta:
        model = Makanan
        fields = [
            'nama_makanan',
            'deskripsi',
            'porsi',
            'foto',
            'lokasi_pengambilan',
            'lokasi_lainnya',
            'batas_layak_konsumsi',
        ]

        labels = {
            'nama_makanan': 'Nama Makanan',
            'deskripsi': 'Deskripsi',
            'porsi': 'Jumlah Porsi',
            'foto': 'Foto Makanan',
            'lokasi_pengambilan': 'Lokasi Pengambilan',
            'lokasi_lainnya': 'Tuliskan Lokasi',
            'batas_layak_konsumsi': 'Batas Layak Konsumsi',
        }

        widgets = {
            'nama_makanan': forms.TextInput(attrs={
                'placeholder': 'Contoh: Nasi ayam',
            }),
            'deskripsi': forms.Textarea(attrs={
                'placeholder': 'Jelaskan kondisi makanan...',
                'rows': 4,
            }),
            'porsi': forms.NumberInput(attrs={
                'min': 1,
            }),
            'foto': forms.ClearableFileInput(),
            'lokasi_pengambilan': forms.Select(),
            'lokasi_lainnya': forms.TextInput(attrs={
                'placeholder': 'Contoh: Selasar Gedung A',
            }),
            'batas_layak_konsumsi': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
            }),
        }

    def clean_nama_makanan(self):
        nama = self.cleaned_data.get('nama_makanan', '').strip()

        if not nama:
            raise ValidationError('Nama makanan wajib diisi.')

        return nama

    def clean_deskripsi(self):
        deskripsi = self.cleaned_data.get('deskripsi', '').strip()

        if not deskripsi:
            raise ValidationError('Deskripsi makanan wajib diisi.')

        return deskripsi

    def clean_porsi(self):
        porsi = self.cleaned_data.get('porsi')

        if porsi is None or porsi < 1:
            raise ValidationError('Jumlah porsi minimal 1.')

        return porsi

    def clean_foto(self):
        foto = self.cleaned_data.get('foto')

        if foto:
            if foto.size > 5 * 1024 * 1024:
                raise ValidationError(
                    'Ukuran foto maksimal 5 MB.'
                )

            content_type = getattr(foto, 'content_type', '')

            if content_type not in [
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

        if batas and batas <= timezone.now():
            raise ValidationError(
                'Batas konsumsi harus berada di masa depan.'
            )

        return batas

    def clean(self):
        cleaned_data = super().clean()

        lokasi = cleaned_data.get('lokasi_pengambilan')
        lokasi_lainnya = (
            cleaned_data.get('lokasi_lainnya') or ''
        ).strip()

        if lokasi == 'lainnya':
            if not lokasi_lainnya:
                self.add_error(
                    'lokasi_lainnya',
                    'Silakan tuliskan lokasi pengambilan.'
                )
            else:
                cleaned_data['lokasi_lainnya'] = lokasi_lainnya
        else:
            cleaned_data['lokasi_lainnya'] = ''

        return cleaned_data


class JanjiTemuForm(forms.ModelForm):
    class Meta:
        model = JanjiTemu
        fields = ['waktu_janji']

        labels = {
            'waktu_janji': 'Waktu Pengambilan',
        }

        widgets = {
            'waktu_janji': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
            }),
        }

    def __init__(self, *args, **kwargs):
        self.makanan = kwargs.pop('makanan', None)
        super().__init__(*args, **kwargs)

    def clean_waktu_janji(self):
        waktu = self.cleaned_data.get('waktu_janji')

        if waktu and waktu <= timezone.now():
            raise ValidationError(
                'Waktu janji temu harus berada di masa depan.'
            )

        if (
            waktu
            and self.makanan
            and waktu >= self.makanan.batas_layak_konsumsi
        ):
            raise ValidationError(
                'Waktu janji temu harus sebelum batas konsumsi.'
            )

        return waktu