"""Curated public website seed for Thy Kingdom Come Schools.

The supplied legacy site is treated as inert source material. This module
translates its verified school information and photographs into the shared
tenant CMS without importing the legacy templates, scripts, or styles.
"""

# Hallmark · pre-emit critique: P5 H4 E5 S5 R4 V5
# Hallmark · genre: modern-minimal · macrostructure: Photographic
# theme: locked tenant-accent cool-neutral · enrichment: supplied school photography
# Hallmark · slop: pass (all applicable seed-content gates; no CSS emitted)

from __future__ import annotations

import hashlib
from pathlib import Path

from django.core.files import File
from django.db import transaction
from django.utils.html import format_html, format_html_join

from core.models import SchoolSettings
from website.models import (
    GalleryImage,
    WebsiteContentItem,
    WebsitePage,
    WebsiteProfile,
    WebsiteSection,
    WebsiteTeamMember,
)


DEFAULT_SCHOOL_SLUG = "thy-kingdom-come-schools"
ASSET_ROOT = Path(__file__).resolve().parent / "seed_assets" / "thy_kingdom_come"

SCHOOL_NAME = "Thy Kingdom Come Schools"
MOTTO = "Nurtured for Greatness"
TAGLINE = "The Home of Excellence"
ADDRESS = "26B, Bamidele Olaifa Street, Off Celestial Road, Igando, Lagos"
PHONE = "08060941945"
PHONE_ALT = "09082019392"
WHATSAPP = "2348060941945"
EMAIL = "thykingdomcomeschoolsprecious@gmail.com"
PROPRIETOR_NAME = "Ogidan T.A"

VISION = (
    "To help pupils and students unlock their greatest potential as they walk "
    "the path to greatness and excellence in all spheres of life."
)
MISSION = "To nurture pupils and students for greatness in all spheres of life."

PROPRIETOR_MESSAGE = (
    "Hello, I am Ogidan T.A and you are welcome to Thy Kingdom Come Schools. "
    "Thy Kingdom Come Schools is the home of excellence where we nurture future "
    "leaders for greatness.",
    "We groom and build our pupils and students into the best version of "
    "themselves. At Thy Kingdom Come, every journey to greatness starts with a "
    "step — and choosing us is the first and best step to take.",
)

ADMISSION_STEPS = (
    (
        "Purchase Form",
        "Visit our school office at 26B, Bamidele Olaifa Street, Off Celestial Road, Igando to obtain the admission form.",
        "fas fa-file-lines",
    ),
    (
        "Submit Documents",
        "Return the completed form with the birth certificate, previous results, and passport photographs.",
        "fas fa-folder-open",
    ),
    (
        "Entrance Examination",
        "Your child will sit for an entrance examination on the scheduled date to assess readiness for admission.",
        "fas fa-pen-to-square",
    ),
    (
        "Admission",
        "Successful candidates are invited for an interview, after which admission letters are issued.",
        "fas fa-circle-check",
    ),
)

DEPARTMENTS = (
    (
        "Early Years and Primary",
        "KG, Nursery, and Basic 1–5 provide strong foundations for confident learning and steady development.",
        "fas fa-shapes",
    ),
    (
        "Science Department",
        "Physics, Chemistry, Biology, and practical learning supported by laboratory experience.",
        "fas fa-flask",
    ),
    (
        "Arts Department",
        "Literature, History, Government, and Languages with a focus on critical thinking and expression.",
        "fas fa-book-open",
    ),
    (
        "Commercial Department",
        "Accounting, Economics, Commerce, and Business Studies for future entrepreneurs and professionals.",
        "fas fa-chart-line",
    ),
)

BEYOND_CLASSROOM = (
    (
        "Sports",
        "Football, basketball, athletics, and other activities build teamwork, discipline, and resilience.",
        "fas fa-futbol",
    ),
    (
        "Clubs",
        "JETS Club, Literary and Debating Society, and other interest-based groups support discovery and confidence.",
        "fas fa-people-group",
    ),
    (
        "Music and Arts",
        "The school choir, drama troupe, and cultural groups help students express their talents.",
        "fas fa-music",
    ),
    (
        "Societies",
        "Red Cross, Boys Scouts, Girls Guide, and other societies develop leadership and service.",
        "fas fa-handshake-angle",
    ),
)

FEE_SCHEDULE = (
    (
        "KG 1 and 2",
        (
            ("Registration", 1000),
            ("Tuition", 21000),
            ("Uniform", 8000),
            ("Tuesday Uniform", 10000),
            ("Sport Wear", 6000),
            ("Friday Wear", 6000),
            ("Cardigan", 7000),
            ("Socks", 2000),
        ),
        61000,
    ),
    (
        "Nursery",
        (
            ("Registration", 1000),
            ("Tuition", 22000),
            ("Uniform", 8000),
            ("Tuesday Uniform", 10000),
            ("Sport Wear", 6000),
            ("Friday Wear", 6000),
            ("Cardigan", 7000),
            ("Socks", 2000),
        ),
        62000,
    ),
    (
        "Basic One",
        (
            ("Registration", 1000),
            ("Tuition", 25000),
            ("Uniform", 8000),
            ("Tuesday Uniform", 10000),
            ("Sport Wear", 6000),
            ("Friday Wear", 6000),
            ("Cardigan", 7000),
            ("Socks", 2000),
        ),
        65000,
    ),
    (
        "Basic 2 to 5",
        (
            ("Registration", 1000),
            ("Tuition", 27500),
            ("Uniform", 8000),
            ("Tuesday Uniform", 10000),
            ("Sport Wear", 6000),
            ("Friday Wear", 6000),
            ("Cardigan", 7000),
            ("Socks", 2000),
        ),
        67500,
    ),
    (
        "Junior Secondary",
        (
            ("Registration", 2000),
            ("Tuition", 36000),
            ("Uniform", 16000),
            ("Sport Wear", 7000),
            ("Friday Wear", 6000),
            ("Socks", 2000),
            ("Tie", 2000),
        ),
        71000,
    ),
    (
        "Senior Secondary",
        (
            ("Registration", 2000),
            ("Tuition", 44000),
            ("Uniform", 18000),
            ("Sport Wear", 7000),
            ("Friday Wear", 6000),
            ("Socks", 2000),
            ("Tie", 2000),
        ),
        78000,
    ),
)


def _paragraphs(*values: str) -> str:
    return str(format_html_join("", "<p>{}</p>", ((value,) for value in values if value)))


def _bullet_list(values: tuple[str, ...], intro: str = "") -> str:
    prefix = _paragraphs(intro) if intro else ""
    items = format_html_join("", "<li>{}</li>", ((value,) for value in values))
    return f"{prefix}<ul>{items}</ul>"


def _fee_schedule_html() -> str:
    blocks = []
    for level, fees, total in FEE_SCHEDULE:
        rows = format_html_join(
            "",
            '<tr><td>{}</td><td class="text-end">₦{}</td></tr>',
            ((label, f"{amount:,.0f}") for label, amount in fees),
        )
        blocks.append(
            format_html(
                """
                <div class="mb-4">
                  <h3>{}</h3>
                  <div class="table-responsive">
                    <table class="table table-bordered align-middle">
                      <thead><tr><th>Item</th><th class="text-end">Amount</th></tr></thead>
                      <tbody>{}<tr><th>Total</th><th class="text-end">₦{}</th></tr></tbody>
                    </table>
                  </div>
                </div>
                """,
                level,
                rows,
                f"{total:,.0f}",
            )
        )
    notice = format_html(
        """
        <h3>Textbooks and Exercise Books</h3>
        <p>All textbooks and exercise books are sold in the school. Parents are advised to purchase books directly from the school to ensure the correct editions and uniformity across classes. Visit the school office for the complete booklist and pricing for your child’s class.</p>
        <h3>Payment Details</h3>
        <p><strong>Bank:</strong> First Bank<br>
        <strong>Account Number:</strong> 2041727429<br>
        <strong>Account Name:</strong> Bo Malkut Elementary &amp; Secondary Schools</p>
        """
    )
    return "".join(str(block) for block in blocks) + str(notice)


def _sha256(stream) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def _asset_path(asset_name: str) -> Path:
    path = ASSET_ROOT / asset_name
    if not path.is_file():
        raise FileNotFoundError(f"Thy Kingdom Come seed asset is missing: {path}")
    return path


def _field_matches_asset(field_file, asset_path: Path) -> bool:
    if not field_file or not field_file.name:
        return False
    try:
        with field_file.open("rb") as current, asset_path.open("rb") as source:
            return _sha256(current) == _sha256(source)
    except (FileNotFoundError, OSError, ValueError):
        return False


def _install_asset(instance, field_name: str, asset_name: str, *, skip_images: bool) -> bool:
    if skip_images:
        return False
    asset_path = _asset_path(asset_name)
    field_file = getattr(instance, field_name)
    if _field_matches_asset(field_file, asset_path):
        return False
    with asset_path.open("rb") as source:
        field_file.save(
            f"thy_kingdom_come/{asset_name}",
            File(source, name=asset_name),
            save=False,
        )
    instance.save(update_fields=[field_name])
    return True


def _replace_page(school, slug: str, defaults: dict, *, header_asset: str, skip_images: bool):
    page, _ = WebsitePage.objects.update_or_create(
        school=school,
        slug=slug,
        defaults=defaults,
    )
    if header_asset:
        _install_asset(page, "header_image", header_asset, skip_images=skip_images)
    page.sections.all().delete()
    return page


def _section(
    page,
    order: int,
    section_type: str,
    *,
    asset: str = "",
    asset_field: str = "image",
    skip_images: bool,
    **values,
):
    section = WebsiteSection.objects.create(
        page=page,
        order=order,
        section_type=section_type,
        is_visible=True,
        **values,
    )
    if asset:
        _install_asset(section, asset_field, asset, skip_images=skip_images)
    return section


def _items(section, values: list[dict], *, skip_images: bool):
    for order, values_for_item in enumerate(values):
        item_data = dict(values_for_item)
        asset = item_data.pop("asset", "")
        item = WebsiteContentItem.objects.create(
            section=section,
            order=order,
            is_visible=True,
            **item_data,
        )
        if asset:
            _install_asset(item, "image", asset, skip_images=skip_images)


def _seed_identity(school, *, skip_images: bool):
    school.name = SCHOOL_NAME
    school.contact_email = EMAIL
    school.contact_phone = PHONE
    school.save(update_fields=["name", "contact_email", "contact_phone", "updated_at"])

    settings, _ = SchoolSettings.objects.get_or_create(school=school)
    settings.school_name = SCHOOL_NAME
    settings.school_address = ADDRESS
    settings.proprietor_name = PROPRIETOR_NAME
    settings.school_motto = MOTTO
    settings.primary_color = "#0498ce"
    settings.secondary_color = "#0369a1"
    settings.accent_color = "#dc2626"
    settings.save(
        update_fields=[
            "school_name",
            "school_address",
            "proprietor_name",
            "school_motto",
            "primary_color",
            "secondary_color",
            "accent_color",
        ]
    )
    _install_asset(settings, "school_logo", "logo.png", skip_images=skip_images)
    _install_asset(settings, "school_seal", "logo.png", skip_images=skip_images)

    profile, _ = WebsiteProfile.objects.update_or_create(
        school=school,
        defaults={
            "site_name": SCHOOL_NAME,
            "tagline": f"{TAGLINE} — {MOTTO}",
            "description": (
                "Thy Kingdom Come Schools provides KG, Nursery, Primary, and "
                "Secondary education in Igando, Lagos, nurturing pupils and "
                "students for greatness in all spheres of life."
            ),
            "phone": PHONE,
            "phone_alt": PHONE_ALT,
            "whatsapp_number": WHATSAPP,
            "email": EMAIL,
            "address": ADDRESS,
            "office_hours": "",
            "instagram_url": "",
            "facebook_url": "",
            "twitter_url": "",
            "youtube_url": "",
            "footer_note": f"{TAGLINE}. {MOTTO}.",
        },
    )
    _install_asset(profile, "logo", "logo.png", skip_images=skip_images)
    _install_asset(profile, "favicon", "logo.png", skip_images=skip_images)
    _install_asset(profile, "default_og_image", "slide2.jpeg", skip_images=skip_images)
    return settings, profile


def _seed_proprietor(school, *, skip_images: bool):
    proprietor = WebsiteTeamMember.objects.filter(
        school=school,
        role__icontains="Proprietor",
    ).order_by("id").first()
    if proprietor is None:
        proprietor = WebsiteTeamMember(school=school)
    proprietor.name = PROPRIETOR_NAME
    proprietor.role = f"Proprietor, {SCHOOL_NAME}"
    proprietor.bio = _paragraphs(*PROPRIETOR_MESSAGE)
    proprietor.order = 0
    proprietor.is_visible = True
    proprietor.save()
    _install_asset(proprietor, "photo", "proprietor.jpeg", skip_images=skip_images)
    return proprietor


def _seed_gallery(school, *, skip_images: bool):
    gallery_data = [
        ("Students in uniform at a school gathering", "slide2.jpeg"),
        ("Early years classroom learning", "slide1.jpeg"),
        ("Pupils representing the school on an educational outing", "school3.jpg"),
        ("Playground activities and friendship", "school10.jpg"),
        ("Inter-house sports day", "school13.jpg"),
        ("Creative craft activity and student achievement", "school14.jpg"),
        ("Students together on an educational outing", "school1.jpg"),
        ("A school group during an educational outing", "school2.jpg"),
        ("Primary pupils with their teacher", "school4.jpg"),
        ("Students learning and growing together", "school5.jpg"),
        ("A pupil enjoying a school activity day", "school6.jpg"),
        ("Learning through play", "school7.jpg"),
        ("Early years activity day", "school8.jpg"),
        ("Confidence and fun beyond the classroom", "school9.jpg"),
        ("Pupils enjoying outdoor activities", "school11.jpg"),
        ("School activity day", "school12.jpg"),
    ]
    records = []
    for order, (caption, asset) in enumerate(gallery_data):
        image = GalleryImage.objects.filter(school=school, order=order).order_by("id").first()
        if image is None:
            image = GalleryImage(school=school, order=order)
        image.caption = caption
        image.is_featured = order < 6
        image.order = order
        image.save()
        _install_asset(image, "image", asset, skip_images=skip_images)
        records.append(image)
    GalleryImage.objects.filter(school=school, order__gte=len(gallery_data)).delete()
    return records


def _seed_home(school, *, skip_images: bool):
    page = _replace_page(
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
            "header_title": SCHOOL_NAME,
            "header_subtitle": f"{TAGLINE} — {MOTTO}",
            "meta_title": f"{SCHOOL_NAME} | KG to SSS 3 in Igando, Lagos",
            "meta_description": (
                "Thy Kingdom Come Schools offers KG, Nursery, Primary, and Secondary "
                "education in Igando, Lagos."
            ),
            "meta_keywords": (
                "Thy Kingdom Come Schools, school Igando Lagos, nursery school Igando, "
                "primary school Igando, secondary school Igando"
            ),
            "og_title": SCHOOL_NAME,
            "og_description": f"{TAGLINE} — {MOTTO}.",
        },
        header_asset="slide2.jpeg",
        skip_images=skip_images,
    )
    _section(
        page,
        0,
        "hero",
        hero_variant="full_width",
        title=SCHOOL_NAME,
        subtitle=MOTTO,
        button_label="Admission Information",
        button_url="/admissions/",
        asset="slide2.jpeg",
        asset_field="background_image",
        skip_images=skip_images,
    )
    _section(
        page,
        10,
        "rich_text",
        title=f"Welcome to {SCHOOL_NAME}",
        subtitle=f"{TAGLINE} — {MOTTO}",
        body=_paragraphs(*PROPRIETOR_MESSAGE),
        button_label="Read Our Story",
        button_url="/about/",
        asset="proprietor.jpeg",
        skip_images=skip_images,
    )
    strengths = _section(
        page,
        20,
        "cards",
        title="A Complete School Experience",
        subtitle="The strengths families encounter across learning and school life.",
        background_color="#f8fafc",
        extra={"item_column_class": "col-md-6 col-lg-3"},
        skip_images=skip_images,
    )
    _items(
        strengths,
        [
            {
                "title": "Expert Teachers",
                "subtitle": "Teachers guide pupils and students with care, structure, and attention.",
                "icon_class": "fas fa-person-chalkboard",
            },
            {
                "title": "Academic Excellence",
                "subtitle": "Strong foundations and purposeful preparation support steady achievement.",
                "icon_class": "fas fa-award",
            },
            {
                "title": "Total Development",
                "subtitle": "Sports, clubs, societies, music, and arts develop the whole child.",
                "icon_class": "fas fa-people-group",
            },
            {
                "title": "Strong Values",
                "subtitle": "Character, discipline, leadership, and service shape everyday school life.",
                "icon_class": "fas fa-shield-heart",
            },
        ],
        skip_images=skip_images,
    )
    stats = _section(
        page,
        30,
        "stats",
        title="School at a Glance",
        skip_images=skip_images,
    )
    _items(
        stats,
        [
            {"title": "98%", "subtitle": "WAEC and NECO pass rate"},
            {"title": "500+", "subtitle": "Students enrolled"},
            {"title": "15+", "subtitle": "Clubs and societies"},
            {"title": "2015", "subtitle": "Year founded"},
        ],
        skip_images=skip_images,
    )
    stages = _section(
        page,
        40,
        "cards",
        title="Learning from KG to SSS 3",
        subtitle="One school community, with guidance appropriate to every stage.",
        extra={"item_column_class": "col-md-6"},
        skip_images=skip_images,
    )
    _items(
        stages,
        [
            {"title": "KG and Nursery", "subtitle": "Early foundations for language, numeracy, confidence, curiosity, and learning through guided activity."},
            {"title": "Primary — Basic 1 to 5", "subtitle": "A broad primary programme that strengthens core knowledge, communication, and independent learning."},
            {"title": "Junior Secondary — JSS 1 to 3", "subtitle": "Broad subject exposure, practical learning, and preparation for senior secondary pathways."},
            {"title": "Senior Secondary — SSS 1 to 3", "subtitle": "Science, Arts, and Commercial pathways with academic and career guidance."},
        ],
        skip_images=skip_images,
    )
    _section(
        page,
        50,
        "gallery",
        title="School Life in Pictures",
        subtitle="Learning, friendship, activity, and achievement across the school community.",
        button_label="View Gallery",
        button_url="/gallery/",
        extra={"featured_only": True, "limit": 6},
        background_color="#f8fafc",
        skip_images=skip_images,
    )
    _section(
        page,
        60,
        "contact",
        title="Begin the Journey to Greatness",
        body=_paragraphs("Contact the school office for admissions, enquiries, or to arrange a visit."),
        skip_images=skip_images,
    )
    return page


def _seed_about(school, *, skip_images: bool):
    page = _replace_page(
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
            "header_title": f"About {SCHOOL_NAME}",
            "header_subtitle": f"{TAGLINE} — {MOTTO}",
            "meta_title": f"About | {SCHOOL_NAME}",
            "meta_description": (
                "Learn about Thy Kingdom Come Schools, founded in 2015 in Igando, Lagos, "
                "its vision, mission, and proprietor."
            ),
        },
        header_asset="school4.jpg",
        skip_images=skip_images,
    )
    _section(
        page,
        0,
        "hero",
        hero_variant="full_width",
        title=f"About {SCHOOL_NAME}",
        subtitle=f"{TAGLINE} — {MOTTO}",
        asset="school4.jpg",
        asset_field="background_image",
        skip_images=skip_images,
    )
    _section(
        page,
        10,
        "rich_text",
        title="A School Built for Greatness",
        body=_paragraphs(
            "Thy Kingdom Come Schools was founded in 2015 in Igando, Lagos.",
            "The school grooms and builds pupils and students into the best version of themselves through learning, character, participation, and steady guidance.",
        ),
        asset="slide2.jpeg",
        skip_images=skip_images,
    )
    purpose = _section(
        page,
        20,
        "cards",
        title="Vision, Mission, and Promise",
        background_color="#f8fafc",
        skip_images=skip_images,
    )
    _items(
        purpose,
        [
            {"title": "Our Vision", "subtitle": VISION, "icon_class": "fas fa-eye"},
            {"title": "Our Mission", "subtitle": MISSION, "icon_class": "fas fa-bullseye"},
            {"title": "Our Promise", "subtitle": f"{TAGLINE}. {MOTTO}.", "icon_class": "fas fa-star"},
        ],
        skip_images=skip_images,
    )
    _section(
        page,
        30,
        "rich_text",
        title="From the Proprietor’s Desk",
        subtitle=PROPRIETOR_NAME,
        body=_paragraphs(*PROPRIETOR_MESSAGE),
        asset="proprietor.jpeg",
        skip_images=skip_images,
    )
    _section(
        page,
        40,
        "gallery",
        title="Our School Community",
        subtitle="Pupils and students learning, participating, and growing together.",
        button_label="View All Photographs",
        button_url="/gallery/",
        extra={"featured_only": True, "limit": 6},
        background_color="#f8fafc",
        skip_images=skip_images,
    )
    return page


def _seed_academics(school, *, skip_images: bool):
    page = _replace_page(
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
            "header_subtitle": "Excellence in learning, character, and leadership",
            "meta_title": f"Academics | {SCHOOL_NAME}",
            "meta_description": (
                "Explore the KG to SSS 3 curriculum, Science, Arts, and Commercial "
                "departments at Thy Kingdom Come Schools."
            ),
        },
        header_asset="slide1.jpeg",
        skip_images=skip_images,
    )
    _section(
        page,
        0,
        "hero",
        hero_variant="full_width",
        title="Learning from KG to SSS 3",
        subtitle="Excellence in learning, character, and leadership",
        asset="slide1.jpeg",
        asset_field="background_image",
        skip_images=skip_images,
    )
    _section(
        page,
        10,
        "rich_text",
        title="Our Curriculum",
        body=_bullet_list(
            (
                "KG and Nursery early-years education",
                "Primary education from Basic 1 to 5",
                "Junior Secondary School from JSS 1 to 3",
                "Senior Secondary School from SSS 1 to 3 with academic and career guidance",
                "Science, Arts, and Commercial departments",
                "Practical learning in ICT and laboratories",
                "Character training through clubs, societies, and mentorship",
            ),
            intro=(
                "The curriculum blends strong academic foundations with practical learning "
                "experiences, nurturing pupils and students for greatness in all spheres of life."
            ),
        ),
        asset="slide2.jpeg",
        skip_images=skip_images,
    )
    departments = _section(
        page,
        20,
        "cards",
        title="Learning Stages and Departments",
        subtitle="Broad foundations followed by focused senior-secondary pathways.",
        background_color="#f8fafc",
        extra={"item_column_class": "col-md-6"},
        skip_images=skip_images,
    )
    _items(
        departments,
        [
            {"title": title, "subtitle": description, "icon_class": icon}
            for title, description, icon in DEPARTMENTS
        ],
        skip_images=skip_images,
    )
    stats = _section(
        page,
        30,
        "stats",
        title="Academic Results and Progression",
        skip_images=skip_images,
    )
    _items(
        stats,
        [
            {"title": "98%", "subtitle": "WAEC pass rate"},
            {"title": "100%", "subtitle": "NECO core subjects"},
            {"title": "50+", "subtitle": "University admissions per year"},
            {"title": "15+", "subtitle": "Clubs and societies"},
        ],
        skip_images=skip_images,
    )
    activities = _section(
        page,
        40,
        "cards",
        title="Beyond the Classroom",
        subtitle="Total development through sports, clubs, societies, music, and arts.",
        extra={"item_column_class": "col-md-6 col-lg-3"},
        skip_images=skip_images,
    )
    _items(
        activities,
        [
            {"title": title, "subtitle": description, "icon_class": icon}
            for title, description, icon in BEYOND_CLASSROOM
        ],
        skip_images=skip_images,
    )
    return page


def _seed_admissions(school, *, skip_images: bool):
    page = _replace_page(
        school,
        "admissions",
        {
            "title": "Admissions",
            "nav_label": "Admissions",
            "template_type": "admissions",
            "is_homepage": False,
            "is_published": True,
            "show_in_nav": True,
            "order": 30,
            "header_title": "Admissions",
            "header_subtitle": "Begin your journey to greatness with us",
            "meta_title": f"Admissions | {SCHOOL_NAME}",
            "meta_description": (
                "Admissions information for KG, Nursery, Primary, and Secondary "
                "classes at Thy Kingdom Come Schools in Igando, Lagos."
            ),
        },
        header_asset="school10.jpg",
        skip_images=skip_images,
    )
    _section(
        page,
        0,
        "hero",
        hero_variant="full_width",
        title="Begin Your Journey to Greatness",
        subtitle="Admissions for KG, Nursery, Primary, and Secondary",
        button_label="Contact Admissions",
        button_url=f"mailto:{EMAIL}",
        asset="school10.jpg",
        asset_field="background_image",
        skip_images=skip_images,
    )
    steps = _section(
        page,
        10,
        "cards",
        title="How to Apply",
        subtitle="Four steps to secure a place at Thy Kingdom Come Schools.",
        extra={"item_column_class": "col-md-6 col-lg-3"},
        skip_images=skip_images,
    )
    _items(
        steps,
        [
            {
                "title": f"Step {index}: {title}",
                "subtitle": description,
                "icon_class": icon,
            }
            for index, (title, description, icon) in enumerate(ADMISSION_STEPS, start=1)
        ],
        skip_images=skip_images,
    )
    _section(
        page,
        20,
        "admissions",
        title="For Enrollment",
        subtitle=f"Call {PHONE} or {PHONE_ALT}, send a WhatsApp message, or email {EMAIL}.",
        background_color="#f8fafc",
        skip_images=skip_images,
    )
    _section(
        page,
        30,
        "contact",
        title="Visit the School Office",
        body=_paragraphs(
            "Visit the school to obtain an admission form, discuss the appropriate class level, or confirm entrance-examination arrangements.",
            "The school office will provide current requirements, dates, and fee information.",
        ),
        skip_images=skip_images,
    )
    return page


def _seed_gallery_page(school, *, skip_images: bool):
    page = _replace_page(
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
            "header_subtitle": "Learning, friendship, activity, and achievement",
            "meta_title": f"Gallery | {SCHOOL_NAME}",
            "meta_description": "Photographs of pupils, students, classrooms, outings, sports, and school activities at Thy Kingdom Come Schools.",
        },
        header_asset="school13.jpg",
        skip_images=skip_images,
    )
    _section(
        page,
        10,
        "gallery",
        title="Life at Thy Kingdom Come Schools",
        subtitle="A photographic record of learning and participation across the school community.",
        background_color="#f8fafc",
        skip_images=skip_images,
    )
    return page


def _seed_fees(school, *, skip_images: bool):
    page = _replace_page(
        school,
        "school-fees",
        {
            "title": "School Fees",
            "nav_label": "School Fees",
            "template_type": "standard",
            "is_homepage": False,
            "is_published": True,
            "show_in_nav": True,
            "order": 50,
            "header_title": "School Fees",
            "header_subtitle": "2025/2026 academic-session fee structure",
            "meta_title": f"School Fees | {SCHOOL_NAME}",
            "meta_description": "The supplied 2025/2026 fee structure for KG, Nursery, Primary, and Secondary classes at Thy Kingdom Come Schools.",
        },
        header_asset="school13.jpg",
        skip_images=skip_images,
    )
    _section(
        page,
        0,
        "hero",
        hero_variant="full_width",
        title="School Fees",
        subtitle="2025/2026 academic-session fee structure",
        asset="school13.jpg",
        asset_field="background_image",
        skip_images=skip_images,
    )
    _section(
        page,
        10,
        "rich_text",
        title="Fee Structure by Class Level",
        subtitle="Please confirm current charges with the school office before making payment.",
        body=_fee_schedule_html(),
        background_color="#f8fafc",
        skip_images=skip_images,
    )
    return page


@transaction.atomic
def seed_thy_kingdom_come_website(school, *, skip_images: bool = False):
    """Replace the six core public CMS pages with curated tenant content."""
    settings, profile = _seed_identity(school, skip_images=skip_images)
    proprietor = _seed_proprietor(school, skip_images=skip_images)
    gallery = _seed_gallery(school, skip_images=skip_images)
    pages = [
        _seed_home(school, skip_images=skip_images),
        _seed_about(school, skip_images=skip_images),
        _seed_academics(school, skip_images=skip_images),
        _seed_admissions(school, skip_images=skip_images),
        _seed_gallery_page(school, skip_images=skip_images),
        _seed_fees(school, skip_images=skip_images),
    ]
    return {
        "school": school,
        "settings": settings,
        "profile": profile,
        "pages": pages,
        "proprietor": proprietor,
        "gallery": gallery,
    }
