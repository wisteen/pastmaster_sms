from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from .models import Result, ResultComponent, SchoolClass, SchoolMembership, SchoolTenant, Student, Subject, Term
from .models_features import SchoolDomain
from .models_license import SystemLicense


User = get_user_model()


class SchoolAdminAcademicSetupTests(TestCase):
    host = 'academic-setup.testserver'

    def setUp(self):
        self.school = SchoolTenant.objects.create(name='Academic Setup School', slug='academic-setup-school')
        SchoolDomain.objects.create(school=self.school, domain=self.host)
        SystemLicense.all_objects.create(
            school=self.school,
            school_name=self.school.name,
            license_key='academic-setup-school-license',
            expiry_date=date.today() + timedelta(days=30),
        )
        self.admin = User.objects.create_user(username='admin', password='password', role='super_admin')
        SchoolMembership.objects.create(school=self.school, user=self.admin, primary_role='super_admin')
        self.client = Client(HTTP_HOST=self.host)
        self.assertTrue(self.client.login(username='admin', password='password'))

    def _create_term(self):
        return Term.all_objects.create(
            school=self.school,
            name='First Term',
            session='2025-2026',
            start_date=date.today() - timedelta(days=90),
            end_date=date.today(),
        )

    def _create_student(self, school_class):
        student_user = User.objects.create_user(username='student', password='password', role='student')
        SchoolMembership.objects.create(school=self.school, user=student_user, primary_role='student')
        return Student.all_objects.create(
            school=self.school,
            user=student_user,
            student_id='STU001',
            school_class=school_class,
            date_of_birth=date(2012, 1, 1),
        )

    def test_academic_lists_have_edit_and_delete_actions(self):
        school_class = SchoolClass.all_objects.create(school=self.school, name='Wrong Subject', stream='')
        subject = Subject.all_objects.create(school=self.school, name='Wrong Class', code='WRC')
        term = self._create_term()

        response = self.client.get(reverse('core:school_admin_academic_setup'))

        self.assertContains(response, f'?class={school_class.id}')
        self.assertContains(response, 'name="action" value="delete_class"')
        self.assertContains(response, f'name="object_id" value="{school_class.id}"')
        self.assertContains(response, f'?subject={subject.id}')
        self.assertContains(response, 'name="action" value="delete_subject"')
        self.assertContains(response, f'name="object_id" value="{subject.id}"')
        self.assertContains(response, f'?term={term.id}')
        self.assertContains(response, 'name="action" value="delete_term"')
        self.assertContains(response, f'name="object_id" value="{term.id}"')

    def test_school_admin_can_delete_unlinked_class(self):
        school_class = SchoolClass.all_objects.create(school=self.school, name='Wrong Subject', stream='')

        response = self.client.post(reverse('core:school_admin_academic_setup'), {
            'action': 'delete_class',
            'object_id': school_class.id,
        })

        self.assertRedirects(response, reverse('core:school_admin_academic_setup'))
        self.assertFalse(SchoolClass.all_objects.filter(id=school_class.id).exists())

    def test_school_admin_can_delete_unlinked_subject(self):
        subject = Subject.all_objects.create(school=self.school, name='Wrong Class', code='WRC')

        response = self.client.post(reverse('core:school_admin_academic_setup'), {
            'action': 'delete_subject',
            'object_id': subject.id,
        })

        self.assertRedirects(response, reverse('core:school_admin_academic_setup'))
        self.assertFalse(Subject.all_objects.filter(id=subject.id).exists())

    def test_school_admin_can_delete_unlinked_term(self):
        term = self._create_term()

        response = self.client.post(reverse('core:school_admin_academic_setup'), {
            'action': 'delete_term',
            'object_id': term.id,
        })

        self.assertRedirects(response, reverse('core:school_admin_academic_setup'))
        self.assertFalse(Term.all_objects.filter(id=term.id).exists())

    def test_school_admin_cannot_delete_class_with_students(self):
        school_class = SchoolClass.all_objects.create(school=self.school, name='JSS 1', stream='A')
        self._create_student(school_class)

        response = self.client.post(reverse('core:school_admin_academic_setup'), {
            'action': 'delete_class',
            'object_id': school_class.id,
        })

        self.assertRedirects(response, reverse('core:school_admin_academic_setup'))
        self.assertTrue(SchoolClass.all_objects.filter(id=school_class.id).exists())

    def test_school_admin_cannot_delete_subject_with_assessment_setup(self):
        school_class = SchoolClass.all_objects.create(school=self.school, name='JSS 1', stream='A')
        subject = Subject.all_objects.create(school=self.school, name='Mathematics', code='MTH')
        ResultComponent.objects.create(
            school_class=school_class,
            subject=subject,
            component_name='CA 1',
            weight=20,
        )

        response = self.client.post(reverse('core:school_admin_academic_setup'), {
            'action': 'delete_subject',
            'object_id': subject.id,
        })

        self.assertRedirects(response, reverse('core:school_admin_academic_setup'))
        self.assertTrue(Subject.all_objects.filter(id=subject.id).exists())

    def test_school_admin_cannot_delete_term_with_results(self):
        school_class = SchoolClass.all_objects.create(school=self.school, name='JSS 1', stream='A')
        subject = Subject.all_objects.create(school=self.school, name='Mathematics', code='MTH')
        term = self._create_term()
        student = self._create_student(school_class)
        Result.objects.create(
            student=student,
            subject=subject,
            term=term,
            total_score=70,
            grade='B',
            grade_point=3,
            remark='Good',
        )

        response = self.client.post(reverse('core:school_admin_academic_setup'), {
            'action': 'delete_term',
            'object_id': term.id,
        })

        self.assertRedirects(response, reverse('core:school_admin_academic_setup'))
        self.assertTrue(Term.all_objects.filter(id=term.id).exists())

    def test_transcripts_are_admin_only(self):
        teacher_user = User.objects.create_user(username='class_teacher', password='password', role='class_teacher')
        SchoolMembership.objects.create(school=self.school, user=teacher_user, primary_role='class_teacher')
        teacher_client = Client(HTTP_HOST=self.host)
        self.assertTrue(teacher_client.login(username='class_teacher', password='password'))

        response = teacher_client.get(reverse('core:school_admin_transcripts'))

        self.assertRedirects(response, reverse('core:dashboard'), fetch_redirect_response=False)

    def test_transcripts_include_print_page_numbering(self):
        response = self.client.get(reverse('core:school_admin_transcripts'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'counter(page)')
        self.assertContains(response, 'counter(pages)')

    def test_duplicate_class_is_rejected_before_save(self):
        SchoolClass.all_objects.create(school=self.school, name='JSS 1', stream='A')

        response = self.client.post(reverse('core:school_admin_academic_setup'), {
            'action': 'class',
            'name': ' jss   1 ',
            'stream': 'a',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This class already exists for this school.')
        self.assertEqual(SchoolClass.all_objects.filter(school=self.school).count(), 1)
