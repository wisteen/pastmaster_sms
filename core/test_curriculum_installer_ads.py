import shutil
import tempfile
from datetime import date, timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (
    Curriculum,
    CurriculumInstallation,
    GlobalAdvertisement,
    LearningObjective,
    SchoolDomain,
    SchoolMembership,
    SchoolTenant,
    Subject,
    Teacher,
    Term,
    User,
)
from .models_license import SystemLicense
from .services_curriculum_installer import CurriculumInstallError, install_curriculum_bundle


class CurriculumInstallerTests(TestCase):
    host = 'curriculum-installer.testserver'

    def setUp(self):
        self.school = self._school('Installer School', 'installer-school', self.host)
        self.teacher_user = self._member(self.school, 'installer-teacher', 'subject_teacher')
        self.teacher = Teacher.all_objects.create(
            school=self.school,
            user=self.teacher_user,
            employee_id='CURR-001',
        )
        self.client = Client(HTTP_HOST=self.host)
        self.client.force_login(self.teacher_user)

    @staticmethod
    def _school(name, slug, host):
        school = SchoolTenant.objects.create(name=name, slug=slug, plan='premium')
        SchoolDomain.objects.create(school=school, domain=host)
        SystemLicense.all_objects.create(
            school=school,
            school_name=name,
            license_key=f'{slug}-license',
            expiry_date=date.today() + timedelta(days=60),
        )
        return school

    @staticmethod
    def _member(school, username, role):
        user = User.objects.create_user(username=username, password='password', role=role)
        SchoolMembership.objects.create(school=school, user=user, primary_role=role)
        return user

    def test_teacher_can_open_installer_from_dashboard_and_curriculum_library(self):
        dashboard = self.client.get(reverse('core:dashboard'))
        installer = self.client.get(reverse('academic:curriculum_installer'))
        library = self.client.get(reverse('academic:curriculum_list'))

        self.assertEqual(installer.status_code, 200)
        self.assertContains(installer, 'Federal / NERDC curriculum')
        self.assertContains(installer, 'Lagos State curriculum')
        self.assertContains(dashboard, reverse('academic:curriculum_installer'))
        self.assertContains(library, reverse('academic:curriculum_installer'))

    def test_federal_install_is_tenant_scoped_repeat_safe_and_preserves_edits(self):
        other = self._school('Other School', 'other-school', 'other-installer.testserver')

        first = install_curriculum_bundle(
            school=self.school,
            creator=self.teacher_user,
            provider='federal',
            levels=['Basic 1', 'JSS 1'],
        )
        curriculum = Curriculum.all_objects.get(
            school=self.school,
            title='Federal NERDC Basic 1 Curriculum',
        )
        objective = curriculum.learning_objectives.order_by('pk').first()
        original_objective_count = curriculum.learning_objectives.count()
        objective.description = 'Teacher-customized learning outcome.'
        objective.save(update_fields=['description'])
        english = Subject.all_objects.get(school=self.school, code='ENG')
        english.name = 'School English Programme'
        english.save(update_fields=['name'])

        second = install_curriculum_bundle(
            school=self.school,
            creator=self.teacher_user,
            provider='federal',
            levels=['Basic 1', 'JSS 1'],
        )

        objective.refresh_from_db()
        english.refresh_from_db()
        self.assertEqual(first['curricula_created'], 2)
        self.assertEqual(second['curricula_created'], 0)
        self.assertEqual(second['curricula_reused'], 2)
        self.assertEqual(objective.description, 'Teacher-customized learning outcome.')
        self.assertEqual(english.name, 'School English Programme')
        self.assertEqual(curriculum.learning_objectives.count(), original_objective_count)
        self.assertFalse(Curriculum.all_objects.filter(school=other).exists())
        self.assertFalse(Term.all_objects.filter(school=self.school, session='2026/2027').exists())
        self.assertEqual(CurriculumInstallation.all_objects.filter(school=self.school).count(), 2)

    def test_lagos_calendar_preserves_existing_dates_and_active_term_by_default(self):
        existing_start = date(2026, 10, 1)
        existing = Term.all_objects.create(
            school=self.school,
            name='First Term',
            session='2026/2027',
            start_date=existing_start,
            end_date=date(2026, 12, 18),
            is_active=False,
        )
        active = Term.all_objects.create(
            school=self.school,
            name='Third Term',
            session='2025/2026',
            start_date=date(2026, 4, 20),
            end_date=date(2026, 7, 24),
            is_active=True,
        )

        install_curriculum_bundle(
            school=self.school,
            creator=self.teacher_user,
            provider='lagos',
            levels=['Basic 6'],
            include_calendar=True,
            activate_first_term=False,
        )

        existing.refresh_from_db()
        active.refresh_from_db()
        self.assertEqual(existing.start_date, existing_start)
        self.assertFalse(existing.is_active)
        self.assertTrue(active.is_active)
        self.assertEqual(Term.all_objects.filter(school=self.school, session='2026-2027').count(), 3)

    def test_subject_conflict_rolls_back_everything(self):
        Subject.all_objects.create(school=self.school, code='ENG', name='English A')
        Subject.all_objects.create(school=self.school, code='ELA', name='English Studies')

        with self.assertRaises(CurriculumInstallError):
            install_curriculum_bundle(
                school=self.school,
                creator=self.teacher_user,
                provider='federal',
                levels=['Basic 1'],
            )

        self.assertFalse(Curriculum.all_objects.filter(school=self.school).exists())
        self.assertFalse(CurriculumInstallation.all_objects.filter(school=self.school).exists())

    def test_student_cannot_install_curriculum(self):
        student = self._member(self.school, 'installer-student', 'student')
        self.client.force_login(student)

        response = self.client.post(reverse('academic:curriculum_installer'), {
            'provider': 'federal',
            'levels': ['Basic 1'],
            'confirmation': 'on',
        })

        self.assertRedirects(
            response,
            reverse('core:dashboard'),
            fetch_redirect_response=False,
        )
        self.assertFalse(Curriculum.all_objects.filter(school=self.school).exists())


class GlobalAdvertisementTests(TestCase):
    media_root = tempfile.mkdtemp(prefix='pastmaster-sms-global-ads-')

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(cls.media_root, ignore_errors=True)

    def setUp(self):
        self.first_school = CurriculumInstallerTests._school(
            'First Tenant', 'first-tenant', 'first-tenant.testserver'
        )
        self.second_school = CurriculumInstallerTests._school(
            'Second Tenant', 'second-tenant', 'second-tenant.testserver'
        )
        self.first_admin = CurriculumInstallerTests._member(
            self.first_school, 'first-admin', 'super_admin'
        )
        self.second_admin = CurriculumInstallerTests._member(
            self.second_school, 'second-admin', 'super_admin'
        )
        self.platform_admin = User.objects.create_superuser(
            username='platform-owner',
            email='owner@example.com',
            password='password',
        )

    @override_settings(MEDIA_ROOT=media_root)
    def test_only_platform_superuser_can_upload_and_manage_global_ads(self):
        tenant_client = Client(HTTP_HOST='first-tenant.testserver')
        tenant_client.force_login(self.first_admin)
        self.assertEqual(tenant_client.get(reverse('core:global_advertisements')).status_code, 403)

        platform_client = Client(HTTP_HOST='first-tenant.testserver')
        platform_client.force_login(self.platform_admin)
        image = SimpleUploadedFile(
            'campaign.gif',
            b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;',
            content_type='image/gif',
        )
        response = platform_client.post(reverse('core:global_advertisements'), {
            'title': 'School supplies offer',
            'message': 'Available to every partner school.',
            'destination_url': 'https://example.com/offer',
            'button_label': 'View offer',
            'priority': 10,
            'is_active': 'on',
            'image': image,
        })

        self.assertRedirects(response, reverse('core:global_advertisements'))
        ad = GlobalAdvertisement.objects.get()
        self.assertEqual(ad.created_by, self.platform_admin)
        self.assertTrue(ad.image.name.startswith('global_ads/'))

    def test_current_ad_appears_for_every_tenant_but_future_ad_does_not(self):
        GlobalAdvertisement.objects.create(
            title='Visible everywhere',
            message='A global tenant campaign.',
            is_active=True,
            created_by=self.platform_admin,
        )
        GlobalAdvertisement.objects.create(
            title='Future campaign',
            message='Not started.',
            is_active=True,
            starts_at=timezone.now() + timedelta(days=1),
            created_by=self.platform_admin,
        )

        first = Client(HTTP_HOST='first-tenant.testserver')
        first.force_login(self.first_admin)
        second = Client(HTTP_HOST='second-tenant.testserver')
        second.force_login(self.second_admin)

        first_response = first.get(reverse('core:dashboard'))
        second_response = second.get(reverse('core:dashboard'))
        for response in (first_response, second_response):
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'Visible everywhere')
            self.assertNotContains(response, 'Future campaign')

    def test_platform_superuser_can_pause_ad_with_post_only(self):
        ad = GlobalAdvertisement.objects.create(
            title='Pause me', message='Campaign', is_active=True,
        )
        client = Client(HTTP_HOST='first-tenant.testserver')
        client.force_login(self.platform_admin)

        get_response = client.get(reverse('core:global_advertisement_toggle', args=[ad.pk]))
        post_response = client.post(reverse('core:global_advertisement_toggle', args=[ad.pk]))

        self.assertEqual(get_response.status_code, 405)
        self.assertRedirects(post_response, reverse('core:global_advertisements'))
        ad.refresh_from_db()
        self.assertFalse(ad.is_active)
