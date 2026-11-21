from datetime import date, timedelta
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from saling_pinjam.models import BorrowItem, BorrowRequest


class SalingPinjamTwoWayHandoverTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='pemilik', password='password123')
        self.borrower = User.objects.create_user(username='peminjam', password='password123')
        self.stranger = User.objects.create_user(username='orang_luar', password='password123')

        self.item = BorrowItem.objects.create(
            owner=self.owner,
            name='Kamera Mirrorless Sony A6000',
            description='Kamera mulus untuk dokumentasi acara kampus.',
            category='ELECTRONICS',
            condition='LIKE_NEW',
            max_duration_days=5,
            deposit_fee=50000,
            pickup_location='Kantin Pacil UI',
            status=BorrowItem.Status.AVAILABLE,
        )

        self.client_owner = APIClient()
        self.client_owner.force_authenticate(user=self.owner)

        self.client_borrower = APIClient()
        self.client_borrower.force_authenticate(user=self.borrower)

        self.client_stranger = APIClient()
        self.client_stranger.force_authenticate(user=self.stranger)

    def test_item_list_and_detail_api(self):
        resp = self.client_borrower.get('/saling-pinjam/api/items/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['data']), 1)

        resp_detail = self.client_borrower.get(f'/saling-pinjam/api/items/{self.item.id}/')
        self.assertEqual(resp_detail.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_detail.data['data']['name'], 'Kamera Mirrorless Sony A6000')

    def test_borrow_request_lifecycle_and_two_way_handover(self):
        # 1. Borrower mengajukan pinjaman
        start = date.today()
        end = start + timedelta(days=3)
        payload = {
            'start_date': start.isoformat(),
            'end_date': end.isoformat(),
            'notes': 'Butuh untuk meliput dies natalis.',
        }
        resp_req = self.client_borrower.post(f'/saling-pinjam/api/items/{self.item.id}/request/', payload, format='json')
        self.assertEqual(resp_req.status_code, status.HTTP_201_CREATED)
        request_id = resp_req.data['data']['id']

        # 2. Owner menyetujui pengajuan (APPROVED)
        resp_approve = self.client_owner.post(
            f'/saling-pinjam/api/requests/{request_id}/status/',
            {'status': 'APPROVED'},
            format='json'
        )
        self.assertEqual(resp_approve.status_code, status.HTTP_200_OK)

        borrow_req = BorrowRequest.objects.get(id=request_id)
        self.assertEqual(borrow_req.status, BorrowRequest.Status.APPROVED)

        # 3. Orang luar mencoba konfirmasi serah-terima -> 403 Forbidden
        resp_stranger = self.client_stranger.post(
            f'/saling-pinjam/api/requests/{request_id}/confirm-handover/',
            format='json'
        )
        self.assertEqual(resp_stranger.status_code, status.HTTP_403_FORBIDDEN)

        # 4. Owner konfirmasi serah barang
        resp_owner_handover = self.client_owner.post(
            f'/saling-pinjam/api/requests/{request_id}/confirm-handover/',
            format='json'
        )
        self.assertEqual(resp_owner_handover.status_code, status.HTTP_200_OK)
        borrow_req.refresh_from_db()
        self.assertTrue(borrow_req.owner_handover_confirmed)
        self.assertFalse(borrow_req.borrower_handover_confirmed)
        # Status masih APPROVED karena baru satu pihak
        self.assertEqual(borrow_req.status, BorrowRequest.Status.APPROVED)

        # 5. Borrower konfirmasi terima barang -> status berubah ONGOING & item jadi BORROWED
        resp_borrower_handover = self.client_borrower.post(
            f'/saling-pinjam/api/requests/{request_id}/confirm-handover/',
            format='json'
        )
        self.assertEqual(resp_borrower_handover.status_code, status.HTTP_200_OK)
        borrow_req.refresh_from_db()
        self.item.refresh_from_db()
        self.assertTrue(borrow_req.handover_ready)
        self.assertEqual(borrow_req.status, BorrowRequest.Status.ONGOING)
        self.assertEqual(self.item.status, BorrowItem.Status.BORROWED)

        # 6. Konfirmasi pengembalian dua arah (Return)
        # Borrower konfirmasi mengembalikan barang
        resp_borrower_return = self.client_borrower.post(
            f'/saling-pinjam/api/requests/{request_id}/confirm-return/',
            format='json'
        )
        self.assertEqual(resp_borrower_return.status_code, status.HTTP_200_OK)
        borrow_req.refresh_from_db()
        self.assertTrue(borrow_req.borrower_return_confirmed)
        self.assertFalse(borrow_req.owner_return_confirmed)
        self.assertEqual(borrow_req.status, BorrowRequest.Status.ONGOING)

        # Owner konfirmasi barang diterima kembali -> status jadi RETURNED & item jadi AVAILABLE
        resp_owner_return = self.client_owner.post(
            f'/saling-pinjam/api/requests/{request_id}/confirm-return/',
            format='json'
        )
        self.assertEqual(resp_owner_return.status_code, status.HTTP_200_OK)
        borrow_req.refresh_from_db()
        self.item.refresh_from_db()
        self.assertTrue(borrow_req.return_ready)
        self.assertEqual(borrow_req.status, BorrowRequest.Status.RETURNED)
        self.assertEqual(self.item.status, BorrowItem.Status.AVAILABLE)
        self.assertIsNotNone(borrow_req.actual_return_date)

    def test_cannot_borrow_own_item(self):
        resp = self.client_owner.post(
            f'/saling-pinjam/api/items/{self.item.id}/request/',
            {
                'start_date': date.today().isoformat(),
                'end_date': (date.today() + timedelta(days=1)).isoformat(),
            },
            format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
