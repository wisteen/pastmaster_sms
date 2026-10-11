from datetime import date, timedelta
import re
import tempfile

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import SchoolClass, SchoolMembership, SchoolSettings, SchoolTenant, Student, Teacher
from .models_features import SchoolDomain
from .models_license import SystemLicense


User = get_user_model()


class PortalPasswordResetTests(TestCase):
    host = 'reset-school.testserver'

    def setUp(self):
        self.media_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.media_dir.cleanup)
        self.settings_override = override_settings(
            EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
            DEFAULT_FROM_EMAIL='default@sms.pastmaster.top',
            MEDIA_ROOT=self.media_dir.name,
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

        self.school = SchoolTenant.objects.create(name='Reset School', slug='reset-school', plan='premium')
        SchoolDomain.objects.create(school=self.school, domain=self.host)
        SystemLicense.all_objects.create(
            school=self.school,
            school_name=self.school.name,
            license_key='reset-school-license',
            expiry_date=date.today() + timedelta(days=30),
        )
        SchoolSettings.all_objects.create(
            school=self.school,
            school_name='Reset School',
            school_address='Reset Road',
            principal_name='Principal',
            email_from_address='portal@reset-school.test',
            school_logo=SimpleUploadedFile('logo.png', b'fake-logo-bytes', content_type='image/png'),
        )

        self.school_class = SchoolClass.all_objects.create(school=self.school, name='JSS 1', stream='A')
        self.student_user = self._user(
            'student-login',
            'student',
            'student@example.com',
            first_name='Student',
            last_name='Login',
        )
        self.student = Student.all_objects.create(
            school=self.school,
            user=self.student_user,
            student_id='STD007',
            school_class=self.school_class,
            date_of_birth=date(2012, 1, 1),
        )

        self.teacher_user = self._user(
            'teacher-login',
            'class_teacher',
            'teacher@example.com',
            first_name='Teacher',
            last_name='Login',
        )
        self.teacher = Teacher.all_objects.create(
            school=self.school,
            user=self.teacher_user,
            employee_id='TCH007',
        )

    def _user(self, username, role, email, first_name='', last_name=''):
        user = User.objects.create_user(
            username=username,
            password='Oldpass12345',
            role=role,
            email=email,
            first_name=first_name,
            last_name=last_name,
        )
        SchoolMembership.objects.create(school=self.school, user=user, primary_role=role)
        return user

    def _client(self):
        return Client(HTTP_HOST=self.host)

    def test_login_accepts_email_student_id_and_teacher_id(self):
        response = self._client().post(reverse('core:login'), {
            'role': 'student',
            'username': 'student@example.com',
            'password': 'Oldpass12345',
        })
        self.assertRedirects(response, reverse('core:dashboard'))

        response = self._client().post(reverse('core:login'), {
            'role': 'student',
            'username': 'STD007',
            'password': 'Oldpass12345',
        })
        self.assertRedirects(response, reverse('core:dashboard'))

        response = self._client().post(reverse('core:login'), {
            'role': 'class_teacher',
            'username': 'TCH007',
            'password': 'Oldpass12345',
        })
        self.assertRedirects(response, reverse('core:dashboard'))

    def test_login_page_shows_reset_password_link(self):
        response = self._client().get(reverse('core:login'), {'role': 'student'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Reset password')
        self.assertContains(response, reverse('core:password_reset') + '?role=student')

    def test_password_reset_by_student_id_sends_branded_code_email_and_changes_password(self):
        client = self._client()
        response = client.post(reverse('core:password_reset'), {
            'step': 'request',
            'role': 'student',
            'identifier': 'STD007',
        })

        self.assertRedirects(response, reverse('core:password_reset') + '?step=confirm')
        self.assertEqual(len(mail.outbox), 1)
        reset_email = mail.outbox[0]
        self.assertEqual(reset_email.to, ['student@example.com'])
        self.assertEqual(reset_email.from_email, 'portal@reset-school.test')
        self.assertIn('Reset School password reset code', reset_email.subject)
        self.assertIn('Reset School', reset_email.alternatives[0][0])
        self.assertIn('data:image/png;base64,', reset_email.alternatives[0][0])
        self.assertIn('Powered by PastMaster SMS', reset_email.alternatives[0][0])

        match = re.search(r'^\d{6}$', reset_email.body, re.MULTILINE)
        self.assertIsNotNone(match)
        code = match.group(0)

        response = client.post(reverse('core:password_reset'), {
            'step': 'confirm',
            'role': 'student',
            'code': code,
            'new_password': 'Newpass12345',
            'confirm_password': 'Newpass12345',
        })

        self.assertRedirects(response, reverse('core:login') + '?role=student')
        self.student_user.refresh_from_db()
        self.assertTrue(self.student_user.check_password('Newpass12345'))

        response = self._client().post(reverse('core:login'), {
            'role': 'student',
            'username': 'STD007',
            'password': 'Newpass12345',
        })
        self.assertRedirects(response, reverse('core:dashboard'))
