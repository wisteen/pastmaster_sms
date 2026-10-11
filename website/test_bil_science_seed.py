import io
import tempfile

from django.contrib.auth.models import AnonymousUser
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import RequestFactory, TestCase, override_settings
from PIL import Image

from core.models import SchoolSettings
from core.models_features import SchoolTenant
from website.bil_science_seed import (
    ACADEMIC_DEPARTMENTS,
    DEFAULT_SCHOOL_SLUG,
    MOTTO,
    PROPRIETOR_NAME,
    PROPRIETOR_SPEECH,
    SCHOOL_NAME,
    seed_bil_science_website,
)
from website.models import (
    DownloadableForm,
    GalleryImage,
    WebsiteContentItem,
    WebsitePage,
    WebsiteProfile,
    WebsiteSection,
    WebsiteTeamMember,
)
from website.views import about, admissions, gallery, home, page_detail


class BilScienceWebsiteSeedTests(TestCase):
    def setUp(self):
        self.media_directory = tempfile.TemporaryDirectory()
        self.media_override = override_settings(MEDIA_ROOT=self.media_directory.name)
        self.media_override.enable()
        self.addCleanup(self.media_override.disable)
        self.addCleanup(self.media_directory.cleanup)

        self.school = SchoolTenant.objects.create(
            name="Old BIL name",
            slug=DEFAULT_SCHOOL_SLUG,
            contact_email="old@example.test",
            contact_phone="000",
        )
        SchoolSettings.objects.create(
            school=self.school,
            school_name="Old school name",
            school_address="Old address",
            principal_name="School Administrator",
            proprietor_name="Proprietor",
        )
        self.other_school = SchoolTenant.objects.create(
            name="Unrelated School",
            slug="unrelated-school",
            contact_email="other@example.test",
        )

    def test_seed_builds_bil_site_with_departments_houses_and_proprietor_message(self):
        DownloadableForm.objects.create(
            school=self.school,
            title="BIL Science Academy Fee Structure",
            description="Legacy title",
        )
        result = seed_bil_science_website(self.school)

        self.school.refresh_from_db()
        settings = SchoolSettings.objects.get(school=self.school)
        profile = WebsiteProfile.objects.get(school=self.school)
        self.assertEqual(self.school.name, SCHOOL_NAME)
        self.assertEqual(SCHOOL_NAME, "Bil Science Academy")
        self.assertEqual(settings.proprietor_name, PROPRIETOR_NAME)
        self.assertEqual(settings.school_motto, MOTTO)
        self.assertEqual(MOTTO, "Knowledge, Character and Excellence")
        self.assertEqual(profile.site_name, SCHOOL_NAME)
        self.assertIn(
            "Bil Science Academy is a co-educational school in Alagbado, Lagos",
            profile.description,
        )
        self.assertTrue(profile.logo.storage.exists(profile.logo.name))

        self.assertEqual(
            set(WebsitePage.objects.filter(school=self.school).values_list("slug", flat=True)),
            {"home", "about", "academics", "clubs", "gallery", "admissions", "school-fees"},
        )
        self.assertEqual(len(result["pages"]), 7)

        home = WebsitePage.objects.get(school=self.school, slug="home")
        self.assertTrue(
            home.sections.filter(title="Begin Your Child's Journey Today").exists()
        )
        self.assertFalse(home.sections.filter(section_type="team").exists())
        self.assertFalse(home.sections.filter(body__icontains=PROPRIETOR_NAME).exists())

        academic_titles = set(
            WebsiteSection.objects.get(page=home, title="Four Academic Departments")
            .items.values_list("title", flat=True)
        )
        self.assertEqual(academic_titles, {title for title, _description, _icon in ACADEMIC_DEPARTMENTS})

        houses = WebsiteSection.objects.get(page=home, title="Our Four Houses")
        self.assertEqual(
            list(houses.items.order_by("order").values_list("title", flat=True)),
            [
                "Afolabi House (Pink)",
                "Al-Ameen House (Yellow)",
                "Kareem House (Green)",
                "Sanyaolu House (Blue)",
            ],
        )

        about_page = WebsitePage.objects.get(school=self.school, slug="about")
        final_section = about_page.sections.order_by("-order").first()
        self.assertEqual(final_section.title, "Welcome from the Proprietor")
        self.assertTrue(final_section.image.storage.exists(final_section.image.name))
        self.assertIn(PROPRIETOR_SPEECH[-1], final_section.body)
        self.assertIn(PROPRIETOR_NAME, final_section.body)

        proprietor = WebsiteTeamMember.objects.get(school=self.school, name=PROPRIETOR_NAME)
        self.assertIn(PROPRIETOR_SPEECH[1], proprietor.bio)
        self.assertTrue(proprietor.photo.storage.exists(proprietor.photo.name))

        self.assertEqual(GalleryImage.objects.filter(school=self.school).count(), 11)
        self.assertEqual(
            list(
                DownloadableForm.objects.filter(school=self.school).values_list(
                    "title", flat=True
                )
            ),
            ["Bil Science Academy Fee Structure"],
        )
        pink = GalleryImage.objects.get(school=self.school, caption="Afolabi House — Pink")
        with pink.image.open("rb") as image_file:
            with Image.open(image_file) as image:
                self.assertGreater(image.width, image.height)

        public_text = [
            self.school.name,
            settings.school_name,
            settings.school_motto,
            profile.site_name,
            profile.tagline,
            profile.description,
            profile.footer_note,
        ]
        public_text.extend(
            str(value or "")
            for values in WebsitePage.objects.filter(school=self.school).values_list(
                "title", "nav_label", "header_title", "header_subtitle", "meta_title",
                "meta_description", "meta_keywords", "og_title", "og_description",
            )
            for value in values
        )
        public_text.extend(
            str(value or "")
            for values in WebsiteSection.objects.filter(page__school=self.school).values_list(
                "title", "subtitle", "body", "button_label"
            )
            for value in values
        )
        public_text.extend(
            str(value or "")
            for values in WebsiteContentItem.objects.filter(
                section__page__school=self.school
            ).values_list("title", "subtitle", "body", "button_label")
            for value in values
        )
        public_text.extend(
            str(value or "")
            for values in WebsiteTeamMember.objects.filter(school=self.school).values_list(
                "name", "role", "bio"
            )
            for value in values
        )
        public_text.extend(
            str(value or "")
            for values in GalleryImage.objects.filter(school=self.school).values_list("caption")
            for value in values
        )
        public_text.extend(
            str(value or "")
            for values in DownloadableForm.objects.filter(school=self.school).values_list(
                "title", "description"
            )
            for value in values
        )
        combined_public_text = " ".join(public_text)
        self.assertNotIn("BIL Science", combined_public_text)
        self.assertNotIn("BIL SCIENCE", combined_public_text)
        for retired_term in ("muslim", "adab", "amanah", "bil journey"):
            self.assertNotIn(retired_term, combined_public_text.lower())

    def test_seed_is_repeatable_without_duplicate_pages_or_records(self):
        seed_bil_science_website(self.school)
        first_counts = {
            "pages": WebsitePage.objects.filter(school=self.school).count(),
            "sections": WebsiteSection.objects.filter(page__school=self.school).count(),
            "team": WebsiteTeamMember.objects.filter(school=self.school).count(),
            "gallery": GalleryImage.objects.filter(school=self.school).count(),
        }

        seed_bil_science_website(self.school)

        self.assertEqual(WebsitePage.objects.filter(school=self.school).count(), first_counts["pages"])
        self.assertEqual(WebsiteSection.objects.filter(page__school=self.school).count(), first_counts["sections"])
        self.assertEqual(WebsiteTeamMember.objects.filter(school=self.school).count(), first_counts["team"])
        self.assertEqual(GalleryImage.objects.filter(school=self.school).count(), first_counts["gallery"])

    def test_seed_does_not_touch_another_tenant(self):
        before = {
            "profile": WebsiteProfile.objects.filter(school=self.other_school).values().first(),
            "pages": list(WebsitePage.objects.filter(school=self.other_school).values_list("slug", flat=True)),
            "gallery": GalleryImage.objects.filter(school=self.other_school).count(),
        }

        seed_bil_science_website(self.school)

        self.other_school.refresh_from_db()
        self.assertEqual(self.other_school.contact_email, "other@example.test")
        self.assertEqual(WebsiteProfile.objects.filter(school=self.other_school).values().first(), before["profile"])
        self.assertEqual(
            list(WebsitePage.objects.filter(school=self.other_school).values_list("slug", flat=True)),
            before["pages"],
        )
        self.assertEqual(GalleryImage.objects.filter(school=self.other_school).count(), before["gallery"])

    def test_command_dry_run_makes_no_changes(self):
        output = io.StringIO()
        profile_before = WebsiteProfile.objects.filter(school=self.school).values().first()
        pages_before = list(WebsitePage.objects.filter(school=self.school).values_list("slug", flat=True))

        call_command("seed_bil_science_website", "--dry-run", stdout=output)

        self.assertIn("No database or media changes were made", output.getvalue())
        self.assertEqual(WebsiteProfile.objects.filter(school=self.school).values().first(), profile_before)
        self.assertEqual(
            list(WebsitePage.objects.filter(school=self.school).values_list("slug", flat=True)),
            pages_before,
        )

    def test_command_rejects_multiple_tenant_selectors(self):
        with self.assertRaisesMessage(CommandError, "Choose only one"):
            call_command(
                "seed_bil_science_website",
                "--school-id",
                str(self.school.id),
                "--school-slug",
                self.school.slug,
            )

    def test_all_seeded_public_pages_render(self):
        seed_bil_science_website(self.school)
        request_factory = RequestFactory()
        routes = [
            ("/", home, ()),
            ("/about/", about, ()),
            ("/admissions/", admissions, ()),
            ("/gallery/", gallery, ()),
            ("/academics/", page_detail, ("academics",)),
            ("/clubs/", page_detail, ("clubs",)),
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
