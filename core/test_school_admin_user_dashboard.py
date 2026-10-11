from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .forms_school_admin import SchoolTeacherForm
from .models import (
    ClassTeacher,
    EffectiveDomain,
    LearnerDomainCriterion,
    LearnerDomainRating,
    Psychomotor,
    Quiz,
    ReportCardSettings,
    SchoolClass,
    SchoolMembership,
    SchoolSettings,
    SchoolTenant,
    Student,
    Subject,
    Teacher,
    Term,
)
from .models_features import SchoolDomain
from .models_license import SystemLicense


User = get_user_model()


class SchoolAdminUserDashboardTests(TestCase):
    host = 'admin-users.testserver'

    def setUp(self):
        self.school = SchoolTenant.objects.create(name='Admin Users School', slug='admin-users-school')
        SchoolDomain.objects.create(school=self.school, domain=self.host)
        SystemLicense.all_objects.create(
            school=self.school,
            school_name=self.school.name,
            license_key='admin-users-school-license',
            expiry_date=date.today() + timedelta(days=30),
        )
        self.admin = self._create_member('admin', 'super_admin')
        self.school_class = SchoolClass.all_objects.create(school=self.school, name='JSS 1', stream='A')
        self.subject = Subject.all_objects.create(school=self.school, name='Mathematics', code='MTH')
        self.client = Client(HTTP_HOST=self.host)
        self.assertTrue(self.client.login(username='admin', password='password'))

    def _create_member(self, username, role):
        user = User.objects.create_user(username=username, password='password', role=role)
        SchoolMembership.objects.create(school=self.school, user=user, primary_role=role)
        return user

    def _class_teacher_client(self, username='domain-teacher'):
        user = self._create_member(username, 'class_teacher')
        teacher = Teacher.all_objects.create(
            school=self.school,
            user=user,
            employee_id=f'TCH{Teacher.all_objects.count() + 1:04d}',
        )
        teacher.classes.add(self.school_class)
        ClassTeacher.objects.create(teacher=teacher, school_class=self.school_class)
        client = Client(HTTP_HOST=self.host)
        self.assertTrue(client.login(username=username, password='password'))
        return client

    def test_super_admin_dashboard_links_to_school_admin(self):
        response = self.client.get(reverse('core:dashboard'))

        self.assertContains(response, reverse('core:school_admin_dashboard'))
        self.assertContains(response, 'School Admin')

    def test_school_admin_dashboard_exposes_domain_management(self):
        response = self.client.get(reverse('core:school_admin_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('core:school_admin_learner_domains'))
        self.assertContains(response, 'Effective Domain / Psychomotor')
        self.assertContains(response, 'Manage ratings')

    def test_class_teacher_can_enter_effective_domain_and_psychomotor(self):
        term = Term.all_objects.create(
            school=self.school,
            name='First Term',
            session='2025-2026',
            start_date=date.today() - timedelta(days=90),
            end_date=date.today(),
            is_active=True,
        )
        student_user = User.objects.create_user(
            username='domain-student',
            password='password',
            first_name='Domain',
            last_name='Student',
            role='student',
        )
        SchoolMembership.objects.create(school=self.school, user=student_user, primary_role='student')
        student = Student.all_objects.create(
            school=self.school,
            user=student_user,
            student_id='DOM001',
            school_class=self.school_class,
            date_of_birth=date(2012, 1, 1),
        )

        teacher_client = self._class_teacher_client('domain-rating-teacher')
        response = teacher_client.post(reverse('core:school_admin_learner_domains'), {
            'school_class': self.school_class.id,
            'term': term.id,
            f'effective_{student.id}_punctuality': '5',
            f'effective_{student.id}_neatness': '4',
            f'effective_{student.id}_attentiveness': '5',
            f'effective_{student.id}_politeness': '4',
            f'effective_{student.id}_relationship_with_others': '5',
            f'psychomotor_{student.id}_sports_games': '3',
            f'psychomotor_{student.id}_handwriting': '4',
            f'psychomotor_{student.id}_drawing_painting': '5',
            f'psychomotor_{student.id}_crafts': '4',
            f'psychomotor_{student.id}_music_drama': '3',
        })

        expected_url = f'{reverse("core:school_admin_learner_domains")}?school_class={self.school_class.id}&term={term.id}'
        self.assertRedirects(response, expected_url)
        effective = EffectiveDomain.objects.get(student=student, term=term)
        psychomotor = Psychomotor.objects.get(student=student, term=term)
        self.assertEqual(effective.punctuality, '5')
        self.assertEqual(effective.relationship_with_others, '5')
        self.assertEqual(psychomotor.handwriting, '4')
        self.assertEqual(psychomotor.music_drama, '3')
        self.assertTrue(
            LearnerDomainRating.all_objects.filter(
                student=student,
                term=term,
                criterion__name='Punctuality',
                value='5',
            ).exists()
        )

    def test_learner_domain_ratings_use_configured_dropdown_guide(self):
        ReportCardSettings.all_objects.create(
            school=self.school,
            domain_rating_guide=[
                {'label': 'Always', 'description': 'Consistently observed'},
                {'label': 'Somewhat', 'description': 'Sometimes observed'},
            ],
        )
        term = Term.all_objects.create(
            school=self.school,
            name='First Term',
            session='2025-2026',
            start_date=date.today() - timedelta(days=90),
            end_date=date.today(),
            is_active=True,
        )
        student_user = User.objects.create_user(
            username='dropdown-student',
            password='password',
            first_name='Dropdown',
            last_name='Student',
            role='student',
        )
        SchoolMembership.objects.create(school=self.school, user=student_user, primary_role='student')
        student = Student.all_objects.create(
            school=self.school,
            user=student_user,
            student_id='DROP001',
            school_class=self.school_class,
            date_of_birth=date(2012, 1, 1),
        )
        LearnerDomainCriterion.ensure_defaults(self.school)
        punctuality = LearnerDomainCriterion.all_objects.get(
            school=self.school,
            domain_type=LearnerDomainCriterion.DOMAIN_EFFECTIVE,
            legacy_field='punctuality',
        )

        teacher_client = self._class_teacher_client('dropdown-rating-teacher')
        response = teacher_client.get(
            f'{reverse("core:school_admin_learner_domains")}?school_class={self.school_class.id}&term={term.id}'
        )
        self.assertContains(response, 'Always - Consistently observed')
        self.assertContains(response, f'<select name="rating_{student.id}_{punctuality.id}"', html=False)

        teacher_client.post(reverse('core:school_admin_learner_domains'), {
            'action': 'save_ratings',
            'school_class': self.school_class.id,
            'term': term.id,
            f'rating_{student.id}_{punctuality.id}': 'Invalid Rating',
        })
        self.assertFalse(
            LearnerDomainRating.all_objects.filter(
                student=student,
                term=term,
                criterion=punctuality,
            ).exists()
        )

        teacher_client.post(reverse('core:school_admin_learner_domains'), {
            'action': 'save_ratings',
            'school_class': self.school_class.id,
            'term': term.id,
            f'rating_{student.id}_{punctuality.id}': 'Always',
        })
        self.assertTrue(
            LearnerDomainRating.all_objects.filter(
                student=student,
                term=term,
                criterion=punctuality,
                value='Always',
            ).exists()
        )

    def test_learner_domain_ratings_use_class_specific_dropdown_guide(self):
        ReportCardSettings.all_objects.create(
            school=self.school,
            domain_rating_guide=[
                {'label': 'Always', 'description': 'Default school guide'},
            ],
            class_domain_rating_guides={
                str(self.school_class.id): [
                    {'label': 'Excellent', 'description': 'JSS guide'},
                    {'label': 'Good', 'description': 'JSS guide'},
                ],
            },
        )
        term = Term.all_objects.create(
            school=self.school,
            name='First Term',
            session='2025-2026',
            start_date=date.today() - timedelta(days=90),
            end_date=date.today(),
            is_active=True,
        )
        student_user = User.objects.create_user(
            username='class-guide-student',
            password='password',
            first_name='Class',
            last_name='Guide',
            role='student',
        )
        SchoolMembership.objects.create(school=self.school, user=student_user, primary_role='student')
        student = Student.all_objects.create(
            school=self.school,
            user=student_user,
            student_id='GUIDE001',
            school_class=self.school_class,
            date_of_birth=date(2012, 1, 1),
        )
        LearnerDomainCriterion.ensure_defaults(self.school)
        punctuality = LearnerDomainCriterion.all_objects.get(
            school=self.school,
            domain_type=LearnerDomainCriterion.DOMAIN_EFFECTIVE,
            legacy_field='punctuality',
        )

        teacher_client = self._class_teacher_client('class-guide-rating-teacher')
        response = teacher_client.get(
            f'{reverse("core:school_admin_learner_domains")}?school_class={self.school_class.id}&term={term.id}'
        )
        self.assertContains(response, 'Excellent - JSS guide')
        self.assertNotContains(response, 'Always - Default school guide')

        teacher_client.post(reverse('core:school_admin_learner_domains'), {
            'action': 'save_ratings',
            'school_class': self.school_class.id,
            'term': term.id,
            f'rating_{student.id}_{punctuality.id}': 'Always',
        })
        self.assertFalse(
            LearnerDomainRating.all_objects.filter(
                student=student,
                term=term,
                criterion=punctuality,
            ).exists()
        )

        teacher_client.post(reverse('core:school_admin_learner_domains'), {
            'action': 'save_ratings',
            'school_class': self.school_class.id,
            'term': term.id,
            f'rating_{student.id}_{punctuality.id}': 'Excellent',
        })
        self.assertTrue(
            LearnerDomainRating.all_objects.filter(
                student=student,
                term=term,
                criterion=punctuality,
                value='Excellent',
            ).exists()
        )

    def test_school_admin_can_update_selected_class_domain_rating_guide(self):
        term = Term.all_objects.create(
            school=self.school,
            name='First Term',
            session='2025-2026',
            start_date=date.today() - timedelta(days=90),
            end_date=date.today(),
            is_active=True,
        )

        response = self.client.post(reverse('core:school_admin_learner_domains'), {
            'action': 'update_domain_rating_guide',
            'school_class': self.school_class.id,
            'term': term.id,
            'domain_rating_1_label': 'Outstanding',
            'domain_rating_1_description': 'Class specific',
            'domain_rating_2_label': 'Developing',
            'domain_rating_2_description': 'Needs support',
        })

        self.assertRedirects(
            response,
            f'{reverse("core:school_admin_learner_domains")}?school_class={self.school_class.id}&term={term.id}',
            fetch_redirect_response=False,
        )
        settings = ReportCardSettings.all_objects.get(school=self.school)
        self.assertEqual(
            settings.class_domain_rating_guides,
            {
                str(self.school_class.id): [
                    {'label': 'Outstanding', 'description': 'Class specific'},
                    {'label': 'Developing', 'description': 'Needs support'},
                ],
            },
        )

    def test_school_admin_can_add_edit_and_remove_domain_criteria(self):
        term = Term.all_objects.create(
            school=self.school,
            name='First Term',
            session='2025-2026',
            start_date=date.today() - timedelta(days=90),
            end_date=date.today(),
            is_active=True,
        )
        response = self.client.get(reverse('core:school_admin_learner_domains'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Punctuality')
        self.assertContains(response, 'Music')

        response = self.client.post(reverse('core:school_admin_learner_domains'), {
            'action': 'add_criterion',
            'domain_type': 'effective',
            'name': 'Leadership',
            'school_class': self.school_class.id,
            'term': term.id,
        })
        self.assertRedirects(
            response,
            f'{reverse("core:school_admin_learner_domains")}?school_class={self.school_class.id}&term={term.id}',
            fetch_redirect_response=False,
        )
        criterion = LearnerDomainCriterion.all_objects.get(
            school=self.school,
            domain_type=LearnerDomainCriterion.DOMAIN_EFFECTIVE,
            name='Leadership',
        )

        response = self.client.post(reverse('core:school_admin_learner_domains'), {
            'action': 'update_criterion',
            'criterion_id': criterion.id,
            'name': 'Leadership Skill',
            'display_order': 7,
            'school_class': self.school_class.id,
            'term': term.id,
        })
        self.assertRedirects(
            response,
            f'{reverse("core:school_admin_learner_domains")}?school_class={self.school_class.id}&term={term.id}',
            fetch_redirect_response=False,
        )
        criterion.refresh_from_db()
        self.assertEqual(criterion.name, 'Leadership Skill')
        self.assertEqual(criterion.display_order, 7)

        response = self.client.post(reverse('core:school_admin_learner_domains'), {
            'action': 'delete_criterion',
            'criterion_id': criterion.id,
            'school_class': self.school_class.id,
            'term': term.id,
        })
        self.assertRedirects(
            response,
            f'{reverse("core:school_admin_learner_domains")}?school_class={self.school_class.id}&term={term.id}',
            fetch_redirect_response=False,
        )
        criterion.refresh_from_db()
        self.assertFalse(criterion.is_active)

    def test_school_admin_can_limit_domain_criteria_to_selected_class(self):
        term = Term.all_objects.create(
            school=self.school,
            name='First Term',
            session='2025-2026',
            start_date=date.today() - timedelta(days=90),
            end_date=date.today(),
            is_active=True,
        )
        other_class = SchoolClass.all_objects.create(school=self.school, name='JSS 2', stream='A')

        response = self.client.post(reverse('core:school_admin_learner_domains'), {
            'action': 'add_criterion',
            'domain_type': LearnerDomainCriterion.DOMAIN_EFFECTIVE,
            'name': 'Health',
            'criterion_scope': 'selected',
            'school_class': self.school_class.id,
            'term': term.id,
        })

        self.assertRedirects(
            response,
            f'{reverse("core:school_admin_learner_domains")}?school_class={self.school_class.id}&term={term.id}',
            fetch_redirect_response=False,
        )
        criterion = LearnerDomainCriterion.all_objects.get(
            school=self.school,
            domain_type=LearnerDomainCriterion.DOMAIN_EFFECTIVE,
            name='Health',
        )
        self.assertEqual(list(criterion.classes.values_list('id', flat=True)), [self.school_class.id])

        response = self.client.get(
            f'{reverse("core:school_admin_learner_domains")}?school_class={self.school_class.id}&term={term.id}'
        )
        self.assertContains(response, 'Health')

        response = self.client.get(
            f'{reverse("core:school_admin_learner_domains")}?school_class={other_class.id}&term={term.id}'
        )
        self.assertNotContains(response, 'Health')

    def test_add_existing_hidden_domain_criterion_makes_it_available_to_selected_class(self):
        term = Term.all_objects.create(
            school=self.school,
            name='First Term',
            session='2025-2026',
            start_date=date.today() - timedelta(days=90),
            end_date=date.today(),
            is_active=True,
        )
        other_class = SchoolClass.all_objects.create(school=self.school, name='JSS 2', stream='A')
        other_school = SchoolTenant.objects.create(name='Other Tenant', slug='other-tenant')
        foreign_class = SchoolClass.all_objects.create(school=other_school, name='JSS 9', stream='A')
        neatness = LearnerDomainCriterion.all_objects.create(
            school=self.school,
            domain_type=LearnerDomainCriterion.DOMAIN_EFFECTIVE,
            name='Neatness',
            display_order=10,
        )
        neatness.classes.set([other_class])

        response = self.client.get(
            f'{reverse("core:school_admin_learner_domains")}?school_class={self.school_class.id}&term={term.id}'
        )
        self.assertNotContains(response, 'Neatness')

        response = self.client.post(reverse('core:school_admin_learner_domains'), {
            'action': 'add_criterion',
            'domain_type': LearnerDomainCriterion.DOMAIN_EFFECTIVE,
            'name': 'Neatness',
            'criterion_scope': 'specific',
            'criterion_classes': [foreign_class.id],
            'school_class': self.school_class.id,
            'term': term.id,
        })

        self.assertRedirects(
            response,
            f'{reverse("core:school_admin_learner_domains")}?school_class={self.school_class.id}&term={term.id}',
            fetch_redirect_response=False,
        )
        neatness.refresh_from_db()
        self.assertEqual(
            set(neatness.classes.values_list('id', flat=True)),
            {self.school_class.id, other_class.id},
        )
        self.assertNotIn(foreign_class.id, set(neatness.classes.values_list('id', flat=True)))

        response = self.client.get(
            f'{reverse("core:school_admin_learner_domains")}?school_class={self.school_class.id}&term={term.id}'
        )
        self.assertContains(response, 'Neatness')
        self.assertNotContains(response, 'Neatness already exists in this domain.')

    def test_school_admin_student_id_is_generated_on_create(self):
        SchoolSettings.all_objects.create(
            school=self.school,
            school_name='Admin Users School',
            school_address='1 Test Road',
            principal_name='Principal',
            student_id_prefix='ADM',
            student_id_digits=3,
        )
        student_user = User.objects.create_user(
            username='auto-id-student',
            password='password',
            first_name='Auto',
            last_name='Student',
            role='student',
        )
        SchoolMembership.objects.create(school=self.school, user=student_user, primary_role='student')

        response = self.client.post(reverse('core:school_admin_students'), {
            'user': student_user.id,
            'student_id': 'MANUAL999',
            'school_class': self.school_class.id,
            'date_of_birth': '2012-01-01',
            'gender': 'M',
            'address': 'Test address',
        })

        self.assertRedirects(response, reverse('core:school_admin_students'))
        student = Student.all_objects.get(user=student_user)
        self.assertEqual(student.student_id, 'ADM001')

    def test_super_admin_recent_activity_is_scoped_to_active_school(self):
        other_school = SchoolTenant.objects.create(name='Other School', slug='other-school')
        other_class = SchoolClass.all_objects.create(school=other_school, name='JSS 2', stream='B')
        other_user = User.objects.create_user(
            username='other-student',
            password='password',
            first_name='Other',
            last_name='Student',
            role='student',
        )
        Student.all_objects.create(
            school=other_school,
            user=other_user,
            student_id='OTH001',
            school_class=other_class,
            date_of_birth=date(2012, 1, 1),
        )

        local_user = User.objects.create_user(
            username='local-student',
            password='password',
            first_name='Local',
            last_name='Student',
            role='student',
        )
        Student.all_objects.create(
            school=self.school,
            user=local_user,
            student_id='LOC001',
            school_class=self.school_class,
            date_of_birth=date(2012, 1, 1),
        )

        response = self.client.get(reverse('core:dashboard'))

        self.assertContains(response, 'Local Student')
        self.assertNotContains(response, 'Other Student')

    def test_user_page_has_initial_password_and_delete_action(self):
        target = self._create_member('target-user', 'student')

        response = self.client.get(reverse('core:school_admin_users'))

        self.assertContains(response, 'data-password-toggle="id_password"')
        self.assertContains(response, 'Initial Password')
        self.assertContains(response, 'fa-eye')
        self.assertContains(response, 'Allow portal login')
        self.assertContains(response, 'Allow result access')
        self.assertContains(response, 'Send Login')
        self.assertContains(response, 'name="action" value="delete_user"')
        self.assertContains(response, f'name="user_id" value="{target.id}"')

    def test_edit_user_page_uses_separate_password_reset_form(self):
        target = self._create_member('edit-target', 'student')

        response = self.client.get(f'{reverse("core:school_admin_users")}?user={target.id}')

        self.assertNotContains(response, 'Initial Password')
        self.assertContains(response, 'Reset Password')
        self.assertContains(response, 'name="action" value="reset_password"')
        self.assertContains(response, 'data-password-toggle="id_new_password"')
        self.assertContains(response, 'data-password-toggle="id_confirm_password"')

    def test_edit_user_does_not_change_password(self):
        target = self._create_member('edit-password-target', 'student')

        response = self.client.post(reverse('core:school_admin_users'), {
            'action': 'save_user',
            'user_id': target.id,
            'username': 'edit-password-target',
            'first_name': 'Edited',
            'last_name': 'User',
            'email': '',
            'phone': '',
            'role': 'student',
            'extra_roles': [],
            'is_active': 'on',
            'portal_access_enabled': 'on',
            'result_access_enabled': 'on',
            'password': 'browser-autofill-should-not-apply',
        })

        self.assertRedirects(response, reverse('core:school_admin_users'))
        target.refresh_from_db()
        self.assertEqual(target.first_name, 'Edited')
        self.assertTrue(target.check_password('password'))
        self.assertFalse(target.check_password('browser-autofill-should-not-apply'))

    def test_school_admin_can_reset_user_password_separately(self):
        target = self._create_member('reset-password-target', 'student')

        response = self.client.post(reverse('core:school_admin_users'), {
            'action': 'reset_password',
            'user_id': target.id,
            'new_password': 'new-secure-password',
            'confirm_password': 'new-secure-password',
        })

        self.assertRedirects(response, reverse('core:school_admin_users'))
        target.refresh_from_db()
        self.assertTrue(target.check_password('new-secure-password'))

    def test_saving_school_admin_user_creates_staff_profile(self):
        response = self.client.post(reverse('core:school_admin_users'), {
            'action': 'save_user',
            'username': 'portal-admin-staff',
            'first_name': 'Portal',
            'last_name': 'Admin',
            'email': 'portal-admin@example.com',
            'phone': '',
            'role': 'super_admin',
            'is_active': 'on',
            'portal_access_enabled': 'on',
            'result_access_enabled': 'on',
            'password': 'password',
        })

        self.assertRedirects(response, reverse('core:school_admin_users'))
        admin_user = User.objects.get(username='portal-admin-staff')
        staff_profile = Teacher.all_objects.get(school=self.school, user=admin_user)
        self.assertTrue(staff_profile.employee_id)

        response = self.client.get(reverse('core:school_admin_staff'))
        self.assertContains(response, 'Portal Admin')

    def test_school_admin_can_delete_user(self):
        target = self._create_member('delete-me', 'student')

        response = self.client.post(reverse('core:school_admin_users'), {
            'action': 'delete_user',
            'user_id': target.id,
        })

        self.assertRedirects(response, reverse('core:school_admin_users'))
        self.assertFalse(User.objects.filter(id=target.id).exists())

    def test_staff_user_dropdown_includes_teacher_extra_role(self):
        staff_user = User.objects.create_user(username='staff-extra-role', password='password', role='accountant')
        SchoolMembership.objects.create(
            school=self.school,
            user=staff_user,
            primary_role='accountant',
            extra_roles=['subject_teacher'],
        )

        form = SchoolTeacherForm(school=self.school)

        self.assertIn(staff_user, form.fields['user'].queryset)

    def test_class_teacher_can_create_and_manage_quizzes(self):
        class_teacher_user = self._create_member('class-teacher', 'class_teacher')
        teacher = Teacher.all_objects.create(
            school=self.school,
            user=class_teacher_user,
            employee_id='TCH001',
        )
        teacher.classes.add(self.school_class)
        teacher.subjects.add(self.subject)
        ClassTeacher.objects.create(teacher=teacher, school_class=self.school_class)

        class_teacher_client = Client(HTTP_HOST=self.host)
        self.assertTrue(class_teacher_client.login(username='class-teacher', password='password'))

        response = class_teacher_client.get(reverse('core:create_quiz'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Create New Quiz')

        start = timezone.now() + timedelta(hours=1)
        end = start + timedelta(hours=1)
        response = class_teacher_client.post(reverse('core:create_quiz'), {
            'title': 'Class Teacher Quiz',
            'subject': self.subject.id,
            'class': self.school_class.id,
            'start_time': start.strftime('%Y-%m-%dT%H:%M'),
            'end_time': end.strftime('%Y-%m-%dT%H:%M'),
            'duration_minutes': 60,
            'instructions': '',
        })

        quiz = Quiz.objects.get(title='Class Teacher Quiz')
        self.assertRedirects(response, reverse('core:add_questions', args=[quiz.id]))

        response = class_teacher_client.get(reverse('core:quiz_management'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Class Teacher Quiz')
