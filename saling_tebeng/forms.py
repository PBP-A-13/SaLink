from django import forms
from django.forms import formset_factory
from django.utils import timezone

from .models import Vehicle


# Opsi lokasi dropdown. GANTI dengan lokasi sebenarnya;
# koordinat di bawah hanya contoh/placeholder.
LOCATIONS = {
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
    'Pusat Kegiatan Mahassiswa',
    'Kutek',
    'Kukel',
    'Stasiun UI',
    'Stasiun Pondok Cina',
    'Rumpun Ilmu Kesehatan',
}
LOCATION_CHOICES = [('', 'Pilih lokasi')] + [(n, n) for n in LOCATIONS]

PRICE_BY_TYPE = {'motor': 5000, 'mobil': 7000}
PRICE_CHOICES = [('paid', 'Berbayar (tarif standar)'), ('free', 'Gratis')]

# Batas kapasitas per jenis kendaraan (ubah sesuai kebutuhan)
MAX_CAPACITY = {'motor': 1, 'mobil': 3}

DAY_NAMES = ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu']


def _time_widget():
    return forms.TimeInput(attrs={'type': 'time'}, format='%H:%M')


# ---------------------------------------------------------------------------
# Cari tebengan
# ---------------------------------------------------------------------------

class RideSearchForm(forms.Form):
    """Form pencarian di halaman NEBENG (dikirim lewat GET)."""
    asal = forms.ChoiceField(choices=LOCATION_CHOICES, label='Asal')
    tujuan = forms.ChoiceField(choices=LOCATION_CHOICES, label='Tujuan')
    jam = forms.TimeField(widget=_time_widget(), label='Waktu Berangkat')
    tanggal = forms.DateField(
        required=False, label='Tanggal',
        widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
    )

    def clean_tanggal(self):
        today = timezone.localdate()
        d = self.cleaned_data.get('tanggal') or today
        if d < today:
            raise forms.ValidationError('Tanggal tidak boleh di masa lalu.')
        return d

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('asal') and cleaned.get('asal') == cleaned.get('tujuan'):
            self.add_error('tujuan', 'Tujuan tidak boleh sama dengan asal.')
        return cleaned


# ---------------------------------------------------------------------------
# Gabung tebengan
# ---------------------------------------------------------------------------

class SeatsForm(forms.Form):
    seats = forms.IntegerField(min_value=1, max_value=8, initial=1, label='Jumlah kursi')


class JoinRideForm(SeatsForm):
    """Dipakai saat gabung dari daftar: membawa kembali data pencarian."""
    asal = forms.CharField()
    tujuan = forms.CharField()
    jam = forms.TimeField()


# ---------------------------------------------------------------------------
# Tawarkan tebengan
# ---------------------------------------------------------------------------

class OfferVehicleForm(forms.Form):
    """Bar di kanan jadwal: jenis kendaraan (dropdown) + kapasitas."""
    vehicle_type = forms.ChoiceField(
        choices=[('', 'Pilih jenis kendaraan')] + list(Vehicle.VEHICLE_TYPE_CHOICES),
        label='Jenis Kendaraan',
    )
    capacity = forms.IntegerField(min_value=1, label='Kapasitas', initial=1)

    # opsional, tapi kolom di model Vehicle wajib terisi (boleh string kosong)
    brand = forms.CharField(max_length=100, required=False, label='Merek')
    model = forms.CharField(max_length=100, required=False, label='Model')
    license_plate = forms.CharField(max_length=20, required=False, label='Plat Nomor')

    def clean(self):
        cleaned = super().clean()
        vt, cap = cleaned.get('vehicle_type'), cleaned.get('capacity')
        if vt and cap and cap > MAX_CAPACITY.get(vt, 8):
            self.add_error(
                'capacity',
                f'Kapasitas {vt} maksimal {MAX_CAPACITY[vt]}.',
            )
        return cleaned


class ScheduleSlotForm(forms.Form):
    """Satu baris jadwal pada satu hari: jam, asal, tujuan."""
    time = forms.TimeField(widget=_time_widget(), label='Jam')
    origin = forms.ChoiceField(choices=LOCATION_CHOICES, label='Asal')
    destination = forms.ChoiceField(choices=LOCATION_CHOICES, label='Tujuan')

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('origin') and cleaned.get('origin') == cleaned.get('destination'):
            self.add_error('destination', 'Asal dan tujuan tidak boleh sama.')
        return cleaned


# extra=1 -> satu baris awal per hari; baris yang tidak diubah dilewati.
# Tombol "tambah jam" cukup menaikkan TOTAL_FORMS lewat JS (clone empty_form).
SlotFormSet = formset_factory(ScheduleSlotForm, extra=1)


def build_week_formsets(days, data=None):
    """
    Satu formset per hari. Prefix unik per tanggal, mis. 'day20261027',
    jadi nama field-nya 'day20261027-0-time', 'day20261027-TOTAL_FORMS', dst.
    Return: [(day_dict, formset), ...]
    """
    return [
        (d, SlotFormSet(data, prefix=f"day{d['date']:%Y%m%d}"))
        for d in days
    ]