from django import forms
from django.utils import timezone
from .models import Vehicle

LOCATIONS = [
    'Fakultas Teknik',
    'Fakultas Ilmu Komputer, Gedung Baru',
    'Fakultas Ilmu Komputer, Gedung Lama',
    'Fakultas Matematika dan Ilmu Pengetahuan Alam',
    'Fakultas Ekonomi dan Bisnis',
    'Fakultas Ilmu Budaya',
    'Fakultas Ilmu Administrasi',
    'Fakultas Kesehatan Masyarakat',
    'Fakultas Ilmu Keperawatan',
    'Fakultas Hukum',
    'Fakultas Psikologi',
    'Fakultas Kedokteran',
    'Vokasi',
    'Fakultas Ilmu Politik dan Sosial',
    'Balairung',
    'Perpusat UI',
    'Sarana Olahraga',
    'RSUI',
    'Pusat Kegiatan Mahasiswa',
    'Kutek',
    'Kukel',
    'Stasiun UI',
    'Stasiun Pondok Cina',
    'Rumpun Ilmu Kesehatan',
]

LOCATION_CHOICES = [('', 'Pilih Lokasi')] + [(loc, loc) for loc in sorted(LOCATIONS)]

TIME_CHOICES = [
    (f"{h:02d}:{m:02d}", f"{h:02d}.{m:02d}")
    for h in range(6, 22)
    for m in (0, 30)
]
TIME_CHOICES_WITH_EMPTY = [('', 'Masukkan Jam')] + TIME_CHOICES

PRICE_BY_TYPE = {'motor': 5000, 'mobil': 7000}
MAX_CAPACITY = {'motor': 2, 'mobil': 8}

DAY_NAMES = ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat']


class RideSearchForm(forms.Form):
    asal = forms.ChoiceField(
        choices=[('', 'Lokasi Sekarang')] + [(loc, loc) for loc in sorted(LOCATIONS)],
        required=False,
        label='Asal',
    )
    tujuan = forms.ChoiceField(
        choices=[('', 'Tujuan')] + [(loc, loc) for loc in sorted(LOCATIONS)],
        required=False,
        label='Tujuan',
    )
    jam = forms.ChoiceField(
        choices=TIME_CHOICES_WITH_EMPTY,
        required=False,
        label='Waktu Berangkat',
    )
    tanggal = forms.DateField(
        required=False,
        label='Tanggal',
        widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
    )

    def clean(self):
        cleaned = super().clean()
        asal = cleaned.get('asal')
        tujuan = cleaned.get('tujuan')
        if asal and tujuan and asal == tujuan:
            self.add_error('tujuan', 'Tujuan tidak boleh sama dengan asal.')
        return cleaned


class SeatsForm(forms.Form):
    seats = forms.IntegerField(min_value=1, max_value=8, initial=1, label='Jumlah kursi')


class JoinRideForm(SeatsForm):
    asal = forms.CharField(required=False)
    tujuan = forms.CharField(required=False)
    jam = forms.CharField(required=False)


class OfferVehicleForm(forms.Form):
    vehicle_type = forms.ChoiceField(
        choices=[('', 'Jenis'), ('motor', 'Motor'), ('mobil', 'Mobil')],
        label='Jenis Kendaraan',
    )
    capacity = forms.ChoiceField(
        choices=[('', 'Kapasitas')] + [(str(i), str(i)) for i in range(1, 9)],
        label='Kapasitas',
    )
    brand = forms.CharField(max_length=100, required=False, initial='Kendaraan')
    model = forms.CharField(max_length=100, required=False, initial='Standard')
    license_plate = forms.CharField(max_length=20, required=False, initial='B 1234 UI')
