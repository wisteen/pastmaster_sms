from datetime import date, timedelta
from io import BytesIO
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import SchoolClass, SchoolMembership, SchoolSettings, SchoolTenant, Student, Subject, Teacher
from .models_biodata import Guardian, StaffBankAccount, StaffBioData, StaffQualification, StudentBioData
from .models_features import SchoolDomain
from .models_license import SystemLicense
from .models_onboarding import OnboardingRecord
from .services_onboarding import create_basic_person
from .services_portal_delivery import TenantPortalDeliveryService


User = get_user_model()


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='Virtuakids <default@virtuakids.test>',
)
class OnboardingWorkflowTests(TestCase):
    host = 'onboarding.testserver'

    def setUp(self):
        self.school = SchoolTenant.objects.create(name='Onboarding School', slug='onboarding-school')
        SchoolDomain.objects.create(school=self.school, domain=self.host)
        SystemLicense.all_objects.create(
            school=self.school,
            school_name=self.school.name,
            license_key='onboarding-school-license',
            expiry_date=date.today() + timedelta(days=30),
        )
        self.admin = User.objects.create_user(
            username='onboarding-admin',
            password='password',
            role='super_admin',
        )
        SchoolMembership.objects.create(
            school=self.school,
            user=self.admin,
            primary_role='super_admin',
        )
        self.school_class = SchoolClass.all_objects.create(
            school=self.school,
            name='JSS 1',
            stream='A',
        )
        self.subject = Subject.all_objects.create(
            school=self.school,
            name='Mathematics',
            code='MTH',
        )
        self.client = Client(HTTP_HOST=self.host)
        self.assertTrue(self.client.login(username='onboarding-admin', password='password'))

    def test_admin_page_tracks_existing_people(self):
        user = User.objects.create_user(
            username='existing-student',
            password='password',
            role='student',
            first_name='Existing',
            last_name='Student',
        )
        SchoolMembership.objects.create(school=self.school, user=user, primary_role='student')
        student = Student.all_objects.create(
            school=self.school,
            user=user,
            school_class=self.school_class,
            date_of_birth=date(2013, 1, 1),
        )

        response = self.client.get(reverse('core:school_admin_onboarding'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Existing Student')
        self.assertContains(response, 'portal-sidebar-toggle')
        record = OnboardingRecord.all_objects.get(school=self.school, student=student)
        self.assertEqual(record.status, OnboardingRecord.STATUS_ACTIVE)

    def test_downloads_csv_and_xlsx_templates(self):
        csv_response = self.client.get(reverse(
            'core:download_onboarding_template',
            args=['student', 'csv'],
        ))
        xlsx_response = self.client.get(reverse(
            'core:download_onboarding_template',
            args=['teacher', 'xlsx'],
        ))

        self.assertEqual(csv_response.status_code, 200)
        self.assertIn('first_name,last_name,class_name', csv_response.content.decode('utf-8-sig'))
        self.assertEqual(xlsx_response.status_code, 200)
        self.assertGreater(len(xlsx_response.content), 1000)

    def test_csv_preview_then_import_creates_disabled_basic_profile(self):
        csv_upload = SimpleUploadedFile(
            'students.csv',
            (
                'first_name,last_name,class_name,class_stream,date_of_birth,gender,'
                'guardian_name,guardian_email,guardian_phone\n'
                'Ada,Nwosu,JSS 1,A,2013-05-10,F,Ifeoma Nwosu,ifeoma@example.com,08030000000\n'
            ).encode('utf-8'),
            content_type='text/csv',
        )
        preview = self.client.post(reverse('core:school_admin_onboarding'), {
            'action': 'preview_upload',
            'upload-person_type': 'student',
            'upload-spreadsheet': csv_upload,
        })
        self.assertEqual(preview.status_code, 200)
        self.assertContains(preview, 'Spreadsheet preview')
        self.assertContains(preview, 'Ada')

        import_response = self.client.post(reverse('core:school_admin_onboarding'), {
            'action': 'import_rows',
            'person_type': 'student',
            'row_count': '1',
            'row_0_first_name': 'Ada',
            'row_0_last_name': 'Nwosu',
            'row_0_class_name': 'JSS 1',
            'row_0_class_stream': 'A',
            'row_0_date_of_birth': '2013-05-10',
            'row_0_gender': 'F',
            'row_0_guardian_name': 'Ifeoma Nwosu',
            'row_0_guardian_email': 'ifeoma@example.com',
            'row_0_guardian_phone': '08030000000',
        })

        self.assertRedirects(import_response, reverse('core:school_admin_onboarding'))
        student = Student.all_objects.get(user__first_name='Ada', school=self.school)
        membership = SchoolMembership.objects.get(school=self.school, user=student.user)
        record = OnboardingRecord.all_objects.get(student=student)
        self.assertFalse(membership.portal_access_enabled)
        self.assertFalse(student.user.has_usable_password())
        self.assertEqual(record.status, OnboardingRecord.STATUS_BASIC)
        self.assertEqual(record.source, OnboardingRecord.SOURCE_BULK)

    def test_preview_rows_can_be_revalidated_without_page_refresh(self):
        response = self.client.post(
            reverse('core:school_admin_onboarding'),
            {
                'action': 'validate_rows',
                'person_type': 'student',
                'row_count': '1',
                'row_0_first_name': 'Ada',
                'row_0_last_name': 'Nwosu',
                'row_0_class_name': 'JSS 1',
                'row_0_class_stream': 'A',
                'row_0_date_of_birth': '2013-05-10',
                'row_0_gender': 'F',
                'row_0_guardian_name': 'Ifeoma Nwosu',
                'row_0_guardian_email': 'ifeoma@example.com',
                'row_0_guardian_phone': '08030000000',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['valid'])
        self.assertEqual(payload['valid_count'], 1)
        self.assertEqual(payload['invalid_count'], 0)

    def test_onboarding_email_retries_with_default_sender_when_school_smtp_fails(self):
        record = create_basic_person(
            self.school,
            OnboardingRecord.PERSON_TEACHER,
            {
                'first_name': 'Zainab',
                'last_name': 'Lawal',
                'email': 'zainab@example.com',
                'phone': '',
                'subjects': [self.subject],
                'classes': [self.school_class],
            },
            created_by=self.admin,
        )
        school_settings, _ = SchoolSettings.objects.get_or_create(
            school=self.school,
            defaults={
                'school_name': self.school.name,
                'school_address': '1 Test Road',
                'principal_name': 'Test Principal',
            },
        )
        school_settings.email_host = 'smtp.school.test'
        school_settings.email_from_address = 'school@school.test'
        school_settings.save(update_fields=['email_host', 'email_from_address'])

        school_message = Mock()
        school_message.send.side_effect = RuntimeError('school smtp unavailable')
        fallback_message = Mock()
        fallback_message.send.return_value = 1

        with patch(
            'core.services_portal_delivery.EmailMultiAlternatives',
            side_effect=[school_message, fallback_message],
        ) as email_class:
            summary = TenantPortalDeliveryService(self.school).send_onboarding_invitation(
                record,
                'https://portal.test/onboarding/invitation/token/',
                ['email'],
            )

        self.assertEqual(summary.sent, 1)
        self.assertEqual(summary.failed, 0)
        self.assertEqual(email_class.call_count, 2)
        self.assertEqual(email_class.call_args_list[0].kwargs['from_email'], 'school@school.test')
        self.assertEqual(
            email_class.call_args_list[1].kwargs['from_email'],
            'Virtuakids <default@virtuakids.test>',
        )

    def test_invitation_token_is_hashed_and_parent_can_submit(self):
        record = create_basic_person(
            self.school,
            OnboardingRecord.PERSON_STUDENT,
            {
                'first_name': 'Chidi',
                'last_name': 'Eze',
                'school_class': self.school_class,
                'date_of_birth': date(2013, 2, 2),
                'gender': 'M',
                'guardian_name': 'Ngozi Eze',
                'guardian_email': 'ngozi@example.com',
                'guardian_phone': '08030000001',
            },
            created_by=self.admin,
        )
        raw_token = record.issue_invitation()
        self.assertNotEqual(record.token_digest, raw_token)
        self.assertNotIn(raw_token, record.token_digest)

        public_client = Client(HTTP_HOST=self.host)
        response = public_client.post(reverse('core:onboarding_invitation', args=[raw_token]), {
            'student-date_of_birth': '2013-02-02',
            'student-place_of_birth': 'Lagos',
            'student-nationality': 'Nigerian',
            'student-state_of_origin': 'Enugu',
            'student-lga': 'Nsukka',
            'student-religion': 'Christianity',
            'student-home_address': '12 School Road',
            'student-phone_number': '08030000001',
            'student-email': 'ngozi@example.com',
            'guardian-relationship': 'mother',
            'guardian-title': 'Mrs',
            'guardian-first_name': 'Ngozi',
            'guardian-last_name': 'Eze',
            'guardian-phone_number': '08030000001',
            'guardian-email': 'ngozi@example.com',
            'guardian-occupation': 'Trader',
            'guardian-home_address': '12 School Road',
            'guardian-is_primary_contact': 'on',
            'guardian-is_emergency_contact': 'on',
        })

        self.assertRedirects(response, reverse('core:onboarding_invitation', args=[raw_token]))
        record.refresh_from_db()
        self.assertEqual(record.status, OnboardingRecord.STATUS_PENDING_REVIEW)
        self.assertTrue(StudentBioData.objects.filter(student=record.student).exists())
        self.assertTrue(Guardian.objects.filter(student=record.student, first_name='Ngozi').exists())

    def test_teacher_self_service_collects_required_records(self):
        record = create_basic_person(
            self.school,
            OnboardingRecord.PERSON_TEACHER,
            {
                'first_name': 'Zainab',
                'last_name': 'Lawal',
                'email': 'zainab@example.com',
                'phone': '08030000002',
                'subjects': [self.subject],
                'classes': [self.school_class],
            },
            created_by=self.admin,
        )
        raw_token = record.issue_invitation()
        signature = SimpleUploadedFile(
            'signature.gif',
            self._gif_bytes(),
            content_type='image/gif',
        )
        public_client = Client(HTTP_HOST=self.host)
        response = public_client.post(reverse('core:onboarding_invitation', args=[raw_token]), {
            'staff-date_of_birth': '1990-01-01',
            'staff-place_of_birth': 'Abuja',
            'staff-nationality': 'Nigerian',
            'staff-state_of_origin': 'Kano',
            'staff-lga': 'Nasarawa',
            'staff-religion': 'Islam',
            'staff-marital_status': 'single',
            'staff-home_address': '4 Learning Avenue',
            'staff-phone_number': '08030000002',
            'staff-email': 'zainab@example.com',
            'staff-emergency_contact_name': 'Amina Lawal',
            'staff-emergency_contact_relationship': 'Sister',
            'staff-emergency_contact_phone': '08030000003',
            'staff-emergency_contact_address': '4 Learning Avenue',
            'staff-date_of_employment': '2026-08-01',
            'staff-employment_type': 'full_time',
            'staff-department': 'Science',
            'staff-position': 'Teacher',
            'staff-years_of_experience': '4',
            'qualification-qualification_type': 'bsc',
            'qualification-institution': 'University of Abuja',
            'qualification-course_of_study': 'Mathematics',
            'qualification-grade': 'Second Class Upper',
            'qualification-year_obtained': '2014',
            'bank-bank_name': 'Test Bank',
            'bank-account_number': '0123456789',
            'bank-account_name': 'Zainab Lawal',
            'bank-account_type': 'savings',
            'teacher-signature': signature,
        })

        self.assertRedirects(response, reverse('core:onboarding_invitation', args=[raw_token]))
        record.refresh_from_db()
        record.teacher.refresh_from_db()
        self.assertEqual(record.status, OnboardingRecord.STATUS_PENDING_REVIEW)
        self.assertTrue(StaffBioData.objects.filter(teacher=record.teacher).exists())
        self.assertTrue(StaffQualification.objects.filter(staff_bio_data__teacher=record.teacher).exists())
        self.assertTrue(StaffBankAccount.objects.filter(staff_bio_data__teacher=record.teacher).exists())
        self.assertTrue(bool(record.teacher.signature))

    def test_admin_approval_then_login_delivery_activates_portal(self):
        record = self._completed_student_record()
        record.status = OnboardingRecord.STATUS_PENDING_REVIEW
        record.save(update_fields=['status', 'updated_at'])

        approval = self.client.post(reverse('core:review_onboarding', args=[record.id]), {
            'action': 'approve',
            'review_note': '',
            'channels': ['email'],
        })
        self.assertRedirects(approval, reverse('core:school_admin_onboarding'))
        record.refresh_from_db()
        self.assertEqual(record.status, OnboardingRecord.STATUS_READY)

        delivery = self.client.post(reverse('core:school_admin_onboarding'), {
            'action': 'send_login',
            'record_id': record.id,
            'channels': ['email'],
        })
        self.assertRedirects(delivery, reverse('core:school_admin_onboarding'))
        record.refresh_from_db()
        record.user.refresh_from_db()
        membership = SchoolMembership.objects.get(school=self.school, user=record.user)
        self.assertEqual(record.status, OnboardingRecord.STATUS_ACTIVE)
        self.assertTrue(record.login_sent_at)
        self.assertTrue(record.user.has_usable_password())
        self.assertTrue(membership.portal_access_enabled)

    def _completed_student_record(self):
        record = create_basic_person(
            self.school,
            OnboardingRecord.PERSON_STUDENT,
            {
                'first_name': 'Bola',
                'last_name': 'Adeyemi',
                'school_class': self.school_class,
                'date_of_birth': date(2013, 3, 3),
                'gender': 'F',
                'guardian_name': 'Tola Adeyemi',
                'guardian_email': 'tola@example.com',
                'guardian_phone': '08030000004',
            },
            created_by=self.admin,
        )
        StudentBioData.objects.create(
            student=record.student,
            date_of_birth=date(2013, 3, 3),
            place_of_birth='Lagos',
            state_of_origin='Lagos',
            lga='Ikeja',
            religion='Christianity',
            home_address='8 Portal Road',
            phone_number='08030000004',
            email='tola@example.com',
        )
        Guardian.objects.create(
            student=record.student,
            relationship='mother',
            title='Mrs',
            first_name='Tola',
            last_name='Adeyemi',
            phone_number='08030000004',
            email='tola@example.com',
            occupation='Engineer',
            home_address='8 Portal Road',
            is_primary_contact=True,
        )
        return record

    @staticmethod
    def _gif_bytes():
        return (
            b'GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00ccc,'
            b'\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
        )
