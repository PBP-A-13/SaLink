from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from .models import BorrowItem, BorrowRequest

Status = BorrowRequest.Status


def hari(offset):
    """Tanggal relatif dari hari ini, biar tes tidak kedaluwarsa."""
    return date.today() + timedelta(days=offset)


class PinjamAPITestCase(TestCase):
    """
    Dasar tes web service. Kliennya meniru aplikasi Flutter: login lewat session,
    mengirim JSON, dan tidak membawa token CSRF.
    """

    def setUp(self):
        self.pemilik = User.objects.create_user('pemilik', password='rahasia123')
        self.peminjam = User.objects.create_user('peminjam', password='rahasia123')
        self.lain = User.objects.create_user('lain', password='rahasia123')
        self.item = BorrowItem.objects.create(
            owner=self.pemilik,
            name='Jas Lab Kimia',
            description='Ukuran L, bersih',
            category=BorrowItem.Category.ACADEMIC,
            max_duration_days=3,
            deposit_fee=50000,
        )
        self.client = APIClient(enforce_csrf_checks=True)

    def login(self, user):
        self.client.force_login(user)

    def post_json(self, url, data=None):
        return self.client.post(url, data or {}, format='json')

    def buat_pengajuan(self, mulai=1, selesai=2, status=Status.PENDING, peminjam=None, item=None):
        return BorrowRequest.objects.create(
            item=item or self.item,
            borrower=peminjam or self.peminjam,
            start_date=hari(mulai),
            end_date=hari(selesai),
            status=status,
        )


class DaftarBarangTests(PinjamAPITestCase):
    url = '/saling-pinjam/api/items/'

    def test_tamu_bisa_melihat_daftar_barang(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['status'], 'success')
        self.assertEqual(len(body['data']), 1)
        barang = body['data'][0]
        self.assertEqual(barang['name'], 'Jas Lab Kimia')
        self.assertEqual(barang['owner'], 'pemilik')
        self.assertEqual(barang['deposit_fee'], 50000)
        self.assertEqual(barang['category_display'], BorrowItem.Category.ACADEMIC.label)
        self.assertFalse(barang['is_owner'])

    def test_header_menyebut_utf8_dan_huruf_non_ascii_utuh(self):
        BorrowItem.objects.create(owner=self.lain, name='Café Kit ☕', description='x')

        response = self.client.get(self.url, {'q': 'café'})

        self.assertEqual(response['Content-Type'], 'application/json; charset=utf-8')
        self.assertIn('Café Kit ☕'.encode('utf-8'), response.content)

    def test_pemilik_ditandai_is_owner(self):
        self.login(self.pemilik)

        barang = self.client.get(self.url).json()['data'][0]

        self.assertTrue(barang['is_owner'])

    def test_filter_kategori_dan_kata_kunci(self):
        BorrowItem.objects.create(
            owner=self.lain, name='Koper Besar', description='Muat banyak',
            category=BorrowItem.Category.TRAVEL,
        )

        kategori = self.client.get(self.url, {'category': 'TRAVEL'}).json()['data']
        kata = self.client.get(self.url, {'q': 'jas'}).json()['data']

        self.assertEqual([b['name'] for b in kategori], ['Koper Besar'])
        self.assertEqual([b['name'] for b in kata], ['Jas Lab Kimia'])

    def test_filter_tanggal_hanya_menampilkan_barang_yang_bebas(self):
        terkunci = BorrowItem.objects.create(owner=self.lain, name='Kalkulator', description='Casio')
        mati = BorrowItem.objects.create(
            owner=self.lain, name='Kabel', description='Panjang', status=BorrowItem.Status.UNAVAILABLE
        )
        BorrowRequest.objects.create(
            item=terkunci, borrower=self.peminjam,
            start_date=hari(1), end_date=hari(3), status=Status.APPROVED,
        )

        bebas = self.client.get(self.url, {'tanggal': hari(2).isoformat()}).json()['data']
        nama = [b['name'] for b in bebas]

        self.assertIn('Jas Lab Kimia', nama)
        self.assertNotIn('Kalkulator', nama)
        self.assertNotIn('Kabel', nama)

    def test_pengajuan_menunggu_tidak_mengunci_tanggal(self):
        self.buat_pengajuan(mulai=1, selesai=3, status=Status.PENDING)

        bebas = self.client.get(self.url, {'tanggal': hari(2).isoformat()}).json()['data']

        self.assertEqual(len(bebas), 1)

    def test_filter_tanggal_menyembunyikan_barang_milik_sendiri(self):
        self.login(self.pemilik)

        data = self.client.get(self.url, {'tanggal': hari(2).isoformat()}).json()['data']

        self.assertEqual(data, [])

    def test_tanggal_tidak_valid_ditolak(self):
        response = self.client.get(self.url, {'tanggal': '20-11-2026'})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['status'], 'error')
        self.assertIn('YYYY-MM-DD', response.json()['message'])


class DetailBarangTests(PinjamAPITestCase):
    def url(self, item=None):
        return f'/saling-pinjam/api/items/{(item or self.item).id}/'

    def test_detail_memuat_tanggal_terkunci_saja(self):
        self.buat_pengajuan(mulai=2, selesai=4, status=Status.APPROVED, peminjam=self.peminjam)
        self.buat_pengajuan(mulai=6, selesai=7, status=Status.PENDING, peminjam=self.lain)
        self.buat_pengajuan(mulai=-10, selesai=-8, status=Status.RETURNED, peminjam=self.lain)

        data = self.client.get(self.url()).json()['data']

        self.assertEqual(
            data['booked_ranges'],
            [{'start_date': hari(2).isoformat(), 'end_date': hari(4).isoformat()}],
        )
        self.assertIsNone(data['my_active_request'])
        self.assertNotIn('locked_count', data)

    def test_peminjam_melihat_pengajuan_aktifnya(self):
        pengajuan = self.buat_pengajuan()
        self.login(self.peminjam)

        data = self.client.get(self.url()).json()['data']

        self.assertEqual(data['my_active_request']['id'], str(pengajuan.id))

    def test_pemilik_melihat_jumlah_pengajuan(self):
        self.buat_pengajuan(mulai=1, selesai=2, status=Status.APPROVED)
        self.buat_pengajuan(mulai=5, selesai=6, status=Status.PENDING, peminjam=self.lain)
        self.login(self.pemilik)

        data = self.client.get(self.url()).json()['data']

        self.assertEqual(data['locked_count'], 1)
        self.assertEqual(data['pending_count'], 1)
        self.assertIsNone(data['my_active_request'])

    def test_barang_tidak_ada(self):
        response = self.client.get('/saling-pinjam/api/items/00000000-0000-0000-0000-000000000000/')

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {'status': 'error', 'message': 'Barang tidak ditemukan.'})


class TambahBarangTests(PinjamAPITestCase):
    url = '/saling-pinjam/api/items/'
    isian = {
        'name': 'Carrier 60L',
        'description': 'Lengkap dengan rain cover',
        'category': 'TRAVEL',
        'condition': 'GOOD',
        'max_duration_days': 5,
        'deposit_fee': 100000,
        'pickup_location': 'Stasiun UI',
        'image_url': 'https://example.com/carrier.jpg',
    }

    def test_tamu_harus_login(self):
        response = self.post_json(self.url, self.isian)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {'status': 'error', 'message': 'Silakan login dulu.'})
        self.assertEqual(BorrowItem.objects.count(), 1)

    def test_berhasil_tanpa_token_csrf(self):
        self.login(self.peminjam)

        response = self.post_json(self.url, self.isian)

        self.assertEqual(response.status_code, 201)
        data = response.json()['data']
        self.assertEqual(data['owner'], 'peminjam')
        self.assertTrue(data['is_owner'])
        self.assertEqual(data['status'], 'AVAILABLE')
        self.assertTrue(BorrowItem.objects.filter(name='Carrier 60L', owner=self.peminjam).exists())

    def test_owner_dan_status_dari_aplikasi_diabaikan(self):
        self.login(self.peminjam)

        response = self.post_json(
            self.url, {**self.isian, 'owner': 'pemilik', 'status': 'UNAVAILABLE'}
        )

        self.assertEqual(response.status_code, 201)
        barang = BorrowItem.objects.get(name='Carrier 60L')
        self.assertEqual(barang.owner, self.peminjam)
        self.assertEqual(barang.status, BorrowItem.Status.AVAILABLE)

    def test_gambar_dan_jaminan_boleh_dikosongkan(self):
        self.login(self.peminjam)
        isian = {k: v for k, v in self.isian.items() if k not in ('image_url', 'deposit_fee')}

        response = self.post_json(self.url, isian)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['data']['deposit_fee'], 0)

    def test_isian_salah_dijelaskan_per_field(self):
        self.login(self.peminjam)

        response = self.post_json(self.url, {
            'name': '',
            'description': 'ok',
            'max_duration_days': 0,
            'deposit_fee': -5,
            'image_url': 'bukan-link',
        })

        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertEqual(body['status'], 'error')
        self.assertEqual(body['errors']['name'], ['Bagian ini wajib diisi.'])
        self.assertEqual(body['errors']['max_duration_days'], ['Minimal 1 hari.'])
        self.assertEqual(body['errors']['deposit_fee'], ['Uang jaminan tidak boleh minus.'])
        self.assertEqual(body['errors']['image_url'], ['Link tidak valid. Pastikan diawali https://'])
        self.assertEqual(BorrowItem.objects.count(), 1)

    def test_pilihan_kategori_tidak_dikenal(self):
        self.login(self.peminjam)

        response = self.post_json(self.url, {**self.isian, 'category': 'MOBIL'})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['errors']['category'], ['Pilihan kategori tidak valid.'])

    def test_body_bukan_json_ditolak(self):
        self.login(self.peminjam)

        response = self.client.post(self.url, self.isian)  # form biasa, bukan JSON

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['message'], 'Request harus berformat JSON.')
        self.assertEqual(BorrowItem.objects.count(), 1)


class UbahBarangTests(PinjamAPITestCase):
    def url(self):
        return f'/saling-pinjam/api/items/{self.item.id}/update/'

    def test_pemilik_boleh_mengubah_sebagian_field(self):
        self.login(self.pemilik)

        response = self.post_json(self.url(), {'max_duration_days': 7})

        self.assertEqual(response.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(self.item.max_duration_days, 7)
        self.assertEqual(self.item.name, 'Jas Lab Kimia')

    def test_bukan_pemilik_ditolak(self):
        self.login(self.lain)

        response = self.post_json(self.url(), {'name': 'Dibajak'})

        self.assertEqual(response.status_code, 403)
        self.item.refresh_from_db()
        self.assertEqual(self.item.name, 'Jas Lab Kimia')

    def test_tamu_harus_login(self):
        response = self.post_json(self.url(), {'name': 'Dibajak'})

        self.assertEqual(response.status_code, 403)

    def test_isian_salah(self):
        self.login(self.pemilik)

        response = self.post_json(self.url(), {'name': ''})

        self.assertEqual(response.status_code, 400)
        self.assertIn('name', response.json()['errors'])

    def test_barang_tidak_ada(self):
        self.login(self.pemilik)

        response = self.post_json('/saling-pinjam/api/items/00000000-0000-0000-0000-000000000000/update/', {})

        self.assertEqual(response.status_code, 404)


class HapusBarangTests(PinjamAPITestCase):
    def url(self):
        return f'/saling-pinjam/api/items/{self.item.id}/delete/'

    def test_pemilik_menghapus_barang_dan_pengajuan_menunggunya(self):
        self.buat_pengajuan(status=Status.PENDING)
        self.login(self.pemilik)

        response = self.post_json(self.url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['message'], 'Barang "Jas Lab Kimia" sudah dihapus.')
        self.assertFalse(BorrowItem.objects.filter(id=self.item.id).exists())
        self.assertEqual(BorrowRequest.objects.count(), 0)

    def test_barang_yang_dikunci_tidak_bisa_dihapus(self):
        self.buat_pengajuan(status=Status.APPROVED)
        self.login(self.pemilik)

        response = self.post_json(self.url())

        self.assertEqual(response.status_code, 409)
        self.assertTrue(BorrowItem.objects.filter(id=self.item.id).exists())

    def test_bukan_pemilik_ditolak(self):
        self.login(self.lain)

        response = self.post_json(self.url())

        self.assertEqual(response.status_code, 403)
        self.assertTrue(BorrowItem.objects.filter(id=self.item.id).exists())


class AjukanPinjamTests(PinjamAPITestCase):
    def url(self, item=None):
        return f'/saling-pinjam/api/items/{(item or self.item).id}/request/'

    def isian(self, mulai=1, selesai=2, **extra):
        return {'start_date': hari(mulai).isoformat(), 'end_date': hari(selesai).isoformat(), **extra}

    def test_berhasil(self):
        self.login(self.peminjam)

        response = self.post_json(self.url(), self.isian(notes='Untuk praktikum'))

        self.assertEqual(response.status_code, 201)
        data = response.json()['data']
        self.assertEqual(data['status'], 'PENDING')
        self.assertEqual(data['borrower'], 'peminjam')
        self.assertEqual(data['notes'], 'Untuk praktikum')
        self.assertEqual(data['item']['name'], 'Jas Lab Kimia')
        self.assertTrue(data['can_cancel'])
        self.assertEqual(data['next_statuses'], ['APPROVED', 'REJECTED'])
        self.assertEqual(BorrowRequest.objects.count(), 1)

    def test_tamu_harus_login(self):
        response = self.post_json(self.url(), self.isian())

        self.assertEqual(response.status_code, 403)

    def test_tidak_boleh_meminjam_barang_sendiri(self):
        self.login(self.pemilik)

        response = self.post_json(self.url(), self.isian())

        self.assertEqual(response.status_code, 403)
        self.assertEqual(BorrowRequest.objects.count(), 0)

    def test_barang_tidak_tersedia(self):
        self.item.status = BorrowItem.Status.UNAVAILABLE
        self.item.save()
        self.login(self.peminjam)

        response = self.post_json(self.url(), self.isian())

        self.assertEqual(response.status_code, 409)

    def test_pengajuan_aktif_untuk_barang_sama_ditolak(self):
        self.buat_pengajuan()
        self.login(self.peminjam)

        response = self.post_json(self.url(), self.isian(mulai=5, selesai=6))

        self.assertEqual(response.status_code, 409)
        self.assertIn('sudah punya pengajuan aktif', response.json()['message'])

    def test_slot_pinjaman_penuh(self):
        for nama in ('Kabel', 'Adapter'):
            barang = BorrowItem.objects.create(owner=self.lain, name=nama, description='x')
            self.buat_pengajuan(item=barang)
        self.login(self.peminjam)

        response = self.post_json(self.url(), self.isian())

        self.assertEqual(response.status_code, 409)
        self.assertIn('Slot pinjaman kamu penuh', response.json()['message'])

    def test_pengajuan_yang_sudah_selesai_tidak_memakai_slot(self):
        for nama in ('Kabel', 'Adapter'):
            barang = BorrowItem.objects.create(owner=self.lain, name=nama, description='x')
            self.buat_pengajuan(item=barang, status=Status.RETURNED)
        self.login(self.peminjam)

        response = self.post_json(self.url(), self.isian())

        self.assertEqual(response.status_code, 201)

    def test_tanggal_mulai_sudah_lewat(self):
        self.login(self.peminjam)

        response = self.post_json(self.url(), self.isian(mulai=-1, selesai=1))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()['errors']['start_date'], ['Tanggal mulai tidak boleh sebelum hari ini.']
        )

    def test_tanggal_kembali_mendahului_tanggal_mulai(self):
        self.login(self.peminjam)

        response = self.post_json(self.url(), self.isian(mulai=3, selesai=2))

        self.assertEqual(response.status_code, 400)
        self.assertIn('end_date', response.json()['errors'])

    def test_melebihi_batas_hari(self):
        self.login(self.peminjam)

        response = self.post_json(self.url(), self.isian(mulai=1, selesai=4))  # 4 hari, batasnya 3

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()['errors']['end_date'], ['Barang ini maksimal dipinjam 3 hari.']
        )

    def test_batas_hari_pas_masih_boleh(self):
        self.login(self.peminjam)

        response = self.post_json(self.url(), self.isian(mulai=1, selesai=3))  # tepat 3 hari

        self.assertEqual(response.status_code, 201)

    def test_bentrok_dengan_pinjaman_yang_sudah_disetujui(self):
        self.buat_pengajuan(mulai=2, selesai=3, status=Status.APPROVED, peminjam=self.lain)
        self.login(self.peminjam)

        response = self.post_json(self.url(), self.isian(mulai=3, selesai=4))

        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertIn('sudah dipinjam orang lain', body['message'])
        self.assertIn('non_field_errors', body['errors'])

    def test_tanggal_wajib_diisi_dan_formatnya_diperiksa(self):
        self.login(self.peminjam)

        kosong = self.post_json(self.url(), {})
        ngawur = self.post_json(self.url(), {'start_date': '1 Desember', 'end_date': '2 Desember'})

        self.assertEqual(kosong.status_code, 400)
        self.assertEqual(kosong.json()['errors']['start_date'], ['Bagian ini wajib diisi.'])
        self.assertEqual(
            ngawur.json()['errors']['start_date'], ['Format tanggal tidak valid (YYYY-MM-DD).']
        )


class PinjamanSayaTests(PinjamAPITestCase):
    url = '/saling-pinjam/api/my-borrows/'

    def test_tamu_harus_login(self):
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_isi_dipisah_sesuai_peran(self):
        dari_peminjam = self.buat_pengajuan(status=Status.APPROVED)
        BorrowRequest.objects.create(
            item=BorrowItem.objects.create(owner=self.lain, name='Kabel', description='x'),
            borrower=self.pemilik, start_date=hari(1), end_date=hari(2),
        )

        sebagai_pemilik = self.client
        self.login(self.pemilik)
        data = sebagai_pemilik.get(self.url).json()['data']

        self.assertEqual([r['id'] for r in data['as_owner']], [str(dari_peminjam.id)])
        self.assertEqual(data['as_owner'][0]['borrower'], 'peminjam')
        self.assertEqual(data['as_owner'][0]['next_statuses'], ['ONGOING'])
        self.assertEqual(len(data['as_borrower']), 1)
        self.assertEqual(data['as_borrower'][0]['item']['name'], 'Kabel')
        self.assertEqual([i['name'] for i in data['my_items']], ['Jas Lab Kimia'])
        self.assertEqual(data['active_count'], 1)
        self.assertEqual(data['max_active'], 2)

    def test_slot_aktif_tidak_menghitung_yang_sudah_selesai(self):
        self.buat_pengajuan(status=Status.RETURNED)
        self.login(self.peminjam)

        data = self.client.get(self.url).json()['data']

        self.assertEqual(data['active_count'], 0)
        self.assertEqual(len(data['as_borrower']), 1)


class BatalkanPengajuanTests(PinjamAPITestCase):
    def url(self, pengajuan):
        return f'/saling-pinjam/api/requests/{pengajuan.id}/cancel/'

    def test_peminjam_membatalkan_pengajuan_menunggu_atau_disetujui(self):
        self.login(self.peminjam)
        for status in (Status.PENDING, Status.APPROVED):
            pengajuan = self.buat_pengajuan(status=status, mulai=10, selesai=11)

            response = self.post_json(self.url(pengajuan))

            self.assertEqual(response.status_code, 200)
            pengajuan.refresh_from_db()
            self.assertEqual(pengajuan.status, Status.CANCELLED)
            pengajuan.delete()

    def test_pengajuan_yang_sudah_berlangsung_tidak_bisa_dibatalkan(self):
        pengajuan = self.buat_pengajuan(status=Status.ONGOING)
        self.login(self.peminjam)

        response = self.post_json(self.url(pengajuan))

        self.assertEqual(response.status_code, 409)
        pengajuan.refresh_from_db()
        self.assertEqual(pengajuan.status, Status.ONGOING)

    def test_pengajuan_orang_lain_tidak_ketemu(self):
        pengajuan = self.buat_pengajuan()
        self.login(self.lain)

        response = self.post_json(self.url(pengajuan))

        self.assertEqual(response.status_code, 404)
        pengajuan.refresh_from_db()
        self.assertEqual(pengajuan.status, Status.PENDING)


class UbahStatusPengajuanTests(PinjamAPITestCase):
    def url(self, pengajuan):
        return f'/saling-pinjam/api/requests/{pengajuan.id}/status/'

    def ubah(self, pengajuan, status):
        return self.post_json(self.url(pengajuan), {'status': status})

    def test_alur_lengkap_dari_menunggu_sampai_dikembalikan(self):
        pengajuan = self.buat_pengajuan()
        self.login(self.pemilik)

        self.assertEqual(self.ubah(pengajuan, 'APPROVED').status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, BorrowItem.Status.AVAILABLE)  # belum diambil

        self.assertEqual(self.ubah(pengajuan, 'ONGOING').status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, BorrowItem.Status.BORROWED)

        response = self.ubah(pengajuan, 'RETURNED')
        self.assertEqual(response.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, BorrowItem.Status.AVAILABLE)
        pengajuan.refresh_from_db()
        self.assertEqual(pengajuan.status, Status.RETURNED)
        self.assertEqual(response.json()['data']['request']['next_statuses'], [])

    def test_menyetujui_menolak_otomatis_pengajuan_menunggu_yang_bentrok(self):
        utama = self.buat_pengajuan(mulai=1, selesai=3)
        bentrok = self.buat_pengajuan(mulai=2, selesai=4, peminjam=self.lain)
        aman = self.buat_pengajuan(
            mulai=10, selesai=11, peminjam=User.objects.create_user('ketiga', password='x')
        )
        self.login(self.pemilik)

        response = self.ubah(utama, 'APPROVED')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data']['auto_rejected'], 1)
        self.assertIn('1 pengajuan lain', response.json()['message'])
        bentrok.refresh_from_db()
        aman.refresh_from_db()
        self.assertEqual(bentrok.status, Status.REJECTED)
        self.assertEqual(aman.status, Status.PENDING)

    def test_menolak(self):
        pengajuan = self.buat_pengajuan()
        self.login(self.pemilik)

        self.assertEqual(self.ubah(pengajuan, 'REJECTED').status_code, 200)

        pengajuan.refresh_from_db()
        self.assertEqual(pengajuan.status, Status.REJECTED)

    def test_loncat_status_ditolak(self):
        pengajuan = self.buat_pengajuan()
        self.login(self.pemilik)

        response = self.ubah(pengajuan, 'ONGOING')  # harus disetujui dulu

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['message'], 'Status tidak valid.')
        pengajuan.refresh_from_db()
        self.assertEqual(pengajuan.status, Status.PENDING)

    def test_status_ngawur_ditolak(self):
        pengajuan = self.buat_pengajuan()
        self.login(self.pemilik)

        response = self.ubah(pengajuan, 'SELESAI')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['message'], 'Status tidak valid.')

    def test_hanya_pemilik_barang_yang_boleh(self):
        pengajuan = self.buat_pengajuan()
        for pengguna in (self.peminjam, self.lain):
            self.login(pengguna)

            response = self.ubah(pengajuan, 'APPROVED')

            self.assertEqual(response.status_code, 404)
        pengajuan.refresh_from_db()
        self.assertEqual(pengajuan.status, Status.PENDING)

    def test_tamu_harus_login(self):
        pengajuan = self.buat_pengajuan()

        self.assertEqual(self.ubah(pengajuan, 'APPROVED').status_code, 403)

    def test_tidak_bisa_menyetujui_kalau_bentrok_dengan_yang_sudah_disetujui(self):
        self.buat_pengajuan(mulai=1, selesai=3, status=Status.APPROVED, peminjam=self.lain)
        pengajuan = self.buat_pengajuan(mulai=2, selesai=4)
        self.login(self.pemilik)

        response = self.ubah(pengajuan, 'APPROVED')

        self.assertEqual(response.status_code, 409)
        self.assertIn('bentrok', response.json()['message'])
        pengajuan.refresh_from_db()
        self.assertEqual(pengajuan.status, Status.PENDING)

    def test_tidak_bisa_menyetujui_barang_yang_dinonaktifkan(self):
        pengajuan = self.buat_pengajuan()
        self.item.status = BorrowItem.Status.UNAVAILABLE
        self.item.save()
        self.login(self.pemilik)

        response = self.ubah(pengajuan, 'APPROVED')

        self.assertEqual(response.status_code, 409)


class AturanSamaDenganWebTests(PinjamAPITestCase):
    """Alur status di API dan di situs web harus tetap sama."""

    def test_next_statuses_mengikuti_alur_di_views(self):
        from .views import ALLOWED_TRANSITIONS

        self.login(self.pemilik)
        for status, tujuan in ALLOWED_TRANSITIONS.items():
            self.buat_pengajuan(
                status=status,
                mulai=20 + len(tujuan),
                selesai=21 + len(tujuan),
                peminjam=User.objects.create_user(f'u-{status}-{len(tujuan)}', password='x'),
            )

        data = self.client.get('/saling-pinjam/api/my-borrows/').json()['data']
        hasil = {r['status']: r['next_statuses'] for r in data['as_owner']}

        for status, tujuan in ALLOWED_TRANSITIONS.items():
            self.assertEqual(hasil[status.value], [t.value for t in tujuan])

    def test_halaman_web_tetap_jalan(self):
        # DRF terpasang di project, pastikan halaman HTML lama tidak ikut berubah
        self.assertEqual(self.client.get(reverse('saling_pinjam:item_list')).status_code, 200)
        self.assertEqual(
            self.client.get(reverse('saling_pinjam:item_detail', args=[self.item.id])).status_code, 200
        )