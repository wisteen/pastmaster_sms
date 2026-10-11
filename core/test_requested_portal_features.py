from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from .forms_communication import SchoolMessageComposeForm
from .models import (
    ClassTeacher,
    ReportCardSettings,
    Result,
    SchoolClass,
    SchoolMembership,
    SchoolTenant,
    Student,
    Subject,
    Teacher,
    Term,
)
from .models_features import SchoolDomain
from .models_license import SystemLicense
from .views import _build_report_card_data


User = get_user_model()


class RequestedPortalFeatureTests(TestCase):
    host = 'requested-features.testserver'

    def setUp(self):
        self.school = SchoolTenant.objects.create(name='Feature School', slug='feature-school')
        SchoolDomain.objects.create(school=self.school, domain=self.host)
        SystemLicense.all_objects.create(
            school=self.school,
            school_name=self.school.name,
            license_key='feature-school-license',
            expiry_date=date.today() + timedelta(days=30),
        )
        self.admin = self._member('admin', 'super_admin')
        self.teacher_user = self._member('teacher', 'class_teacher')
        self.student_user = self._member('learner', 'student')
        self.other_student_user = self._member('other-learner', 'student')
        self.school_class = SchoolClass.all_objects.create(school=self.school, name='JSS 1', stream='A')
        self.other_class = SchoolClass.all_objects.create(school=self.school, name='JSS 2', stream='A')
        self.teacher = Teacher.all_objects.create(
            school=self.school, user=self.teacher_user, employee_id='T001',
        )
        ClassTeacher.objects.create(teacher=self.teacher, school_class=self.school_class)
        self.student = Student.all_objects.create(
            school=self.school, user=self.student_user, student_id='S001',
            school_class=self.school_class, date_of_birth=date(2012, 1, 1), gender='F',
        )
        self.other_student = Student.all_objects.create(
            school=self.school, user=self.other_student_user, student_id='S002',
            school_class=self.other_class, date_of_birth=date(2011, 1, 1), gender='M',
        )
        self.client = Client(HTTP_HOST=self.host)

    def _member(self, username, role):
        user = User.objects.create_user(username=username, password='password', role=role)
        SchoolMembership.objects.create(school=self.school, user=user, primary_role=role)
        return user

    def test_class_teacher_community_is_limited_to_assigned_class(self):
        self.client.force_login(self.teacher_user)
        response = self.client.get(reverse('core:class_community'))

        self.assertContains(response, 'S001')
        self.assertNotContains(response, 'S002')
        self.assertEqual(response.context['total_population'], 1)
        self.assertEqual(response.context['female_population'], 1)

    def test_class_teacher_can_enrol_a_student_with_portal_credentials(self):
        self.client.force_login(self.teacher_user)

        response = self.client.post(reverse('core:class_teacher_students'), {
            'first_name': 'New',
            'last_name': 'Learner',
            'username': 'new-learner',
            'password': 'SafeStudentPass123!',
            'confirm_password': 'SafeStudentPass123!',
            'school_class': self.school_class.id,
            'date_of_birth': '2013-04-20',
            'gender': 'F',
            'email': 'new.learner@example.test',
            'phone': '08000000000',
            'address': 'Test address',
        })

        self.assertRedirects(response, reverse('core:class_teacher_students'))
        user = User.objects.get(username='new-learner')
        student = Student.all_objects.get(user=user)
        membership = SchoolMembership.objects.get(school=self.school, user=user)
        self.assertTrue(user.check_password('SafeStudentPass123!'))
        self.assertEqual(user.role, 'student')
        self.assertEqual(student.school_class, self.school_class)
        self.assertEqual(membership.primary_role, 'student')
        self.assertTrue(membership.has_portal_access())

    def test_class_teacher_cannot_enrol_a_student_in_an_unassigned_class(self):
        self.client.force_login(self.teacher_user)

        response = self.client.post(reverse('core:class_teacher_students'), {
            'first_name': 'Other',
            'last_name': 'Class',
            'username': 'other-class-learner',
            'password': 'SafeStudentPass123!',
            'confirm_password': 'SafeStudentPass123!',
            'school_class': self.other_class.id,
            'date_of_birth': '2013-04-20',
            'gender': 'F',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='other-class-learner').exists())

    def test_class_teacher_signature_page_is_available_only_to_assigned_teacher(self):
        self.client.force_login(self.teacher_user)

        response = self.client.get(reverse('core:class_teacher_signature'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Class Teacher Signature')

    def test_ai_question_import_is_available_without_subscription(self):
        subject_teacher_user = self._member('free-ai-teacher', 'subject_teacher')
        subject_teacher = Teacher.all_objects.create(
            school=self.school,
            user=subject_teacher_user,
            employee_id='FREEAI001',
        )
        self.client.force_login(subject_teacher_user)

        response = self.client.get(reverse('core:import_questions_ai'))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(subject_teacher.has_ai_access())

    def test_admin_can_view_promotion_criteria_for_unassigned_class(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('core:student_promotion'), {'class_id': self.other_class.id})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['selected_class'], self.other_class)
        self.assertContains(response, 'Promotion Criteria')

    def test_archiving_student_retains_record_and_disables_portal(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('core:school_admin_students'), {
            'student_pk': self.student.id,
            'user': self.student_user.id,
            'school_class': self.school_class.id,
            'date_of_birth': '2012-01-01',
            'gender': 'F',
            'address': '',
            'status': 'relocated',
            'archive_note': 'Moved to another state',
        })

        self.assertRedirects(response, reverse('core:school_admin_students'))
        self.student.refresh_from_db()
        membership = SchoolMembership.objects.get(school=self.school, user=self.student_user)
        self.assertEqual(self.student.status, 'relocated')
        self.assertIsNotNone(self.student.archived_at)
        self.assertFalse(membership.portal_access_enabled)

    def test_third_term_can_be_term_only_or_cumulative(self):
        first = Term.all_objects.create(
            school=self.school, name='First Term', session='2025-2026',
            start_date=date(2025, 9, 1), end_date=date(2025, 12, 1),
        )
        third = Term.all_objects.create(
            school=self.school, name='Third Term', session='2025-2026',
            start_date=date(2026, 4, 1), end_date=date(2026, 7, 1),
        )
        subject = Subject.all_objects.create(school=self.school, name='English', code='ENG')
        Result.objects.create(student=self.student, subject=subject, term=first, total_score=60)
        Result.objects.create(student=self.student, subject=subject, term=third, total_score=80)
        settings = ReportCardSettings.all_objects.create(school=self.school, third_term_mode='term_only')

        self.assertEqual(_build_report_card_data(self.student, third)['cumulative_results'], [])
        settings.third_term_mode = 'cumulative'
        settings.save(update_fields=['third_term_mode'])
        self.assertEqual(len(_build_report_card_data(self.student, third)['cumulative_results']), 1)

    def test_compose_form_can_target_one_class(self):
        form = SchoolMessageComposeForm({
            'audience': 'class',
            'recipient_class': self.school_class.id,
            'subject': 'Class notice',
            'body': 'Bring your books.',
        }, school=self.school, sender=self.admin)

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(list(form.resolved_recipients()), [self.student_user])
