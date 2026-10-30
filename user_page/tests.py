from django.contrib.auth.models import User
from django.utils import timezone
from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from saling_tebeng.models import RideBooking, RideOffer, RideSchedule, Vehicle
from user_page.models import SSOIdentity


class UserPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='kampus_user',
            email='user@example.test',
            password='SaLink-test-password-2026',
        )

    def test_anonymous_profile_redirects_to_login(self):
        response = self.client.get(reverse('user_page:profile'))

        self.assertEqual(response.status_code, 302)
        self.assertIn('/akun/login/', response['Location'])
        self.assertIn('next=', response['Location'])

    def test_login_returns_user_to_requested_module(self):
        response = self.client.post(
            f"{reverse('user_page:login')}?next=/saling-pinjam/create/",
            {'username': self.user.username, 'password': 'SaLink-test-password-2026'},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/saling-pinjam/create/')

    def test_module_login_aliases_return_to_their_module(self):
        module_routes = (
            ('saling_beli:login', '/saling-beli/'),
            ('saling_bagi:login', '/saling-bagi/'),
            ('saling_pinjam:login', '/saling-pinjam/'),
        )

        for route_name, module_path in module_routes:
            with self.subTest(route=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 302)
                self.assertIn(f'next={module_path.replace("/", "%2F")}', response['Location'])

    def test_registration_signs_user_in_and_opens_profile(self):
        response = self.client.post(reverse('user_page:register'), {
            'username': 'new_member',
            'email': 'new@example.test',
            'password1': 'SaLink-new-password-2026',
            'password2': 'SaLink-new-password-2026',
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('user_page:profile'))
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_profile_renders_module_activity(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('user_page:profile'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Saling Beli')
        self.assertContains(response, 'Saling Bagi')

    def test_module_login_rejects_external_redirect_target(self):
        response = self.client.get(reverse('saling_beli:login'), {'next': 'https://evil.example/'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/akun/login/', response['Location'])
        self.assertNotIn('evil.example', response['Location'])

    def start_sso_flow(self, mode='login'):
        if mode == 'link':
            url = reverse('user_page:sso_link')
        else:
            url = reverse('user_page:sso_login')

        with patch('user_page.views.get_cas_client') as mock_cas:
            mock_cas.return_value.get_login_url.return_value = (
                'https://sso.ui.ac.id/cas2/login?service=test'
            )

            response = self.client.get(url)

        self.assertEqual(response.status_code, 302)
        self.assertIn('sso.ui.ac.id', response['Location'])

        session = self.client.session
        flows = session['ui_sso_flows']
        state = next(iter(flows))

        return state

    def complete_sso_callback(self, state, subject='ui_student_123'):
        with patch('user_page.views.get_cas_client') as mock_cas:
            mock_cas.return_value.verify_ticket.return_value = (
                subject,
                {},
                None,
            )

            return self.client.get(
                reverse('user_page:sso_callback'),
                {
                    'ticket': 'ST-test-ticket',
                    'state': state,
                },
            )
    
    def test_sso_link_success(self):
        self.client.force_login(self.user)

        state = self.start_sso_flow(mode='link')
        response = self.complete_sso_callback(state)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response['Location'],
            reverse('user_page:profile'),
        )

        identity = SSOIdentity.objects.get(user=self.user)
        self.assertEqual(identity.provider, 'ui')
        self.assertEqual(identity.subject, 'ui_student_123')


    def test_sso_link_rejects_identity_owned_by_another_user(self):
        another_user = User.objects.create_user(
            username='another_user',
            password='Another-test-password-2026',
        )

        SSOIdentity.objects.create(
            user=another_user,
            provider='ui',
            subject='ui_student_123',
        )

        self.client.force_login(self.user)

        state = self.start_sso_flow(mode='link')
        response = self.complete_sso_callback(state)

        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            SSOIdentity.objects.filter(user=self.user).exists()
        )
        self.assertTrue(
            SSOIdentity.objects.filter(
                user=another_user,
                subject='ui_student_123',
            ).exists()
        )


    def test_sso_login_success_for_linked_identity(self):
        SSOIdentity.objects.create(
            user=self.user,
            provider='ui',
            subject='ui_student_123',
        )

        state = self.start_sso_flow(mode='login')
        response = self.complete_sso_callback(state)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response['Location'],
            reverse('user_page:profile'),
        )

        self.assertEqual(
            str(self.client.session['_auth_user_id']),
            str(self.user.pk),
        )


    def test_sso_login_rejects_unlinked_identity(self):
        state = self.start_sso_flow(mode='login')
        response = self.complete_sso_callback(state)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response['Location'],
            reverse('user_page:login'),
        )

        self.assertNotIn('_auth_user_id', self.client.session)


    def test_sso_callback_rejects_invalid_ticket(self):
        state = self.start_sso_flow(mode='login')

        with patch('user_page.views.get_cas_client') as mock_cas:
            mock_cas.return_value.verify_ticket.side_effect = (
                Exception('Invalid CAS ticket')
            )

            response = self.client.get(
                reverse('user_page:sso_callback'),
                {
                    'ticket': 'ST-invalid-ticket',
                    'state': state,
                },
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response['Location'],
            reverse('user_page:login'),
        )

        self.assertNotIn('_auth_user_id', self.client.session)


    def test_sso_link_rejects_changed_account_session(self):
        self.client.force_login(self.user)

        state = self.start_sso_flow(mode='link')

        another_user = User.objects.create_user(
            username='different_user',
            password='Different-test-password-2026',
        )
        self.client.force_login(another_user)

        response = self.complete_sso_callback(state)

        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            SSOIdentity.objects.filter(
                user=self.user,
            ).exists()
        )
        self.assertFalse(
            SSOIdentity.objects.filter(
                user=another_user,
            ).exists()
        )

