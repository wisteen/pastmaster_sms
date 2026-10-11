import json
from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from website.models import WebsitePage

from .models import (
    ClassTeacher,
    Comment,
    ComponentResult,
    HeadTeacher,
    LearnerDomainCriterion,
    LearnerDomainRating,
    ReportCardSettings,
    Result,
    ResultComponent,
    ResultToken,
    SchoolClass,
    SchoolMembership,
    SchoolSettings,
    SchoolTenant,
    Student,
    Subject,
    Teacher,
    Term,
)
from .models_biodata import Guardian
from .models_features import SchoolDomain
from .models_license import SystemLicense


User = get_user_model()


class SchoolPortalSettingsTests(TestCase):
    host = 'portal.testserver'

    def setUp(self):
        self.school = SchoolTenant.objects.create(name='Portal School', slug='portal-school')
        SchoolDomain.objects.create(school=self.school, domain=self.host)
        SystemLicense.all_objects.create(
            school=self.school,
            school_name=self.school.name,
            license_key='portal-school-license',
            expiry_date=date.today() + timedelta(days=30),
        )
        self.school_class = SchoolClass.all_objects.create(school=self.school, name='JSS 1', stream='A')
        self.subject = Subject.all_objects.create(school=self.school, name='Mathematics', code='MTH')
        self.term = Term.all_objects.create(
            school=self.school,
            name='First Term',
            session='2025-2026',
            start_date=date.today() - timedelta(days=90),
            end_date=date.today(),
        )

        self.admin_user = self._create_member('admin', 'super_admin')
        self.student_user = self._create_member('student', 'student')
        self.parent_user = self._create_member('parent', 'parent')
        self.student = Student.all_objects.create(
            school=self.school,
            user=self.student_user,
            student_id='STU0001',
            school_class=self.school_class,
            date_of_birth=date(2012, 1, 1),
        )
        Guardian.objects.create(
            student=self.student,
            user=self.parent_user,
            relationship='father',
            title='Mr',
            first_name='Test',
            last_name='Parent',
            phone_number='08012345678',
            occupation='Parent',
            home_address='Home',
        )
        self.result = Result.all_objects.create(
            student=self.student,
            subject=self.subject,
            term=self.term,
            total_score=75,
            grade='B',
            grade_point=3,
            remark='Very Good',
        )

    def _create_member(self, username, role):
        user = User.objects.create_user(username=username, password='password', role=role)
        SchoolMembership.objects.create(school=self.school, user=user, primary_role=role)
        return user

    def _client_for(self, username):
        client = Client(HTTP_HOST=self.host)
        self.assertTrue(client.login(username=username, password='password'))
        return client

    def _create_class_teacher(self, username='class-teacher', can_print_download=False):
        teacher_user = self._create_member(username, 'class_teacher')
        teacher = Teacher.all_objects.create(
            school=self.school,
            user=teacher_user,
            employee_id=f'TCH{Teacher.all_objects.count() + 1:04d}',
        )
        teacher.classes.add(self.school_class)
        teacher.subjects.add(self.subject)
        ClassTeacher.objects.create(
            teacher=teacher,
            school_class=self.school_class,
            can_print_download_results=can_print_download,
        )
        return teacher_user, teacher, self._client_for(username)

    def test_login_accepts_trimmed_case_insensitive_username(self):
        client = Client(HTTP_HOST=self.host)
        response = client.post(reverse('core:login'), {
            'username': '  STUDENT  ',
            'password': 'password',
            'role': 'student',
        })

        self.assertRedirects(response, reverse('core:dashboard'))

    def test_login_reports_portal_access_disabled_for_correct_credentials(self):
        membership = SchoolMembership.objects.get(school=self.school, user=self.student_user)
        membership.portal_access_enabled = False
        membership.save(update_fields=['portal_access_enabled'])

        client = Client(HTTP_HOST=self.host)
        response = client.post(reverse('core:login'), {
            'username': 'student',
            'password': 'password',
            'role': 'student',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'portal access for this school is disabled')

    def test_result_access_disabled_blocks_student_page_and_token_lookup(self):
        self.term.result_published = True
        self.term.save(update_fields=['result_published'])
        membership = SchoolMembership.objects.get(school=self.school, user=self.student_user)
        membership.result_access_enabled = False
        membership.save(update_fields=['result_access_enabled'])
        token = ResultToken.all_objects.create(student=self.student, term=self.term, max_uses=3)

        student_client = self._client_for('student')
        response = student_client.get(reverse('core:student_results'), follow=True)
        self.assertContains(response, 'result access for this school is disabled')

        public_client = Client(HTTP_HOST=self.host)
        response = public_client.post(reverse('core:check_result'), {'token': token.token}, follow=True)
        self.assertContains(response, 'Result access for this student is currently disabled')
        token.refresh_from_db()
        self.assertEqual(token.uses_count, 0)

    def test_token_result_page_can_switch_between_published_terms(self):
        self.term.result_published = True
        self.term.save(update_fields=['result_published'])
        second_term = Term.all_objects.create(
            school=self.school,
            name='Second Term',
            session='2025-2026',
            start_date=date.today() - timedelta(days=30),
            end_date=date.today() + timedelta(days=60),
            result_published=True,
        )
        Result.all_objects.create(
            student=self.student,
            subject=self.subject,
            term=second_term,
            total_score=82,
            grade='A',
            grade_point=4,
            remark='Excellent',
        )
        first_token = ResultToken.all_objects.create(student=self.student, term=self.term, max_uses=3)
        ResultToken.all_objects.create(student=self.student, term=second_term, max_uses=3)

        response = Client(HTTP_HOST=self.host).get(reverse('core:view_result_card', args=[first_token.token]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Session / Term')
        self.assertContains(response, '2025-2026 - Second Term')

    def test_results_are_hidden_until_admin_sends_them_to_portals(self):
        student_client = self._client_for('student')
        parent_client = self._client_for('parent')

        response = student_client.get(reverse('core:student_results'))
        self.assertNotContains(response, 'Mathematics')
        response = parent_client.get(reverse('core:parent_dashboard'))
        self.assertNotContains(response, 'Mathematics')

        admin_client = self._client_for('admin')
        response = admin_client.post(
            reverse('core:school_admin_result_publication'),
            {'term_id': self.term.id, 'action': 'publish'},
        )
        self.assertRedirects(response, reverse('core:school_admin_result_publication'))

        response = student_client.get(reverse('core:student_results'))
        self.assertContains(response, 'Mathematics')
        response = parent_client.get(reverse('core:parent_dashboard'))
        self.assertContains(response, 'Mathematics')

    def test_published_term_blocks_teacher_score_adjustments_until_unpublished(self):
        _, _, teacher_client = self._create_class_teacher('score-lock-teacher')
        component = ResultComponent.objects.create(
            school_class=self.school_class,
            subject=self.subject,
            component_name='Exam',
            weight=100,
            max_score=100,
        )
        self.term.result_published = True
        self.term.save(update_fields=['result_published'])

        response = teacher_client.post(
            reverse('core:update_component_score'),
            data=json.dumps({
                'student_id': self.student.id,
                'component_id': component.id,
                'term_id': self.term.id,
                'score': 88,
            }),
            content_type='application/json',
        )

        self.assertFalse(response.json()['success'])
        self.assertFalse(ComponentResult.objects.filter(student=self.student, component=component, term=self.term).exists())

        admin_client = self._client_for('admin')
        admin_client.post(
            reverse('core:school_admin_result_publication'),
            {'term_id': self.term.id, 'action': 'unpublish'},
        )
        response = teacher_client.post(
            reverse('core:update_component_score'),
            data=json.dumps({
                'student_id': self.student.id,
                'component_id': component.id,
                'term_id': self.term.id,
                'score': 88,
            }),
            content_type='application/json',
        )

        self.assertTrue(response.json()['success'])
        self.assertTrue(ComponentResult.objects.filter(student=self.student, component=component, term=self.term).exists())

    def test_broadsheet_comments_are_saved_by_role_only(self):
        Comment.objects.create(
            student=self.student,
            term=self.term,
            teacher_comment='Original teacher',
            proprietor_comment='Original admin',
        )
        _, _, teacher_client = self._create_class_teacher('comment-split-teacher')

        response = teacher_client.post(
            reverse('core:save_broadsheet_comments'),
            data=json.dumps({
                'class_id': self.school_class.id,
                'term_id': self.term.id,
                'comment_scope': 'teacher',
                'comments': [{
                    'student_id': self.student.id,
                    'teacher_comment': 'Updated teacher',
                    'ht_comment': 'Teacher should not change admin',
                }],
            }),
            content_type='application/json',
        )

        self.assertTrue(response.json()['success'])
        comment = Comment.objects.get(student=self.student, term=self.term)
        self.assertEqual(comment.teacher_comment, 'Updated teacher')
        self.assertEqual(comment.proprietor_comment, 'Original admin')

        response = teacher_client.post(
            reverse('core:save_broadsheet_comments'),
            data=json.dumps({
                'class_id': self.school_class.id,
                'term_id': self.term.id,
                'comment_scope': 'admin',
                'comments': [{'student_id': self.student.id, 'ht_comment': 'Blocked admin edit'}],
            }),
            content_type='application/json',
        )
        self.assertFalse(response.json()['success'])

        admin_client = self._client_for('admin')
        response = admin_client.post(
            reverse('core:save_broadsheet_comments'),
            data=json.dumps({
                'class_id': self.school_class.id,
                'term_id': self.term.id,
                'comment_scope': 'admin',
                'comments': [{
                    'student_id': self.student.id,
                    'teacher_comment': 'Admin should not change teacher',
                    'ht_comment': 'Updated admin',
                }],
            }),
            content_type='application/json',
        )

        self.assertTrue(response.json()['success'])
        comment.refresh_from_db()
        self.assertEqual(comment.teacher_comment, 'Updated teacher')
        self.assertEqual(comment.proprietor_comment, 'Updated admin')

    def test_report_card_print_download_controls_follow_class_teacher_permission(self):
        _, teacher, teacher_client = self._create_class_teacher('print-view-teacher')

        response = teacher_client.get(reverse('core:admin_view_result', args=[self.student.id, self.term.id]))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Download Image')
        self.assertContains(response, 'View only')

        assignment = ClassTeacher.objects.get(teacher=teacher, school_class=self.school_class)
        assignment.can_print_download_results = True
        assignment.save(update_fields=['can_print_download_results'])

        response = teacher_client.get(reverse('core:admin_view_result', args=[self.student.id, self.term.id]))

        self.assertContains(response, 'Download Image')
        self.assertContains(response, 'Image PDF')

    def test_school_admin_can_save_tenant_school_details(self):
        admin_client = self._client_for('admin')
        response = admin_client.post(reverse('core:school_admin_settings'), {
            'school_name': 'Configured Portal School',
            'school_address': '123 School Road',
            'principal_name': 'A. Principal',
            'proprietor_name': 'A. Proprietor',
            'school_motto': 'Knowledge',
            'primary_color': '#112233',
            'secondary_color': '#445566',
            'accent_color': '#778899',
            'back_home_url': 'https://portal-school.example.com/',
            'email_from_address': 'results@portal-school.example.com',
            'email_host': 'smtp.portal-school.example.com',
            'email_port': 465,
            'email_host_user': 'smtp-user',
            'email_host_password': 'smtp-password',
            'termii_api_key': 'termii-key',
            'termii_base_url': 'https://api.ng.termii.com',
            'termii_sender_id': 'PortalSch',
            'termii_channel': 'dnd',
            'student_id_prefix': 'STD',
            'student_id_digits': 5,
            'teacher_id_prefix': 'TCH',
            'teacher_id_digits': 4,
            'email_use_tls': 'on',
        })
        self.assertRedirects(response, reverse('core:school_admin_settings'))

        settings = SchoolSettings.all_objects.get(school=self.school)
        self.assertEqual(settings.school_name, 'Configured Portal School')
        self.assertEqual(settings.primary_color, '#112233')
        self.assertEqual(settings.back_home_url, 'https://portal-school.example.com/')
        self.assertEqual(settings.email_host, 'smtp.portal-school.example.com')
        self.assertEqual(settings.email_host_password, 'smtp-password')
        self.assertEqual(settings.termii_api_key, 'termii-key')
        self.assertEqual(settings.termii_sender_id, 'PortalSch')

        response = admin_client.post(reverse('core:school_admin_settings'), {
            'school_name': 'Configured Portal School',
            'school_address': '123 School Road',
            'principal_name': 'A. Principal',
            'proprietor_name': 'A. Proprietor',
            'school_motto': 'Knowledge',
            'primary_color': '#112233',
            'secondary_color': '#445566',
            'accent_color': '#778899',
            'back_home_url': 'https://portal-school.example.com/',
            'email_from_address': 'results@portal-school.example.com',
            'email_host': 'smtp.portal-school.example.com',
            'email_port': 465,
            'email_host_user': 'smtp-user',
            'termii_base_url': 'https://api.ng.termii.com',
            'termii_sender_id': 'PortalSch',
            'termii_channel': 'dnd',
            'student_id_prefix': 'STD',
            'student_id_digits': 5,
            'teacher_id_prefix': 'TCH',
            'teacher_id_digits': 4,
            'email_use_tls': 'on',
        })
        self.assertRedirects(response, reverse('core:school_admin_settings'))

        settings.refresh_from_db()
        self.assertEqual(settings.email_host_password, 'smtp-password')
        self.assertEqual(settings.termii_api_key, 'termii-key')

    def test_school_admin_settings_renders_visual_brand_color_pickers(self):
        admin_client = self._client_for('admin')

        response = admin_client.get(reverse('core:school_admin_settings'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="brand-color-field"', count=3)
        self.assertContains(response, 'data-color-picker aria-label', count=3)
        self.assertContains(response, '_picker" class="brand-color-picker"', count=3)
        self.assertContains(response, 'data-color-text=""', count=3)
        self.assertContains(response, 'type="color"', count=3)
        self.assertContains(response, 'data-color-status-text>Selected color:', count=3)
        for field_name in ['primary_color', 'secondary_color', 'accent_color']:
            field = response.context['form'].fields[field_name]
            self.assertEqual(field.widget.attrs['pattern'], '#[0-9A-Fa-f]{6}')
            self.assertEqual(field.widget.attrs['maxlength'], '7')
            self.assertIn(f'id_{field_name}_status', field.widget.attrs['aria-describedby'])

    @override_settings(PRIMARY_TENANT_HOSTS=['sms.pastmaster.top'], DEFAULT_SCHOOL_SLUG='')
    def test_primary_host_without_domain_uses_only_active_school(self):
        SchoolTenant.objects.exclude(pk=self.school.pk).update(is_active=False)
        SchoolDomain.objects.filter(school=self.school).delete()
        WebsitePage.objects.update_or_create(
            school=self.school,
            slug='home',
            defaults={
                'title': 'Home',
                'is_homepage': True,
                'is_published': True,
                'header_title': 'Portal School Home',
            },
        )

        client = Client(HTTP_HOST='sms.pastmaster.top')
        response = client.get(reverse('website:home'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['active_school'], self.school)

    def test_auth_back_home_links_use_default_homepage_without_tenant_url(self):
        client = Client(HTTP_HOST=self.host)
        expected_href = f'href="{reverse("website:home")}"'

        response = client.get(reverse('core:role_selection'))
        self.assertContains(response, expected_href)

        response = client.get(reverse('core:login'))
        self.assertContains(response, expected_href)

    def test_auth_back_home_links_use_tenant_configured_url(self):
        SchoolSettings.all_objects.create(
            school=self.school,
            school_name='Portal School',
            school_address='123 School Road',
            principal_name='A. Principal',
            back_home_url='https://existing-school.example.com/',
        )
        client = Client(HTTP_HOST=self.host)
        expected_href = 'href="https://existing-school.example.com/"'

        response = client.get(reverse('core:role_selection'))
        self.assertContains(response, expected_href)

        response = client.get(reverse('core:login'))
        self.assertContains(response, expected_href)

    def test_admin_with_student_role_grant_can_view_student_biodata(self):
        membership = SchoolMembership.objects.get(school=self.school, user=self.admin_user)
        membership.extra_roles = ['student']
        membership.save()

        admin_client = self._client_for('admin')
        response = admin_client.get(reverse('student_biodata_view', args=[self.student.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Student Bio-Data')

    def test_tenant_superuser_membership_can_access_dashboard(self):
        tenant_admin = User.objects.create_superuser(
            username='tenant-root',
            password='password',
            email='tenant-root@example.com',
            role='super_admin',
        )
        SchoolMembership.objects.create(
            school=self.school,
            user=tenant_admin,
            primary_role='super_admin',
        )

        client = Client(HTTP_HOST=self.host)
        self.assertTrue(client.login(username='tenant-root', password='password'))
        response = client.get(reverse('core:dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboards/super_admin.html')

    def test_global_superuser_without_membership_can_login_to_tenant_dashboard(self):
        tenant_admin = User.objects.create_superuser(
            username='global-root',
            password='password',
            email='global-root@example.com',
            role='super_admin',
        )

        client = Client(HTTP_HOST=self.host)
        response = client.post(reverse('core:login'), {
            'username': tenant_admin.username,
            'password': 'password',
            'role': 'super_admin',
        })
        self.assertRedirects(response, reverse('core:dashboard'))

        response = client.get(reverse('core:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboards/super_admin.html')

    def test_school_admin_can_configure_report_templates_and_signatories(self):
        admin_client = self._client_for('admin')
        response = admin_client.post(reverse('core:report_card_settings'), {
            'template': ReportCardSettings.TEMPLATE_THEME_BACKGROUND,
            f'class_template_{self.school_class.id}': ReportCardSettings.TEMPLATE_NURSERY_CLEAN,
            'show_position': 'on',
            'show_subject_position': 'on',
            'show_class_average': 'on',
            'show_highest_in_class': 'on',
            'show_attendance': 'on',
            'show_psychomotor': 'on',
            'show_effective_domain': 'on',
            'show_next_resumption': 'on',
            'show_total_obtainable': 'on',
            'show_school_opened_days': 'on',
            'signatory_1_name': 'Grace Ade',
            'signatory_1_title': 'Director',
            'signatory_1_comment': 'Excellent progress.',
            'signatory_2_name': 'John Bello',
            'signatory_2_title': 'Class Teacher',
            'signatory_2_comment': '',
            'signatory_3_name': '',
            'signatory_3_title': '',
            'signatory_3_comment': '',
            'domain_rating_1_label': 'Always',
            'domain_rating_1_description': 'Consistently observed',
            'domain_rating_2_label': 'Somewhat',
            'domain_rating_2_description': 'Sometimes observed',
            f'class_domain_rating_{self.school_class.id}_1_label': 'Excellent',
            f'class_domain_rating_{self.school_class.id}_1_description': 'JSS excellent',
            f'class_domain_rating_{self.school_class.id}_2_label': 'Good',
            f'class_domain_rating_{self.school_class.id}_2_description': 'JSS good',
        })

        self.assertRedirects(response, reverse('core:report_card_settings'))
        settings = ReportCardSettings.all_objects.get(school=self.school)
        self.assertEqual(settings.template, ReportCardSettings.TEMPLATE_THEME_BACKGROUND)
        self.assertEqual(
            settings.class_templates,
            {str(self.school_class.id): ReportCardSettings.TEMPLATE_NURSERY_CLEAN},
        )
        self.assertEqual(len(settings.signatories), 2)
        self.assertEqual(settings.signatories[0]['title'], 'Director')
        self.assertEqual(
            settings.domain_rating_guide,
            [
                {'label': 'Always', 'description': 'Consistently observed'},
                {'label': 'Somewhat', 'description': 'Sometimes observed'},
            ],
        )
        self.assertEqual(
            settings.class_domain_rating_guides,
            {
                str(self.school_class.id): [
                    {'label': 'Excellent', 'description': 'JSS excellent'},
                    {'label': 'Good', 'description': 'JSS good'},
                ],
            },
        )

    def test_admin_result_uses_class_report_template_override(self):
        ReportCardSettings.all_objects.create(
            school=self.school,
            template=ReportCardSettings.TEMPLATE_CLASSIC,
            class_templates={str(self.school_class.id): ReportCardSettings.TEMPLATE_NURSERY_CLEAN},
            signatories=[{
                'name': 'Grace Ade',
                'title': 'Director',
                'comment': 'Excellent progress.',
            }],
        )

        admin_client = self._client_for('admin')
        response = admin_client.get(reverse('core:admin_view_result', args=[self.student.id, self.term.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Nursery School Report')
        self.assertContains(response, 'Grace Ade')
        self.assertContains(response, 'Excellent progress.')

    def test_report_card_comment_title_uses_class_head_teacher_title(self):
        ReportCardSettings.all_objects.create(
            school=self.school,
            template=ReportCardSettings.TEMPLATE_CLASSIC,
        )
        signatory_user = self._create_member('director-user', 'subject_teacher')
        signatory_user.first_name = 'Class'
        signatory_user.last_name = 'Director'
        signatory_user.save(update_fields=['first_name', 'last_name'])
        teacher = Teacher.all_objects.create(
            school=self.school,
            user=signatory_user,
            employee_id='DIR001',
        )
        head_teacher = HeadTeacher.objects.create(
            teacher=teacher,
            title='Director',
        )
        head_teacher.classes.set([self.school_class])
        Comment.objects.create(
            student=self.student,
            term=self.term,
            teacher_comment='Good work.',
            proprietor_comment='Keep improving.',
        )

        admin_client = self._client_for('admin')
        response = admin_client.get(reverse('core:admin_view_result', args=[self.student.id, self.term.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Director's Comment")
        self.assertNotContains(response, "Principal's Comment")

    def test_admin_result_can_render_playful_nursery_template(self):
        ReportCardSettings.all_objects.create(
            school=self.school,
            template=ReportCardSettings.TEMPLATE_NURSERY_PLAYFUL,
        )

        admin_client = self._client_for('admin')
        response = admin_client.get(reverse('core:admin_view_result', args=[self.student.id, self.term.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Nursery Progress Report')
        self.assertContains(response, 'Topics Covered')

    def test_playful_nursery_template_uses_class_specific_domain_table(self):
        ReportCardSettings.all_objects.create(
            school=self.school,
            template=ReportCardSettings.TEMPLATE_NURSERY_PLAYFUL,
        )
        other_class = SchoolClass.all_objects.create(school=self.school, name='Nursery 2', stream='A')
        health = LearnerDomainCriterion.all_objects.create(
            school=self.school,
            domain_type=LearnerDomainCriterion.DOMAIN_EFFECTIVE,
            name='Health',
            display_order=5,
        )
        health.classes.set([self.school_class])
        hidden = LearnerDomainCriterion.all_objects.create(
            school=self.school,
            domain_type=LearnerDomainCriterion.DOMAIN_EFFECTIVE,
            name='Other Class Habit',
            display_order=6,
        )
        hidden.classes.set([other_class])
        LearnerDomainRating.all_objects.create(
            school=self.school,
            student=self.student,
            term=self.term,
            criterion=health,
            value='Very Good',
        )

        admin_client = self._client_for('admin')
        response = admin_client.get(reverse('core:admin_view_result', args=[self.student.id, self.term.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Social and Emotional Learning')
        self.assertContains(response, 'Health')
        self.assertContains(response, 'Very Good')
        self.assertNotContains(response, 'Other Class Habit')

    def test_default_report_card_shows_flexible_domain_ratings(self):
        ReportCardSettings.all_objects.create(
            school=self.school,
            template=ReportCardSettings.TEMPLATE_CLASSIC,
            show_effective_domain=True,
            show_psychomotor=True,
            domain_rating_guide=[
                {'label': 'Always', 'description': 'Consistently observed'},
                {'label': 'Somewhat', 'description': 'Sometimes observed'},
            ],
        )
        effective = LearnerDomainCriterion.all_objects.create(
            school=self.school,
            domain_type=LearnerDomainCriterion.DOMAIN_EFFECTIVE,
            name='Participation',
            display_order=5,
        )
        psychomotor = LearnerDomainCriterion.all_objects.create(
            school=self.school,
            domain_type=LearnerDomainCriterion.DOMAIN_PSYCHOMOTOR,
            name='Coordination',
            display_order=5,
        )
        LearnerDomainRating.all_objects.create(
            school=self.school,
            student=self.student,
            term=self.term,
            criterion=effective,
            value='Always',
        )
        LearnerDomainRating.all_objects.create(
            school=self.school,
            student=self.student,
            term=self.term,
            criterion=psychomotor,
            value='Somewhat',
        )

        admin_client = self._client_for('admin')
        response = admin_client.get(reverse('core:admin_view_result', args=[self.student.id, self.term.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Effective Domain')
        self.assertContains(response, 'Psychomotor Skills')
        self.assertContains(response, 'Participation')
        self.assertContains(response, 'Coordination')
        self.assertContains(response, 'Always')
        self.assertContains(response, 'Somewhat')
        self.assertContains(response, 'Always - Consistently observed')
        self.assertContains(response, 'Somewhat - Sometimes observed')

    def test_report_card_uses_class_specific_domain_rating_guide(self):
        ReportCardSettings.all_objects.create(
            school=self.school,
            template=ReportCardSettings.TEMPLATE_CLASSIC,
            show_effective_domain=True,
            domain_rating_guide=[
                {'label': 'Always', 'description': 'Default school guide'},
            ],
            class_domain_rating_guides={
                str(self.school_class.id): [
                    {'label': 'Developing', 'description': 'JSS guide'},
                ],
            },
        )
        criterion = LearnerDomainCriterion.all_objects.create(
            school=self.school,
            domain_type=LearnerDomainCriterion.DOMAIN_EFFECTIVE,
            name='Participation',
            display_order=5,
        )
        LearnerDomainRating.all_objects.create(
            school=self.school,
            student=self.student,
            term=self.term,
            criterion=criterion,
            value='Developing',
        )

        admin_client = self._client_for('admin')
        response = admin_client.get(reverse('core:admin_view_result', args=[self.student.id, self.term.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Developing - JSS guide')
        self.assertNotContains(response, 'Always - Default school guide')

    def test_admin_result_renders_when_domain_class_scope_unavailable(self):
        ReportCardSettings.all_objects.create(
            school=self.school,
            template=ReportCardSettings.TEMPLATE_NURSERY_PLAYFUL,
        )
        LearnerDomainCriterion.all_objects.create(
            school=self.school,
            domain_type=LearnerDomainCriterion.DOMAIN_EFFECTIVE,
            name='Health',
            display_order=5,
        )

        admin_client = self._client_for('admin')
        with patch('core.views._learner_domain_criterion_supports_class_scope', return_value=False):
            response = admin_client.get(reverse('core:admin_view_result', args=[self.student.id, self.term.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Health')
