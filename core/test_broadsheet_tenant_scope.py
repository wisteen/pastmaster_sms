from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from .models import (
    ClassTeacher,
    RoomAssignment,
    Result,
    ResultComponent,
    ResultToken,
    SchoolClass,
    SchoolMembership,
    SchoolTenant,
    Student,
    Subject,
    Teacher,
    Term,
    TimeSlot,
    Timetable,
)
from .models_features import SchoolDomain
from .models_license import SystemLicense


User = get_user_model()


class BroadsheetTenantScopeTests(TestCase):
    host = 'broadsheet.testserver'
    other_host = 'other-broadsheet.testserver'

    def setUp(self):
        self.school = SchoolTenant.objects.create(name='Broadsheet School', slug='broadsheet-school')
        self.other_school = SchoolTenant.objects.create(name='Other School', slug='other-school')
        SchoolDomain.objects.create(school=self.school, domain=self.host)
        SchoolDomain.objects.create(school=self.other_school, domain=self.other_host)
        for school in (self.school, self.other_school):
            SystemLicense.all_objects.create(
                school=school,
                school_name=school.name,
                license_key=f'{school.slug}-license',
                expiry_date=date.today() + timedelta(days=30),
            )

        self.admin = self._user('admin', 'super_admin')
        SchoolMembership.objects.create(school=self.school, user=self.admin, primary_role='super_admin')

        self.school_class = SchoolClass.all_objects.create(school=self.school, name='JSS 1', stream='A')
        self.other_class = SchoolClass.all_objects.create(school=self.school, name='JSS 2', stream='A')
        self.foreign_class = SchoolClass.all_objects.create(school=self.other_school, name='JSS 1', stream='B')

        self.first_term = self._term(self.school, 'First Term', '2025-2026', is_active=True)
        self.second_term = self._term(self.school, 'Second Term', '2025-2026')
        self.foreign_term = self._term(self.other_school, 'First Term', '2025-2026', is_active=True)

        self.math = Subject.all_objects.create(school=self.school, name='Mathematics', code='MTH')
        self.english = Subject.all_objects.create(school=self.school, name='English', code='ENG')
        self.unoffered_subject = Subject.all_objects.create(school=self.school, name='Music', code='MUS')
        self.foreign_subject = Subject.all_objects.create(school=self.other_school, name='Science', code='SCI')

        ResultComponent.objects.create(
            school_class=self.school_class,
            subject=self.math,
            component_name='Exam',
            weight=100,
            max_score=100,
        )
        ResultComponent.objects.create(
            school_class=self.other_class,
            subject=self.english,
            component_name='Exam',
            weight=100,
            max_score=100,
        )

        self.student = self._student('managed_student', self.school, self.school_class, 'STU001', 'Managed', 'Student')
        self.other_student = self._student('other_student', self.school, self.other_class, 'STU002', 'Other', 'Student')
        self.foreign_student = self._student('foreign_student', self.other_school, self.foreign_class, 'OSTU001', 'Foreign', 'Student')

        Result.all_objects.create(
            student=self.student,
            subject=self.math,
            term=self.first_term,
            total_score=75,
            grade='B',
            grade_point=3,
            remark='Good',
        )
        Result.all_objects.create(
            student=self.student,
            subject=self.math,
            term=self.second_term,
            total_score=88,
            grade='A',
            grade_point=4,
            remark='Excellent',
        )
        Result.all_objects.create(
            student=self.other_student,
            subject=self.english,
            term=self.first_term,
            total_score=67,
            grade='C',
            grade_point=2,
            remark='Fair',
        )
        Result.all_objects.create(
            student=self.student,
            subject=self.foreign_subject,
            term=self.first_term,
            total_score=99,
            grade='A',
            grade_point=4,
            remark='Wrong tenant subject',
        )
        Result.all_objects.create(
            student=self.student,
            subject=self.unoffered_subject,
            term=self.first_term,
            total_score=91,
            grade='A',
            grade_point=4,
            remark='Not offered for class',
        )

        self.admin_client = Client(HTTP_HOST=self.host)
        self.assertTrue(self.admin_client.login(username='admin', password='password'))

    def _user(self, username, role, first_name=None, last_name=None):
        return User.objects.create_user(
            username=username,
            password='password',
            role=role,
            first_name=first_name or username.title(),
            last_name=last_name or 'User',
        )

    def _term(self, school, name, session, is_active=False):
        return Term.all_objects.create(
            school=school,
            name=name,
            session=session,
            start_date=date.today() - timedelta(days=90),
            end_date=date.today() + timedelta(days=10),
            is_active=is_active,
        )

    def _student(self, username, school, school_class, student_id, first_name, last_name):
        user = self._user(username, 'student', first_name, last_name)
        SchoolMembership.objects.create(school=school, user=user, primary_role='student')
        return Student.all_objects.create(
            school=school,
            user=user,
            student_id=student_id,
            school_class=school_class,
            date_of_birth=date(2012, 1, 1),
        )

    def test_generate_tokens_is_limited_to_active_tenant(self):
        response = self.admin_client.post(reverse('core:generate_tokens'), {
            'term_id': self.first_term.id,
            'max_uses': '3',
            'action': 'create',
        })

        self.assertRedirects(response, reverse('core:generate_tokens'))
        self.assertEqual(
            ResultToken.all_objects.filter(student__school=self.school, term=self.first_term).count(),
            2,
        )
        self.assertFalse(ResultToken.all_objects.filter(student=self.foreign_student).exists())

    def test_generate_tokens_can_be_limited_to_selected_class(self):
        response = self.admin_client.post(reverse('core:generate_tokens'), {
            'term_id': self.first_term.id,
            'school_class': self.school_class.id,
            'max_uses': '3',
            'action': 'create',
        })

        self.assertRedirects(response, reverse('core:generate_tokens'))
        self.assertTrue(
            ResultToken.all_objects.filter(student=self.student, term=self.first_term).exists()
        )
        self.assertFalse(
            ResultToken.all_objects.filter(student=self.other_student, term=self.first_term).exists()
        )
        self.assertFalse(ResultToken.all_objects.filter(student=self.foreign_student).exists())

    def test_regenerate_tokens_for_selected_class_does_not_replace_other_class_tokens(self):
        managed_token = ResultToken.all_objects.create(student=self.student, term=self.first_term, max_uses=3)
        other_token = ResultToken.all_objects.create(student=self.other_student, term=self.first_term, max_uses=3)

        response = self.admin_client.post(reverse('core:generate_tokens'), {
            'term_id': self.first_term.id,
            'school_class': self.school_class.id,
            'max_uses': '5',
            'action': 'regenerate',
        })

        self.assertRedirects(response, reverse('core:generate_tokens'))
        self.assertFalse(ResultToken.all_objects.filter(pk=managed_token.pk).exists())
        self.assertTrue(ResultToken.all_objects.filter(pk=other_token.pk).exists())
        new_token = ResultToken.all_objects.get(student=self.student, term=self.first_term)
        self.assertEqual(new_token.max_uses, 5)

    def test_generate_tokens_page_filters_by_class_and_search_and_includes_copy_details(self):
        ResultToken.all_objects.create(student=self.student, term=self.first_term, max_uses=3)
        ResultToken.all_objects.create(student=self.other_student, term=self.first_term, max_uses=3)

        response = self.admin_client.get(reverse('core:generate_tokens'), {
            'school_class': self.school_class.id,
            'q': 'STU001',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual([token.student_id for token in response.context['tokens']], [self.student.id])
        self.assertContains(response, 'Managed Student')
        self.assertContains(response, 'Copy Visible Tokens')
        self.assertContains(response, 'Student ID: STU001')
        self.assertContains(response, reverse('core:check_result'))

    def test_admin_broadsheet_uses_selected_term_and_school_subjects_only(self):
        response = self.admin_client.get(reverse('core:class_broadsheet'), {
            'class_id': self.school_class.id,
            'term_id': self.second_term.id,
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '2025-2026 - Second Term')
        self.assertContains(response, 'MTH')
        self.assertContains(response, '88')
        self.assertNotContains(response, 'SCI')

    def test_broadsheet_hides_same_school_subjects_not_offered_for_class(self):
        response = self.admin_client.get(reverse('core:class_broadsheet'), {
            'class_id': self.school_class.id,
            'term_id': self.first_term.id,
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'MTH')
        self.assertNotContains(response, 'MUS')
        self.assertNotContains(response, '91')

    def test_broadsheet_hides_timetabled_subject_without_assessment_setup(self):
        teacher_user = self._user('music_teacher', 'subject_teacher', 'Music', 'Teacher')
        SchoolMembership.objects.create(school=self.school, user=teacher_user, primary_role='subject_teacher')
        teacher = Teacher.all_objects.create(school=self.school, user=teacher_user, employee_id='MUS001')
        time_slot = TimeSlot.objects.create(
            school=self.school,
            name='Period 1',
            start_time=time(8, 0),
            end_time=time(8, 40),
            day_of_week=0,
        )
        room = RoomAssignment.objects.create(
            school=self.school,
            room_name='Room 1',
            capacity=30,
            room_type='Classroom',
        )
        Timetable.objects.create(
            time_slot=time_slot,
            subject=self.unoffered_subject,
            teacher=teacher,
            school_class=self.school_class,
            room=room,
            term=self.first_term,
            academic_year='2025-2026',
        )

        response = self.admin_client.get(reverse('core:class_broadsheet'), {
            'class_id': self.school_class.id,
            'term_id': self.first_term.id,
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'MTH')
        self.assertNotContains(response, 'MUS')

    def test_broadsheet_download_returns_landscape_pdf(self):
        response = self.admin_client.get(reverse('core:download_broadsheet'), {
            'class_id': self.school_class.id,
            'term_id': self.first_term.id,
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('.pdf', response['Content-Disposition'])
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_class_teacher_result_lookup_is_limited_to_managed_classes(self):
        teacher_user = self._user('class_teacher', 'class_teacher', 'Class', 'Teacher')
        SchoolMembership.objects.create(school=self.school, user=teacher_user, primary_role='class_teacher')
        teacher = Teacher.all_objects.create(school=self.school, user=teacher_user, employee_id='TCH001')
        teacher.classes.add(self.other_class)
        ClassTeacher.all_objects.create(teacher=teacher, school_class=self.school_class)

        client = Client(HTTP_HOST=self.host)
        self.assertTrue(client.login(username='class_teacher', password='password'))
        response = client.get(reverse('core:student_results_lookup'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Managed Student')
        self.assertNotContains(response, 'Other Student')

    def test_class_teacher_cannot_open_unmanaged_student_report_card_directly(self):
        teacher_user = self._user('guarded_teacher', 'class_teacher', 'Guarded', 'Teacher')
        SchoolMembership.objects.create(school=self.school, user=teacher_user, primary_role='class_teacher')
        teacher = Teacher.all_objects.create(school=self.school, user=teacher_user, employee_id='TCH003')
        teacher.classes.add(self.other_class)
        ClassTeacher.all_objects.create(teacher=teacher, school_class=self.school_class)

        client = Client(HTTP_HOST=self.host)
        self.assertTrue(client.login(username='guarded_teacher', password='password'))
        response = client.get(reverse('core:admin_view_result', args=[self.other_student.id, self.first_term.id]))

        self.assertRedirects(response, reverse('core:dashboard'))

    def test_class_teacher_broadsheet_does_not_switch_to_unmanaged_class(self):
        teacher_user = self._user('restricted_teacher', 'class_teacher', 'Restricted', 'Teacher')
        SchoolMembership.objects.create(school=self.school, user=teacher_user, primary_role='class_teacher')
        teacher = Teacher.all_objects.create(school=self.school, user=teacher_user, employee_id='TCH002')
        teacher.classes.add(self.other_class)
        ClassTeacher.all_objects.create(teacher=teacher, school_class=self.school_class)

        client = Client(HTTP_HOST=self.host)
        self.assertTrue(client.login(username='restricted_teacher', password='password'))
        response = client.get(reverse('core:class_broadsheet'), {
            'class_id': self.other_class.id,
            'term_id': self.first_term.id,
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Managed Student')
        self.assertNotContains(response, 'Other Student')

    def test_admin_can_bulk_print_report_cards_for_selected_class(self):
        response = self.admin_client.get(reverse('core:bulk_print_report_cards'), {
            'class_id': self.school_class.id,
            'term_id': self.first_term.id,
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Bulk Report Cards')
        self.assertContains(response, 'Print All Report Cards')
        self.assertContains(response, 'Managed Student')
        self.assertContains(response, 'Mathematics')
        self.assertNotContains(response, 'Other Student')
        self.assertNotContains(response, 'Science')

    def test_class_teacher_can_bulk_print_report_cards_when_enabled(self):
        teacher_user = self._user('bulk_teacher', 'class_teacher', 'Bulk', 'Teacher')
        SchoolMembership.objects.create(school=self.school, user=teacher_user, primary_role='class_teacher')
        teacher = Teacher.all_objects.create(school=self.school, user=teacher_user, employee_id='TCH004')
        ClassTeacher.all_objects.create(
            teacher=teacher,
            school_class=self.school_class,
            can_print_download_results=True,
        )

        client = Client(HTTP_HOST=self.host)
        self.assertTrue(client.login(username='bulk_teacher', password='password'))
        response = client.get(reverse('core:bulk_print_report_cards'), {
            'class_id': self.school_class.id,
            'term_id': self.first_term.id,
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Managed Student')
        self.assertNotContains(response, 'Other Student')

    def test_class_teacher_cannot_bulk_print_report_cards_when_disabled(self):
        teacher_user = self._user('view_only_bulk_teacher', 'class_teacher', 'View', 'Only')
        SchoolMembership.objects.create(school=self.school, user=teacher_user, primary_role='class_teacher')
        teacher = Teacher.all_objects.create(school=self.school, user=teacher_user, employee_id='TCH005')
        ClassTeacher.all_objects.create(
            teacher=teacher,
            school_class=self.school_class,
            can_print_download_results=False,
        )

        client = Client(HTTP_HOST=self.host)
        self.assertTrue(client.login(username='view_only_bulk_teacher', password='password'))
        response = client.get(reverse('core:bulk_print_report_cards'), {
            'class_id': self.school_class.id,
            'term_id': self.first_term.id,
        })

        self.assertRedirects(response, reverse('core:student_results_lookup'))
