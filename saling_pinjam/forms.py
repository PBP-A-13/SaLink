from django import forms
from .models import BorrowItem, BorrowRequest

class BorrowItemForm(forms.ModelForm):
    class Meta:
        model = BorrowItem
        fields = [
            'name',
            'description',
            'category',
            'condition',
            'max_duration_days',
            'deposit_fee',
            'pickup_location',
            'image_url',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500',
                'placeholder': 'Contoh: Jas Almamater UI Ukuran M / Koper 24 Inch'
            }),
            'description': forms.Textarea(attrs={
                'rows': 4,
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500',
                'placeholder': 'Jelaskan kondisi fisik barang, aksesoris/kelengkapan, dan ketentuan pemakaian...'
            }),
            'category': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500'
            }),
            'condition': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500'
            }),
            'max_duration_days': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500',
                'min': '1',
                'placeholder': '7'
            }),
            'deposit_fee': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500',
                'min': '0',
                'placeholder': '0 jika tidak ada jaminan uang'
            }),
            'pickup_location': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500',
                'placeholder': 'Contoh: Perpustakaan Pusat UI / Stasiun UI'
            }),
            'image_url': forms.URLInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500',
                'placeholder': 'https://example.com/foto-barang.jpg'
            }),
        }
        labels = {
            'name': 'Nama Barang',
            'description': 'Deskripsi Barang',
            'category': 'Kategori Barang',
            'condition': 'Kondisi Barang',
            'max_duration_days': 'Batas Maksimal Durasi Pinjam (Hari)',
            'deposit_fee': 'Uang Jaminan / Deposit (Rp)',
            'pickup_location': 'Titik Serah Terima / COD',
            'image_url': 'Tautan Foto Barang (Opsional)',
        }


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

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if start_date and end_date and end_date < start_date:
            self.add_error('end_date', 'Tanggal pengembalian tidak boleh mendahului tanggal mulai.')
        return cleaned_data
