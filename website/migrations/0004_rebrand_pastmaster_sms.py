from django.db import migrations


PRODUCT_NAME = "PastMaster SMS"
PRODUCT_DOMAIN = "sms.pastmaster.top"
OLD_NAMES = ("virtuakids", "virtua kids", "virtual kids")


def _replace_legacy_text(value):
    if not value:
        return value
    updated = value.replace("sms.virtuakids.com.ng", PRODUCT_DOMAIN)
    updated = updated.replace("virtuakids.com.ng", PRODUCT_DOMAIN)
    for old in ("VirtuaKids", "Virtuakids", "VIRTUAKIDS", "Virtual Kids", "virtual kids"):
        updated = updated.replace(old, PRODUCT_NAME)
    return updated


def rebrand_website_data(apps, schema_editor):
    WebsiteProfile = apps.get_model("website", "WebsiteProfile")
    Site = apps.get_model("sites", "Site")

    text_fields = (
        "site_name",
        "description",
        "email",
        "facebook_url",
        "instagram_url",
        "twitter_url",
        "youtube_url",
        "footer_note",
    )
    for profile in WebsiteProfile.objects.all():
        changed = []
        for field_name in text_fields:
            value = getattr(profile, field_name, "")
            if field_name == "site_name" and (value or "").strip().lower() in OLD_NAMES:
                replacement = PRODUCT_NAME
            else:
                replacement = _replace_legacy_text(value)
            if replacement != value:
                setattr(profile, field_name, replacement)
                changed.append(field_name)
        if changed:
            profile.save(update_fields=changed)

    conflicting_site = Site.objects.filter(domain=PRODUCT_DOMAIN).exclude(pk=1).first()
    if conflicting_site:
        conflicting_site.delete()
    Site.objects.update_or_create(
        pk=1,
        defaults={"domain": PRODUCT_DOMAIN, "name": PRODUCT_NAME},
    )


class Migration(migrations.Migration):
    dependencies = [
        ("sites", "0002_alter_domain_unique"),
        ("website", "0003_websitesection_hero_variant"),
    ]

    operations = [
        migrations.RunPython(rebrand_website_data, migrations.RunPython.noop),
    ]
