from django.db import migrations


PRODUCT_NAME = "PastMaster SMS"
PRODUCT_DOMAIN = "sms.pastmaster.top"
OLD_NAMES = ("virtuakids", "virtua kids", "virtual kids")


def _replace_legacy_text(value):
    if not value:
        return value

    updated = value
    domain_replacements = (
        ("sms.virtuakids.com.ng", PRODUCT_DOMAIN),
        ("virtuakids.com.ng", PRODUCT_DOMAIN),
    )
    for old, new in domain_replacements:
        updated = updated.replace(old, new).replace(old.upper(), new)

    for old in ("VirtuaKids", "Virtuakids", "VIRTUAKIDS", "Virtual Kids", "virtual kids"):
        updated = updated.replace(old, PRODUCT_NAME)
    return updated


def _replacement_domain(domain):
    value = (domain or "").strip().lower()
    if value in {"virtuakids.com.ng", "www.virtuakids.com.ng", "sms.virtuakids.com.ng"}:
        return PRODUCT_DOMAIN
    if value.endswith(".sms.virtuakids.com.ng"):
        return f"{value[:-len('.sms.virtuakids.com.ng')]}.{PRODUCT_DOMAIN}"
    if value.endswith(".virtuakids.com.ng"):
        return f"{value[:-len('.virtuakids.com.ng')]}.{PRODUCT_DOMAIN}"
    return value


def rebrand_core_data(apps, schema_editor):
    SchoolTenant = apps.get_model("core", "SchoolTenant")
    SchoolDomain = apps.get_model("core", "SchoolDomain")
    SchoolSettings = apps.get_model("core", "SchoolSettings")

    for mapping in SchoolDomain.objects.all().order_by("pk"):
        replacement = _replacement_domain(mapping.domain)
        if replacement == mapping.domain.lower():
            continue
        duplicate = SchoolDomain.objects.filter(domain__iexact=replacement).exclude(pk=mapping.pk).first()
        if duplicate:
            mapping.delete()
        else:
            mapping.domain = replacement
            mapping.save(update_fields=["domain"])

    for school in SchoolTenant.objects.all():
        changed = []
        if (school.name or "").strip().lower() in OLD_NAMES:
            school.name = PRODUCT_NAME
            changed.append("name")
        replacement_email = _replace_legacy_text(school.contact_email)
        if replacement_email != school.contact_email:
            school.contact_email = replacement_email
            changed.append("contact_email")
        if school.slug in {"virtuakids", "virtua-kids", "virtual-kids"}:
            if not SchoolTenant.objects.filter(slug="pastmaster-sms").exclude(pk=school.pk).exists():
                school.slug = "pastmaster-sms"
                changed.append("slug")
        if changed:
            school.save(update_fields=changed)

    text_fields = ("school_name", "back_home_url", "email_from_address", "email_host_user")
    for school_settings in SchoolSettings.objects.all():
        changed = []
        for field_name in text_fields:
            value = getattr(school_settings, field_name, "")
            if field_name == "school_name" and (value or "").strip().lower() in OLD_NAMES:
                replacement = PRODUCT_NAME
            else:
                replacement = _replace_legacy_text(value)
            if replacement != value:
                setattr(school_settings, field_name, replacement)
                changed.append(field_name)
        if changed:
            school_settings.save(update_fields=changed)


class Migration(migrations.Migration):
    dependencies = [("core", "0075_pastmaster_integration")]

    operations = [
        migrations.RunPython(rebrand_core_data, migrations.RunPython.noop),
    ]
