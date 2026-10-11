from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from .models import ResultComponent, SchoolClass, SchoolMembership, SchoolTenant, Subject
from .models_features import SchoolDomain
from .models_license import SystemLicense


User = get_user_model()


class SchoolAdminAssessmentTests(TestCase):
    host = 'assessments.testserver'

    def setUp(self):
        self.school = SchoolTenant.objects.create(name='Assessment School', slug='assessment-school')
        SchoolDomain.objects.create(school=self.school, domain=self.host)
        SystemLicense.all_objects.create(
            school=self.school,
            school_name=self.school.name,
            license_key='assessment-school-license',
            expiry_date=date.today() + timedelta(days=30),
        )
        self.admin = User.objects.create_user(username='admin', password='password', role='super_admin')
        SchoolMembership.objects.create(school=self.school, user=self.admin, primary_role='super_admin')
        self.school_class = SchoolClass.all_objects.create(school=self.school, name='JSS 1', stream='A')
        self.subject = Subject.all_objects.create(school=self.school, name='Mathematics', code='MTH')
        self.component = ResultComponent.objects.create(
            school_class=self.school_class,
            subject=self.subject,
            component_name='CA1',
            weight=20,
            max_score=20,
        )
        self.client = Client(HTTP_HOST=self.host)
        self.assertTrue(self.client.login(username='admin', password='password'))

    def test_assessment_list_has_row_delete_action(self):
        response = self.client.get(reverse('core:school_admin_assessments'))

        self.assertContains(response, 'name="action" value="delete"')
        self.assertContains(response, f'name="component_id" value="{self.component.id}"')
        self.assertContains(response, 'Delete')

    def test_school_admin_can_delete_assessment_from_list_action(self):
        response = self.client.post(reverse('core:school_admin_assessments'), {
            'action': 'delete',
            'component_id': self.component.id,
        })

        self.assertRedirects(response, reverse('core:school_admin_assessments'))
        self.assertFalse(ResultComponent.objects.filter(id=self.component.id).exists())

    def test_school_admin_can_bulk_delete_selected_assessments(self):
        second_component = ResultComponent.objects.create(
            school_class=self.school_class,
            subject=self.subject,
            component_name='Exam',
            weight=80,
            max_score=100,
        )
        retained_component = ResultComponent.objects.create(
            school_class=self.school_class,
            subject=self.subject,
            component_name='Project',
            weight=10,
            max_score=10,
        )

        response = self.client.post(reverse('core:school_admin_assessments'), {
            'action': 'bulk_delete',
            'component_ids': [self.component.id, second_component.id],
        })

        self.assertRedirects(response, reverse('core:school_admin_assessments'))
        self.assertFalse(ResultComponent.objects.filter(id=self.component.id).exists())
        self.assertFalse(ResultComponent.objects.filter(id=second_component.id).exists())
        self.assertTrue(ResultComponent.objects.filter(id=retained_component.id).exists())
