from datetime import date, timedelta
from decimal import Decimal
import json
import re
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import (
    FeeStructure,
    PayrollStructure,
    Result,
    ResultToken,
    SchoolClass,
    SchoolMembership,
    SchoolSettings,
    SchoolMessage,
    SchoolTenant,
    StaffPayroll,
    Student,
    StudentFee,
    Subject,
    Teacher,
    Term,
)
from .models_biodata import Guardian
from .models_features import SchoolDomain
from .models_license import SystemLicense


User = get_user_model()


class FakeTermiiResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return b'{"code": "ok", "message_id": "termii-123"}'


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='PastMaster SMS <notifications@sms.pastmaster.test>',
)
class SchoolCommunicationTests(TestCase):
    host = 'communication.testserver'

    def setUp(self):
        self.school = SchoolTenant.objects.create(name='Communication School', slug='communication-school')
        SchoolDomain.objects.create(school=self.school, domain=self.host)
        SystemLicense.all_objects.create(
            school=self.school,
            school_name=self.school.name,
            license_key='communication-school-license',
            expiry_date=date.today() + timedelta(days=30),
        )
        self.admin = self._create_member('admin', 'super_admin', 'admin@example.com')
        self.student_user = self._create_member('student', 'student', 'student@example.com')
        self.parent = self._create_member('parent', 'parent', 'parent@example.com')
        self.teacher_user = self._create_member('teacher', 'subject_teacher', 'teacher@example.com')
        self.school_class = SchoolClass.all_objects.create(school=self.school, name='JSS 1', stream='A')
        self.term = Term.all_objects.create(
            school=self.school,
            name='First Term',
            session='2025-2026',
            start_date=date(2025, 9, 1),
            end_date=date(2025, 12, 15),
        )
        self.subject = Subject.all_objects.create(school=self.school, name='Mathematics', code='MTH')
        self.student = Student.all_objects.create(
            school=self.school,
            user=self.student_user,
            student_id='STU001',
            school_class=self.school_class,
            date_of_birth=date(2012, 1, 1),
        )
        Guardian.objects.create(
            student=self.student,
            user=self.parent,
            relationship='father',
            title='Mr',
            first_name='Test',
            last_name='Parent',
            phone_number='08012345678',
            email='parent@example.com',
            occupation='Parent',
            home_address='Home',
        )
        self.teacher = Teacher.all_objects.create(
            school=self.school,
            user=self.teacher_user,
            employee_id='TCH001',
        )
        self.client = Client(HTTP_HOST=self.host)
        self.assertTrue(self.client.login(username='admin', password='password'))

    def _create_member(self, username, role, email):
        user = User.objects.create_user(username=username, password='password', role=role, email=email)
        SchoolMembership.objects.create(school=self.school, user=user, primary_role=role)
        return user

    def test_admin_can_publish_and_email_result_to_student_and_parent(self):
        Result.all_objects.create(
            student=self.student,
            subject=self.subject,
            term=self.term,
            total_score=75,
            grade='B',
            grade_point=3,
            remark='Very Good',
        )

        response = self.client.post(reverse('core:school_admin_communications'), {
            'message_type': 'result',
            'student': self.student.id,
            'term': self.term.id,
        })

        self.assertRedirects(response, reverse('core:school_admin_communications'))
        self.term.refresh_from_db()
        self.assertTrue(self.term.result_published)
        self.assertEqual({email.to[0] for email in mail.outbox}, {'student@example.com', 'parent@example.com'})
        self.assertIn('Mathematics', mail.outbox[0].alternatives[0][0])

    def test_admin_can_email_fee_statement_with_outstanding_balance(self):
        structure = FeeStructure.objects.create(
            name='First Term Fees',
            school_class=self.school_class,
            term=self.term,
            tuition_fee=Decimal('1000.00'),
        )
        StudentFee.objects.create(
            student=self.student,
            fee_structure=structure,
            total_amount=Decimal('1000.00'),
            paid_amount=Decimal('300.00'),
            discount_amount=Decimal('100.00'),
            due_date=self.term.end_date,
        )

        self.client.post(reverse('core:school_admin_communications'), {
            'message_type': 'fee_statement',
            'student': self.student.id,
        })

        self.assertEqual(len(mail.outbox), 2)
        self.assertIn('600.00', mail.outbox[0].alternatives[0][0])

    def test_admin_can_email_teacher_payslip(self):
        structure = PayrollStructure.all_objects.create(
            school=self.school,
            name='Teachers',
            basic_salary=Decimal('1000.00'),
        )
        payroll = StaffPayroll.objects.create(
            teacher=self.teacher,
            payroll_structure=structure,
            month=date(2026, 6, 1),
            gross_salary=Decimal('1000.00'),
            net_salary=Decimal('1000.00'),
        )

        self.client.post(reverse('core:school_admin_communications'), {
            'message_type': 'payslip',
            'payroll': payroll.id,
        })

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['teacher@example.com'])
        self.assertIn('Payslip for June 2026', mail.outbox[0].subject)

    def test_admin_can_send_general_information_to_everyone_without_duplicate_parent_email(self):
        response = self.client.post(reverse('core:school_admin_communications'), {
            'message_type': 'announcement',
            'audience': 'everyone',
            'subject': 'School Reopens Monday',
            'message': 'Please check the portal for the updated calendar.',
        })

        self.assertRedirects(response, reverse('core:school_admin_communications'))
        self.assertEqual(
            {email.to[0] for email in mail.outbox},
            {'student@example.com', 'parent@example.com', 'teacher@example.com'},
        )

    def test_admin_can_send_login_details_by_tenant_email(self):
        response = self.client.post(reverse('core:school_admin_users'), {
            'action': 'send_login_details',
            'user_id': self.student_user.id,
            'channels': ['email'],
        })

        self.assertRedirects(response, reverse('core:school_admin_users'))
        self.assertEqual({email.to[0] for email in mail.outbox}, {'student@example.com', 'parent@example.com'})
        self.assertIn('portal login details', mail.outbox[0].subject)
        self.assertIn('Username: student', mail.outbox[0].body)
        match = re.search(r'^Password: (.+)$', mail.outbox[0].body, re.MULTILINE)
        self.assertIsNotNone(match)

        client = Client(HTTP_HOST=self.host)
        response = client.post(reverse('core:login'), {
            'username': 'student',
            'password': match.group(1),
            'role': 'student',
        })
        self.assertRedirects(response, reverse('core:dashboard'))

    @patch('core.services_portal_delivery.url_request.urlopen')
    def test_admin_can_send_result_token_through_tenant_termii_sms(self, mocked_urlopen):
        mocked_urlopen.return_value = FakeTermiiResponse()
        SchoolSettings.all_objects.create(
            school=self.school,
            school_name='Communication School',
            school_address='School Road',
            principal_name='Principal',
            termii_api_key='tenant-termii-key',
            termii_base_url='https://api.ng.termii.com',
            termii_sender_id='CommSch',
            termii_channel='dnd',
        )
        token = ResultToken.all_objects.create(student=self.student, term=self.term, max_uses=3)

        response = self.client.post(reverse('core:generate_tokens'), {
            'action': 'send_token_details',
            'token_id': token.id,
            'channels': ['sms'],
        })

        self.assertRedirects(response, reverse('core:generate_tokens'))
        mocked_urlopen.assert_called_once()
        request = mocked_urlopen.call_args[0][0]
        payload = json.loads(request.data.decode('utf-8'))
        self.assertEqual(request.full_url, 'https://api.ng.termii.com/api/sms/send')
        self.assertEqual(payload['api_key'], 'tenant-termii-key')
        self.assertEqual(payload['from'], 'CommSch')
        self.assertEqual(payload['channel'], 'dnd')
        self.assertEqual(payload['to'], '2348012345678')
        self.assertIn(token.token, payload['sms'])

    def test_admin_can_send_in_app_message_to_school_users(self):
        response = self.client.post(reverse('core:message_center'), {
            'audience': 'everyone',
            'subject': 'PTA Meeting',
            'body': 'The PTA meeting is now on the portal calendar.',
        })

        self.assertRedirects(response, reverse('core:message_center'))
        message = SchoolMessage.all_objects.get(subject='PTA Meeting')
        self.assertEqual(message.school, self.school)
        self.assertEqual(message.sender, self.admin)
        self.assertEqual(
            set(message.recipients.values_list('username', flat=True)),
            {'student', 'parent', 'teacher'},
        )
        self.assertEqual(len(mail.outbox), 3)
        self.assertEqual(
            {email.to[0] for email in mail.outbox},
            {'student@example.com', 'parent@example.com', 'teacher@example.com'},
        )
        self.assertTrue(all(
            email.from_email == 'PastMaster SMS <notifications@sms.pastmaster.test>'
            for email in mail.outbox
        ))
        self.assertTrue(all('New message from admin' in email.subject for email in mail.outbox))
        self.assertTrue(all(
            reverse('core:message_detail', args=[message.id]) in email.body
            for email in mail.outbox
        ))

    def test_teacher_can_read_and_reply_to_in_app_message(self):
        message = SchoolMessage.all_objects.create(
            school=self.school,
            sender=self.admin,
            audience='selected',
            subject='Class Update',
            body='Please send your class update.',
        )
        message.recipients.add(self.teacher_user)

        teacher_client = Client(HTTP_HOST=self.host)
        self.assertTrue(teacher_client.login(username='teacher', password='password'))

        response = teacher_client.get(reverse('core:message_center'))
        self.assertContains(response, 'Class Update')

        response = teacher_client.get(reverse('core:message_detail', args=[message.id]))
        self.assertContains(response, 'Please send your class update.')
        self.assertTrue(message.read_by.filter(id=self.teacher_user.id).exists())

        response = teacher_client.post(reverse('core:message_detail', args=[message.id]), {
            'body': 'The update is ready.',
        })

        reply = SchoolMessage.all_objects.get(parent=message)
        self.assertRedirects(response, reverse('core:message_detail', args=[reply.id]))
        self.assertEqual(reply.sender, self.teacher_user)
        self.assertEqual(list(reply.recipients.all()), [self.admin])
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['admin@example.com'])
        self.assertNotIn('teacher@example.com', mail.outbox[0].to)
        self.assertIn('New reply from teacher', mail.outbox[0].subject)
        self.assertIn(reverse('core:message_detail', args=[reply.id]), mail.outbox[0].body)

    def test_replying_to_a_reply_notifies_the_other_party(self):
        message = SchoolMessage.all_objects.create(
            school=self.school,
            sender=self.admin,
            audience='selected',
            subject='Class Update',
            body='Please send your class update.',
        )
        message.recipients.add(self.teacher_user)
        reply = SchoolMessage.all_objects.create(
            school=self.school,
            sender=self.teacher_user,
            parent=message,
            audience='selected',
            subject='Re: Class Update',
            body='The update is ready.',
        )
        reply.recipients.add(self.admin)

        response = self.client.post(reverse('core:message_detail', args=[reply.id]), {
            'body': 'Thank you. I have reviewed it.',
        })

        second_reply = SchoolMessage.all_objects.get(parent=reply)
        self.assertRedirects(response, reverse('core:message_detail', args=[second_reply.id]))
        self.assertEqual(list(second_reply.recipients.all()), [self.teacher_user])
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['teacher@example.com'])
        self.assertNotIn('admin@example.com', mail.outbox[0].to)
