from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from .models import Result, SchoolClass, SchoolMembership, SchoolSettings, SchoolTenant, Student, Subject, Term
from .models_biodata import Guardian
from .models_features import SchoolDomain
from .models_license import SystemLicense


User = get_user_model()


class SchoolPortalSettingsTests(TestCase):
    host = 'portal.testserver'

    def setUp(self):
        self.school = SchoolTenant.objects.create(name='Portal School', slug='portal-school')
        SchoolDomain.objects.create(school=self.school, domain=self.host)
        SystemLicense.all_objects.create(
            school=self.school,
            school_name=self.school.name,
            license_key='portal-school-license',
            expiry_date=date.today() + timedelta(days=30),
        )
        self.school_class = SchoolClass.all_objects.create(school=self.school, name='JSS 1', stream='A')
        self.subject = Subject.all_objects.create(school=self.school, name='Mathematics', code='MTH')
        self.term = Term.all_objects.create(
            school=self.school,
            name='First Term',
            session='2025-2026',
            start_date=date.today() - timedelta(days=90),
            end_date=date.today(),
        )

        self.admin_user = self._create_member('admin', 'super_admin')
        self.student_user = self._create_member('student', 'student')
        self.parent_user = self._create_member('parent', 'parent')
        self.student = Student.all_objects.create(
            school=self.school,
            user=self.student_user,
            student_id='STU0001',
            school_class=self.school_class,
            date_of_birth=date(2012, 1, 1),
        )
        Guardian.objects.create(
            student=self.student,
            user=self.parent_user,
            relationship='father',
            title='Mr',
            first_name='Test',
            last_name='Parent',
            phone_number='08012345678',
            occupation='Parent',
            home_address='Home',
        )
        self.result = Result.all_objects.create(
            student=self.student,
            subject=self.subject,
            term=self.term,
            total_score=75,
            grade='B',
            grade_point=3,
            remark='Very Good',
        )

    def _create_member(self, username, role):
        user = User.objects.create_user(username=username, password='password', role=role)
        SchoolMembership.objects.create(school=self.school, user=user, primary_role=role)
        return user

    def _client_for(self, username):
        client = Client(HTTP_HOST=self.host)
        self.assertTrue(client.login(username=username, password='password'))
        return client

    def test_results_are_hidden_until_admin_sends_them_to_portals(self):
        student_client = self._client_for('student')
        parent_client = self._client_for('parent')

        response = student_client.get(reverse('core:student_results'))
        self.assertNotContains(response, 'Mathematics')
        response = parent_client.get(reverse('core:parent_dashboard'))
        self.assertNotContains(response, 'Mathematics')

        admin_client = self._client_for('admin')
        response = admin_client.post(
            reverse('core:school_admin_result_publication'),
            {'term_id': self.term.id, 'action': 'publish'},
        )
        self.assertRedirects(response, reverse('core:school_admin_result_publication'))

        response = student_client.get(reverse('core:student_results'))
        self.assertContains(response, 'Mathematics')
        response = parent_client.get(reverse('core:parent_dashboard'))
        self.assertContains(response, 'Mathematics')

    def test_school_admin_can_save_tenant_school_details(self):
        admin_client = self._client_for('admin')
        response = admin_client.post(reverse('core:school_admin_settings'), {
            'school_name': 'Configured Portal School',
            'school_address': '123 School Road',
            'principal_name': 'A. Principal',
            'proprietor_name': 'A. Proprietor',
            'school_motto': 'Knowledge',
            'primary_color': '#112233',
            'secondary_color': '#445566',
            'accent_color': '#778899',
            'student_id_prefix': 'STD',
            'student_id_digits': 5,
            'teacher_id_prefix': 'TCH',
            'teacher_id_digits': 4,
        })
        self.assertRedirects(response, reverse('core:school_admin_settings'))

        settings = SchoolSettings.all_objects.get(school=self.school)
        self.assertEqual(settings.school_name, 'Configured Portal School')
        self.assertEqual(settings.primary_color, '#112233')
