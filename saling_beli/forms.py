from django import forms
from .models import ItemListing


class ItemListingForm(forms.ModelForm):
    PAYOUT_METHOD_CHOICES = [
        ('BCA', 'Bank BCA'),
        ('Mandiri', 'Bank Mandiri'),
        ('BRI', 'Bank BRI'),
        ('BNI', 'Bank BNI'),
        ('BTN', 'Bank Tabungan Negara (BTN)'),
        ('BSI', 'Bank Syariah Indonesia (BSI)'),
        ('GoPay', 'GoPay'),
        ('OVO', 'OVO'),
        ('ShopeePay', 'ShopeePay'),
        ('DANA', 'DANA'),
    ]

    payout_method = forms.ChoiceField(
        choices=PAYOUT_METHOD_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_payout_method'}),
        label='Bank / E-Wallet Pencairan Dana',
    )

    class Meta:
        model = ItemListing
        fields = [
            'title',
            'category',
            'condition',
            'is_free',
            'price',
            'description',
            'pickup_location',
            'payout_method',
            'payout_account_name',
            'payout_account_number',
            'image',
            'image_url',
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Contoh: Buku Kalkulus Thomas Ed 14 / Jas Lab MIPA M',
                'required': True,
            }),
            'category': forms.Select(attrs={
                'class': 'form-select',
            }),
            'condition': forms.Select(attrs={
                'class': 'form-select',
            }),
            'is_free': forms.CheckboxInput(attrs={
                'class': 'form-checkbox',
                'id': 'id_is_free',
                'onchange': 'togglePriceField()',
            }),
            'price': forms.NumberInput(attrs={
                'class': 'form-input',
                'placeholder': '0 jika gratis',
                'min': '0',
                'id': 'id_price',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 4,
                'placeholder': 'Ceritakan kondisi fisik barang, alasan jual/hibah, atau kelengkapan...',
                'required': True,
            }),
            'pickup_location': forms.TextInput(attrs={
                'class': 'form-input',
                'id': 'id_pickup_location',
                'placeholder': 'Contoh: Perpustakaan Pusat UI / Stasiun Pocin / Kutek',
                'required': True,
            }),
            'payout_account_name': forms.TextInput(attrs={
                'class': 'form-input',
                'id': 'id_payout_account_name',
                'placeholder': 'Nama sesuai rekening / e-wallet (Contoh: Budi Santoso)',
            }),
            'payout_account_number': forms.TextInput(attrs={
                'class': 'form-input',
                'id': 'id_payout_account_number',
                'placeholder': 'Nomor rekening atau nomor HP e-wallet (Contoh: 08123456789 / 5210123456)',
            }),
            'image': forms.FileInput(attrs={
                'class': 'form-file-input',
                'accept': 'image/*',
            }),
            'image_url': forms.URLInput(attrs={
                'class': 'form-input',
                'placeholder': 'https://images.unsplash.com/... (opsional jika tidak upload foto)',
            }),
        }
        labels = {
            'title': 'Judul Barang / Barang yang Dihibahkan',
            'category': 'Kategori Barang',
            'condition': 'Kondisi Fisik',
            'is_free': 'Hibahkan Secara Gratis (Rp0)?',
            'price': 'Harga (Rp)',
            'description': 'Deskripsi Lengkap',
            'pickup_location': 'Titik Temu COD Kampus UI',
            'payout_method': 'Bank / E-Wallet Penerima Dana Penjualan',
            'payout_account_name': 'Atas Nama Rekening / Akun E-Wallet Penjual',
            'payout_account_number': 'Nomor Rekening / No. HP E-Wallet',
            'image': 'Upload Foto dari Galeri/Perangkat (Disarankan)',
            'image_url': 'Atau Masukkan URL Foto Eksternal',
        }

