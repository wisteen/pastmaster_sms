from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from core.admin import SchoolTenantAdmin
from core.models_features import SchoolMembership, SchoolTenant


class SchoolTenantAdminTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='tenant-admin-test',
            email='tenant-admin@example.com',
            password='test-password',
        )
        self.school = SchoolTenant.objects.create(
            name='Large Membership School',
            slug='large-membership-school',
        )
        self.model_admin = SchoolTenantAdmin(SchoolTenant, AdminSite())
        self.request = RequestFactory().get('/admin/core/schooltenant/1/change/')
        self.request.user = self.user

    def test_memberships_are_not_rendered_as_unbounded_inline_forms(self):
        inline_models = {
            inline.model
            for inline in self.model_admin.get_inline_instances(self.request, self.school)
        }

        self.assertNotIn(SchoolMembership, inline_models)

    def test_membership_link_opens_filtered_membership_admin(self):
        link = str(self.model_admin.memberships_link(self.school))

        self.assertIn('/admin/core/schoolmembership/', link)
        self.assertIn(f'school__id__exact={self.school.pk}', link)
        self.assertIn('Manage 0 memberships', link)
