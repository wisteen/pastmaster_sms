import json
from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import SchoolClass, SchoolMembership, SchoolTenant, Student, Teacher
from .models_attendance import AttendanceRecord, AttendanceSession, IDCard
from .models_features import SchoolDomain
from .models_license import SystemLicense
from .services_id_cards import resolve_id_card, tenant_card_code


User = get_user_model()


class AttendanceIDHotfixTests(TestCase):
    host = 'attendance-hotfix.testserver'

    def setUp(self):
        self.school = SchoolTenant.objects.create(
            name='Attendance Hotfix School',
            slug='attendance-hotfix',
        )
        SchoolDomain.objects.create(school=self.school, domain=self.host)
        SystemLicense.all_objects.create(
            school=self.school,
            school_name=self.school.name,
            license_key='attendance-hotfix-license',
            expiry_date=date.today() + timedelta(days=30),
        )
        self.admin = self._member('attendance-admin', 'super_admin')
        self.school_class = SchoolClass.all_objects.create(school=self.school, name='Basic 2')
        self.client = Client(HTTP_HOST=self.host)

    def _member(self, username, role):
        user = User.objects.create_user(username=username, password='password', role=role)
        SchoolMembership.objects.create(school=self.school, user=user, primary_role=role)
        return user

    def _card_values(self, card_type, holder_id):
        tenant = tenant_card_code(self.school)
        if card_type == 'student':
            return f'{tenant}-STU-{holder_id}', f'{tenant}:STUDENT:{holder_id}'
        return f'{tenant}-TCH-{holder_id}', f'{tenant}:TEACHER:{holder_id}'

    def test_web_scanner_accepts_legacy_student_barcode_after_card_upgrade(self):
        student_user = self._member('legacy-student', 'student')
        student = Student.all_objects.create(
            school=self.school,
            user=student_user,
            student_id='STU0099',
            school_class=self.school_class,
            date_of_birth=date(2014, 1, 1),
        )
        card_number, barcode_data = self._card_values('student', student.student_id)
        IDCard.all_objects.create(
            student=student,
            card_type='student',
            card_number=card_number,
            barcode_data=barcode_data,
            expiry_date=timezone.localdate() + timedelta(days=365),
        )
        self.assertTrue(self.client.login(username='attendance-admin', password='password'))

        response = self.client.post(
            reverse('attendance:scan_barcode'),
            data=json.dumps({'barcode': 'STUDENT-STU0099'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data']['id'], student.student_id)

    def test_mobile_api_clocks_teacher_in_with_barcode_and_out_with_employee_id(self):
        teacher_user = self._member('attendance-teacher', 'subject_teacher')
        teacher = Teacher.all_objects.create(
            school=self.school,
            user=teacher_user,
            employee_id='TCH0042',
        )
        card_number, barcode_data = self._card_values('teacher', teacher.employee_id)
        card = IDCard.all_objects.create(
            teacher=teacher,
            card_type='teacher',
            card_number=card_number,
            barcode_data=barcode_data,
            expiry_date=timezone.localdate() + timedelta(days=365),
        )
        session = AttendanceSession.all_objects.create(
            school=self.school,
            date=timezone.localdate(),
            session_type='morning',
            created_by=self.admin,
        )

        check_in = self.client.post(reverse('core:api_mark_attendance'), {
            'barcode': barcode_data,
            'session_id': session.id,
            'action': 'in',
        })
        with patch(
            'core.views_attendance_api.timezone.now',
            return_value=timezone.now() + timedelta(minutes=11),
        ):
            check_out = self.client.post(reverse('core:api_mark_attendance'), {
                'student_id': teacher.employee_id,
                'session_id': session.id,
                'action': 'out',
            })

        self.assertEqual(check_in.status_code, 200)
        self.assertEqual(check_in.json()['holder_type'], 'teacher')
        self.assertEqual(check_out.status_code, 200)
        record = AttendanceRecord.objects.get(session=session, id_card=card)
        self.assertEqual(record.teacher, teacher)
        self.assertIsNone(record.student)
        self.assertIsNotNone(record.check_out_time)

    def test_mobile_api_reports_archived_teacher_card_as_inactive(self):
        teacher_user = self._member('former-attendance-teacher', 'subject_teacher')
        teacher = Teacher.all_objects.create(
            school=self.school,
            user=teacher_user,
            employee_id='TCH0043',
            status='former',
        )
        card_number, barcode_data = self._card_values('teacher', teacher.employee_id)
        IDCard.all_objects.create(
            teacher=teacher,
            card_type='teacher',
            card_number=card_number,
            barcode_data=barcode_data,
            expiry_date=timezone.localdate() + timedelta(days=365),
        )
        session = AttendanceSession.all_objects.create(
            school=self.school,
            date=timezone.localdate(),
            session_type='morning',
            created_by=self.admin,
        )

        response = self.client.post(reverse('core:api_mark_attendance'), {
            'barcode': barcode_data,
            'session_id': session.id,
            'action': 'in',
        })

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['message'], 'This ID card is inactive.')

    def test_tenant_prefixed_card_cannot_fall_back_to_same_id_in_another_school(self):
        local_user = self._member('local-same-id-teacher', 'subject_teacher')
        local_teacher = Teacher.all_objects.create(
            school=self.school,
            user=local_user,
            employee_id='TCH-SAME',
        )
        local_number, local_barcode = self._card_values('teacher', local_teacher.employee_id)
        IDCard.all_objects.create(
            teacher=local_teacher,
            card_type='teacher',
            card_number=local_number,
            barcode_data=local_barcode,
            expiry_date=timezone.localdate() + timedelta(days=365),
        )

        other_school = SchoolTenant.objects.create(name='Other School', slug='other-school')
        other_user = User.objects.create_user(
            username='other-same-id-teacher',
            password='password',
            role='subject_teacher',
        )
        SchoolMembership.objects.create(
            school=other_school,
            user=other_user,
            primary_role='subject_teacher',
        )
        other_teacher = Teacher.all_objects.create(
            school=other_school,
            user=other_user,
            employee_id='TCH-SAME',
        )
        other_tenant = tenant_card_code(other_school)
        other_card = IDCard.all_objects.create(
            teacher=other_teacher,
            card_type='teacher',
            card_number=f'{other_tenant}-TCH-{other_teacher.employee_id}',
            barcode_data=f'{other_tenant}:TEACHER:{other_teacher.employee_id}',
            expiry_date=timezone.localdate() + timedelta(days=365),
        )

        resolved = resolve_id_card(
            other_card.barcode_data,
            school=self.school,
            allow_teacher_number=True,
        )

        self.assertIsNone(resolved)
