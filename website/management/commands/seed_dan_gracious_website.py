from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from core.models_features import SchoolTenant
from website.dan_gracious_seed import (
    DEFAULT_SCHOOL_SLUG,
    seed_dan_gracious_website,
)


class Command(BaseCommand):
    help = (
        "Replace the Dan-Gracious tenant's six public CMS pages with the curated "
        "content and images supplied for that school."
    )

    def add_arguments(self, parser):
        parser.add_argument("--school-id", type=int, help="Target tenant school ID.")
        parser.add_argument(
            "--school-slug",
            help=f"Target tenant slug. Defaults to {DEFAULT_SCHOOL_SLUG!r}.",
        )
        parser.add_argument("--school-name", help="Exact or partial tenant school name.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show the selected tenant and planned changes without writing to the database or media storage.",
        )
        parser.add_argument(
            "--skip-images",
            action="store_true",
            help="Update CMS text and records without copying the bundled images into MEDIA_ROOT.",
        )

    def handle(self, *args, **options):
        school = self._selected_school(options)
        self.stdout.write(f"Selected tenant: {school.name} ({school.slug}, ID {school.id})")
        self.stdout.write(
            "Scope: public profile and branding, Home, About, Academics, Admissions, "
            "Gallery, School Fees, leadership, gallery images and public FAQs."
        )
        self.stdout.write(
            "The command does not read the legacy HTML at runtime and does not touch students, "
            "results, users, inquiries, subscribers or financial ledger records."
        )

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run complete. No database or media changes were made."))
            return

        try:
            result = seed_dan_gracious_website(
                school,
                skip_images=options["skip_images"],
            )
        except FileNotFoundError as exc:
            raise CommandError(str(exc)) from exc

        page_slugs = ", ".join(page.slug for page in result["pages"])
        image_note = "images skipped" if options["skip_images"] else "bundled images installed"
        self.stdout.write(
            self.style.SUCCESS(
                f"Dan-Gracious website updated: {page_slugs}; "
                f"{len(result['team'])} leadership profiles; "
                f"{len(result['gallery'])} curated gallery entries; {image_note}."
            )
        )

    def _selected_school(self, options):
        selectors = [
            bool(options.get("school_id")),
            bool(options.get("school_slug")),
            bool(options.get("school_name")),
        ]
        if sum(selectors) > 1:
            raise CommandError("Choose only one of --school-id, --school-slug or --school-name.")

        if options.get("school_id"):
            school = SchoolTenant.objects.filter(id=options["school_id"]).first()
        elif options.get("school_name"):
            name = options["school_name"].strip()
            exact = SchoolTenant.objects.filter(name__iexact=name)
            if exact.count() == 1:
                school = exact.first()
            else:
                matches = SchoolTenant.objects.filter(
                    Q(name__icontains=name) | Q(slug__icontains=name)
                ).order_by("name")
                if matches.count() > 1:
                    choices = ", ".join(f"{item.name} ({item.slug})" for item in matches)
                    raise CommandError(f"Multiple schools matched: {choices}")
                school = matches.first()
        else:
            slug = options.get("school_slug") or DEFAULT_SCHOOL_SLUG
            school = SchoolTenant.objects.filter(slug=slug).first()

        if school is None:
            raise CommandError(
                "No tenant school matched. Run `python manage.py seed_tenant_website --list` "
                "and pass the correct --school-slug or --school-id."
            )
        return school
