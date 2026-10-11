import json
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import SchoolClass, SchoolMembership, SchoolMessage, SchoolTenant, Student, Term
from .models_biodata import Guardian
from .models_daily_attendance import DailyAttendanceRecord
from .models_attendance import AttendanceRecord, AttendanceSession, IDCard
from .models_features import SchoolDomain
from .models_license import SystemLicense
from .services_attendance_notifications import send_attendance_notifications
from .views_attendance_api import get_active_session


User = get_user_model()


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    EMAIL_HOST='smtp.test',
    EMAIL_HOST_USER='school@test.example',
    DEFAULT_FROM_EMAIL='school@test.example',
)
class AttendanceNotificationTests(TestCase):
    host = 'attendance-alerts.testserver'

    def setUp(self):
        self.school = SchoolTenant.objects.create(
            name='Attendance School', slug='attendance-school', plan='premium'
        )
        SchoolDomain.objects.create(school=self.school, domain=self.host)
        SystemLicense.all_objects.create(
            school=self.school,
            school_name=self.school.name,
            license_key='attendance-school-license',
            expiry_date=date.today() + timedelta(days=30),
        )
        self.student_user = self._member('student', 'student', 'student@example.com')
        self.parent_user = self._member('parent', 'parent', 'parent@example.com')
        self.school_class = SchoolClass.all_objects.create(
            school=self.school, name='JSS 1', stream='A'
        )
        self.student = Student.all_objects.create(
            school=self.school,
            user=self.student_user,
            student_id='STU-001',
            school_class=self.school_class,
            date_of_birth=date(2012, 1, 1),
        )
        Guardian.objects.create(
            student=self.student,
            user=self.parent_user,
            relationship='mother',
            title='Mrs',
            first_name='Test',
            last_name='Parent',
            phone_number='08012345678',
            email='parent@example.com',
            occupation='Parent',
            home_address='Home',
        )
        self.term = Term.all_objects.create(
            school=self.school,
            name='First Term',
            session='2026-2027',
            start_date=date.today() - timedelta(days=7),
            end_date=date.today() + timedelta(days=90),
            is_active=True,
        )
        self.client = Client(HTTP_HOST=self.host)
        self.client.force_login(self.student_user)

    def _member(self, username, role, email):
        user = User.objects.create_user(
            username=username, password='password', role=role, email=email
        )
        SchoolMembership.objects.create(
            school=self.school, user=user, primary_role=role
        )
        return user

    def test_notification_reaches_student_and_parent_in_app_and_email(self):
        result = send_attendance_notifications(
            self.student, 'check_in', actor=self.student_user
        )

        self.assertTrue(result['in_app'])
        self.assertEqual(result['email_sent'], 2)
        self.assertEqual({message.to[0] for message in mail.outbox}, {
            'student@example.com', 'parent@example.com',
        })
        alert = SchoolMessage.all_objects.get(school=self.school)
        self.assertEqual(
            set(alert.recipients.values_list('id', flat=True)),
            {self.student_user.id, self.parent_user.id},
        )

    def test_student_clock_prevents_duplicates_and_sends_each_transition_once(self):
        url = reverse('core:student_check_in_out')
        check_in = self.client.post(
            url, data='{"action":"in"}', content_type='application/json'
        )
        duplicate = self.client.post(
            url, data='{"action":"in"}', content_type='application/json'
        )
        check_out = self.client.post(
            url, data='{"action":"out"}', content_type='application/json'
        )

        self.assertEqual(check_in.status_code, 200)
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(check_out.status_code, 200)
        record = DailyAttendanceRecord.objects.get(student=self.student)
        self.assertIsNotNone(record.morning_time)
        self.assertIsNotNone(record.afternoon_time)
        self.assertEqual(SchoolMessage.all_objects.filter(school=self.school).count(), 2)
        self.assertEqual(len(mail.outbox), 4)

    def test_student_dashboard_restores_requested_service_links(self):
        response = self.client.get(reverse('core:dashboard'))

        self.assertEqual(response.status_code, 200)
        for label in [
            'School messages', 'View results', 'My assignments',
            'Academic calendar', 'Class timetable', 'Check result', 'CBT', 'Library',
        ]:
            self.assertContains(response, label)

    def test_scanner_session_lookup_requires_and_respects_school_context(self):
        other_school = SchoolTenant.objects.create(
            name='Other Attendance School',
            slug='other-attendance-school',
            plan='premium',
        )
        own_session = AttendanceSession.all_objects.create(
            school=self.school,
            date=timezone.localdate(),
            session_type='morning',
            created_by=self.parent_user,
        )
        AttendanceSession.all_objects.create(
            school=other_school,
            date=timezone.localdate(),
            session_type='morning',
            created_by=self.parent_user,
        )
        factory = RequestFactory()

        unscoped = get_active_session(factory.get('/api/attendance/active-session/'))
        scoped_request = factory.get('/api/attendance/active-session/')
        scoped_request.school = self.school
        scoped = get_active_session(scoped_request)

        self.assertEqual(unscoped.status_code, 400)
        self.assertEqual(scoped.status_code, 200)
        self.assertEqual(json.loads(scoped.content)['session_id'], own_session.id)

    def test_scanner_api_accepts_the_value_encoded_on_generated_id_cards(self):
        session = AttendanceSession.all_objects.create(
            school=self.school,
            date=timezone.localdate(),
            session_type='morning',
            created_by=self.parent_user,
        )
        card = IDCard.all_objects.create(
            student=self.student,
            card_number='S1-ATTENDANCE-STU-STU-001',
            barcode_data='S1-ATTENDANCE:STUDENT:STU-001',
            card_type='student',
            expiry_date=timezone.localdate() + timedelta(days=365),
        )

        response = self.client.post(reverse('core:api_mark_attendance'), {
            'student_id': card.barcode_data,
            'session_id': str(session.id),
            'action': 'in',
        })

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertTrue(AttendanceRecord.objects.filter(
            session=session,
            id_card=card,
            student=self.student,
        ).exists())
