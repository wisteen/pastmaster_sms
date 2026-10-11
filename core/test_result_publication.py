from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from .models import Result, SchoolClass, SchoolMembership, SchoolTenant, Student, Subject, Term
from .models_features import SchoolDomain
from .models_license import SystemLicense


User = get_user_model()


class ResultPublicationTests(TestCase):
    host = 'publication.testserver'

    def setUp(self):
        self.school = SchoolTenant.objects.create(name='Publication School', slug='publication-school')
        SchoolDomain.objects.create(school=self.school, domain=self.host)
        SystemLicense.all_objects.create(
            school=self.school,
            school_name=self.school.name,
            license_key='publication-school-license',
            expiry_date=date.today() + timedelta(days=30),
        )
        self.admin = User.objects.create_user('publisher', password='password', role='super_admin')
        SchoolMembership.objects.create(
            school=self.school,
            user=self.admin,
            primary_role='super_admin',
        )
        self.school_class = SchoolClass.all_objects.create(school=self.school, name='JSS 1')
        self.subject = Subject.all_objects.create(school=self.school, name='Mathematics', code='MTH')
        self.term = Term.all_objects.create(
            school=self.school,
            name='First Term',
            session='2025-2026',
            start_date=date(2025, 9, 1),
            end_date=date(2025, 12, 19),
        )
        student_user = User.objects.create_user('learner', password='password', role='student')
        SchoolMembership.objects.create(school=self.school, user=student_user, primary_role='student')
        self.student = Student.all_objects.create(
            school=self.school,
            user=student_user,
            student_id='STU-001',
            school_class=self.school_class,
            date_of_birth=date(2012, 1, 1),
        )
        self.client = Client(HTTP_HOST=self.host)
        self.assertTrue(self.client.login(username='publisher', password='password'))

    def _set_publication(self, action):
        return self.client.post(
            reverse('core:school_admin_result_publication'),
            {'term_id': self.term.id, 'action': action},
        )

    def test_empty_term_cannot_be_published(self):
        response = self._set_publication('publish')

        self.assertRedirects(response, reverse('core:school_admin_result_publication'))
        self.term.refresh_from_db()
        self.assertFalse(self.term.result_published)

    def test_admin_can_publish_and_unpublish_a_term_with_results(self):
        Result.all_objects.create(
            student=self.student,
            subject=self.subject,
            term=self.term,
            total_score=75,
            grade='B',
            grade_point=3,
        )

        self._set_publication('publish')
        self.term.refresh_from_db()
        self.assertTrue(self.term.result_published)

        self._set_publication('unpublish')
        self.term.refresh_from_db()
        self.assertFalse(self.term.result_published)


