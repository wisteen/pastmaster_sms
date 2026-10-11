from __future__ import annotations

import os
import shutil
import sys
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
SOURCE_DIR = WORKSPACE / "bil science academy"
MEDIA_ROOT = ROOT / "media"
DB = ROOT / "db.sqlite3"
SLUG = "bil-science-academy"
TENANT_MEDIA_PREFIX = f"tenant_imports/{SLUG}"

sys.path.insert(0, str(ROOT))


SCHOOL = {
    "name": "Bil Science Academy",
    "domain": "bilscienceacademy.com",
    "address": (
        "BIL HUB: 1, Prince Kosoko Crescent, Suberu-Oje, Oke-Abiye, "
        "Amikanle Axis, Alagbado Lagos."
    ),
    "phone_display": "0814 124 8867",
    "phone_link": "2348141248867",
    "email": "bilsciencea@gmail.com",
    "tagline": "Knowledge, Character and Excellence",
    "vision": "Aspiring to create global competitive leaders/citizens and building future intellectuals.",
    "mission": (
        "Setting up an academic structure and curriculum to bring out the inherent intellectual prowess "
        "in every student through intensive academic commitments, innovations/creativity, a multi-cultural "
        "environment, and productive life-long learners."
    ),
    "core_values": ["Consistency", "Resiliency", "Academic Excellence"],
    "clubs": [
        "Taekwondo Kids Club",
        "Young Motivators Club",
        "Jet Club",
        "Speech & Oratory Club",
    ],
}


ASSETS = {
    "computer_lab": "WhatsApp Image 2026-07-31 at 8.25.55 AM.jpeg",
    "building_front": "WhatsApp Image 2026-07-31 at 8.25.56 AM.jpeg",
    "students_group": "WhatsApp Image 2026-07-31 at 8.25.56 AM (1).jpeg",
    "building_exterior": "WhatsApp Image 2026-07-31 at 8.25.56 AM (2).jpeg",
    "building_signage": "WhatsApp Image 2026-07-31 at 8.25.56 AM (3).jpeg",
    "science_lab": "WhatsApp Image 2026-07-31 at 8.25.57 AM.jpeg",
    "logo": "WhatsApp Image 2026-07-31 at 8.25.57 AM (1).jpeg",
    "proprietor": "WhatsApp Image 2026-07-31 at 8.25.57 AM (2).jpeg",
}


FEES = [
    ("Acceptance Fee", 10000),
    ("Uniforms", 20000),
    ("Sport Wear", 15000),
    ("Hat (Girls)", 10000),
    ("Tuition Fee", 60000),
    ("Medical", 5000),
    ("Coding and Graphics (Per Term)", 20000),
]
BOYS_TOTAL = 130000
GIRLS_TOTAL = 140000


def clean_domain(value: str) -> str:
    parsed = urlparse(value)
    host = parsed.netloc or parsed.path
    return host.split("/")[0].split(":")[0].lower()


def backup_database() -> Path:
    from django.utils import timezone

    backup = DB.with_suffix(
        f".pre_bil_science_{timezone.now().strftime('%Y%m%d_%H%M%S')}.bak"
    )
    shutil.copy2(DB, backup)
    return backup


def copy_asset(filename: str, destination_name: str) -> str:
    source = SOURCE_DIR / filename
    if not source.exists():
        raise FileNotFoundError(f"Missing BIL asset: {source}")
    destination = MEDIA_ROOT / TENANT_MEDIA_PREFIX / "website" / destination_name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return f"{TENANT_MEDIA_PREFIX}/website/{destination_name}"


def make_pdf(path: Path) -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=42, leftMargin=42, topMargin=42, bottomMargin=42)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Bil Science Academy", styles["Title"]),
        Paragraph("Fee Structure and Payment Information", styles["Heading2"]),
        Paragraph(SCHOOL["address"], styles["Normal"]),
        Spacer(1, 0.2 * inch),
    ]

    data = [["Item", "Amount (NGN)"]]
    data.extend([[name, f"{amount:,.2f}"] for name, amount in FEES])
    data.extend([["Total for Boys", f"{BOYS_TOTAL:,.2f}"], ["Total for Girls", f"{GIRLS_TOTAL:,.2f}"]])
    table = Table(data, colWidths=[3.8 * inch, 1.8 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#047857")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
                ("BACKGROUND", (0, -2), (-1, -1), colors.HexColor("#ecfdf5")),
                ("FONTNAME", (0, -2), (-1, -1), "Helvetica-Bold"),
                ("ALIGN", (1, 1), (1, -1), "RIGHT"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.extend([table, Spacer(1, 0.25 * inch)])

    requirements = [
        "Complete school approved textbook",
        "Exercise books with school logo",
        "A pair of black shoes",
        "Black belt",
        "Canvas with white socks for sport",
        "Black belt for boys",
    ]
    story.append(Paragraph("Compulsory School Requirements", styles["Heading2"]))
    for item in requirements:
        story.append(Paragraph(f"- {item}", styles["Normal"]))
    story.extend(
        [
            Spacer(1, 0.2 * inch),
            Paragraph("Payment Information", styles["Heading2"]),
            Paragraph("Bank: Zenith Bank Plc.", styles["Normal"]),
            Paragraph("Account Name: Bil Hub Oceanic Ltd", styles["Normal"]),
            Paragraph("Account Number: 1310 3410 94", styles["Normal"]),
        ]
    )
    doc.build(story)


def set_attrs(instance, attrs):
    changed = False
    for key, value in attrs.items():
        if getattr(instance, key) != value:
            setattr(instance, key, value)
            changed = True
    if changed:
        instance.save()
    return instance


def page(model, school, slug, defaults):
    obj, _ = model.objects.get_or_create(school=school, slug=slug, defaults=defaults)
    return set_attrs(obj, defaults)


def section(model, page_obj, order, section_type, defaults):
    obj, _ = model.objects.get_or_create(
        page=page_obj,
        order=order,
        defaults={"section_type": section_type, **defaults},
    )
    return set_attrs(obj, {"section_type": section_type, **defaults})


def replace_items(WebsiteContentItem, section_obj, items):
    section_obj.items.all().delete()
    WebsiteContentItem.objects.bulk_create(
        WebsiteContentItem(section=section_obj, order=index, **item)
        for index, item in enumerate(items)
    )


def html_intro(logo_path: str) -> str:
    values = "".join(f"<li>{value}</li>" for value in SCHOOL["core_values"])
    return f"""
<div class="row align-items-center g-5">
  <div class="col-lg-4 text-center">
    <img src="/media/{logo_path}" alt="Bil Science Academy logo" class="img-fluid" style="max-width:260px;max-height:220px;object-fit:contain;">
  </div>
  <div class="col-lg-8">
    <h2>Bil Science Academy</h2>
    <p>{SCHOOL["tagline"]}.</p>
    <p>{SCHOOL["mission"]}</p>
    <p><strong>Core values:</strong></p>
    <ul>{values}</ul>
  </div>
</div>
"""


def fee_html(pdf_path: str) -> str:
    rows = "".join(
        f"<tr><td>{name}</td><td style=\"text-align:right;\">NGN {amount:,.2f}</td></tr>"
        for name, amount in FEES
    )
    requirements = "".join(
        f"<li>{item}</li>"
        for item in [
            "Complete school approved textbook",
            "Exercise books with school logo",
            "A pair of black shoes",
            "Black belt",
            "Canvas with white socks for sport",
            "Black belt for boys",
        ]
    )
    return f"""
<div class="row g-4">
  <div class="col-lg-7">
    <div class="table-responsive">
      <table class="table table-bordered align-middle">
        <thead><tr><th>Item</th><th class="text-end">Amount</th></tr></thead>
        <tbody>{rows}
          <tr><th>Total for Boys</th><th class="text-end">NGN {BOYS_TOTAL:,.2f}</th></tr>
          <tr><th>Total for Girls</th><th class="text-end">NGN {GIRLS_TOTAL:,.2f}</th></tr>
        </tbody>
      </table>
    </div>
    <a class="tenant-btn mt-2" href="/media/{pdf_path}" target="_blank" rel="noopener">Download Fee Structure PDF</a>
  </div>
  <div class="col-lg-5">
    <h3>Compulsory School Requirements</h3>
    <ul>{requirements}</ul>
    <h3 class="mt-4">Payment Information</h3>
    <p><strong>Bank:</strong> Zenith Bank Plc.<br>
    <strong>Account Name:</strong> Bil Hub Oceanic Ltd<br>
    <strong>Account Number:</strong> 1310 3410 94</p>
  </div>
</div>
"""


def main() -> None:
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
    from website.models import (
        DownloadableForm,
        GalleryImage,
        WebsiteContentItem,
        WebsitePage,
        WebsiteProfile,
        WebsiteSection,
        WebsiteTeamMember,
    )
    from website.services_seed import seed_website_for_school

    backup = backup_database()
    copied = {
        "logo": copy_asset(ASSETS["logo"], "branding/logo.jpeg"),
        "building_front": copy_asset(ASSETS["building_front"], "gallery/building-front.jpeg"),
        "building_exterior": copy_asset(ASSETS["building_exterior"], "gallery/building-exterior.jpeg"),
        "building_signage": copy_asset(ASSETS["building_signage"], "gallery/building-signage.jpeg"),
        "students_group": copy_asset(ASSETS["students_group"], "gallery/students-science-group.jpeg"),
        "science_lab": copy_asset(ASSETS["science_lab"], "gallery/science-lab.jpeg"),
        "computer_lab": copy_asset(ASSETS["computer_lab"], "gallery/computer-lab.jpeg"),
        "proprietor": copy_asset(ASSETS["proprietor"], "team/proprietor.jpeg"),
    }
    pdf_rel_path = f"{TENANT_MEDIA_PREFIX}/forms/bil-science-academy-fee-structure.pdf"
    make_pdf(MEDIA_ROOT / pdf_rel_path)

    with transaction.atomic():
        school, _ = SchoolTenant.objects.update_or_create(
            slug=SLUG,
            defaults={
                "name": SCHOOL["name"],
                "plan": "premium",
                "is_active": True,
                "contact_name": "Bil Science Academy Administrator",
                "contact_email": SCHOOL["email"],
                "contact_phone": SCHOOL["phone_link"],
            },
        )
        SchoolDomain.objects.update_or_create(
            domain=clean_domain(SCHOOL["domain"]),
            defaults={"school": school, "is_primary": True},
        )

        SchoolSettings.all_objects.update_or_create(
            school=school,
            defaults={
                "school_name": SCHOOL["name"],
                "school_address": SCHOOL["address"],
                "school_logo": copied["logo"],
                "school_seal": copied["logo"],
                "principal_signature": "",
                "primary_color": "#047857",
                "secondary_color": "#0f766e",
                "accent_color": "#f59e0b",
                "back_home_url": f"https://{SCHOOL['domain']}",
                "email_from_address": SCHOOL["email"],
                "email_host": "",
                "email_port": 587,
                "email_host_user": "",
                "email_host_password": "",
                "email_use_tls": True,
                "termii_api_key": "",
                "termii_base_url": "https://api.ng.termii.com",
                "termii_sender_id": "",
                "termii_channel": "dnd",
                "principal_name": "School Administrator",
                "proprietor_name": "Proprietor",
                "school_motto": SCHOOL["tagline"],
                "student_id_prefix": "BIL",
                "student_id_digits": 4,
                "teacher_id_prefix": "BILT",
                "teacher_id_digits": 4,
                "promotion_min_average": 50,
                "promotion_max_failed_subjects": 2,
                "promotion_min_attendance": 75,
            },
        )

        today = timezone.now().date()
        SystemLicense.all_objects.update_or_create(
            school=school,
            defaults={
                "school_name": SCHOOL["name"],
                "license_key": "BIL-SCIENCE-ACADEMY",
                "activation_date": today,
                "expiry_date": today + timedelta(days=365),
                "is_active": True,
                "grace_period_days": 7,
                "contact_email": SCHOOL["email"],
                "contact_phone": SCHOOL["phone_display"],
                "admin_message": "",
            },
        )

        profile, _ = WebsiteProfile.objects.get_or_create(school=school)
        set_attrs(
            profile,
            {
                "site_name": SCHOOL["name"],
                "tagline": SCHOOL["tagline"],
                "description": (
                    "Bil Science Academy is a co-educational school in Alagbado, Lagos, "
                    "building future intellectuals through academic commitment, creativity, "
                    "innovation, and character."
                ),
                "logo": copied["logo"],
                "favicon": copied["logo"],
                "default_og_image": copied["building_front"],
                "phone": SCHOOL["phone_display"],
                "phone_alt": "",
                "whatsapp_number": SCHOOL["phone_link"],
                "email": SCHOOL["email"],
                "address": SCHOOL["address"],
                "office_hours": "",
                "facebook_url": "",
                "instagram_url": "",
                "twitter_url": "",
                "youtube_url": "",
                "footer_note": "All rights reserved.",
            },
        )

        seed_website_for_school(school, overwrite=False)

        home = page(
            WebsitePage,
            school,
            "home",
            {
                "title": "Home",
                "nav_label": "Home",
                "template_type": "standard",
                "is_homepage": True,
                "is_published": True,
                "show_in_nav": True,
                "order": 0,
                "header_title": SCHOOL["name"],
                "header_subtitle": SCHOOL["tagline"],
                "header_image": copied["building_front"],
                "meta_title": f"{SCHOOL['name']} | Official Website",
                "meta_description": SCHOOL["tagline"],
                "meta_keywords": "Bil Science Academy, science school, Alagbado school, Lagos school",
                "og_title": SCHOOL["name"],
                "og_description": SCHOOL["tagline"],
                "og_image": copied["building_front"],
                "canonical_url": f"https://{SCHOOL['domain']}/",
            },
        )
        home_hero = section(
            WebsiteSection,
            home,
            0,
            "hero",
            {
                "hero_variant": "carousel",
                "title": SCHOOL["name"],
                "subtitle": SCHOOL["tagline"],
                "body": "",
                "background_image": copied["building_front"],
                "button_label": "Admissions",
                "button_url": "/admissions/",
                "background_color": "",
                "extra": {},
                "is_visible": True,
            },
        )
        replace_items(
            WebsiteContentItem,
            home_hero,
            [
                {
                    "title": SCHOOL["name"],
                    "subtitle": SCHOOL["tagline"],
                    "body": "<p>Building future intellectuals through a science-focused learning environment.</p>",
                    "image": copied["building_front"],
                    "button_label": "Admissions",
                    "button_url": "/admissions/",
                    "is_visible": True,
                },
                {
                    "title": "Science-Based Learning",
                    "subtitle": "Laboratory, coding, creativity, and academic excellence",
                    "body": "<p>Students learn through structured academics, practical science exposure, and innovation.</p>",
                    "image": copied["science_lab"],
                    "button_label": "Academics",
                    "button_url": "/academics/",
                    "is_visible": True,
                },
                {
                    "title": "Clubs That Build Confidence",
                    "subtitle": "Taekwondo, JET, Young Motivators, Speech and Oratory",
                    "body": "<p>Our clubs help learners develop discipline, leadership, communication, and discovery.</p>",
                    "image": copied["students_group"],
                    "button_label": "Explore Clubs",
                    "button_url": "/clubs/",
                    "is_visible": True,
                },
            ],
        )
        section(
            WebsiteSection,
            home,
            10,
            "rich_text",
            {
                "title": "A Science-Focused School for Future Intellectuals",
                "subtitle": "",
                "body": html_intro(copied["logo"]),
                "image": copied["building_exterior"],
                "background_image": "",
                "button_label": "Learn More",
                "button_url": "/about/",
                "background_color": "#ffffff",
                "extra": {},
                "is_visible": True,
            },
        )
        values_section = section(
            WebsiteSection,
            home,
            20,
            "cards",
            {
                "title": "Vision, Mission, and Values",
                "subtitle": "The foundation behind the Bil Science Academy learning culture.",
                "body": "",
                "image": "",
                "background_image": "",
                "button_label": "",
                "button_url": "",
                "background_color": "#f8fafc",
                "extra": {},
                "is_visible": True,
            },
        )
        replace_items(
            WebsiteContentItem,
            values_section,
            [
                {"title": "Vision", "subtitle": SCHOOL["vision"], "icon_class": "fas fa-eye", "is_visible": True},
                {"title": "Mission", "subtitle": SCHOOL["mission"], "icon_class": "fas fa-bullseye", "is_visible": True},
                {"title": "Core Values", "subtitle": ", ".join(SCHOOL["core_values"]), "icon_class": "fas fa-award", "is_visible": True},
            ],
        )
        clubs_preview = section(
            WebsiteSection,
            home,
            30,
            "cards",
            {
                "title": "Clubs and Activities",
                "subtitle": "Structured activities for discipline, expression, motivation, and discovery.",
                "body": "",
                "image": "",
                "background_image": "",
                "button_label": "",
                "button_url": "",
                "background_color": "#ffffff",
                "extra": {"item_column_class": "col-md-6 col-lg-3"},
                "is_visible": True,
            },
        )
        replace_items(
            WebsiteContentItem,
            clubs_preview,
            [
                {"title": SCHOOL["clubs"][0], "subtitle": "Discipline, fitness, and confidence.", "icon_class": "fas fa-person-running", "is_visible": True},
                {"title": SCHOOL["clubs"][1], "subtitle": "Leadership, motivation, and positive influence.", "icon_class": "fas fa-users", "is_visible": True},
                {"title": SCHOOL["clubs"][2], "subtitle": "Science, technology, and discovery.", "icon_class": "fas fa-rocket", "is_visible": True},
                {"title": SCHOOL["clubs"][3], "subtitle": "Speech, confidence, and public communication.", "icon_class": "fas fa-microphone", "is_visible": True},
            ],
        )
        section(
            WebsiteSection,
            home,
            40,
            "gallery",
            {
                "title": "School Life",
                "subtitle": "Facilities, practical learning, and student activities at Bil Science Academy.",
                "body": "",
                "image": "",
                "background_image": "",
                "button_label": "View Gallery",
                "button_url": "/gallery/",
                "background_color": "#f8fafc",
                "extra": {"featured_only": True, "limit": 6},
                "is_visible": True,
            },
        )

        about = page(
            WebsitePage,
            school,
            "about",
            {
                "title": "About Us",
                "nav_label": "About",
                "template_type": "standard",
                "is_homepage": False,
                "is_published": True,
                "show_in_nav": True,
                "order": 10,
                "header_title": "About Bil Science Academy",
                "header_subtitle": SCHOOL["tagline"],
                "header_image": copied["building_exterior"],
                "meta_title": f"About {SCHOOL['name']}",
                "meta_description": SCHOOL["vision"],
                "meta_keywords": "",
                "og_title": "",
                "og_description": "",
                "og_image": copied["building_exterior"],
                "canonical_url": f"https://{SCHOOL['domain']}/about/",
            },
        )
        section(
            WebsiteSection,
            about,
            0,
            "hero",
            {
                "hero_variant": "morphism",
                "title": "About Bil Science Academy",
                "subtitle": SCHOOL["tagline"],
                "body": "",
                "image": "",
                "background_image": copied["building_exterior"],
                "button_label": "",
                "button_url": "",
                "background_color": "",
                "extra": {},
                "is_visible": True,
            },
        )
        section(
            WebsiteSection,
            about,
            10,
            "rich_text",
            {
                "title": "Who We Are",
                "subtitle": "",
                "body": (
                    f"<p>{SCHOOL['vision']}</p>"
                    f"<p>{SCHOOL['mission']}</p>"
                    f"<p><strong>Core values:</strong> {', '.join(SCHOOL['core_values'])}.</p>"
                ),
                "image": copied["students_group"],
                "background_image": "",
                "button_label": "",
                "button_url": "",
                "background_color": "#ffffff",
                "extra": {},
                "is_visible": True,
            },
        )
        section(
            WebsiteSection,
            about,
            20,
            "team",
            {
                "title": "From the Proprietor's Desk",
                "subtitle": "Portrait and full statement will be updated with the final supplied copy.",
                "body": "",
                "image": "",
                "background_image": "",
                "button_label": "",
                "button_url": "",
                "background_color": "#f8fafc",
                "extra": {},
                "is_visible": True,
            },
        )
        WebsiteTeamMember.objects.filter(school=school).delete()
        WebsiteTeamMember.objects.create(
            school=school,
            name="Proprietor",
            role="Proprietor, Bil Science Academy",
            photo=copied["proprietor"],
            bio="",
            email="",
            phone="",
            order=0,
            is_visible=True,
        )

        academics = page(
            WebsitePage,
            school,
            "academics",
            {
                "title": "Academics",
                "nav_label": "Academics",
                "template_type": "standard",
                "is_homepage": False,
                "is_published": True,
                "show_in_nav": True,
                "order": 20,
                "header_title": "Academics",
                "header_subtitle": "Science-based learning with academic structure and creativity.",
                "header_image": copied["science_lab"],
                "meta_title": f"Academics | {SCHOOL['name']}",
                "meta_description": SCHOOL["mission"],
                "meta_keywords": "",
                "og_title": "",
                "og_description": "",
                "og_image": copied["science_lab"],
                "canonical_url": f"https://{SCHOOL['domain']}/academics/",
            },
        )
        academics_cards = section(
            WebsiteSection,
            academics,
            10,
            "cards",
            {
                "title": "Academic Focus",
                "subtitle": "A curriculum built around intellectual growth and practical learning.",
                "body": "",
                "image": "",
                "background_image": "",
                "button_label": "",
                "button_url": "",
                "background_color": "#f8fafc",
                "extra": {},
                "is_visible": True,
            },
        )
        replace_items(
            WebsiteContentItem,
            academics_cards,
            [
                {"title": "Intensive Academic Commitment", "subtitle": "Consistent learning habits and focused academic structure.", "icon_class": "fas fa-book-open", "is_visible": True},
                {"title": "Innovation and Creativity", "subtitle": "Practical exposure through science, coding, and creative work.", "icon_class": "fas fa-lightbulb", "is_visible": True},
                {"title": "Multi-Cultural Environment", "subtitle": "A learning community that prepares students for a wider world.", "icon_class": "fas fa-globe-africa", "is_visible": True},
                {"title": "Life-Long Learners", "subtitle": "Developing students who keep learning, leading, and solving problems.", "icon_class": "fas fa-seedling", "is_visible": True},
            ],
        )

        clubs = page(
            WebsitePage,
            school,
            "clubs",
            {
                "title": "Clubs",
                "nav_label": "Clubs",
                "template_type": "standard",
                "is_homepage": False,
                "is_published": True,
                "show_in_nav": True,
                "order": 30,
                "header_title": "Clubs",
                "header_subtitle": "Student activities for discipline, confidence, and discovery.",
                "header_image": copied["students_group"],
                "meta_title": f"Clubs | {SCHOOL['name']}",
                "meta_description": "Bil Science Academy clubs and student activities.",
                "meta_keywords": "",
                "og_title": "",
                "og_description": "",
                "og_image": copied["students_group"],
                "canonical_url": f"https://{SCHOOL['domain']}/clubs/",
            },
        )
        clubs_cards = section(
            WebsiteSection,
            clubs,
            10,
            "cards",
            {
                "title": "Student Clubs",
                "subtitle": "Learners grow beyond the classroom through structured co-curricular activities.",
                "body": "",
                "image": "",
                "background_image": "",
                "button_label": "",
                "button_url": "",
                "background_color": "#f8fafc",
                "extra": {},
                "is_visible": True,
            },
        )
        replace_items(
            WebsiteContentItem,
            clubs_cards,
            [
                {"title": "Taekwondo Kids Club", "subtitle": "Discipline, resilience, movement, and confidence.", "icon_class": "fas fa-person-running", "is_visible": True},
                {"title": "Young Motivators Club", "subtitle": "Leadership, positive influence, and personal development.", "icon_class": "fas fa-users", "is_visible": True},
                {"title": "Jet Club", "subtitle": "Science curiosity, technology, and practical discovery.", "icon_class": "fas fa-rocket", "is_visible": True},
                {"title": "Speech & Oratory Club", "subtitle": "Public speaking, expression, and confidence.", "icon_class": "fas fa-microphone", "is_visible": True},
            ],
        )

        gallery = page(
            WebsitePage,
            school,
            "gallery",
            {
                "title": "Gallery",
                "nav_label": "Gallery",
                "template_type": "gallery",
                "is_homepage": False,
                "is_published": True,
                "show_in_nav": True,
                "order": 40,
                "header_title": "Gallery",
                "header_subtitle": "School building, facilities, students, and activities.",
                "header_image": copied["building_front"],
                "meta_title": f"Gallery | {SCHOOL['name']}",
                "meta_description": "Photos from Bil Science Academy.",
                "meta_keywords": "",
                "og_title": "",
                "og_description": "",
                "og_image": copied["building_front"],
                "canonical_url": f"https://{SCHOOL['domain']}/gallery/",
            },
        )
        section(
            WebsiteSection,
            gallery,
            10,
            "gallery",
            {
                "title": "Our Gallery",
                "subtitle": "A look at the Bil Science Academy environment and learning activities.",
                "body": "",
                "image": "",
                "background_image": "",
                "button_label": "",
                "button_url": "",
                "background_color": "#f8fafc",
                "extra": {},
                "is_visible": True,
            },
        )
        GalleryImage.objects.filter(school=school).delete()
        captions = {
            "building_front": "School compound and building frontage",
            "building_exterior": "Bil Science Academy exterior",
            "building_signage": "School building and signage",
            "students_group": "Students in science learning attire",
            "science_lab": "Science laboratory practical session",
            "computer_lab": "Computer and digital learning space",
        }
        for index, key in enumerate(captions):
            GalleryImage.objects.create(
                school=school,
                image=copied[key],
                caption=captions[key],
                is_featured=True,
                order=index,
            )

        admissions = page(
            WebsitePage,
            school,
            "admissions",
            {
                "title": "Admissions and Contact",
                "nav_label": "Admissions",
                "template_type": "admissions",
                "is_homepage": False,
                "is_published": True,
                "show_in_nav": True,
                "order": 50,
                "header_title": "Admissions and Contact",
                "header_subtitle": "Reach Bil Science Academy for enrollment and inquiries.",
                "header_image": copied["building_signage"],
                "meta_title": f"Admissions | {SCHOOL['name']}",
                "meta_description": "Admissions and contact information for Bil Science Academy.",
                "meta_keywords": "",
                "og_title": "",
                "og_description": "",
                "og_image": copied["building_signage"],
                "canonical_url": f"https://{SCHOOL['domain']}/admissions/",
            },
        )
        section(
            WebsiteSection,
            admissions,
            10,
            "admissions",
            {
                "title": "For Enrollment",
                "subtitle": f"Call {SCHOOL['phone_display']} or email {SCHOOL['email']}.",
                "body": "",
                "image": "",
                "background_image": "",
                "button_label": "",
                "button_url": "",
                "background_color": "#f8fafc",
                "extra": {},
                "is_visible": True,
            },
        )
        section(
            WebsiteSection,
            admissions,
            20,
            "contact",
            {
                "title": "Contact Information",
                "subtitle": "",
                "body": (
                    f"<p><strong>Vision:</strong> {SCHOOL['vision']}</p>"
                    f"<p><strong>Mission:</strong> {SCHOOL['mission']}</p>"
                ),
                "image": "",
                "background_image": "",
                "button_label": "",
                "button_url": "",
                "background_color": "#ffffff",
                "extra": {},
                "is_visible": True,
            },
        )

        fees = page(
            WebsitePage,
            school,
            "school-fees",
            {
                "title": "School Fees",
                "nav_label": "School Fees",
                "template_type": "standard",
                "is_homepage": False,
                "is_published": True,
                "show_in_nav": True,
                "order": 60,
                "header_title": "School Fees",
                "header_subtitle": "Fee structure, requirements, and payment information.",
                "header_image": copied["computer_lab"],
                "meta_title": f"School Fees | {SCHOOL['name']}",
                "meta_description": "Fee structure and payment information for Bil Science Academy.",
                "meta_keywords": "",
                "og_title": "",
                "og_description": "",
                "og_image": copied["computer_lab"],
                "canonical_url": f"https://{SCHOOL['domain']}/school-fees/",
            },
        )
        section(
            WebsiteSection,
            fees,
            10,
            "rich_text",
            {
                "title": "Fee Structure",
                "subtitle": "Downloadable PDF included for prospective parents.",
                "body": fee_html(pdf_rel_path),
                "image": "",
                "background_image": "",
                "button_label": "",
                "button_url": "",
                "background_color": "#f8fafc",
                "extra": {},
                "is_visible": True,
            },
        )
        DownloadableForm.objects.update_or_create(
            school=school,
            title="Bil Science Academy Fee Structure",
            defaults={
                "description": "Fee structure and payment information for prospective parents.",
                "document": pdf_rel_path,
                "active": True,
                "order": 0,
            },
        )

        try:
            wisteen = User.objects.get(username="wisteen")
        except User.DoesNotExist:
            wisteen = None
        if wisteen:
            SchoolMembership.objects.update_or_create(
                school=school,
                user=wisteen,
                defaults={
                    "primary_role": "super_admin",
                    "extra_roles": [],
                    "is_active": True,
                    "portal_access_enabled": True,
                    "result_access_enabled": True,
                },
            )

    print(f"backup={backup}")
    print(f"tenant_slug={SLUG}")
    print(f"domain={SCHOOL['domain']}")
    print(f"logo={copied['logo']}")
    print(f"fee_pdf={pdf_rel_path}")


if __name__ == "__main__":
    main()
