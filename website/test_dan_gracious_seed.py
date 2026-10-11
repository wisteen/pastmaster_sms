import io
import tempfile

from django.contrib.auth.models import AnonymousUser
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import RequestFactory, TestCase, override_settings

from core.models import SchoolSettings
from core.models_features import SchoolTenant
from website.dan_gracious_seed import (
    DEFAULT_SCHOOL_SLUG,
    DIRECTOR_NAME,
    DIRECTOR_SPEECH,
    EMAIL,
    PHONE,
    PRINCIPAL_NAME,
    PRINCIPAL_SPEECH,
    SCHOOL_NAME,
    seed_dan_gracious_website,
)
from website.models import (
    Faq,
    GalleryImage,
    WebsitePage,
    WebsiteProfile,
    WebsiteSection,
    WebsiteTeamMember,
)
from website.views import about, admissions, gallery, home, page_detail


class DanGraciousWebsiteSeedTests(TestCase):
    def setUp(self):
        self.media_directory = tempfile.TemporaryDirectory()
        self.media_override = override_settings(MEDIA_ROOT=self.media_directory.name)
        self.media_override.enable()
        self.addCleanup(self.media_override.disable)
        self.addCleanup(self.media_directory.cleanup)

        self.school = SchoolTenant.objects.create(
            name="Dan-Graciousland Schools",
            slug=DEFAULT_SCHOOL_SLUG,
            contact_email="old@example.test",
            contact_phone="000",
        )
        SchoolSettings.objects.create(
            school=self.school,
            school_name="Old school name",
            school_address="Old address",
            principal_name="Old principal",
        )
        self.other_school = SchoolTenant.objects.create(
            name="Unrelated School",
            slug="unrelated-school",
            contact_email="other@example.test",
        )

    def test_seed_builds_curated_public_site_and_installs_assets(self):
        result = seed_dan_gracious_website(self.school)

        self.school.refresh_from_db()
        settings = SchoolSettings.objects.get(school=self.school)
        profile = WebsiteProfile.objects.get(school=self.school)

        self.assertEqual(self.school.contact_email, EMAIL)
        self.assertEqual(self.school.contact_phone, PHONE)
        self.assertEqual(settings.school_name, SCHOOL_NAME)
        self.assertEqual(settings.principal_name, PRINCIPAL_NAME)
        self.assertEqual(settings.proprietor_name, DIRECTOR_NAME)
        self.assertTrue(settings.school_logo)
        self.assertTrue(settings.school_logo.storage.exists(settings.school_logo.name))
        self.assertTrue(settings.school_seal.storage.exists(settings.school_seal.name))

        self.assertEqual(profile.site_name, SCHOOL_NAME)
        self.assertEqual(profile.email, EMAIL)
        self.assertEqual(profile.phone, PHONE)
        self.assertTrue(profile.logo.storage.exists(profile.logo.name))
        self.assertTrue(profile.default_og_image.storage.exists(profile.default_og_image.name))

        self.assertEqual(
            set(WebsitePage.objects.filter(school=self.school).values_list("slug", flat=True)),
            {"home", "about", "academics", "admissions", "gallery", "school-fees"},
        )
        self.assertEqual(WebsiteSection.objects.filter(page__school=self.school).count(), 29)
        self.assertEqual(len(result["pages"]), 6)

        principal = WebsiteTeamMember.objects.get(school=self.school, name=PRINCIPAL_NAME)
        director = WebsiteTeamMember.objects.get(school=self.school, name=DIRECTOR_NAME)
        self.assertEqual(principal.role, "Principal")
        self.assertEqual(director.role, "Proprietor / Child's Care Director")
        self.assertIn(PRINCIPAL_SPEECH, principal.bio)
        self.assertIn(DIRECTOR_SPEECH, director.bio)
        self.assertTrue(principal.photo.storage.exists(principal.photo.name))
        self.assertTrue(director.photo.storage.exists(director.photo.name))

        self.assertEqual(GalleryImage.objects.filter(school=self.school).count(), 8)
        self.assertEqual(GalleryImage.objects.filter(school=self.school, is_featured=True).count(), 6)
        for image in GalleryImage.objects.filter(school=self.school):
            self.assertTrue(image.image.storage.exists(image.image.name))

        fees_page = WebsitePage.objects.get(school=self.school, slug="school-fees")
        fee_text = " ".join(
            [section.title + " " + section.subtitle + " " + section.body for section in fees_page.sections.all()]
            + [
                item.title + " " + item.subtitle + " " + item.body
                for section in fees_page.sections.all()
                for item in section.items.all()
            ]
        )
        self.assertIn("₦150,000", fee_text)
        self.assertIn("₦80,000", fee_text)
        self.assertIn("2005478300", fee_text)
        self.assertIn("confirm", fee_text.lower())
        self.assertEqual(Faq.objects.filter(school=self.school, published=True).count(), 3)

    def test_seed_is_repeatable_without_duplicate_pages_team_or_gallery(self):
        seed_dan_gracious_website(self.school)
        first_names = {
            "pages": WebsitePage.objects.filter(school=self.school).count(),
            "team": WebsiteTeamMember.objects.filter(school=self.school).count(),
            "gallery": GalleryImage.objects.filter(school=self.school).count(),
            "faqs": Faq.objects.filter(school=self.school).count(),
        }

        seed_dan_gracious_website(self.school)

        self.assertEqual(WebsitePage.objects.filter(school=self.school).count(), first_names["pages"])
        self.assertEqual(WebsiteTeamMember.objects.filter(school=self.school).count(), first_names["team"])
        self.assertEqual(GalleryImage.objects.filter(school=self.school).count(), first_names["gallery"])
        self.assertEqual(Faq.objects.filter(school=self.school).count(), first_names["faqs"])
        self.assertEqual(WebsiteSection.objects.filter(page__school=self.school).count(), 29)

    def test_seed_does_not_touch_another_tenant(self):
        other_profile_before = WebsiteProfile.objects.filter(school=self.other_school).values().first()
        other_pages_before = list(
            WebsitePage.objects.filter(school=self.other_school).values_list("slug", "title", "order")
        )
        other_sections_before = WebsiteSection.objects.filter(page__school=self.other_school).count()
        other_gallery_before = GalleryImage.objects.filter(school=self.other_school).count()

        seed_dan_gracious_website(self.school)

        self.other_school.refresh_from_db()
        self.assertEqual(self.other_school.contact_email, "other@example.test")
        self.assertEqual(
            WebsiteProfile.objects.filter(school=self.other_school).values().first(),
            other_profile_before,
        )
        self.assertEqual(
            list(WebsitePage.objects.filter(school=self.other_school).values_list("slug", "title", "order")),
            other_pages_before,
        )
        self.assertEqual(
            WebsiteSection.objects.filter(page__school=self.other_school).count(),
            other_sections_before,
        )
        self.assertEqual(GalleryImage.objects.filter(school=self.other_school).count(), other_gallery_before)

    def test_command_dry_run_makes_no_changes(self):
        output = io.StringIO()
        profile_before = WebsiteProfile.objects.filter(school=self.school).values().first()
        pages_before = list(WebsitePage.objects.filter(school=self.school).values_list("slug", "title", "order"))
        sections_before = WebsiteSection.objects.filter(page__school=self.school).count()

        call_command("seed_dan_gracious_website", "--dry-run", stdout=output)

        self.assertIn("No database or media changes were made", output.getvalue())
        self.assertEqual(WebsiteProfile.objects.filter(school=self.school).values().first(), profile_before)
        self.assertEqual(
            list(WebsitePage.objects.filter(school=self.school).values_list("slug", "title", "order")),
            pages_before,
        )
        self.assertEqual(WebsiteSection.objects.filter(page__school=self.school).count(), sections_before)

    def test_command_rejects_multiple_tenant_selectors(self):
        with self.assertRaisesMessage(CommandError, "Choose only one"):
            call_command(
                "seed_dan_gracious_website",
                "--school-id",
                str(self.school.id),
                "--school-slug",
                self.school.slug,
            )

    def test_all_seeded_public_pages_render(self):
        seed_dan_gracious_website(self.school)
        request_factory = RequestFactory()
        routes = [
            ("/", home, ()),
            ("/about/", about, ()),
            ("/admissions/", admissions, ()),
            ("/gallery/", gallery, ()),
            ("/academics/", page_detail, ("academics",)),
            ("/school-fees/", page_detail, ("school-fees",)),
        ]

        for path, view, args in routes:
            with self.subTest(path=path):
                request = request_factory.get(path)
                request.school = self.school
                request.user = AnonymousUser()
                response = view(request, *args)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, SCHOOL_NAME)
