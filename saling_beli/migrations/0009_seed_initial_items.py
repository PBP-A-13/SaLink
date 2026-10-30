import sys
from django.db import migrations


# ==============================================================================
# DAFTAR DATA BARANG AWAL (SEED DATA) SALING BELI
# ------------------------------------------------------------------------------
# Anda bebas menambah, mengubah, atau menghapus item di dalam list SEED_ITEMS ini.
# Format tiap item:
# {
#     'title': 'Nama Barang',
#     'description': 'Deskripsi kondisi barang...',
#     'category': 'BOOKS',  # Pilihan: 'FURNITURE', 'ELECTRONICS', 'BOOKS', 'CLOTHING', 'KITCHEN', 'OTHER'
#     'condition': 'GOOD',  # Pilihan: 'BRAND_NEW', 'LIKE_NEW', 'GOOD', 'FAIR'
#     'is_free': False,     # True jika barang dibagikan gratis (Rp0), False jika dijual
#     'price': 50000,       # Harga barang dalam rupiah (isikan 0 jika is_free: True)
#     'image_url': 'https://...',  # Link gambar online (atau None jika tanpa gambar)
#     'pickup_location': 'Perpustakaan Pusat UI',  # Titik temu COD kampus
#     'payout_method': 'Bank BCA',  # Pilihan transfer: 'Bank BCA', 'Mandiri', 'GoPay', dll
#     'payout_account_name': 'Nama Pemilik Rekening',
#     'payout_account_number': '1234567890',
#     'status': 'AVAILABLE',  # 'AVAILABLE' (tersedia) atau 'RESERVED' (sedang dipesan)
#     'seller_username': 'salink_seller',  # Username pemilik barang
# }
# ==============================================================================
SEED_ITEMS = [
    # Contoh template barang 1 (Silakan ganti dengan data barang Anda):
    {
        'title': 'Waters of Maluku by Project 1945 ',
        'description': 'A popular unisex fragrance inspired by the maritime heritage and fresh coastal waters of Maluku',
        'category': 'OTHER',
        'condition': 'LIKE_NEW',
        'is_free': False,
        'price': 160000,
        'image_url': "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRJP0_d431uqOfaHRon_JhZBPztW0g3tYf0a26hGxZgSQ&s=10",
        'pickup_location': 'Kantin Pacil UI',
        'payout_method': 'Bank BTN',
        'payout_account_name': 'Zetian Phoenix',
        'payout_account_number': '1234567890',
        'status': 'AVAILABLE',
        'seller_username': 'zetian',
    },
    # Contoh template barang 2 (Gratis / Hibah):
    {
        'title': 'Dipan Kasur 200x200 cm',
        'description': 'Dihibahkan gratis untuk mahasiswa yang membutuhkan. Sudah lulus, jadi ga dibawa lagi',
        'category': 'FURNITURE',
        'condition': 'FAIR',
        'is_free': True,
        'price': 0,
        'image_url': "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRGUzMMOVKV5ssDEr_9udkEZgLSkt-CwTdfhBflLlADfg&s=10",
        'pickup_location': 'Kutek/Kukel, sesuaiin nanti',
        'payout_method': '',
        'payout_account_name': '',
        'payout_account_number': '',
        'status': 'AVAILABLE',
        'seller_username': 'januardi',
    },
    {
        'title': 'Kalkulator Casio fx-991EX',
        'description': ' 552 fungsi (termasuk trigonometri, logaritma, statistik, matriks hingga 4x4, vektor, integral, dan diferensial). High-Resolution LCD dengan tampilan Natural Textbook Display (menampilkan rumus seperti penulisan di buku pelajaran). Fitur Spreadsheet: Mendukung pembuatan tabel ukuran 5 kolom × 45 baris. Sumber Tenaga: Tenaga ganda (Dual Power), yaitu baterai (LR44) dan tenaga surya (solar).Integrasi QR Code: Dapat menghasilkan QR code untuk visualisasi grafik atau data secara online menggunakan layanan Casio ClassPad. Dimensi & Berat: Ukuran 77 x 165.5 x 11.1 mm dengan berat sekitar 90 gram.',
        'category': 'ELECTRONICS',
        'condition': 'GOOD',
        'is_free': False,
        'price': 190000,
        'image_url': "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQCQlcZQZbvKLYD-olQ17boc4wKNY2EOuanNBlJyRdFhA&s=10",
        'pickup_location': 'Dallas FMIPA',
        'payout_method': 'Bank BCA',
        'payout_account_name': 'Balqis Raihana',
        'payout_account_number': '1234567890',
        'status': 'AVAILABLE',
        'seller_username': 'balqis',
    },
    {
        'title': 'Tripod Sony VCT-P300',
        'description': 'Bawaan Anda ringan tanpa harus kehilangan platform kokoh untuk kamera dengan lensa yang dapat ditukar dan kamera Anda lainnya. Tripod VCT-P300 yang sangat ringkas, ringan, dan kuat ini dapat dimasukkan ke dalam tas Anda dengan mudah, dan bahkan dapat digunakan untuk mendudukkan kamera dengan lensa zoom besar. Dengan kepalanya yang fleksibel dan rentang ketinggiannya yang bervariasi, tripod ringkas ini ideal bagi siapa saja yang ingin praktis dalam mengambil gambar tak bergerak.',
        'category': 'ELECTRONICS',
        'condition': 'GOOD',
        'is_free': False,
        'price': 199999,
        'image_url': "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSFXiVZvr966nQAF1DaBPnSxAIx4vFYSgh5wo4qN401Zw&s=10",
        'pickup_location': 'Kanmer FH',
        'payout_method': 'Bank Mandiri',
        'payout_account_name': 'Cruella Deville',
        'payout_account_number': '1234567890',
        'status': 'AVAILABLE',
        'seller_username': 'cruel_ella',
    },
]


def seed_saling_beli_data(apps, schema_editor):
    db_name = str(schema_editor.connection.settings_dict.get('NAME', ''))
    if 'test' in sys.argv or db_name.startswith('test_') or ':memory:' in db_name:
        return

    User = apps.get_model('auth', 'User')
    ItemListing = apps.get_model('saling_beli', 'ItemListing')

    for item_data in SEED_ITEMS:
        title = item_data.get('title')
        if not title:
            continue

        seller_username = item_data.get('seller_username', 'salink_seller')
        seller, _ = User.objects.get_or_create(
            username=seller_username,
            defaults={
                'email': f'{seller_username}@salink.ui.ac.id',
                'first_name': 'Penjual',
                'last_name': 'SaLink',
            }
        )

        is_free = bool(item_data.get('is_free', False))
        price = 0 if is_free else item_data.get('price', 0)

        # Gunakan update_or_create berdasarkan title agar idempoten dan tidak menduplikasi data
        ItemListing.objects.update_or_create(
            title=title,
            defaults={
                'user': seller,
                'description': item_data.get('description', ''),
                'category': item_data.get('category', 'OTHER'),
                'condition': item_data.get('condition', 'GOOD'),
                'is_free': is_free,
                'price': price,
                'image_url': item_data.get('image_url') or None,
                'pickup_location': item_data.get('pickup_location', 'Perpustakaan Pusat UI'),
                'payout_method': item_data.get('payout_method', 'Bank BCA'),
                'payout_account_name': item_data.get('payout_account_name', ''),
                'payout_account_number': item_data.get('payout_account_number', ''),
                'status': item_data.get('status', 'AVAILABLE'),
            }
        )


def reverse_seed_data(apps, schema_editor):
    db_name = str(schema_editor.connection.settings_dict.get('NAME', ''))
    if 'test' in sys.argv or db_name.startswith('test_') or ':memory:' in db_name:
        return

    ItemListing = apps.get_model('saling_beli', 'ItemListing')
    titles = [item.get('title') for item in SEED_ITEMS if item.get('title')]
    if titles:
        ItemListing.objects.filter(title__in=titles).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('saling_beli', '0008_order_confirmations_and_unique_active_item'),
    ]

    operations = [
        migrations.RunPython(seed_saling_beli_data, reverse_seed_data),
    ]

