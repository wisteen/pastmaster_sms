from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from .models import (
    ClassTeacher,
    ResultComponent,
    SchoolClass,
    SchoolMembership,
    SchoolTenant,
    Student,
    StudentTermPlacement,
    Subject,
    Teacher,
    Term,
)
from .models_features import SchoolDomain
from .models_license import SystemLicense
from .views import (
    _build_report_card_data,
    _get_teacher_assessment_scope,
    _get_teacher_dashboard_subjects,
)


User = get_user_model()


class TeacherSubjectReportLifecycleTests(TestCase):
    host = 'lifecycle.testserver'

    def setUp(self):
        self.school = SchoolTenant.objects.create(name='Lifecycle School', slug='lifecycle-school')
        SchoolDomain.objects.create(school=self.school, domain=self.host)
        SystemLicense.all_objects.create(
            school=self.school,
            school_name=self.school.name,
            license_key='lifecycle-school-license',
            expiry_date=date.today() + timedelta(days=30),
        )
        self.school_class = SchoolClass.all_objects.create(school=self.school, name='Basic 2')
        self.term = Term.all_objects.create(
            school=self.school,
            name='First Term',
            session='2026-2027',
            start_date=date.today() - timedelta(days=30),
            end_date=date.today() + timedelta(days=60),
            is_active=True,
        )
        self.admin = self._member('lifecycle-admin', 'super_admin')

    def _member(self, username, role):
        user = User.objects.create_user(username=username, password='password', role=role)
        SchoolMembership.objects.create(
            school=self.school,
            user=user,
            primary_role=role,
        )
        return user

    def _teacher(self, username, employee_id, role='subject_teacher', status='active'):
        user = self._member(username, role)
        teacher = Teacher.all_objects.create(
            school=self.school,
            user=user,
            employee_id=employee_id,
            status=status,
        )
        if status != 'active':
            membership = SchoolMembership.objects.get(school=self.school, user=user)
            membership.is_active = False
            membership.portal_access_enabled = False
            membership.result_access_enabled = False
            membership.save()
        return teacher

    def test_dashboard_subjects_are_not_expanded_by_class_components(self):
        teacher = self._teacher('class-teacher', 'TCH001', role='class_teacher')
        assigned = Subject.all_objects.create(
            school=self.school, name='English', code='ENG', subject_type='academic',
        )
        inherited = Subject.all_objects.create(
            school=self.school, name='Mathematics', code='MTH', subject_type='academic',
        )
        teacher.subjects.add(assigned)
        ClassTeacher.objects.create(teacher=teacher, school_class=self.school_class)
        for subject in (assigned, inherited):
            ResultComponent.all_objects.create(
                school_class=self.school_class,
                subject=subject,
                component_name='Exam',
                weight=100,
                max_score=100,
            )

        classes, assessment_subjects = _get_teacher_assessment_scope(teacher)
        dashboard_subjects = _get_teacher_dashboard_subjects(teacher, assessment_subjects)

        self.assertEqual(list(classes), [self.school_class])
        self.assertEqual(set(assessment_subjects), {assigned, inherited})
        self.assertEqual(list(dashboard_subjects), [assigned])

    def test_teacher_without_explicit_subjects_uses_class_setup_as_fallback(self):
        teacher = self._teacher('fallback-teacher', 'TCH002', role='class_teacher')
        subject = Subject.all_objects.create(
            school=self.school, name='Science', code='SCI', subject_type='academic',
        )
        ClassTeacher.objects.create(teacher=teacher, school_class=self.school_class)
        ResultComponent.all_objects.create(
            school_class=self.school_class,
            subject=subject,
            component_name='Exam',
            weight=100,
            max_score=100,
        )

        _, subjects = _get_teacher_assessment_scope(teacher)

        self.assertEqual(list(subjects), [subject])

    def test_admin_can_replace_historical_report_teacher_for_one_term(self):
        student_user = self._member('report-student', 'student')
        student = Student.all_objects.create(
            school=self.school,
            user=student_user,
            student_id='STU001',
            school_class=self.school_class,
            date_of_birth=date(2015, 1, 1),
        )
        replacement = self._teacher('former-teacher', 'TCH003', status='former')
        client = Client(HTTP_HOST=self.host)
        client.force_login(self.admin)

        response = client.post(reverse('core:report_card_settings'), {
            'action': 'save_report_teachers',
            'teacher_term': self.term.id,
            f'report_teacher_{self.school_class.id}': replacement.id,
        })

        self.assertEqual(response.status_code, 302)
        placement = StudentTermPlacement.all_objects.get(student=student, term=self.term)
        self.assertEqual(placement.class_teacher, replacement)
        self.assertTrue(placement.signatory_frozen)
        self.assertEqual(placement.teacher_name, replacement.user.get_full_name() or replacement.user.username)
        report_data = _build_report_card_data(student, self.term)
        self.assertEqual(report_data['class_teacher_name'], replacement.user.username)

    def test_archived_assignment_is_not_used_automatically_on_new_report(self):
        student_user = self._member('new-report-student', 'student')
        student = Student.all_objects.create(
            school=self.school,
            user=student_user,
            student_id='STU002',
            school_class=self.school_class,
            date_of_birth=date(2015, 1, 1),
        )
        former_teacher = self._teacher('old-class-teacher', 'TCH005', status='former')
        ClassTeacher.objects.create(teacher=former_teacher, school_class=self.school_class)

        report_data = _build_report_card_data(student, self.term)

        self.assertEqual(report_data['class_teacher_name'], '')

    def test_archiving_and_reactivating_teacher_controls_membership_and_active_list(self):
        teacher = self._teacher('leaving-teacher', 'TCH004')
        client = Client(HTTP_HOST=self.host)
        client.force_login(self.admin)

        archive_response = client.post(reverse('core:school_admin_staff'), {
            'teacher_id': teacher.id,
            'user': teacher.user_id,
            'employee_id': teacher.employee_id,
            'status': 'former',
            'archive_note': 'Left the school',
        })

        self.assertEqual(archive_response.status_code, 302)
        teacher.refresh_from_db()
        membership = SchoolMembership.objects.get(school=self.school, user=teacher.user)
        self.assertEqual(teacher.status, 'former')
        self.assertIsNotNone(teacher.archived_at)
        self.assertFalse(membership.is_active)
        self.assertFalse(membership.portal_access_enabled)
        self.assertFalse(membership.result_access_enabled)

        active_page = client.get(reverse('core:school_admin_staff'))
        self.assertNotContains(active_page, 'leaving-teacher')
        former_page = client.get(reverse('core:school_admin_staff'), {'status': 'former'})
        self.assertContains(former_page, 'leaving-teacher')

        reactivate_response = client.post(reverse('core:school_admin_staff'), {
            'teacher_id': teacher.id,
            'user': teacher.user_id,
            'employee_id': teacher.employee_id,
            'status': 'active',
            'archive_note': '',
        })
        self.assertEqual(reactivate_response.status_code, 302)
        teacher.refresh_from_db()
        membership.refresh_from_db()
        self.assertEqual(teacher.status, 'active')
        self.assertIsNone(teacher.archived_at)
        self.assertTrue(membership.is_active)
        self.assertTrue(membership.portal_access_enabled)
        self.assertTrue(membership.result_access_enabled)
