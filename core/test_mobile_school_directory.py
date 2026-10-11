from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models_features import SchoolDomain, SchoolTenant


class MobileSchoolDirectoryTests(TestCase):
    def test_lists_only_active_schools_with_valid_domains(self):
        active = SchoolTenant.objects.create(name='Calvary School', slug='calvary')
        SchoolDomain.objects.create(
            school=active,
            domain='backup.example.com',
            is_primary=False,
        )
        SchoolDomain.objects.create(
            school=active,
            domain='calvary.example.com',
            is_primary=True,
        )
        inactive = SchoolTenant.objects.create(
            name='Closed School',
            slug='closed',
            is_active=False,
        )
        SchoolDomain.objects.create(school=inactive, domain='closed.example.com')
        SchoolTenant.objects.create(name='No Domain School', slug='no-domain')

        response = self.client.get(reverse('core:mobile_school_directory'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'public, max-age=300')
        self.assertEqual(response.json(), {
            'schools': [{
                'name': 'Calvary School',
                'slug': 'calvary',
                'base_url': 'https://calvary.example.com',
            }],
        })


class AttendanceLoginRedirectTests(TestCase):
    def setUp(self):
        self.password = 'Strong-test-password-42'
        self.user = get_user_model().objects.create_superuser(
            username='attendance-admin',
            email='attendance@example.com',
            password=self.password,
        )

    def test_login_honours_safe_attendance_destination(self):
        response = self.client.post(
            f"{reverse('core:login')}?next=/attendance/mark/",
            {
                'username': self.user.username,
                'password': self.password,
                'role': 'super_admin',
                'next': '/attendance/mark/',
            },
        )

        self.assertRedirects(
            response,
            '/attendance/mark/',
            fetch_redirect_response=False,
        )

    def test_login_rejects_external_destination(self):
        response = self.client.post(
            reverse('core:login'),
            {
                'username': self.user.username,
                'password': self.password,
                'role': 'super_admin',
                'next': 'https://malicious.example/steal-session',
            },
        )

        self.assertRedirects(
            response,
            reverse('core:dashboard'),
            fetch_redirect_response=False,
        )
