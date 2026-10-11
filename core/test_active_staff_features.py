import importlib
import json
from datetime import date, timedelta
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .forms_biodata import GuardianForm
from .forms_school_admin import SchoolUserForm
from .models import SchoolClass, SchoolMembership, SchoolSettings, SchoolTenant, Student, Teacher
from .models_attendance import AttendanceSession, IDCard
from .models_features import SchoolDomain
from .models_license import SystemLicense
from .services_id_cards import resolve_id_card
from .staffing import active_staff, active_students


User = get_user_model()


class ActiveStaffFeatureTests(TestCase):
    host = 'active-school.testserver'

    def setUp(self):
        self.school = self.make_school('Active School', 'active-school', self.host)
        self.other_school = self.make_school('Other School', 'other-school', 'other-school.testserver')
        self.school_class = SchoolClass.all_objects.create(school=self.school, name='JSS 1')
        self.other_class = SchoolClass.all_objects.create(school=self.other_school, name='JSS 1')
        SchoolSettings.all_objects.create(school=self.school, school_name=self.school.name)
        self.admin = self.make_user('admin', 'super_admin', self.school, first='Ada', last='Admin')
        self.client = Client(HTTP_HOST=self.host)
        self.client.force_login(self.admin)

    def make_school(self, name, slug, host):
        school = SchoolTenant.objects.create(name=name, slug=slug, plan='premium')
        SchoolDomain.objects.create(school=school, domain=host)
        SystemLicense.all_objects.create(
            school=school,
            school_name=name,
            license_key=f'{slug}-license',
            expiry_date=date.today() + timedelta(days=30),
        )
        return school

    def make_user(self, username, role, school, *, active=True, membership_active=True, first='', last=''):
        user = User.objects.create_user(
            username=username,
            password='password',
            role=role,
            is_active=active,
            first_name=first,
            last_name=last,
        )
        SchoolMembership.objects.create(
            school=school,
            user=user,
            primary_role=role,
            is_active=membership_active,
        )
        return user

    def make_student(self, username, status='active', *, active=True, membership_active=True, school=None):
        school = school or self.school
        school_class = self.school_class if school == self.school else self.other_class
        user = self.make_user(
            username, 'student', school, active=active, membership_active=membership_active,
            first=username.title(), last='Learner',
        )
        return Student.all_objects.create(
            school=school,
            user=user,
            student_id=f'S-{username}',
            school_class=school_class,
            date_of_birth=date(2012, 1, 1),
            status=status,
        )

    def make_staff(self, username, role='cleaner', status='active', *, active=True, membership_active=True, school=None, title=''):
        school = school or self.school
        user = self.make_user(
            username, role, school, active=active, membership_active=membership_active,
            first=username.title(), last='Staff',
        )
        return Teacher.all_objects.create(
            school=school,
            user=user,
            employee_id=f'E-{username}',
            status=status,
            custom_job_title=title,
        )

    def test_active_querysets_exclude_every_inactive_state_account_and_membership(self):
        active_student = self.make_student('active-student')
        for status in ('withdrawn', 'relocated', 'transferred', 'graduated', 'suspended', 'inactive'):
            self.make_student(f'student-{status}', status=status)
        self.make_student('student-disabled', active=False)
        self.make_student('student-membership-disabled', membership_active=False)

        active_member = self.make_staff('active-cleaner')
        for status in ('former', 'retired', 'resigned', 'fired', 'terminated', 'suspended', 'inactive'):
            self.make_staff(f'staff-{status}', status=status)
        self.make_staff('staff-disabled', active=False)
        self.make_staff('staff-membership-disabled', membership_active=False)

        self.assertQuerySetEqual(active_students(self.school), [active_student], transform=lambda item: item)
        self.assertQuerySetEqual(active_staff(self.school), [active_member], transform=lambda item: item)

        response = self.client.get(reverse('core:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_students'], 1)
        self.assertEqual(response.context['total_teachers'], 1)

    def test_guardian_dropdown_is_same_school_active_parent_only_and_uses_full_name(self):
        student = self.make_student('ward')
        parent = self.make_user('parent-one', 'parent', self.school, first='Pat', last='Parent')
        self.make_user('parent-disabled', 'parent', self.school, active=False)
        self.make_user('parent-membership-disabled', 'parent', self.school, membership_active=False)
        other_parent = self.make_user('other-parent', 'parent', self.other_school, first='Other', last='Parent')
        self.make_user('cleaner-user', 'cleaner', self.school)

        form = GuardianForm(school=self.school, student=student)
        self.assertEqual(list(form.fields['user'].queryset), [parent])
        self.assertEqual(form.fields['user'].label_from_instance(parent), 'Pat Parent')

        data = {
            'user': other_parent.pk, 'relationship': 'guardian', 'title': 'Mr',
            'first_name': 'Other', 'last_name': 'Parent', 'phone_number': '08012345678',
            'email': '', 'occupation': 'Trader', 'employer': '', 'office_address': '',
            'home_address': 'Elsewhere', 'is_primary_contact': '', 'is_emergency_contact': '',
        }
        submitted = GuardianForm(data=data, school=self.school, student=student)
        self.assertFalse(submitted.is_valid())
        self.assertIn('user', submitted.errors)

    def test_other_staff_requires_title_and_predefined_role_clears_it(self):
        invalid = SchoolUserForm(data={'username': 'other', 'role': 'staff', 'custom_job_title': ''})
        self.assertFalse(invalid.is_valid())
        self.assertIn('custom_job_title', invalid.errors)

        predefined = SchoolUserForm(data={
            'username': 'cleaner', 'role': 'cleaner', 'custom_job_title': 'Should clear',
        })
        self.assertTrue(predefined.is_valid(), predefined.errors)
        self.assertEqual(predefined.cleaned_data['custom_job_title'], '')

    def test_school_user_creation_builds_staff_profile_and_custom_title(self):
        response = self.client.post(reverse('core:school_admin_users'), {
            'action': 'save_user', 'username': 'lab-assistant', 'first_name': 'Lee',
            'last_name': 'Helper', 'role': 'staff', 'custom_job_title': 'Laboratory Assistant',
            'password': 'A-safe-password-123!', 'is_active': 'on',
            'portal_access_enabled': 'on', 'result_access_enabled': 'on',
        })
        self.assertRedirects(response, reverse('core:school_admin_users'))
        profile = Teacher.all_objects.get(user__username='lab-assistant')
        self.assertEqual(profile.school, self.school)
        self.assertEqual(profile.custom_job_title, 'Laboratory Assistant')
        self.assertEqual(profile.get_staff_title(), 'Laboratory Assistant')

    def test_backfill_creates_missing_active_staff_only(self):
        active_user = self.make_user('legacy-driver', 'driver', self.school)
        inactive_user = self.make_user('legacy-fired', 'cleaner', self.school, membership_active=False)
        migration = importlib.import_module('core.migrations.0072_active_staff_roles')
        migration.backfill_staff_profiles(apps, None)
        self.assertTrue(Teacher.all_objects.filter(user=active_user, status='active').exists())
        self.assertFalse(Teacher.all_objects.filter(user=inactive_user).exists())

    def test_staff_card_generation_and_cross_tenant_or_inactive_rejection(self):
        staff = self.make_staff('nurse-one', role='nurse')
        response = self.client.get(reverse('attendance:generate_id_card', args=['staff', staff.pk]))
        self.assertEqual(response.status_code, 200)
        card = IDCard.all_objects.get(teacher=staff)
        self.assertEqual(card.card_type, 'staff')
        self.assertContains(response, 'Nurse')

        other = self.make_staff('other-driver', role='driver', school=self.other_school)
        cross = self.client.get(reverse('attendance:generate_id_card', args=['staff', other.pk]))
        self.assertEqual(cross.status_code, 404)

        staff.status = 'terminated' if 'terminated' in dict(Teacher.STATUS_CHOICES) else 'fired'
        staff.save(update_fields=['status'])
        inactive = self.client.get(reverse('attendance:generate_id_card', args=['staff', staff.pk]))
        self.assertEqual(inactive.status_code, 404)

    def test_non_teaching_staff_clock_in_out_and_terminated_staff_is_rejected(self):
        staff = self.make_staff('driver-one', role='driver')
        card = IDCard.all_objects.create(
            teacher=staff,
            card_number='STAFF-DRIVER-1',
            barcode_data='STAFF-DRIVER-1-CODE',
            card_type='staff',
            expiry_date=date.today() + timedelta(days=365),
        )
        session = AttendanceSession.all_objects.create(
            school=self.school,
            date=timezone.localdate(),
            session_type='morning',
            created_by=self.admin,
        )
        api_url = reverse('core:api_mark_attendance')
        payload = {'school': self.school.slug, 'session_id': session.pk, 'barcode': card.barcode_data}
        check_in = self.client.post(api_url, json.dumps(payload), content_type='application/json')
        self.assertEqual(check_in.status_code, 200)
        self.assertEqual(check_in.json()['action'], 'check_in')
        self.assertEqual(check_in.json()['holder_role'], 'Driver')
        with patch(
            'core.views_attendance_api.timezone.now',
            return_value=timezone.now() + timedelta(minutes=11),
        ):
            check_out = self.client.post(api_url, json.dumps(payload), content_type='application/json')
        self.assertEqual(check_out.status_code, 200)
        self.assertEqual(check_out.json()['action'], 'check_out')

        staff.status = 'fired'
        staff.save(update_fields=['status'])
        self.assertIsNone(resolve_id_card(card.barcode_data, school=self.school))

    def test_generic_staff_login_routes_to_limited_staff_dashboard(self):
        staff = self.make_staff('cleaner-login', role='cleaner')
        anonymous = Client(HTTP_HOST=self.host)
        response = anonymous.post(reverse('core:login') + '?role=staff', {
            'username': staff.user.username,
            'password': 'password',
            'role': 'staff',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboards/staff.html')
        self.assertContains(response, 'Cleaner')
        forbidden_admin = anonymous.get(reverse('core:school_admin_dashboard'))
        self.assertRedirects(forbidden_admin, reverse('core:dashboard'))

    def test_back_home_configured_url_and_safe_fallback(self):
        from .context_processors import _back_home_url
        settings = SchoolSettings.get_for_school(self.school)
        settings.back_home_url = 'https://school.example.com/'
        settings.save(update_fields=['back_home_url'])
        self.assertEqual(_back_home_url(self.school, settings), 'https://school.example.com/')
        settings.back_home_url = ''
        settings.save(update_fields=['back_home_url'])
        self.assertEqual(_back_home_url(self.school, settings), '/')
