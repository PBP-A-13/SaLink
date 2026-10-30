from datetime import date

from django import forms
from .models import BorrowItem, BorrowRequest

# Pengajuan dengan status ini "mengunci" tanggal barang.
# Yang masih Menunggu sengaja tidak dihitung, supaya orang tidak bisa
# mengunci barang cuma dengan mengajukan.
BOOKED_STATUSES = [
    BorrowRequest.Status.APPROVED,
    BorrowRequest.Status.ONGOING,
]


def conflicting_bookings(item, start, end, exclude_id=None):
    """Pinjaman disetujui/berlangsung atas `item` yang tanggalnya bentrok dengan start..end."""
    bookings = BorrowRequest.objects.filter(
        item=item,
        status__in=BOOKED_STATUSES,
        start_date__lte=end,
        end_date__gte=start,
    )
    if exclude_id:
        bookings = bookings.exclude(id=exclude_id)
    return bookings


class BorrowItemForm(forms.ModelForm):
    """Form untuk mendaftarkan barang yang mau dipinjamkan."""

    class Meta:
        model = BorrowItem
        fields = [
            'name',
            'category',
            'condition',
            'pickup_location',
            'max_duration_days',
            'deposit_fee',
            'image_url',
            'description',
        ]
        labels = {
            'name': 'Nama barang',
            'category': 'Kategori',
            'condition': 'Kondisi',
            'pickup_location': 'Lokasi pengambilan',
            'max_duration_days': 'Maksimal lama pinjam',
            'deposit_fee': 'Uang jaminan',
            'image_url': 'Link foto barang',
            'description': 'Deskripsi',
        }
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Jas Lab Kimia Ukuran L'}),
            'pickup_location': forms.TextInput(attrs={'placeholder': 'Perpustakaan Pusat UI'}),
            'max_duration_days': forms.NumberInput(attrs={'min': 1}),
            'deposit_fee': forms.NumberInput(attrs={'min': 0, 'placeholder': '0'}),
            'image_url': forms.URLInput(attrs={'placeholder': 'https://i.imgur.com/contoh.jpg'}),
            'description': forms.Textarea(attrs={
                'rows': 5,
                'placeholder': 'Kelengkapan, kondisi detail, dan aturan pakainya',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.widget.attrs['class'] = 'field__input'
            field.error_messages['required'] = 'Bagian ini wajib diisi.'

        # Pesan error dalam bahasa Indonesia, apa pun LANGUAGE_CODE di settings
        self.fields['image_url'].error_messages['invalid'] = 'Link tidak valid. Pastikan diawali https://'
        self.fields['max_duration_days'].error_messages.update({
            'invalid': 'Isi dengan angka.',
            'min_value': 'Minimal 1 hari.',
        })
        self.fields['deposit_fee'].error_messages.update({
            'invalid': 'Isi dengan angka.',
            'max_digits': 'Nominalnya terlalu besar.',
            'max_decimal_places': 'Isi tanpa angka desimal.',
            'max_whole_digits': 'Nominalnya terlalu besar.',
        })

    def clean_max_duration_days(self):
        days = self.cleaned_data.get('max_duration_days')
        if days is not None and days < 1:
            raise forms.ValidationError('Minimal 1 hari.')
        return days

    def clean_deposit_fee(self):
        fee = self.cleaned_data.get('deposit_fee')
        if fee is not None and fee < 0:
            raise forms.ValidationError('Uang jaminan tidak boleh minus.')
        return fee


class BorrowRequestForm(forms.ModelForm):
    class Meta:
        model = BorrowRequest
        fields = ['start_date', 'end_date', 'notes']
        widgets = {
            'start_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500'
            }),
            'end_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500'
            }),
            'notes': forms.Textarea(attrs={
                'rows': 3,
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500',
                'placeholder': 'Jelaskan keperluan peminjaman Anda dan kesepakatan waktu bertemu...'
            }),
        }
        labels = {
            'start_date': 'Tanggal Mulai Pinjam',
            'end_date': 'Rencana Tanggal Pengembalian',
            'notes': 'Catatan / Alasan Peminjaman',
        }

    def __init__(self, *args, item=None, **kwargs):
        # `item` dikirim dari view supaya form bisa cek durasi dan jadwal barangnya
        super().__init__(*args, **kwargs)
        self.item = item

        for field in self.fields.values():
            field.error_messages['required'] = 'Bagian ini wajib diisi.'
        self.fields['start_date'].error_messages['invalid'] = 'Format tanggal tidak valid.'
        self.fields['end_date'].error_messages['invalid'] = 'Format tanggal tidak valid.'

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if start_date and start_date < date.today():
            self.add_error('start_date', 'Tanggal mulai tidak boleh sebelum hari ini.')

        if start_date and end_date:
            if end_date < start_date:
                self.add_error('end_date', 'Tanggal pengembalian tidak boleh mendahului tanggal mulai.')
            elif self.item is not None:
                days = (end_date - start_date).days + 1
                if days > self.item.max_duration_days:
                    self.add_error(
                        'end_date',
                        f'Barang ini maksimal dipinjam {self.item.max_duration_days} hari.',
                    )
                elif conflicting_bookings(self.item, start_date, end_date).exists():
                    self.add_error(
                        None,
                        'Barang ini sudah dipinjam orang lain di sebagian tanggal itu. Coba tanggal lain.',
                    )
        return cleaned_data