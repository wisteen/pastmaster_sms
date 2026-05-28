from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from core.models_features import SchoolTenant
from website.services_seed import seed_website_for_school


class Command(BaseCommand):
    help = "Create starter CMS website pages for tenant schools."

    def add_arguments(self, parser):
        parser.add_argument("--list", action="store_true", help="List tenant schools and exit.")
        parser.add_argument("--all", action="store_true", help="Seed all active tenant schools.")
        parser.add_argument("--school-id", type=int, help="Seed one tenant school by ID.")
        parser.add_argument("--school-slug", help="Seed one tenant school by slug.")
        parser.add_argument("--school-name", help="Seed one tenant school by exact or partial name.")
        parser.add_argument("--overwrite", action="store_true", help="Overwrite existing starter CMS content.")
        parser.add_argument(
            "--jewels-about",
            action="store_true",
            help="Use the Jewels of Calvary About page wording supplied by the client.",
        )

    def handle(self, *args, **options):
        if options["list"]:
            schools = SchoolTenant.objects.order_by("name")
            if not schools.exists():
                self.stdout.write(self.style.WARNING("No tenant schools found."))
                return
            for school in schools:
                status = "active" if school.is_active else "inactive"
                self.stdout.write(f"{school.id}: {school.name} ({school.slug}) - {status}")
            return

        schools = self._selected_schools(options)
        if not schools:
            raise CommandError("No tenant school matched. Use --list to see available tenants.")

        for school in schools:
            result = seed_website_for_school(
                school,
                overwrite=options["overwrite"],
                jewels_about=options["jewels_about"],
            )
            page_slugs = ", ".join(page.slug for page in result["pages"])
            self.stdout.write(
                self.style.SUCCESS(f"Seeded website pages for {school.name} ({school.slug}): {page_slugs}")
            )

    def _selected_schools(self, options):
        if options["all"]:
            return list(SchoolTenant.objects.filter(is_active=True).order_by("name"))

        if options["school_id"]:
            return list(SchoolTenant.objects.filter(id=options["school_id"]))

        if options["school_slug"]:
            return list(SchoolTenant.objects.filter(slug=options["school_slug"]))

        if options["school_name"]:
            name = options["school_name"]
            exact = SchoolTenant.objects.filter(name__iexact=name)
            if exact.count() == 1:
                return list(exact)

            matches = SchoolTenant.objects.filter(Q(name__icontains=name) | Q(slug__icontains=name)).order_by("name")
            if matches.count() > 1:
                matched = ", ".join(f"{school.name} ({school.slug})" for school in matches)
                raise CommandError(f"Multiple tenant schools matched: {matched}. Use --school-slug or --school-id.")
            return list(matches)

        raise CommandError("Choose --all, --school-id, --school-slug, --school-name, or --list.")
