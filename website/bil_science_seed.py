"""Curated public website seed for Bil Science Academy."""

# Hallmark · pre-emit critique: P5 H4 E5 S5 R4 V5
# Hallmark · genre: modern-minimal · macrostructure: Split Studio / Long Document
# tone: warm conventional-school editorial · theme: locked tenant-accent cool-neutral

from __future__ import annotations

import hashlib
from pathlib import Path

from django.core.files import File
from django.db import transaction
from django.utils.html import format_html, format_html_join

from core.models import SchoolSettings
from website.models import (
    DownloadableForm,
    GalleryImage,
    WebsiteContentItem,
    WebsitePage,
    WebsiteProfile,
    WebsiteSection,
    WebsiteTeamMember,
)


DEFAULT_SCHOOL_SLUG = "bil-science-academy"
ASSET_ROOT = Path(__file__).resolve().parent / "seed_assets" / "bil_science"

SCHOOL_NAME = "Bil Science Academy"
MOTTO = "Knowledge, Character and Excellence"
TAGLINE = "Where Future Leaders are Built"
ADDRESS = (
    "BIL HUB: 1, Prince Kosoko Crescent, Suberu-Oje, Oke-Abiye, "
    "Amikanle Axis, Alagbado Lagos."
)
PHONE = "0814 124 8867"
WHATSAPP = "2348141248867"
EMAIL = "bilsciencea@gmail.com"
PROPRIETOR_NAME = "LANA, Ismaeel A. (CSNT, BDE)"

VISION = (
    "Aspiring to create globally competitive leaders and citizens while building "
    "the intellectuals of the future."
)
MISSION = (
    "To establish an academic structure and curriculum that brings out the inherent "
    "intellectual prowess in every student through intensive academic commitment, "
    "innovation, creativity, a multicultural environment, and lifelong learning."
)
CORE_VALUES = ("Consistency", "Resilience", "Academic Excellence")

ACADEMIC_DEPARTMENTS = (
    (
        "Science",
        "Rigorous scientific study, laboratory experience, investigation, and problem-solving for future scientists, doctors, and engineers.",
        "fas fa-flask",
    ),
    (
        "Business (Commercial)",
        "Enterprise, accounting, commerce, and economic thinking for future entrepreneurs and business leaders.",
        "fas fa-chart-line",
    ),
    (
        "Humanities (Art)",
        "Language, society, creativity, communication, and critical thought for future advocates, writers, designers, and leaders.",
        "fas fa-landmark",
    ),
    (
        "Informatics (Artificial Intelligence & Robotics)",
        "Computational thinking, coding, artificial intelligence, and robotics for students preparing to shape the digital future.",
        "fas fa-robot",
    ),
)

HOUSE_DATA = (
    (
        "Afolabi House",
        "Pink",
        "house-pink.jpeg",
        "Afolabi House students and house owners in their distinctive pink colours.",
    ),
    (
        "Al-Ameen House",
        "Yellow",
        "house-yellow.jpeg",
        "Al-Ameen House students and house owners in their distinctive yellow colours.",
    ),
    (
        "Kareem House",
        "Green",
        "house-green.jpeg",
        "Kareem House students and house owners in their distinctive green colours.",
    ),
    (
        "Sanyaolu House",
        "Blue",
        "house-blue.jpeg",
        "Sanyaolu House students and house owners in their distinctive blue colours.",
    ),
)

PROPRIETOR_SPEECH = (
    "Dear Parents, Students, and Esteemed Visitors,",
    (
        "It is with great pride and excitement that I welcome you to Bil Science "
        "Academy — Where Future Leaders are Built."
    ),
    (
        "At Bil Science Academy, we believe every child is born with extraordinary potential. Our "
        "mission is to unlock that potential through Intensive Academic Commitment, "
        "Innovation, Creativity, and Strong Character."
    ),
    (
        "We offer a complete and balanced education across 4 major departments: "
        "Science, Humanities (Arts), Business (Commercial), and Informatics — AI & "
        "Robotics. Whether your child dreams of becoming a doctor, engineer, lawyer, "
        "entrepreneur, designer, or tech innovator, BSA provides the foundation."
    ),
    (
        "In a world driven by Technology and Global Competition, we go beyond preparing "
        "students to pass exams. We prepare them to think critically, to lead, to solve "
        "real-world problems, and to make a positive impact. From our AI & Robotics Lab, "
        "to our Business Hub, Arts Studios, and Science Laboratories, we equip students "
        "with 21st century skills while building strong values and leadership."
    ),
    (
        "Our vision is clear: To create global leaders and build the intellectuals of "
        "the future."
    ),
    (
        "To our esteemed parents: Thank you for entrusting us with your children. We "
        "promise to nurture them with diligence, discipline, care, and respect for every "
        "background and talent."
    ),
    (
        "To our students: The future belongs to you. Dream big, work hard, stay curious, "
        "and with knowledge, consistency, and courage, nothing is impossible."
    ),
    "Welcome to Bil Science Academy. Welcome to the future.",
)

CLUBS = (
    ("Taekwondo Kids Club", "Discipline, resilience, movement, and confidence.", "fas fa-person-running"),
    ("Young Motivators Club", "Leadership, positive influence, and personal development.", "fas fa-users"),
    ("JET Club", "Science curiosity, technology, and practical discovery.", "fas fa-rocket"),
    ("Speech & Oratory Club", "Public speaking, expression, and confidence.", "fas fa-microphone"),
)

FEES = (
    ("Acceptance Fee", 10000),
    ("Uniforms", 20000),
    ("Sport Wear", 15000),
    ("Hat (Girls)", 10000),
    ("Tuition Fee", 60000),
    ("Medical", 5000),
    ("Coding and Graphics (Per Term)", 20000),
)


def _paragraphs(*values: str) -> str:
    return str(format_html_join("", "<p>{}</p>", ((value,) for value in values if value)))


def _bullet_list(values: tuple[str, ...], intro: str = "") -> str:
    prefix = _paragraphs(intro) if intro else ""
    items = format_html_join("", "<li>{}</li>", ((value,) for value in values))
    return f"{prefix}<ul>{items}</ul>"


def _proprietor_speech_html() -> str:
    body = format_html_join("", "<p>{}</p>", ((paragraph,) for paragraph in PROPRIETOR_SPEECH))
    signature = format_html(
        "<p><strong>Warm regards,<br>{}</strong><br><span>Proprietor, Bil Science Academy</span></p>",
        PROPRIETOR_NAME,
    )
    return str(body) + str(signature)


def _fee_html() -> str:
    rows = format_html_join(
        "",
        '<tr><td>{}</td><td class="text-end">NGN {}</td></tr>',
        ((name, f"{amount:,.2f}") for name, amount in FEES),
    )
    requirements = format_html_join(
        "",
        "<li>{}</li>",
        ((item,) for item in (
            "Complete school-approved textbooks",
            "Exercise books with the school logo",
            "A pair of black shoes",
            "Black belt",
            "Canvas shoes with white socks for sports",
        )),
    )
    return str(format_html(
        """
        <div class="table-responsive">
          <table class="table table-bordered align-middle">
            <thead><tr><th>Item</th><th class="text-end">Amount</th></tr></thead>
            <tbody>{}<tr><th>Total for Boys</th><th class="text-end">NGN 130,000.00</th></tr>
            <tr><th>Total for Girls</th><th class="text-end">NGN 140,000.00</th></tr></tbody>
          </table>
        </div>
        <h3>Compulsory School Requirements</h3><ul>{}</ul>
        <h3>Payment Information</h3>
        <p><strong>Bank:</strong> Zenith Bank Plc.<br>
        <strong>Account Name:</strong> Bil Hub Oceanic Ltd<br>
        <strong>Account Number:</strong> 1310 3410 94</p>
        """,
        rows,
        requirements,
    ))


def _sha256(stream) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def _asset_path(asset_name: str) -> Path:
    path = ASSET_ROOT / asset_name
    if not path.is_file():
        raise FileNotFoundError(f"Bil Science Academy seed asset is missing: {path}")
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
            f"bil_science/{asset_name}",
            File(source, name=asset_name),
            save=False,
        )
    instance.save(update_fields=[field_name])
    return True


def _replace_page(school, slug: str, defaults: dict, *, header_asset: str, skip_images: bool):
    page, _ = WebsitePage.objects.update_or_create(school=school, slug=slug, defaults=defaults)
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
    for order, data in enumerate(values):
        item_data = dict(data)
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
    school.contact_phone = WHATSAPP
    school.save(update_fields=["name", "contact_email", "contact_phone", "updated_at"])

    settings, _ = SchoolSettings.objects.get_or_create(school=school)
    settings.school_name = SCHOOL_NAME
    settings.school_address = ADDRESS
    settings.proprietor_name = PROPRIETOR_NAME
    settings.school_motto = MOTTO
    settings.primary_color = "#047857"
    settings.secondary_color = "#0f766e"
    settings.accent_color = "#f59e0b"
    settings.save(update_fields=[
        "school_name",
        "school_address",
        "proprietor_name",
        "school_motto",
        "primary_color",
        "secondary_color",
        "accent_color",
    ])
    _install_asset(settings, "school_logo", "logo.jpeg", skip_images=skip_images)
    _install_asset(settings, "school_seal", "logo.jpeg", skip_images=skip_images)

    profile, _ = WebsiteProfile.objects.update_or_create(
        school=school,
        defaults={
            "site_name": SCHOOL_NAME,
            "tagline": TAGLINE,
            "description": (
                "Bil Science Academy is a co-educational school in Alagbado, Lagos, "
                "developing future leaders through science, humanities, business, "
                "artificial intelligence, robotics, and strong character."
            ),
            "phone": PHONE,
            "phone_alt": "",
            "whatsapp_number": WHATSAPP,
            "email": EMAIL,
            "address": ADDRESS,
            "office_hours": "",
            "footer_note": MOTTO,
        },
    )
    _install_asset(profile, "logo", "logo.jpeg", skip_images=skip_images)
    _install_asset(profile, "favicon", "logo.jpeg", skip_images=skip_images)
    _install_asset(profile, "default_og_image", "building-front.jpeg", skip_images=skip_images)
    return settings, profile


def _seed_proprietor(school, *, skip_images: bool):
    proprietor = WebsiteTeamMember.objects.filter(
        school=school,
        role__icontains="Proprietor",
    ).order_by("id").first()
    if proprietor is None:
        proprietor = WebsiteTeamMember(school=school)
    proprietor.name = PROPRIETOR_NAME
    proprietor.role = "Proprietor, Bil Science Academy"
    proprietor.bio = _proprietor_speech_html()
    proprietor.order = 0
    proprietor.is_visible = True
    proprietor.save()
    _install_asset(proprietor, "photo", "proprietor.jpeg", skip_images=skip_images)
    return proprietor


def _seed_gallery(school, *, skip_images: bool):
    gallery_data = [
        ("School compound and building frontage", "building-front.jpeg"),
        ("Bil Science Academy exterior", "building-exterior.jpeg"),
        ("School building and signage", "building-signage.jpeg"),
        ("Students in science learning attire", "students-science-group.jpeg"),
        ("Science laboratory practical session", "science-lab.jpeg"),
        ("Computer and digital learning space", "computer-lab.jpeg"),
        ("Meet the House Owners — from right: Afolabi, Al-Ameen, Kareem, and Sanyaolu Houses", "main-house.jpeg"),
        ("Afolabi House — Pink", "house-pink.jpeg"),
        ("Al-Ameen House — Yellow", "house-yellow.jpeg"),
        ("Kareem House — Green", "house-green.jpeg"),
        ("Sanyaolu House — Blue", "house-blue.jpeg"),
    ]
    records = []
    for order, (caption, asset) in enumerate(gallery_data):
        image = GalleryImage.objects.filter(school=school, order=order).order_by("id").first()
        if image is None:
            image = GalleryImage(school=school, order=order)
        image.caption = caption
        image.is_featured = order in {0, 3, 4, 6, 7, 10}
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
            "header_subtitle": TAGLINE,
            "meta_title": f"{SCHOOL_NAME} | Future Leaders in Alagbado, Lagos",
            "meta_description": (
                "Explore Bil Science Academy's four academic departments, learning "
                "environment, school houses, facilities, and admissions."
            ),
            "meta_keywords": "Bil Science Academy, co-educational school Lagos, AI robotics school, Alagbado school",
            "og_title": SCHOOL_NAME,
            "og_description": TAGLINE,
        },
        header_asset="building-front.jpeg",
        skip_images=skip_images,
    )
    hero = _section(
        page,
        0,
        "hero",
        hero_variant="carousel",
        title=SCHOOL_NAME,
        subtitle=TAGLINE,
        button_label="Admission Information",
        button_url="/admissions/",
        skip_images=skip_images,
    )
    _items(
        hero,
        [
            {
                "title": "Where Future Leaders Are Built",
                "subtitle": SCHOOL_NAME,
                "body": _paragraphs("Knowledge, character, innovation, and courage for the world ahead."),
                "button_label": "Admission Information",
                "button_url": "/admissions/",
                "asset": "building-front.jpeg",
            },
            {
                "title": "Four Pathways. One Future.",
                "subtitle": "Science · Business · Humanities · Informatics",
                "body": _paragraphs("A balanced education shaped around each student's strengths and ambitions."),
                "button_label": "Explore Academics",
                "button_url": "/academics/",
                "asset": "science-lab.jpeg",
            },
            {
                "title": MOTTO,
                "subtitle": "A balanced learning community",
                "body": _paragraphs("Intellectual ambition strengthened by discipline, respect, service, and strong character."),
                "button_label": "About Bil Science",
                "button_url": "/about/",
                "asset": "students-science-group.jpeg",
            },
        ],
        skip_images=skip_images,
    )
    _section(
        page,
        10,
        "rich_text",
        title="A Complete Education for a Changing World",
        subtitle="Built around potential, purpose, and possibility.",
        body=_paragraphs(
            "Every child carries extraordinary potential. Bil Science Academy develops that potential through intensive academic commitment, innovation, creativity, and strong character.",
            "Students are prepared not only to pass examinations, but to think critically, lead responsibly, solve real-world problems, and make a positive impact.",
        ),
        button_label="Discover Our Story",
        button_url="/about/",
        asset="building-exterior.jpeg",
        skip_images=skip_images,
    )
    departments = _section(
        page,
        20,
        "cards",
        title="Four Academic Departments",
        subtitle="Distinct pathways with one shared standard of excellence.",
        background_color="#f8fafc",
        extra={"item_column_class": "col-md-6 col-lg-3"},
        skip_images=skip_images,
    )
    _items(
        departments,
        [
            {"title": title, "subtitle": description, "icon_class": icon}
            for title, description, icon in ACADEMIC_DEPARTMENTS
        ],
        skip_images=skip_images,
    )
    ethos = _section(
        page,
        30,
        "cards",
        title=MOTTO,
        subtitle="A balanced learning environment where achievement is joined with responsibility.",
        extra={"item_column_class": "col-md-4"},
        skip_images=skip_images,
    )
    _items(
        ethos,
        [
            {
                "title": "Knowledge with Purpose",
                "subtitle": "Learning is treated as a responsibility: to understand deeply, ask better questions, and use knowledge well.",
                "icon_class": "fas fa-book-open",
            },
            {
                "title": "Integrity and Strong Character",
                "subtitle": "Respect, discipline, care, honesty, and consideration shape how students learn and live together.",
                "icon_class": "fas fa-hands-holding-child",
            },
            {
                "title": "Excellence through Service",
                "subtitle": "Leadership means using talent, courage, and creativity to contribute positively to society.",
                "icon_class": "fas fa-hand-holding-heart",
            },
        ],
        skip_images=skip_images,
    )
    _section(
        page,
        40,
        "rich_text",
        title="Meet House Owners",
        subtitle="From right to left in the photograph.",
        body=_paragraphs(
            "AFOLABI HOUSE (Pink) · AL-AMEEN HOUSE (Yellow) · KAREEM HOUSE (Green) · SANYAOLU HOUSE (Blue)",
            "The house system brings students together through identity, participation, teamwork, healthy competition, and shared celebration.",
        ),
        asset="main-house.jpeg",
        skip_images=skip_images,
    )
    houses = _section(
        page,
        50,
        "cards",
        title="Our Four Houses",
        subtitle="Four colours, one Bil Science Academy community.",
        background_color="#f8fafc",
        extra={"item_column_class": "col-md-6 col-lg-3"},
        skip_images=skip_images,
    )
    _items(
        houses,
        [
            {"title": f"{name} ({colour})", "subtitle": description, "asset": asset}
            for name, colour, asset, description in HOUSE_DATA
        ],
        skip_images=skip_images,
    )
    _section(
        page,
        60,
        "gallery",
        title="Life at Bil Science",
        subtitle="Learning, culture, leadership, and school community in pictures.",
        button_label="View Gallery",
        button_url="/gallery/",
        extra={"featured_only": True, "limit": 6},
        skip_images=skip_images,
    )
    _section(
        page,
        70,
        "contact",
        title="Begin Your Child's Journey Today",
        body=_paragraphs("Contact the school for admission information, enquiries, or to arrange a visit."),
        background_color="#f8fafc",
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
            "header_title": "About Bil Science Academy",
            "header_subtitle": TAGLINE,
            "meta_title": f"About | {SCHOOL_NAME}",
            "meta_description": "Read the vision, mission, values, and proprietor's welcome for Bil Science Academy.",
        },
        header_asset="building-exterior.jpeg",
        skip_images=skip_images,
    )
    _section(
        page,
        0,
        "hero",
        hero_variant="morphism",
        title="About Bil Science Academy",
        subtitle=TAGLINE,
        asset="building-exterior.jpeg",
        asset_field="background_image",
        skip_images=skip_images,
    )
    _section(
        page,
        10,
        "rich_text",
        title="Built for Intellectual Courage",
        body=_paragraphs(
            "Bil Science Academy is a co-educational school in Alagbado, Lagos.",
            "Its educational approach brings rigorous academics together with innovation, creativity, discipline, character, and preparation for global competition.",
        ),
        asset="students-science-group.jpeg",
        skip_images=skip_images,
    )
    purpose = _section(
        page,
        20,
        "cards",
        title="Our Purpose",
        background_color="#f8fafc",
        skip_images=skip_images,
    )
    _items(
        purpose,
        [
            {"title": "Vision", "subtitle": VISION, "icon_class": "fas fa-eye"},
            {"title": "Mission", "subtitle": MISSION, "icon_class": "fas fa-bullseye"},
            {"title": "Core Values", "subtitle": ", ".join(CORE_VALUES), "icon_class": "fas fa-award"},
        ],
        skip_images=skip_images,
    )
    _section(
        page,
        30,
        "rich_text",
        title="Character-Driven, Future-Focused",
        body=_paragraphs(
            "Bil Science Academy gives equal attention to intellectual growth and strong character. Students are encouraged to combine curiosity with integrity, responsibility, diligence, and service.",
            "The aim is a grounded learner who can compete globally without losing the character required to lead well.",
        ),
        asset="science-lab.jpeg",
        skip_images=skip_images,
    )
    _section(
        page,
        90,
        "rich_text",
        title="Welcome from the Proprietor",
        subtitle="A message to parents, students, and visitors.",
        body=_proprietor_speech_html(),
        asset="proprietor.jpeg",
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
            "header_subtitle": "Four pathways for the professions shaping tomorrow",
            "meta_title": f"Academics | {SCHOOL_NAME}",
            "meta_description": "Explore Science, Business, Humanities, and Informatics at Bil Science Academy.",
        },
        header_asset="science-lab.jpeg",
        skip_images=skip_images,
    )
    _section(
        page,
        0,
        "hero",
        hero_variant="morphism",
        title="Four Pathways. One Future.",
        subtitle="Academic depth, practical learning, and intelligent career preparation.",
        asset="science-lab.jpeg",
        asset_field="background_image",
        skip_images=skip_images,
    )
    departments = _section(
        page,
        10,
        "cards",
        title="Academic Departments",
        subtitle="Students develop within the pathway that best supports their strengths and ambitions.",
        background_color="#f8fafc",
        extra={"item_column_class": "col-md-6"},
        skip_images=skip_images,
    )
    _items(
        departments,
        [
            {"title": title, "subtitle": description, "icon_class": icon}
            for title, description, icon in ACADEMIC_DEPARTMENTS
        ],
        skip_images=skip_images,
    )
    _section(
        page,
        20,
        "rich_text",
        title="Beyond Examination Preparation",
        body=_bullet_list(
            (
                "Critical thinking and confident communication",
                "Real-world problem-solving and practical investigation",
                "Leadership, collaboration, and strong character",
                "Digital literacy, artificial intelligence, coding, and robotics",
                "Enterprise awareness, creativity, and career direction",
            ),
            intro="Bil Science Academy prepares students to use knowledge, not merely repeat it.",
        ),
        asset="computer-lab.jpeg",
        skip_images=skip_images,
    )
    return page


def _seed_clubs(school, *, skip_images: bool):
    page = _replace_page(
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
            "header_title": "Clubs and Student Life",
            "header_subtitle": "Discipline, confidence, expression, and discovery",
            "meta_title": f"Clubs | {SCHOOL_NAME}",
            "meta_description": "Explore clubs and student activities at Bil Science Academy.",
        },
        header_asset="main-house.jpeg",
        skip_images=skip_images,
    )
    clubs = _section(
        page,
        10,
        "cards",
        title="Student Clubs",
        subtitle="Structured activities help learners discover talent and practise leadership.",
        background_color="#f8fafc",
        extra={"item_column_class": "col-md-6 col-lg-3"},
        skip_images=skip_images,
    )
    _items(
        clubs,
        [
            {"title": title, "subtitle": description, "icon_class": icon}
            for title, description, icon in CLUBS
        ],
        skip_images=skip_images,
    )
    _section(
        page,
        20,
        "rich_text",
        title="Four Houses, One Community",
        body=_paragraphs(
            "Afolabi House (Pink), Al-Ameen House (Yellow), Kareem House (Green), and Sanyaolu House (Blue) give students a shared identity for participation and healthy competition."
        ),
        asset="main-house.jpeg",
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
            "header_subtitle": "Learning, culture, leadership, and community",
            "meta_title": f"Gallery | {SCHOOL_NAME}",
            "meta_description": "See campus, learning, and house activities at Bil Science Academy.",
        },
        header_asset="main-house.jpeg",
        skip_images=skip_images,
    )
    _section(
        page,
        10,
        "gallery",
        title="Life at Bil Science Academy",
        subtitle="Campus, laboratories, student activities, and the four school houses.",
        background_color="#f8fafc",
        skip_images=skip_images,
    )
    return page


def _seed_admissions(school, *, skip_images: bool):
    page = _replace_page(
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
            "header_title": "Admissions",
            "header_subtitle": "Begin Your Child's Journey Today",
            "meta_title": f"Admissions | {SCHOOL_NAME}",
            "meta_description": "Contact Bil Science Academy for admission information and school visits.",
        },
        header_asset="building-signage.jpeg",
        skip_images=skip_images,
    )
    _section(
        page,
        0,
        "hero",
        hero_variant="morphism",
        title="Begin Your Child's Journey Today",
        subtitle="A complete education across four future-facing departments.",
        button_label="Contact Admissions",
        button_url=f"mailto:{EMAIL}",
        asset="building-signage.jpeg",
        asset_field="background_image",
        skip_images=skip_images,
    )
    _section(
        page,
        10,
        "admissions",
        title="For Enrollment",
        subtitle=f"Call {PHONE}, send a WhatsApp message, or email {EMAIL}.",
        background_color="#f8fafc",
        skip_images=skip_images,
    )
    _section(
        page,
        20,
        "contact",
        title="Visit or Contact Bil Science Academy",
        body=_paragraphs(
            "Ask about available classes, admission requirements, fees, or arranging a visit to the school.",
            "The school office will provide the current admission steps and confirm the information your family needs.",
        ),
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
            "order": 60,
            "header_title": "School Fees",
            "header_subtitle": "Fee structure, requirements, and payment information",
            "meta_title": f"School Fees | {SCHOOL_NAME}",
            "meta_description": "Fee and payment information for Bil Science Academy.",
        },
        header_asset="computer-lab.jpeg",
        skip_images=skip_images,
    )
    _section(
        page,
        10,
        "rich_text",
        title="Fee Structure",
        subtitle="Please confirm current charges with the school office before payment.",
        body=_fee_html(),
        background_color="#f8fafc",
        skip_images=skip_images,
    )
    fee_form_title = "Bil Science Academy Fee Structure"
    matching_forms = list(
        DownloadableForm.objects.filter(
            school=school,
            title__iexact=fee_form_title,
        ).order_by("id")
    )
    form = matching_forms[0] if matching_forms else DownloadableForm(school=school)
    form.title = fee_form_title
    form.description = "Fee structure and payment information for prospective parents."
    form.active = True
    form.order = 0
    form.save()
    DownloadableForm.objects.filter(
        school=school,
        title__iexact=fee_form_title,
    ).exclude(pk=form.pk).delete()
    _install_asset(form, "document", "fee-structure.pdf", skip_images=skip_images)
    return page


@transaction.atomic
def seed_bil_science_website(school, *, skip_images: bool = False):
    """Replace the seven Bil Science public CMS pages with curated tenant content."""
    settings, profile = _seed_identity(school, skip_images=skip_images)
    proprietor = _seed_proprietor(school, skip_images=skip_images)
    gallery = _seed_gallery(school, skip_images=skip_images)
    pages = [
        _seed_home(school, skip_images=skip_images),
        _seed_about(school, skip_images=skip_images),
        _seed_academics(school, skip_images=skip_images),
        _seed_clubs(school, skip_images=skip_images),
        _seed_gallery_page(school, skip_images=skip_images),
        _seed_admissions(school, skip_images=skip_images),
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
