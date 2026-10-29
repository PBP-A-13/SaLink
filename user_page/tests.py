from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


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
