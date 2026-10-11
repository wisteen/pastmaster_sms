import io
import tempfile

from django.contrib.auth.models import AnonymousUser
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import RequestFactory, TestCase, override_settings

from core.models import SchoolSettings
from core.models_features import SchoolTenant
from website.models import (
    GalleryImage,
    WebsiteContentItem,
    WebsitePage,
    WebsiteProfile,
    WebsiteSection,
    WebsiteTeamMember,
)
from website.thy_kingdom_come_seed import (
    ADDRESS,
    DEFAULT_SCHOOL_SLUG,
    EMAIL,
    FEE_SCHEDULE,
    MOTTO,
    PHONE,
    PROPRIETOR_NAME,
    SCHOOL_NAME,
    seed_thy_kingdom_come_website,
)
from website.views import about, admissions, gallery, home, page_detail


class ThyKingdomComeWebsiteSeedTests(TestCase):
    def setUp(self):
        self.media_directory = tempfile.TemporaryDirectory()
        self.media_override = override_settings(MEDIA_ROOT=self.media_directory.name)
        self.media_override.enable()
        self.addCleanup(self.media_override.disable)
        self.addCleanup(self.media_directory.cleanup)

        self.school = SchoolTenant.objects.create(
            name="Old Thy Kingdom Come name",
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
            slug="unrelated-thy-kingdom-school",
            contact_email="other@example.test",
        )

    def test_seed_builds_complete_school_site_from_supplied_content_and_images(self):
        result = seed_thy_kingdom_come_website(self.school)

        self.school.refresh_from_db()
        settings = SchoolSettings.objects.get(school=self.school)
        profile = WebsiteProfile.objects.get(school=self.school)
        self.assertEqual(self.school.name, SCHOOL_NAME)
        self.assertEqual(self.school.contact_email, EMAIL)
        self.assertEqual(self.school.contact_phone, PHONE)
        self.assertEqual(settings.school_name, SCHOOL_NAME)
        self.assertEqual(settings.school_motto, MOTTO)
        self.assertEqual(settings.school_address, ADDRESS)
        self.assertEqual(settings.proprietor_name, PROPRIETOR_NAME)
        self.assertEqual(profile.site_name, SCHOOL_NAME)
        self.assertIn("KG, Nursery, Primary, and Secondary", profile.description)
        self.assertTrue(profile.logo.storage.exists(profile.logo.name))

        self.assertEqual(
            set(
                WebsitePage.objects.filter(school=self.school).values_list(
                    "slug", flat=True
                )
            ),
            {"home", "about", "academics", "admissions", "gallery", "school-fees"},
        )
        self.assertEqual(len(result["pages"]), 6)

        home_page = WebsitePage.objects.get(school=self.school, slug="home")
        hero = WebsiteSection.objects.get(page=home_page, section_type="hero")
        self.assertEqual(hero.hero_variant, "full_width")
        self.assertEqual(hero.items.count(), 0)
        self.assertTrue(hero.background_image.storage.exists(hero.background_image.name))

        proprietor = WebsiteTeamMember.objects.get(
            school=self.school,
            name=PROPRIETOR_NAME,
        )
        self.assertIn("home of excellence", proprietor.bio.lower())
        self.assertTrue(proprietor.photo.storage.exists(proprietor.photo.name))

        gallery_images = GalleryImage.objects.filter(school=self.school).order_by("order")
        self.assertEqual(gallery_images.count(), 16)
        self.assertEqual(gallery_images.filter(is_featured=True).count(), 6)
        for gallery_image in gallery_images:
            self.assertTrue(gallery_image.image.storage.exists(gallery_image.image.name))

        admissions_page = WebsitePage.objects.get(school=self.school, slug="admissions")
        admissions_steps = WebsiteSection.objects.get(
            page=admissions_page,
            title="How to Apply",
        )
        self.assertEqual(
            list(admissions_steps.items.order_by("order").values_list("title", flat=True)),
            [
                "Step 1: Purchase Form",
                "Step 2: Submit Documents",
                "Step 3: Entrance Examination",
                "Step 4: Admission",
            ],
        )

        fees_page = WebsitePage.objects.get(school=self.school, slug="school-fees")
        fee_section = WebsiteSection.objects.get(
            page=fees_page,
            title="Fee Structure by Class Level",
        )
        self.assertIn("2025/2026", fees_page.header_subtitle)
        self.assertIn("2041727429", fee_section.body)
        self.assertIn("Bo Malkut Elementary &amp; Secondary Schools", fee_section.body)
        for level, _rows, total in FEE_SCHEDULE:
            self.assertIn(level, fee_section.body)
            self.assertIn(f"₦{total:,.0f}", fee_section.body)

    def test_seed_is_repeatable_without_duplicate_records(self):
        seed_thy_kingdom_come_website(self.school)
        first_counts = {
            "pages": WebsitePage.objects.filter(school=self.school).count(),
            "sections": WebsiteSection.objects.filter(page__school=self.school).count(),
            "items": WebsiteContentItem.objects.filter(
                section__page__school=self.school
            ).count(),
            "team": WebsiteTeamMember.objects.filter(school=self.school).count(),
            "gallery": GalleryImage.objects.filter(school=self.school).count(),
        }

        seed_thy_kingdom_come_website(self.school)

        self.assertEqual(
            WebsitePage.objects.filter(school=self.school).count(), first_counts["pages"]
        )
        self.assertEqual(
            WebsiteSection.objects.filter(page__school=self.school).count(),
            first_counts["sections"],
        )
        self.assertEqual(
            WebsiteContentItem.objects.filter(
                section__page__school=self.school
            ).count(),
            first_counts["items"],
        )
        self.assertEqual(
            WebsiteTeamMember.objects.filter(school=self.school).count(),
            first_counts["team"],
        )
        self.assertEqual(
            GalleryImage.objects.filter(school=self.school).count(),
            first_counts["gallery"],
        )

    def test_seed_does_not_touch_another_tenant(self):
        other_profile_before = WebsiteProfile.objects.filter(
            school=self.other_school
        ).values().first()
        other_pages_before = list(
            WebsitePage.objects.filter(school=self.other_school).values_list(
                "slug", "title", "order"
            )
        )

        seed_thy_kingdom_come_website(self.school)

        self.other_school.refresh_from_db()
        self.assertEqual(self.other_school.contact_email, "other@example.test")
        self.assertEqual(
            WebsiteProfile.objects.filter(school=self.other_school).values().first(),
            other_profile_before,
        )
        self.assertEqual(
            list(
                WebsitePage.objects.filter(school=self.other_school).values_list(
                    "slug", "title", "order"
                )
            ),
            other_pages_before,
        )

    def test_command_dry_run_makes_no_changes(self):
        output = io.StringIO()
        profile_before = WebsiteProfile.objects.filter(school=self.school).values().first()
        pages_before = list(
            WebsitePage.objects.filter(school=self.school).values_list("slug", flat=True)
        )

        call_command("seed_thy_kingdom_come_website", "--dry-run", stdout=output)

        self.assertIn("No database or media changes were made", output.getvalue())
        self.assertEqual(
            WebsiteProfile.objects.filter(school=self.school).values().first(),
            profile_before,
        )
        self.assertEqual(
            list(
                WebsitePage.objects.filter(school=self.school).values_list(
                    "slug", flat=True
                )
            ),
            pages_before,
        )

    def test_command_rejects_multiple_tenant_selectors(self):
        with self.assertRaisesMessage(CommandError, "Choose only one"):
            call_command(
                "seed_thy_kingdom_come_website",
                "--school-id",
                str(self.school.id),
                "--school-slug",
                self.school.slug,
            )

    def test_all_seeded_public_pages_render(self):
        seed_thy_kingdom_come_website(self.school)
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
