from unittest.mock import patch
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    PastMasterConnection,
    SchoolClass,
    SchoolMembership,
    SchoolTenant,
    Student,
    User,
)
from .models_license import SystemLicense


class PastMasterConnectionTests(TestCase):
    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Connected School", slug="connected-school")
        self.other_school = SchoolTenant.objects.create(name="Other School", slug="other-school")
        self.admin = User.objects.create_superuser(username="integration-admin", password="password")
        self.client.force_login(self.admin)

    def test_client_secret_is_encrypted_and_round_trips(self):
        connection = PastMasterConnection(school=self.school, client_id="client-id")
        connection.set_client_secret("plain-secret")
        connection.save()
        self.assertNotIn("plain-secret", connection.client_secret_encrypted)
        self.assertEqual(connection.get_client_secret(), "plain-secret")

    def test_connection_dashboard_only_shows_active_tenant(self):
        PastMasterConnection.objects.create(
            school=self.other_school,
            base_url="https://pastmaster.example",
            client_id="other-client",
        )
        response = self.client.get(
            reverse("core:pastmaster_connection"),
            {"school": self.school.slug},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "other-client")

    def test_admin_can_open_complete_illustrated_guide(self):
        response = self.client.get(
            reverse("core:pastmaster_guide"),
            {"school": self.school.slug},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Connect and use PastMaster")
        self.assertContains(response, "roster-sync.svg")
        self.assertContains(response, "intelligence-report.svg")
        self.assertContains(response, "safe-disconnect.svg")

    @patch("core.views_pastmaster.PastMasterClient")
    def test_admin_can_sync_roster(self, client_class):
        connection = PastMasterConnection(
            school=self.school,
            base_url="https://pastmaster.example",
            client_id="client-id",
        )
        connection.set_client_secret("plain-secret")
        connection.save()
        client_class.return_value.sync_roster.return_value = {
            "succeeded": 3,
            "failed": 0,
        }
        response = self.client.post(
            f"{reverse('core:pastmaster_connection')}?school={self.school.slug}",
            {"action": "sync_roster"},
        )
        self.assertEqual(response.status_code, 302)
        connection.refresh_from_db()
        self.assertEqual(connection.status, PastMasterConnection.Status.ACTIVE)
        self.assertIsNotNone(connection.last_roster_sync_at)


class PastMasterStudentLaunchTests(TestCase):
    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Student School", slug="student-school")
        self.school_class = SchoolClass.all_objects.create(school=self.school, name="SS 3", stream="A")
        self.user = User.objects.create_user(username="student", password="password", role="student")
        SchoolMembership.objects.create(school=self.school, user=self.user, primary_role="student")
        self.student = Student.all_objects.create(
            school=self.school,
            user=self.user,
            student_id="STU-1",
            school_class=self.school_class,
            date_of_birth="2008-01-01",
        )
        connection = PastMasterConnection(
            school=self.school,
            base_url="https://pastmaster.example",
            client_id="client-id",
            status=PastMasterConnection.Status.ACTIVE,
        )
        connection.set_client_secret("plain-secret")
        connection.save()
        SystemLicense.all_objects.create(
            school=self.school,
            school_name=self.school.name,
            license_key="student-school-license",
            expiry_date=timezone.now().date() + timedelta(days=30),
        )
        self.client.force_login(self.user)

    @patch("core.views_pastmaster.PastMasterClient")
    def test_student_is_redirected_to_one_time_launch(self, client_class):
        client_class.return_value.create_student_launch.return_value = {
            "launch_url": "https://pastmaster.example/integrations/sso/?code=ABCD-2345"
        }
        response = self.client.get(
            reverse("core:pastmaster_student_launch"),
            {"school": self.school.slug},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "https://pastmaster.example/integrations/sso/?code=ABCD-2345")
        client_class.return_value.create_student_launch.assert_called_once_with("STU-1")
