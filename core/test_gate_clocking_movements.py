import json
from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import SchoolMembership, SchoolTenant, Teacher
from .models_attendance import AttendanceMovement, AttendanceRecord, IDCard
from .models_features import SchoolDomain
from .models_license import SystemLicense


User = get_user_model()


class GateClockingMovementTests(TestCase):
    host = 'virtuakids-gate-clock.testserver'

    def setUp(self):
        self.school = SchoolTenant.objects.create(
            name='VirtuaKids Gate School', slug='virtuakids-gate', plan='premium'
        )
        SchoolDomain.objects.create(school=self.school, domain=self.host)
        SystemLicense.all_objects.create(
            school=self.school,
            school_name=self.school.name,
            license_key='virtuakids-gate-license',
            expiry_date=date.today() + timedelta(days=30),
        )
        self.security = self._member('gate-security', 'security')
        staff_user = self._member('gate-driver', 'driver')
        self.staff = Teacher.all_objects.create(
            school=self.school,
            user=staff_user,
            employee_id='STF-GATE-1',
            status='active',
        )
        self.card = IDCard.all_objects.create(
            teacher=self.staff,
            card_type='staff',
            card_number='STAFF-GATE-1',
            barcode_data='STAFF-GATE-1-CODE',
            expiry_date=timezone.localdate() + timedelta(days=365),
        )
        self.client = Client(HTTP_HOST=self.host)
        self.assertTrue(self.client.login(username='gate-security', password='password'))

    def _member(self, username, role, extra_roles=None):
        user = User.objects.create_user(username=username, password='password', role=role)
        SchoolMembership.objects.create(
            school=self.school,
            user=user,
            primary_role=role,
            extra_roles=extra_roles or [],
        )
        return user

    def _scan(self, at):
        with patch('core.views_attendance.timezone.now', return_value=at):
            return self.client.post(
                reverse('attendance:scan_barcode'),
                data=json.dumps({'barcode': self.card.barcode_data}),
                content_type='application/json',
            )

    def test_all_staff_roles_use_guard_and_temporary_return_cycle(self):
        start = timezone.now().replace(hour=8, minute=0, second=0, microsecond=0)

        clock_in = self._scan(start)
        too_soon = self._scan(start + timedelta(minutes=5))
        temporary_exit = self._scan(start + timedelta(minutes=11))
        returned = self._scan(start + timedelta(minutes=30))
        final_exit = self._scan(start + timedelta(hours=7))

        self.assertEqual(clock_in.status_code, 200)
        self.assertEqual(too_soon.status_code, 409)
        self.assertEqual(too_soon.json()['code'], 'minimum_stay')
        self.assertEqual(temporary_exit.json()['data']['action'], 'checkout')
        self.assertEqual(returned.json()['data']['action'], 'checkin')
        self.assertEqual(returned.json()['data']['type'], 'Driver')
        self.assertEqual(final_exit.json()['data']['action'], 'checkout')

        record = AttendanceRecord.objects.get(id_card=self.card)
        self.assertEqual(record.check_in_time, start)
        self.assertEqual(record.check_out_time, start + timedelta(hours=7))
        self.assertEqual(
            list(AttendanceMovement.objects.filter(record=record).values_list('action', flat=True)),
            ['in', 'out', 'in', 'out'],
        )

        report = self.client.get(reverse('attendance:report'))
        entry = report.context['days'][0]['entries'][0]
        self.assertEqual(entry['role'], 'Driver')
        self.assertEqual(entry['movement_count'], 4)
        self.assertFalse(entry['is_on_premises'])

    def test_security_dashboard_shows_gate_and_visitor_tools(self):
        response = self.client.get(reverse('core:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboards/security.html')
        self.assertContains(response, 'Open Attendance Scanner')
        self.assertContains(response, 'Manage Visitors')


class SecurityRoleRoutingTests(TestCase):
    host = 'virtuakids-security-route.testserver'

    def test_selected_security_role_wins_over_admin_fallback(self):
        school = SchoolTenant.objects.create(
            name='VirtuaKids Security Route', slug='virtuakids-security-route', plan='premium'
        )
        SchoolDomain.objects.create(school=school, domain=self.host)
        SystemLicense.all_objects.create(
            school=school,
            school_name=school.name,
            license_key='virtuakids-security-route-license',
            expiry_date=date.today() + timedelta(days=30),
        )
        user = User.objects.create_user(
            username='virtuakids-admin-security', password='password', role='super_admin'
        )
        SchoolMembership.objects.create(
            school=school,
            user=user,
            primary_role='super_admin',
            extra_roles=['security'],
        )
        client = Client(HTTP_HOST=self.host)
        self.assertTrue(client.login(username=user.username, password='password'))
        session = client.session
        session['selected_role'] = 'security'
        session.save()

        response = client.get(reverse('core:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboards/security.html')
