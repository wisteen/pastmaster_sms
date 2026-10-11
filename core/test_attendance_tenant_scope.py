from datetime import date, timedelta
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import SchoolClass, SchoolMembership, SchoolSettings, SchoolTenant, Student
from .models_attendance import IDCard
from .models_features import SchoolDomain
from .models_license import SystemLicense


User = get_user_model()


class AttendanceIDCardTenantScopeTests(TestCase):
    platform_host = 'virtuakids.com.ng'
    jewels_host = 'jewelsofcalvaryschools.com.ng'

    def setUp(self):
        self.platform_school = self._school('Virtuakids', 'virtuakids', self.platform_host)
        self.jewels_school = self._school('Jewels of Calvary School', 'jewels-of-calvary', self.jewels_host)
        SchoolSettings.all_objects.create(
            school=self.jewels_school,
            school_name='Jewels of Calvary School',
            school_address='Calvary Road',
            principal_name='Principal',
            primary_color='#123456',
            secondary_color='#654321',
            accent_color='#ff8800',
        )

        self.platform_admin = self._user('virtuakids-admin', 'super_admin', 'Virtual', 'Kids')
        self.jewels_admin = self._user('jewels-admin', 'super_admin', 'Jewels', 'Admin')
        SchoolMembership.objects.create(
            school=self.platform_school,
            user=self.platform_admin,
            primary_role='super_admin',
        )
        SchoolMembership.objects.create(
            school=self.jewels_school,
            user=self.jewels_admin,
            primary_role='super_admin',
        )

        self.platform_class = SchoolClass.all_objects.create(
            school=self.platform_school,
            name='JSS 1',
            stream='A',
        )
        self.jewels_class = SchoolClass.all_objects.create(
            school=self.jewels_school,
            name='JSS 1',
            stream='A',
        )
        self.platform_student = self._student(
            'virtuakids-student',
            self.platform_school,
            self.platform_class,
            'STU0007',
            'Virtual',
            'Student',
        )
        self.jewels_student = self._student(
            'jewels-student',
            self.jewels_school,
            self.jewels_class,
            'STU0007',
            'Jewels',
            'Student',
        )
        self.legacy_platform_card = IDCard.all_objects.create(
            student=self.platform_student,
            card_number='STU-STU0007',
            barcode_data='STUDENT-STU0007',
            card_type='student',
            expiry_date=timezone.now().date() + timedelta(days=365),
        )

        self.jewels_client = Client(HTTP_HOST=self.jewels_host)
        self.assertTrue(self.jewels_client.login(username='jewels-admin', password='password'))

    def _school(self, name, slug, host):
        school = SchoolTenant.objects.create(name=name, slug=slug, plan='premium')
        SchoolDomain.objects.create(school=school, domain=host)
        SystemLicense.all_objects.create(
            school=school,
            school_name=name,
            license_key=f'{slug}-license',
            expiry_date=date.today() + timedelta(days=30),
        )
        return school

    def _user(self, username, role, first_name, last_name):
        return User.objects.create_user(
            username=username,
            password='password',
            role=role,
            first_name=first_name,
            last_name=last_name,
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

    def _jewels_card_identity(self):
        return (
            f'S{self.jewels_school.pk}-JEWELSOFCALVARY-STU-STU0007',
            f'S{self.jewels_school.pk}-JEWELSOFCALVARY:STUDENT:STU0007',
        )

    def test_same_student_number_in_different_tenants_generates_unique_card(self):
        response = self.jewels_client.get(
            reverse('attendance:generate_id_card', args=['student', self.jewels_student.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '#123456')
        self.assertNotContains(response, 'DOB')
        self.assertNotContains(response, 'Date of Birth')
        self.assertNotContains(response, 'Expires')
        self.assertNotContains(response, 'Valid')
        self.assertNotContains(response, '<strong>Address:')
        jewels_card = IDCard.all_objects.get(student=self.jewels_student)
        expected_card_number, expected_barcode = self._jewels_card_identity()
        self.assertEqual(jewels_card.card_number, expected_card_number)
        self.assertEqual(jewels_card.barcode_data, expected_barcode)
        self.assertNotEqual(jewels_card.card_number, self.legacy_platform_card.card_number)
        self.assertNotEqual(jewels_card.barcode_data, self.legacy_platform_card.barcode_data)

    def test_generate_id_card_does_not_allow_cross_tenant_holder_id(self):
        response = self.jewels_client.get(
            reverse('attendance:generate_id_card', args=['student', self.platform_student.id])
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(IDCard.all_objects.filter(student=self.jewels_student).exists())

    def test_id_card_list_only_shows_active_tenant_cards(self):
        card_number, barcode_data = self._jewels_card_identity()
        jewels_card = IDCard.all_objects.create(
            student=self.jewels_student,
            card_number=card_number,
            barcode_data=barcode_data,
            card_type='student',
            expiry_date=timezone.now().date() + timedelta(days=365),
        )

        response = self.jewels_client.get(reverse('attendance:id_card_list'))

        self.assertEqual(response.status_code, 200)
        cards = list(response.context['cards'])
        self.assertEqual(cards, [jewels_card])
        self.assertNotIn(self.legacy_platform_card, cards)
        self.assertContains(response, jewels_card.card_number)

    def test_download_id_card_does_not_allow_cross_tenant_card_id(self):
        response = self.jewels_client.get(
            reverse('attendance:download_id_card', args=[self.legacy_platform_card.id])
        )

        self.assertEqual(response.status_code, 404)

    def test_scan_barcode_does_not_accept_another_tenant_card(self):
        response = self.jewels_client.post(
            reverse('attendance:scan_barcode'),
            data=json.dumps({'barcode': self.legacy_platform_card.barcode_data}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {
            'success': False,
            'error': 'Invalid ID card for this school',
        })

    def test_scan_accepts_generated_qr_and_printed_card_number(self):
        generate_response = self.jewels_client.get(
            reverse('attendance:generate_id_card', args=['student', self.jewels_student.id])
        )
        self.assertEqual(generate_response.status_code, 200)
        card = IDCard.all_objects.get(student=self.jewels_student)

        check_in = self.jewels_client.post(
            reverse('attendance:scan_barcode'),
            data=json.dumps({'barcode': f'  {card.barcode_data}\n'}),
            content_type='application/json',
        )
        with patch(
            'core.views_attendance.timezone.now',
            return_value=timezone.now() + timedelta(minutes=11),
        ):
            check_out = self.jewels_client.post(
                reverse('attendance:scan_barcode'),
                data=json.dumps({'barcode': card.card_number}),
                content_type='application/json',
            )

        self.assertEqual(check_in.status_code, 200)
        self.assertEqual(check_in.json()['data']['action'], 'checkin')
        self.assertEqual(check_out.status_code, 200)
        self.assertEqual(check_out.json()['data']['action'], 'checkout')

    def test_scan_explains_when_matching_card_is_inactive(self):
        card_number, barcode_data = self._jewels_card_identity()
        IDCard.all_objects.create(
            student=self.jewels_student,
            card_number=card_number,
            barcode_data=barcode_data,
            card_type='student',
            expiry_date=timezone.localdate() + timedelta(days=365),
            is_active=False,
        )

        response = self.jewels_client.post(
            reverse('attendance:scan_barcode'),
            data=json.dumps({'barcode': barcode_data}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {
            'success': False,
            'error': 'This ID card is inactive',
        })

    def test_bulk_print_page_is_tenant_scoped_and_omits_dob(self):
        card_number, barcode_data = self._jewels_card_identity()
        jewels_card = IDCard.all_objects.create(
            student=self.jewels_student,
            card_number=card_number,
            barcode_data=barcode_data,
            card_type='student',
            expiry_date=timezone.now().date() + timedelta(days=365),
        )

        response = self.jewels_client.get(reverse('attendance:print_id_cards'), {
            'ids': f'{jewels_card.id},{self.legacy_platform_card.id}',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['id_card'] for item in response.context['card_items']], [jewels_card])
        self.assertContains(response, '#123456')
        self.assertContains(response, 'Print ID Cards')
        self.assertNotContains(response, 'DOB')
        self.assertNotContains(response, 'Date of Birth')
        self.assertNotContains(response, 'Expires')
        self.assertNotContains(response, 'Valid')
        self.assertNotContains(response, '<strong>Address:')

    def test_pdf_download_returns_card_pdf(self):
        card_number, barcode_data = self._jewels_card_identity()
        jewels_card = IDCard.all_objects.create(
            student=self.jewels_student,
            card_number=card_number,
            barcode_data=barcode_data,
            card_type='student',
            expiry_date=timezone.now().date() + timedelta(days=365),
        )

        response = self.jewels_client.get(reverse('attendance:download_id_card', args=[jewels_card.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_scan_barcode_does_not_reject_cards_by_expiry_date(self):
        card_number, barcode_data = self._jewels_card_identity()
        IDCard.all_objects.create(
            student=self.jewels_student,
            card_number=card_number,
            barcode_data=barcode_data,
            card_type='student',
            expiry_date=timezone.now().date() - timedelta(days=1),
        )

        response = self.jewels_client.post(
            reverse('attendance:scan_barcode'),
            data=json.dumps({'barcode': barcode_data}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])

    def test_png_download_returns_card_image(self):
        card_number, barcode_data = self._jewels_card_identity()
        jewels_card = IDCard.all_objects.create(
            student=self.jewels_student,
            card_number=card_number,
            barcode_data=barcode_data,
            card_type='student',
            expiry_date=timezone.now().date() + timedelta(days=365),
        )

        response = self.jewels_client.get(
            reverse('attendance:download_id_card_image', args=[jewels_card.id, 'front'])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/png')
        self.assertIn('id_card_', response['Content-Disposition'])
        self.assertTrue(response.content.startswith(b'\x89PNG\r\n\x1a\n'))

    def test_bulk_pdf_download_is_tenant_scoped(self):
        card_number, barcode_data = self._jewels_card_identity()
        jewels_card = IDCard.all_objects.create(
            student=self.jewels_student,
            card_number=card_number,
            barcode_data=barcode_data,
            card_type='student',
            expiry_date=timezone.now().date() + timedelta(days=365),
        )

        with patch('core.views_attendance._draw_id_card_pdf') as draw_card:
            response = self.jewels_client.get(reverse('attendance:download_id_cards_pdf'), {
                'ids': f'{jewels_card.id},{self.legacy_platform_card.id}',
            })

        drawn_card_ids = [call.args[1].id for call in draw_card.call_args_list]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))
        self.assertEqual(drawn_card_ids, [jewels_card.id, jewels_card.id])

    def test_bulk_generate_returns_pdf_download_url(self):
        response = self.jewels_client.post(reverse('attendance:bulk_generate_cards'), {
            'card_type': 'student',
            'selected_ids': [self.jewels_student.id],
        })

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['success'])
        self.assertEqual(payload['count'], 1)
        self.assertIn(reverse('attendance:download_id_cards_pdf'), payload['pdf_url'])
