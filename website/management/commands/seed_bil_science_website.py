from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from core.models_features import SchoolTenant
from website.bil_science_seed import DEFAULT_SCHOOL_SLUG, seed_bil_science_website


class Command(BaseCommand):
    help = (
        "Replace the Bil Science Academy tenant's seven public CMS pages with "
        "the curated school content and bundled images."
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
            help="Show the selected tenant and scope without changing the database or media storage.",
        )
        parser.add_argument(
            "--skip-images",
            action="store_true",
            help="Update CMS content without installing the bundled image and PDF assets.",
        )

    def handle(self, *args, **options):
        school = self._selected_school(options)
        self.stdout.write(f"Selected tenant: {school.name} ({school.slug}, ID {school.id})")
        self.stdout.write(
            "Scope: public identity, Home, About, Academics, Clubs, Gallery, "
            "Admissions, School Fees, proprietor message, and gallery images."
        )
        self.stdout.write(
            "The command does not modify students, users, results, attendance, "
            "inquiries, subscriptions, or financial ledger records."
        )

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run complete. No database or media changes were made."))
            return

        try:
            result = seed_bil_science_website(
                school,
                skip_images=options["skip_images"],
            )
        except FileNotFoundError as exc:
            raise CommandError(str(exc)) from exc

        page_slugs = ", ".join(page.slug for page in result["pages"])
        asset_note = "assets skipped" if options["skip_images"] else "bundled assets installed"
        self.stdout.write(
            self.style.SUCCESS(
                f"Bil Science Academy website updated: {page_slugs}; "
                f"{len(result['gallery'])} curated gallery entries; {asset_note}."
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
                "No tenant school matched. Use --school-slug, --school-name, or --school-id."
            )
        return school
