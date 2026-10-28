from django import forms
from .models import ItemListing


class ItemListingForm(forms.ModelForm):
    """Form untuk input dan validasi barang prelove atau gratis dari penjual/pemberi."""
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
        label='Bank / E-Wallet Penjual',
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
                'id': 'id_price',
                'min': '0',
                'step': '1000',
                'placeholder': 'Contoh: 50000',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 4,
                'placeholder': 'Ceritakan kondisi fisik barang, alasan jual, atau kelengkapan...',
                'required': True,
            }),
            'pickup_location': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Contoh: Perpusat UI / Kantin Dallas / Balairung',
                'required': True,
            }),
            'payout_account_name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Nama pemilik rekening / akun e-wallet penjual',
            }),
            'payout_account_number': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Nomor rekening atau nomor handphone e-wallet',
            }),
            'image': forms.FileInput(attrs={
                'class': 'form-file-input',
                'accept': 'image/*',
            }),
            'image_url': forms.URLInput(attrs={
                'class': 'form-input',
                'placeholder': 'https://example.com/foto-barang.jpg (Opsional jika upload foto)',
            }),
        }
        labels = {
            'title': 'Judul Barang',
            'category': 'Kategori Barang',
            'condition': 'Kondisi Fisik',
            'is_free': 'Bagikan Secara Gratis (Rp0)?',
            'price': 'Harga (Rp)',
            'description': 'Deskripsi Lengkap',
            'pickup_location': 'Titik Temu COD',
            'payout_account_name': 'Nama Pemilik Rekening / Akun E-Wallet',
            'payout_account_number': 'Nomor Rekening / No. HP E-Wallet Penjual',
            'image': 'Upload Foto Barang (Dari Perangkat)',
            'image_url': 'Atau URL Foto Eksternal (Opsional)',
        }

    def clean(self):
        """Validasi logika: jika gratis maka harga = 0, jika berbayar wajib isi rekening pembayaran."""
        cleaned_data = super().clean()
        is_free = cleaned_data.get('is_free')
        price = cleaned_data.get('price')
        payout_number = cleaned_data.get('payout_account_number')

        if is_free:
            cleaned_data['price'] = 0
        else:
            if price is None or price <= 0:
                self.add_error('price', 'Untuk barang berbayar, harga harus lebih dari 0.')
            if not payout_number:
                self.add_error('payout_account_number', 'Nomor rekening/e-wallet penjual wajib diisi sebagai tujuan transfer pembeli.')

        return cleaned_data
