from __future__ import annotations

import argparse
import os
import shutil
import sys
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "db.sqlite3"
sys.path.insert(0, str(ROOT))


def backup_database() -> Path:
    from django.utils import timezone

    backup = DB.with_suffix(
        f".pre_demo_school_{timezone.now().strftime('%Y%m%d_%H%M%S')}.bak"
    )
    shutil.copy2(DB, backup)
    return backup


def clean_domain(value: str) -> str:
    parsed = urlparse(value)
    host = parsed.netloc or parsed.path
    return host.split("/")[0].split(":")[0].lower()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a demo tenant school and super-admin login.")
    parser.add_argument("--school-name", default="Demo School")
    parser.add_argument("--slug", default="demo-school")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--domain", action="append", default=[])
    parser.add_argument("--skip-backup", action="store_true")
    args = parser.parse_args()

    os.environ["LOCAL_DB_PASSWORD"] = ""
    os.environ.setdefault("DATABASE_PROFILE", "local")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "school_management.settings")

    import django

    django.setup()

    from django.db import transaction
    from django.utils import timezone

    from core.models import SchoolSettings, User
    from core.models_features import SchoolDomain, SchoolMembership, SchoolTenant
    from core.models_license import SystemLicense
    from website.services_seed import seed_website_for_school

    backup = None if args.skip_backup else backup_database()

    with transaction.atomic():
        school, _ = SchoolTenant.objects.update_or_create(
            slug=args.slug,
            defaults={
                "name": args.school_name,
                "plan": "premium",
                "is_active": True,
                "contact_name": "Demo Administrator",
                "contact_email": "",
                "contact_phone": "",
            },
        )

        for domain in args.domain:
            normalized = clean_domain(domain)
            if normalized:
                SchoolDomain.objects.update_or_create(
                    domain=normalized,
                    defaults={"school": school, "is_primary": True},
                )

        SchoolSettings.all_objects.update_or_create(
            school=school,
            defaults={
                "school_name": args.school_name,
                "school_address": "Demo school address",
                "school_logo": "",
                "school_seal": "",
                "principal_signature": "",
                "primary_color": "#2563eb",
                "secondary_color": "#1d4ed8",
                "accent_color": "#f97316",
                "principal_name": "Demo Principal",
                "proprietor_name": "Demo Proprietor",
                "school_motto": "Learning for today and tomorrow",
                "student_id_prefix": "DSTU",
                "student_id_digits": 4,
                "teacher_id_prefix": "DTCH",
                "teacher_id_digits": 4,
                "back_home_url": "",
                "email_from_address": "",
                "email_host": "",
                "email_port": 587,
                "email_host_user": "",
                "email_host_password": "",
                "email_use_tls": True,
                "termii_api_key": "",
                "termii_base_url": "https://api.ng.termii.com",
                "termii_sender_id": "",
                "termii_channel": "dnd",
                "promotion_min_average": 50,
                "promotion_max_failed_subjects": 2,
                "promotion_min_attendance": 75,
            },
        )

        user, _ = User.objects.get_or_create(
            username=args.username,
            defaults={
                "first_name": "Demo",
                "last_name": "Administrator",
                "email": "",
                "phone": "",
            },
        )
        user.set_password(args.password)
        user.is_superuser = True
        user.is_staff = True
        user.is_active = True
        user.role = "super_admin"
        user.extra_roles = []
        user.save()

        SchoolMembership.objects.filter(user=user).update(
            primary_role="super_admin",
            is_active=True,
            portal_access_enabled=True,
            result_access_enabled=True,
        )
        membership, _ = SchoolMembership.objects.update_or_create(
            school=school,
            user=user,
            defaults={
                "primary_role": "super_admin",
                "extra_roles": [],
                "is_active": True,
                "portal_access_enabled": True,
                "result_access_enabled": True,
            },
        )

        today = timezone.now().date()
        SystemLicense.all_objects.update_or_create(
            school=school,
            defaults={
                "school_name": args.school_name,
                "license_key": f"{args.slug.upper()}-DEMO",
                "activation_date": today,
                "expiry_date": today + timedelta(days=365),
                "is_active": True,
                "grace_period_days": 7,
                "contact_email": "",
                "contact_phone": "",
                "admin_message": "",
            },
        )

        seed_website_for_school(school, overwrite=False)

    print(f"backup={backup or ''}")
    print(f"school_id={school.id}")
    print(f"school_slug={school.slug}")
    print(f"username={user.username}")
    print(f"user_id={user.id}")
    print(f"membership_id={membership.id}")


if __name__ == "__main__":
    main()
