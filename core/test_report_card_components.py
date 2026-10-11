from datetime import date, timedelta
from decimal import Decimal
import json
from importlib import import_module
from django.apps import apps
from django.db import connection

from django.test import Client, TestCase
from django.urls import reverse

from .models import (
    Attendance, ComponentResult, ReportCardSettings, Result, ResultComponent, ResultToken,
    SchoolClass, SchoolMembership, SchoolTenant, Student, Subject, Term, User,
    ClassTeacher, Teacher, StudentTermPlacement, GradingSystem,
)
from .models_features import SchoolDomain
from .models_license import SystemLicense
from .views import _build_report_card_data
from .services_term_placements import capture_term_placement


class ReportCardComponentTests(TestCase):
    def setUp(self):
        self.school = SchoolTenant.objects.create(name='Report School', slug='report-test')
        SchoolDomain.objects.create(school=self.school, domain='reports.testserver')
        SystemLicense.all_objects.create(
            school=self.school, school_name=self.school.name, license_key='reports-test',
            expiry_date=date.today() + timedelta(days=30),
        )
        self.old_class = SchoolClass.all_objects.create(school=self.school, name='Basic 1')
        self.new_class = SchoolClass.all_objects.create(school=self.school, name='Basic 2')
        user = User.objects.create_user(username='report-student', role='student')
        self.admin = User.objects.create_user(username='report-admin', role='super_admin')
        for member in (user, self.admin):
            SchoolMembership.objects.create(school=self.school, user=member, primary_role=member.role)
        self.student = Student.all_objects.create(
            school=self.school, user=user, student_id='R001', school_class=self.old_class,
            date_of_birth=date(2015, 1, 1),
        )
        self.subject = Subject.all_objects.create(school=self.school, name='English', code='ENG')
        self.term = Term.all_objects.create(
            school=self.school, name='Third Term', session='2025-2026',
            start_date=date(2026, 4, 1), end_date=date(2026, 7, 15),
            vacation_date=date(2026, 7, 16), resumption_date=date(2026, 9, 14), result_published=True,
        )
        self.settings = ReportCardSettings.all_objects.create(school=self.school, third_term_mode='cumulative')
        self.ce = ResultComponent.all_objects.create(
            school_class=self.old_class, subject=self.subject, component_name='CE', weight=30, max_score=30,
        )
        self.exam = ResultComponent.all_objects.create(
            school_class=self.old_class, subject=self.subject, component_name='Exam', weight=70, max_score=70,
        )
        ComponentResult.all_objects.create(student=self.student, term=self.term, component=self.ce, score=24)
        ComponentResult.all_objects.create(student=self.student, term=self.term, component=self.exam, score=56)
        self.result = Result.all_objects.create(student=self.student, subject=self.subject, term=self.term, total_score=80)
        self.client = Client(HTTP_HOST='reports.testserver')

    def _promote(self):
        self.student.school_class = self.new_class
        self.student.save(update_fields=['school_class'])
        for name, weight in [('Exam', 70), ('CE', 30)]:
            ResultComponent.all_objects.create(
                school_class=self.new_class, subject=self.subject, component_name=name, weight=weight, max_score=weight,
            )

    def _assert_scores(self, context):
        self.assertEqual([c['score'] for c in context['component_breakdown'][0]['components']], [24, 56])
        self.assertEqual([c['score'] for c in context['cumulative_results'][0]['components']], [24, 56])
        self.assertEqual(context['total_score'], 80)
        self.assertEqual(context['result_warnings'], [])
        self.assertEqual(context['vacation_date'], self.term.vacation_date)
        self.assertEqual(context['next_resumption'], self.term.resumption_date)

    def test_promoted_student_keeps_saved_components_in_all_report_routes(self):
        self._promote()
        token = ResultToken.all_objects.create(student=self.student, term=self.term)
        response = self.client.get(reverse('core:view_result_card', args=[token.token]))
        self.assertEqual(response.status_code, 200)
        self._assert_scores(response.context)
        self.client.force_login(self.admin)
        response = self.client.get(reverse('core:admin_view_result', args=[self.student.id, self.term.id]))
        self.assertEqual(response.status_code, 200)
        self._assert_scores(response.context)
        response = self.client.get(reverse('core:bulk_print_report_cards'), {
            'class_id': self.old_class.id, 'term_id': self.term.id,
        })
        self.assertEqual(response.status_code, 200)
        self._assert_scores(response.context['report_cards'][0])

    def test_aggregate_includes_actual_zero_and_ignores_absent_terms(self):
        first = Term.all_objects.create(
            school=self.school, name='First Term', session=self.term.session,
            start_date=date(2025, 9, 1), end_date=date(2025, 12, 1),
        )
        Result.all_objects.create(student=self.student, subject=self.subject, term=first, total_score=0)
        self._promote()
        row = _build_report_card_data(self.student, self.term)['cumulative_results'][0]
        self.assertEqual(row['first_term'], 0)
        self.assertIsNone(row['second_term'])
        self.assertEqual(row['cumulative_total'], 80)
        self.assertEqual(row['cumulative_average'], 40)

    def test_missing_component_is_not_shown_as_zero(self):
        ComponentResult.all_objects.filter(component=self.exam).delete()
        ComponentResult.all_objects.filter(component=self.ce).update(score=0)
        data = _build_report_card_data(self.student, self.term)
        self.assertEqual([c['score'] for c in data['component_breakdown'][0]['components']], [0, None])
        self.assertTrue(data['result_warnings'])
        self.assertEqual(data['total_score'], 80)

    def test_subject_columns_align_when_definitions_are_created_in_reverse_order(self):
        maths = Subject.all_objects.create(school=self.school, name='Maths', code='MTH')
        for name, weight, score in [('Exam', 70, 60), ('CE', 30, 20)]:
            component = ResultComponent.all_objects.create(
                school_class=self.old_class, subject=maths, component_name=name, weight=weight, max_score=weight,
            )
            ComponentResult.all_objects.create(student=self.student, term=self.term, component=component, score=score)
        Result.all_objects.create(student=self.student, subject=maths, term=self.term, total_score=80)
        rows = _build_report_card_data(self.student, self.term)['component_breakdown']
        for row in rows:
            self.assertEqual([c['name'] for c in row['components']], ['CE', 'Exam'])
        self.assertEqual([c['score'] for c in rows[1]['components']], [20, 60])

    def test_weighted_scores_and_total_mismatches_are_checked_without_overwriting_results(self):
        self.ce.max_score = 100
        self.ce.save(update_fields=['max_score'])
        ComponentResult.all_objects.filter(component=self.ce).update(score=80)
        data = _build_report_card_data(self.student, self.term)
        self.assertEqual(data['result_warnings'], [])
        self.result.total_score = Decimal('90')
        self.result.save(update_fields=['total_score'])
        data = _build_report_card_data(self.student, self.term)
        self.assertIn('saved total differs', data['result_warnings'][0])
        self.result.refresh_from_db()
        self.assertEqual(self.result.total_score, 90)

    def test_term_only_mode_still_uses_original_components_after_promotion(self):
        self.settings.third_term_mode = 'term_only'
        self.settings.save(update_fields=['third_term_mode'])
        self._promote()
        data = _build_report_card_data(self.student, self.term)
        self.assertEqual(data['cumulative_results'], [])
        self.assertEqual([c['score'] for c in data['component_breakdown'][0]['components']], [24, 56])

    def _assign_teacher(self, name, school_class):
        user = User.objects.create_user(username=name, first_name=name, role='class_teacher')
        SchoolMembership.objects.create(school=self.school, user=user, primary_role='class_teacher')
        teacher = Teacher.all_objects.create(school=self.school, user=user, employee_id=name, signature=f'signatures/{name}.png')
        ClassTeacher.objects.create(teacher=teacher, school_class=school_class, can_print_download_results=True)
        return teacher

    def _real_promotion(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('core:promote_students'), json.dumps({
            'student_ids': [self.student.pk], 'target_class_id': self.new_class.pk,
        }), content_type='application/json')
        self.assertTrue(response.json()['success'], response.content)
        self.student.refresh_from_db()

    def test_promotion_preserves_class_teacher_signature_and_original_report_class(self):
        old_teacher = self._assign_teacher('Basic4Teacher', self.old_class)
        self._assign_teacher('MrsCollins', self.new_class)
        self._real_promotion()
        old_teacher.user.first_name = 'Changed name'
        old_teacher.user.save(update_fields=['first_name'])
        old_teacher.signature = 'signatures/replacement.png'
        old_teacher.save(update_fields=['signature'])
        report = _build_report_card_data(self.student, self.term)
        self.assertEqual(report['report_class'], self.old_class)
        self.assertEqual(report['class_teacher_name'], 'Basic4Teacher')
        self.assertEqual(report['class_teacher_signature'].name, 'signatures/Basic4Teacher.png')
        response = self.client.get(reverse('core:admin_view_result', args=[self.student.pk, self.term.pk]))
        self.assertContains(response, 'Basic4Teacher')
        self.assertNotContains(response, 'MrsCollins')
        self.assertContains(response, 'signatures/Basic4Teacher.png')

    def test_original_teacher_can_find_and_correct_unpublished_historical_assessments(self):
        old_teacher = self._assign_teacher('OriginalTeacher', self.old_class)
        new_teacher = self._assign_teacher('NewTeacher', self.new_class)
        self._real_promotion()
        self.term.result_published = False
        self.term.save(update_fields=['result_published'])
        self.client.force_login(old_teacher.user)
        response = self.client.get(reverse('core:get_student_results'), {
            'class_id': self.old_class.pk, 'subject_id': self.subject.pk, 'term_id': self.term.pk,
        })
        self.assertEqual([row['id'] for row in response.json()['students']], [self.student.pk])
        response = self.client.get(reverse('core:admin_view_result', args=[self.student.pk, self.term.pk]))
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse('core:class_broadsheet'), {'class_id': self.old_class.pk, 'term_id': self.term.pk})
        self.assertContains(response, 'R001')
        response = self.client.get(reverse('core:export_results'), {'class_id': self.old_class.pk, 'subject_id': self.subject.pk})
        self.assertContains(response, 'R001')
        payload = {'student_id': self.student.pk, 'component_id': self.ce.pk, 'term_id': self.term.pk, 'score': 25}
        response = self.client.post(reverse('core:update_component_score'), json.dumps(payload), content_type='application/json')
        self.assertTrue(response.json()['success'], response.content)
        self.result.refresh_from_db()
        self.assertEqual(self.result.total_score, 81)
        self.client.force_login(new_teacher.user)
        response = self.client.get(reverse('core:get_student_results'), {
            'class_id': self.new_class.pk, 'subject_id': self.subject.pk, 'term_id': self.term.pk,
        })
        self.assertEqual(response.json()['students'], [])
        response = self.client.get(reverse('core:get_recent_results'), {'class_id': self.new_class.pk, 'subject_id': self.subject.pk})
        self.assertEqual(response.json()['results'], [])
        payload['score'] = 0
        response = self.client.post(reverse('core:update_component_score'), json.dumps(payload), content_type='application/json')
        self.assertFalse(response.json()['success'])
        self.result.refresh_from_db()
        self.assertEqual(self.result.total_score, 81)

    def test_published_historical_marks_stay_locked_after_promotion(self):
        teacher = self._assign_teacher('LockedTeacher', self.old_class)
        self._real_promotion()
        self.client.force_login(teacher.user)
        response = self.client.post(reverse('core:update_component_score'), json.dumps({
            'student_id': self.student.pk, 'component_id': self.ce.pk, 'term_id': self.term.pk, 'score': 0,
        }), content_type='application/json')
        self.assertFalse(response.json()['success'])
        self.result.refresh_from_db()
        self.assertEqual(self.result.total_score, 80)

    def test_historical_class_teacher_can_manage_attendance_after_promotion(self):
        teacher = self._assign_teacher('AttendanceTeacher', self.old_class)
        self._real_promotion()
        self.term.result_published = False
        self.term.save(update_fields=['result_published'])
        self.client.force_login(teacher.user)

        response = self.client.get(reverse('core:manage_attendance'), {
            'class_id': self.old_class.pk,
            'term_id': self.term.pk,
            'academic_session': self.term.session,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual([student.pk for student in response.context['students']], [self.student.pk])

        response = self.client.post(reverse('core:manage_attendance'), {
            'class_id': self.old_class.pk,
            'term_id': self.term.pk,
            'academic_session': self.term.session,
            f'attendance_{self.student.pk}_days_present': '92',
            f'attendance_{self.student.pk}_total_days': '100',
        })
        self.assertEqual(response.status_code, 302)
        attendance = Attendance.objects.get(student=self.student, term=self.term)
        self.assertEqual(attendance.days_present, 92)
        self.assertEqual(attendance.days_absent, 8)
        self.assertEqual(attendance.total_days, 100)

    def test_promotion_captures_an_attendance_only_term_placement(self):
        ComponentResult.all_objects.filter(student=self.student, term=self.term).delete()
        Result.all_objects.filter(student=self.student, term=self.term).delete()
        Attendance.all_objects.create(
            student=self.student,
            term=self.term,
            days_present=90,
            days_absent=10,
            total_days=100,
        )

        self._real_promotion()

        placement = StudentTermPlacement.all_objects.get(
            student=self.student,
            term=self.term,
        )
        self.assertEqual(placement.school_class, self.old_class)
        self.student.refresh_from_db()
        self.assertEqual(self.student.school_class, self.new_class)

    def test_attendance_rejects_present_days_above_total_without_partial_save(self):
        teacher = self._assign_teacher('AttendanceValidator', self.old_class)
        self.term.result_published = False
        self.term.save(update_fields=['result_published'])
        attendance = Attendance.objects.create(
            student=self.student,
            term=self.term,
            days_present=80,
            days_absent=20,
            total_days=100,
        )
        self.client.force_login(teacher.user)

        response = self.client.post(reverse('core:manage_attendance'), {
            'class_id': self.old_class.pk,
            'term_id': self.term.pk,
            'academic_session': self.term.session,
            f'attendance_{self.student.pk}_days_present': '106',
            f'attendance_{self.student.pk}_total_days': '92',
        })

        self.assertEqual(response.status_code, 302)
        attendance.refresh_from_db()
        self.assertEqual(attendance.days_present, 80)
        self.assertEqual(attendance.days_absent, 20)
        self.assertEqual(attendance.total_days, 100)

    def test_new_term_uses_new_class_without_relisting_learner_in_old_class(self):
        self._assign_teacher('PreviousTeacher', self.old_class)
        new_teacher = self._assign_teacher('CurrentTeacher', self.new_class)
        self._real_promotion()
        term = Term.all_objects.create(school=self.school, name='First Term', session='2026-2027', start_date=date(2026, 9, 14), end_date=date(2026, 12, 18))
        self.client.force_login(new_teacher.user)
        response = self.client.get(reverse('core:get_student_results'), {
            'class_id': self.new_class.pk, 'subject_id': self.subject.pk, 'term_id': term.pk,
        })
        self.assertEqual([row['id'] for row in response.json()['students']], [self.student.pk])
        self.assertEqual(_build_report_card_data(self.student, term)['class_teacher_name'], 'CurrentTeacher')

    def test_legacy_backfill_recovers_class_from_marks_and_does_not_overwrite_snapshots(self):
        self._assign_teacher('LegacyTeacher', self.old_class)
        self._assign_teacher('WrongNewTeacher', self.new_class)
        self._promote()
        migration = import_module('core.migrations.0068_backfill_student_term_placements')
        migration.backfill(apps, connection.schema_editor(atomic=False))
        placement = StudentTermPlacement.all_objects.get(student=self.student, term=self.term)
        self.assertEqual(placement.school_class, self.old_class)
        self.assertEqual(placement.teacher_name, 'LegacyTeacher')
        placement.teacher_name = 'Confirmed original teacher'
        placement.save(update_fields=['teacher_name'])
        migration.backfill(apps, connection.schema_editor(atomic=False))
        placement.refresh_from_db()
        self.assertEqual(placement.teacher_name, 'Confirmed original teacher')

    def test_signatory_is_frozen_at_publication_not_during_draft_entry(self):
        teacher = self._assign_teacher('DraftTeacher', self.old_class)
        capture_term_placement(self.student, self.term)
        teacher.user.first_name = 'FinalTeacher'
        teacher.user.save(update_fields=['first_name'])
        self.client.force_login(self.admin)
        self.client.post(reverse('core:school_admin_result_publication'), {'term_id': self.term.pk, 'action': 'publish'})
        placement = StudentTermPlacement.all_objects.get(student=self.student, term=self.term)
        self.assertTrue(placement.signatory_frozen)
        self.assertEqual(placement.teacher_name, 'FinalTeacher')

    def test_second_promotion_and_revert_do_not_rewrite_old_placement(self):
        self._assign_teacher('FirstTeacher', self.old_class)
        self._real_promotion()
        third_class = SchoolClass.all_objects.create(school=self.school, name='Basic 3')
        response = self.client.post(reverse('core:promote_students'), json.dumps({
            'student_ids': [self.student.pk], 'target_class_id': third_class.pk,
        }), content_type='application/json')
        self.assertTrue(response.json()['success'])
        response = self.client.post(reverse('core:revert_promotion'), json.dumps({
            'student_id': self.student.pk,
        }), content_type='application/json')
        self.assertTrue(response.json()['success'])
        self.student.refresh_from_db()
        self.assertEqual(self.student.school_class, self.new_class)
        placement = StudentTermPlacement.all_objects.get(student=self.student, term=self.term)
        self.assertEqual(placement.school_class, self.old_class)
        self.assertEqual(placement.teacher_name, 'FirstTeacher')

    def test_legacy_total_without_class_evidence_does_not_use_new_teacher(self):
        self._assign_teacher('MrsNewTeacher', self.new_class)
        self._real_promotion()
        unknown_term = Term.all_objects.create(
            school=self.school, name='Second Term', session=self.term.session,
            start_date=date(2026, 1, 1), end_date=date(2026, 3, 31),
        )
        Result.all_objects.create(student=self.student, subject=self.subject, term=unknown_term, total_score=65)
        data = _build_report_card_data(self.student, unknown_term)
        self.assertIsNone(data['report_class'])
        self.assertEqual(data['class_teacher_name'], '')
        self.assertTrue(data['result_warnings'])

    def test_component_page_honours_requested_historical_term_instead_of_active_term(self):
        teacher = self._assign_teacher('TermSelectorTeacher', self.old_class)
        Term.all_objects.create(school=self.school, name='First Term', session='2026-2027', start_date=date(2026, 9, 14), end_date=date(2026, 12, 18), is_active=True)
        self.client.force_login(teacher.user)
        response = self.client.get(reverse('core:component_results'), {'term_id': self.term.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['selected_term'], self.term)

    def test_teacher_with_both_roles_can_manage_all_subjects_in_assigned_class(self):
        teacher = self._assign_teacher('BothRolesTeacher', self.old_class)
        SchoolMembership.objects.filter(school=self.school, user=teacher.user).update(extra_roles=['subject_teacher'])
        other_subject = Subject.all_objects.create(school=self.school, name='Music', code='MUS')
        teacher.subjects.add(other_subject)
        self.client.force_login(teacher.user)
        response = self.client.get(reverse('core:component_results'))
        self.assertIn(self.subject, response.context['subjects'])
        response = self.client.get(reverse('core:get_student_results'), {
            'class_id': self.old_class.pk, 'subject_id': self.subject.pk, 'term_id': self.term.pk,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['students']), 1)

    def test_zero_scores_round_trip_with_school_configured_grade(self):
        teacher = self._assign_teacher('ZeroScoreTeacher', self.old_class)
        self.client.force_login(teacher.user)
        self.term.result_published = False
        self.term.save(update_fields=['result_published'])
        ComponentResult.all_objects.filter(student=self.student).update(score=0)
        GradingSystem.all_objects.create(school=self.school, min_score=0, max_score=100, grade='EX', grade_point=1, remark='Custom scale')
        response = self.client.post(reverse('core:update_component_score'), json.dumps({
            'student_id': self.student.pk, 'component_id': self.ce.pk, 'term_id': self.term.pk, 'score': '0',
        }), content_type='application/json')
        self.assertTrue(response.json()['success'])
        self.assertEqual(response.json()['total_score'], 0)
        self.assertEqual(response.json()['grade'], 'EX')
        response = self.client.get(reverse('core:get_student_results'), {
            'class_id': self.old_class.pk, 'subject_id': self.subject.pk, 'term_id': self.term.pk,
        })
        row = response.json()['students'][0]
        self.assertEqual(row['component_scores'][str(self.ce.pk)], 0)
        self.assertEqual(row['total_score'], 0)
        self.assertEqual(row['grade'], 'EX')

    def test_invalid_score_does_not_change_saved_marks_or_total(self):
        teacher = self._assign_teacher('ValidationTeacher', self.old_class)
        self.client.force_login(teacher.user)
        self.term.result_published = False
        self.term.save(update_fields=['result_published'])
        for value in ('', '-1', '31', '1.234', 'NaN'):
            with self.subTest(score=value):
                response = self.client.post(reverse('core:update_component_score'), json.dumps({
                    'student_id': self.student.pk, 'component_id': self.ce.pk, 'term_id': self.term.pk, 'score': value,
                }), content_type='application/json')
                self.assertFalse(response.json()['success'])
                self.result.refresh_from_db()
                self.assertEqual(self.result.total_score, 80)
                self.assertEqual(ComponentResult.all_objects.get(student=self.student, component=self.ce, term=self.term).score, 24)

    def test_recalculation_clears_an_old_grade_when_new_total_has_no_matching_grade(self):
        self.result.grade = 'A'
        self.result.remark = 'Excellent'
        self.result.save(update_fields=['grade', 'remark'])
        self.result.calculate_total()
        self.result.refresh_from_db()
        self.assertEqual(self.result.total_score, 80)
        self.assertEqual(self.result.grade, '')
        self.assertEqual(self.result.remark, '')

