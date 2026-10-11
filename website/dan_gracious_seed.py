"""Curated public website seed for Dan-Gracious Land High School.

The supplied legacy pages were treated as inert source material.  This module
contains independently structured CMS data and does not import their markup,
styles, scripts, or template code.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from django.core.files import File
from django.db import transaction
from django.utils.html import format_html_join

from core.models import SchoolSettings
from website.models import (
    Faq,
    GalleryImage,
    WebsiteContentItem,
    WebsitePage,
    WebsiteProfile,
    WebsiteSection,
    WebsiteTeamMember,
)


DEFAULT_SCHOOL_SLUG = "dan-graciousland-schools"
ASSET_ROOT = Path(__file__).resolve().parent / "seed_assets" / "dan_gracious"

SCHOOL_NAME = "Dan-Gracious Land High School"
MOTTO = "Knowledge is wealth"
ADDRESS = "3 Balogun Avenue, Off Arobaba, Idimu, Alimosho, Lagos State, Nigeria"
PHONE = "+234 802 339 5126"
WHATSAPP = "2348023395126"
EMAIL = "dangraciouslandschool@gmail.com"
PRINCIPAL_NAME = "Pastor Juliet Olele"
DIRECTOR_NAME = "Mrs Okorafor Peace Ngozika"

PRINCIPAL_SPEECH = (
    "Welcome to Dan-Gracious Land High School. We are dedicated to nurturing young minds "
    "and building the leaders of tomorrow. Our holistic approach ensures that every student "
    "achieves their full potential in academics, morals and leadership."
)
DIRECTOR_SPEECH = (
    "At Dan-Gracious Land High School, we believe that quality education is the foundation "
    "for a better future. Our commitment is to provide an environment where every child can "
    "thrive academically, morally and spiritually."
)


def _paragraphs(*values: str) -> str:
    return str(format_html_join("", "<p>{}</p>", ((value,) for value in values if value)))


def _bullet_list(values: list[str], intro: str = "") -> str:
    prefix = _paragraphs(intro) if intro else ""
    items = format_html_join("", "<li>{}</li>", ((value,) for value in values))
    return f"{prefix}<ul>{items}</ul>"


def _sha256(stream) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def _asset_path(asset_name: str) -> Path:
    path = ASSET_ROOT / asset_name
    if not path.is_file():
        raise FileNotFoundError(f"Dan-Gracious seed asset is missing: {path}")
    return path


def _field_matches_asset(field_file, asset_path: Path) -> bool:
    if not field_file or not field_file.name:
        return False
    try:
        with field_file.open("rb") as current, asset_path.open("rb") as source:
            return _sha256(current) == _sha256(source)
    except (FileNotFoundError, OSError, ValueError):
        return False


def _install_image(instance, field_name: str, asset_name: str, *, skip_images: bool) -> bool:
    if skip_images:
        return False
    asset_path = _asset_path(asset_name)
    field_file = getattr(instance, field_name)
    if _field_matches_asset(field_file, asset_path):
        return False

    with asset_path.open("rb") as source:
        field_file.save(
            f"dan_gracious/{asset_name}",
            File(source, name=asset_name),
            save=False,
        )
    instance.save(update_fields=[field_name])
    return True


def _replace_page(school, slug: str, defaults: dict, *, header_asset: str = "", skip_images: bool):
    page, _ = WebsitePage.objects.update_or_create(
        school=school,
        slug=slug,
        defaults=defaults,
    )
    if header_asset:
        _install_image(page, "header_image", header_asset, skip_images=skip_images)
    page.sections.all().delete()
    return page


def _section(page, order: int, section_type: str, *, asset: str = "", asset_field: str = "image", skip_images: bool, **values):
    section = WebsiteSection.objects.create(
        page=page,
        order=order,
        section_type=section_type,
        is_visible=True,
        **values,
    )
    if asset:
        _install_image(section, asset_field, asset, skip_images=skip_images)
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
            _install_image(item, "image", asset, skip_images=skip_images)


def _seed_identity(school, *, skip_images: bool):
    school.contact_email = EMAIL
    school.contact_phone = PHONE
    school.save(update_fields=["contact_email", "contact_phone", "updated_at"])

    settings, _ = SchoolSettings.objects.get_or_create(
        school=school,
        defaults={
            "school_name": SCHOOL_NAME,
            "school_address": ADDRESS,
            "principal_name": PRINCIPAL_NAME,
        },
    )
    settings.school_name = SCHOOL_NAME
    settings.school_address = ADDRESS
    settings.principal_name = PRINCIPAL_NAME
    settings.proprietor_name = DIRECTOR_NAME
    settings.school_motto = MOTTO
    settings.save(
        update_fields=[
            "school_name",
            "school_address",
            "principal_name",
            "proprietor_name",
            "school_motto",
        ]
    )
    _install_image(settings, "school_logo", "logo.png", skip_images=skip_images)
    _install_image(settings, "school_seal", "seal.png", skip_images=skip_images)

    profile, _ = WebsiteProfile.objects.update_or_create(
        school=school,
        defaults={
            "site_name": SCHOOL_NAME,
            "tagline": MOTTO,
            "description": (
                "A co-educational independent secondary school established in 2013, committed "
                "to academic excellence, character formation and total child development."
            ),
            "phone": PHONE,
            "phone_alt": "",
            "whatsapp_number": WHATSAPP,
            "email": EMAIL,
            "address": ADDRESS,
            "office_hours": "",
            "footer_note": "All rights reserved.",
        },
    )
    _install_image(profile, "logo", "logo.png", skip_images=skip_images)
    _install_image(profile, "favicon", "logo.png", skip_images=skip_images)
    _install_image(profile, "default_og_image", "building.jpg", skip_images=skip_images)
    return settings, profile


def _seed_team(school, *, skip_images: bool):
    WebsiteTeamMember.objects.filter(
        school=school,
        name__in=["School Director", "Head Teacher", "Administrative Lead"],
    ).delete()

    principal, _ = WebsiteTeamMember.objects.update_or_create(
        school=school,
        name=PRINCIPAL_NAME,
        defaults={
            "role": "Principal",
            "bio": _paragraphs(PRINCIPAL_SPEECH),
            "order": 0,
            "is_visible": True,
        },
    )
    _install_image(principal, "photo", "principal.jpg", skip_images=skip_images)

    director, _ = WebsiteTeamMember.objects.update_or_create(
        school=school,
        name=DIRECTOR_NAME,
        defaults={
            "role": "Proprietor / Child's Care Director",
            "bio": _paragraphs(DIRECTOR_SPEECH),
            "order": 1,
            "is_visible": True,
        },
    )
    _install_image(director, "photo", "director.jpg", skip_images=skip_images)
    return [principal, director]


def _seed_gallery(school, *, skip_images: bool):
    gallery_data = [
        ("School campus", "building.jpg"),
        ("Learning in the classroom", "classroom.jpg"),
        ("School band and music activities", "music.jpg"),
        ("Student award presentation", "club.jpeg"),
        ("Readers are leaders", "gallery-library.jpg"),
        ("Practical baking class", "gallery-baking.jpg"),
        ("Student award recognition", "gallery-award.jpg"),
        ("Student counselling session", "gallery-counselling.jpg"),
    ]
    records = []
    for order, (caption, asset) in enumerate(gallery_data):
        image = GalleryImage.objects.filter(school=school, order=order).order_by("id").first()
        if image is None:
            image = GalleryImage.objects.create(school=school, caption=caption, order=order)
        else:
            image.caption = caption
            image.is_featured = order < 6
            image.order = order
            image.save(update_fields=["caption", "is_featured", "order"])
        if image.is_featured != (order < 6):
            image.is_featured = order < 6
            image.save(update_fields=["is_featured"])
        _install_image(image, "image", asset, skip_images=skip_images)
        records.append(image)
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
            "header_subtitle": MOTTO,
            "meta_title": f"{SCHOOL_NAME} | Quality Secondary Education in Idimu, Lagos",
            "meta_description": (
                "Dan-Gracious Land High School provides quality secondary education, character "
                "formation and total child development in Idimu, Lagos."
            ),
            "meta_keywords": "secondary school Idimu, high school Lagos, Dan-Gracious Land High School",
            "og_title": SCHOOL_NAME,
            "og_description": "Academic excellence, character formation and total child development.",
        },
        header_asset="building.jpg",
        skip_images=skip_images,
    )
    hero = _section(
        page,
        0,
        "hero",
        hero_variant="carousel",
        title=SCHOOL_NAME,
        subtitle=MOTTO,
        button_label="Admission Information",
        button_url="/admissions/",
        skip_images=skip_images,
    )
    _items(
        hero,
        [
            {
                "title": "Nurturing leaders of tomorrow",
                "subtitle": MOTTO,
                "body": _paragraphs(
                    "Quality education, academic excellence, character formation and total child development."
                ),
                "button_label": "Discover Our School",
                "button_url": "/about/",
                "asset": "building.jpg",
            },
            {
                "title": "Broad, balanced and future-focused learning",
                "subtitle": "Academic excellence",
                "body": _paragraphs(
                    "Strong academic foundations are combined with practical learning experiences."
                ),
                "button_label": "Explore Academics",
                "button_url": "/academics/",
                "asset": "classroom.jpg",
            },
            {
                "title": "A vibrant learning community",
                "subtitle": "Beyond the classroom",
                "body": _paragraphs(
                    "Sports, clubs, music, arts and societies help students develop confidence and leadership."
                ),
                "button_label": "View Gallery",
                "button_url": "/gallery/",
                "asset": "music.jpg",
            },
        ],
        skip_images=skip_images,
    )

    _section(
        page,
        10,
        "rich_text",
        title="Welcome from the Director",
        subtitle="Every child carries greatness within.",
        body=_paragraphs(
            "At Dan-Gracious Land High School, we are passionate about raising disciplined, "
            "confident and academically excellent students prepared to impact their world.",
            f"— {DIRECTOR_NAME}, Child's Care Director",
        ),
        asset="director.jpg",
        skip_images=skip_images,
    )

    identity = _section(
        page,
        20,
        "cards",
        title="Mission, Vision and Core Values",
        subtitle="The principles that guide our school community.",
        background_color="#f8fafc",
        skip_images=skip_images,
    )
    _items(
        identity,
        [
            {
                "title": "Vision",
                "subtitle": "To develop each student into a total person, adequately equipped to fit into and positively influence the larger society.",
                "icon_class": "fas fa-eye",
            },
            {
                "title": "Mission",
                "subtitle": "Providing quality education with academic excellence and developing the child physically, spiritually and academically.",
                "icon_class": "fas fa-bullseye",
            },
            {
                "title": "Core Values",
                "subtitle": "Discipline, integrity, excellence, fear of God, leadership and service.",
                "icon_class": "fas fa-shield-heart",
            },
        ],
        skip_images=skip_images,
    )

    stats = _section(
        page,
        30,
        "stats",
        title="A record of growth and achievement",
        skip_images=skip_images,
    )
    _items(
        stats,
        [
            {"title": "98%", "subtitle": "Average WAEC/NECO pass rate"},
            {"title": "500+", "subtitle": "Students across JSS and SSS"},
            {"title": "15+", "subtitle": "Sports, clubs and societies"},
            {"title": "2013", "subtitle": "Year established"},
        ],
        skip_images=skip_images,
    )

    reasons = _section(
        page,
        40,
        "cards",
        title="Why families choose Dan-Gracious Land",
        subtitle="Academic support, whole-child development and strong parent partnership.",
        skip_images=skip_images,
    )
    _items(
        reasons,
        [
            {
                "title": "Academic Excellence",
                "subtitle": "A strong culture of high performance with support for every learner.",
                "icon_class": "fas fa-award",
            },
            {
                "title": "Total Development",
                "subtitle": "Spiritual, moral, physical and leadership training through structured activities.",
                "icon_class": "fas fa-people-group",
            },
            {
                "title": "Strong Partnership",
                "subtitle": "Close collaboration with parents and guardians through regular engagement and feedback.",
                "icon_class": "fas fa-handshake",
            },
        ],
        skip_images=skip_images,
    )
    _section(
        page,
        50,
        "gallery",
        title="Campus Gallery",
        subtitle="A glimpse into learning, friendship and achievement at DGLHS.",
        button_label="View Gallery",
        button_url="/gallery/",
        extra={"featured_only": True, "limit": 6},
        background_color="#f8fafc",
        skip_images=skip_images,
    )
    _section(
        page,
        60,
        "team",
        title="School Leadership",
        subtitle="Meet the leaders guiding the school vision.",
        skip_images=skip_images,
    )
    _section(
        page,
        70,
        "contact",
        title="Contact Dan-Gracious Land High School",
        body=_paragraphs("Reach the school office for admissions, visits and general inquiries."),
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
            "header_title": "About Dan-Gracious Land High School",
            "header_subtitle": "Rooted in excellence, growing with purpose",
            "meta_title": f"About | {SCHOOL_NAME}",
            "meta_description": "Learn about the story, vision, mission, values and leadership of Dan-Gracious Land High School.",
        },
        header_asset="building.jpg",
        skip_images=skip_images,
    )
    _section(
        page,
        0,
        "hero",
        hero_variant="morphism",
        title="Rooted in excellence, growing with purpose",
        subtitle=MOTTO,
        asset="building.jpg",
        asset_field="background_image",
        skip_images=skip_images,
    )
    _section(
        page,
        10,
        "rich_text",
        title="Our Story",
        body=_paragraphs(
            "Dan-Gracious Land High School is a co-educational, independent school established in 2013.",
            "Our campus is situated in Idimu, Alimosho Local Government Area of Lagos State, in a serene and secure environment that supports serious learning.",
            "Guided by the motto ‘Knowledge is wealth’, we offer boys and girls of secondary school age a high standard of education that recognises the potential of every learner.",
            "We work closely with parents to help every student fulfil their God-given potential.",
        ),
        asset="building.jpg",
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
            {
                "title": "Vision",
                "subtitle": "To develop each student into a total person, adequately equipped to fit into and positively influence the larger society.",
                "icon_class": "fas fa-eye",
            },
            {
                "title": "Mission Statement",
                "subtitle": "Providing quality education with academic excellence, developing the child physically, spiritually and academically, and raising leaders with strong character.",
                "icon_class": "fas fa-bullseye",
            },
        ],
        skip_images=skip_images,
    )
    _section(
        page,
        30,
        "rich_text",
        title="Our Core Values",
        body=_bullet_list(
            [
                "Self-reliance, discipline, honesty, truth and patriotism.",
                "Physical fitness through sports and healthy competition.",
                "Character training through clubs, societies and mentorship.",
                "A sustained culture of excellence in teaching and learning.",
                "Moral uprightness and the fear of God.",
                "Restoring strong moral values in today’s generation.",
                "Lifting up fallen standards in academics and morals.",
                "Providing affordable, high-quality child education.",
                "Producing morally sound and spiritually inclined young people.",
            ]
        ),
        skip_images=skip_images,
    )
    _section(
        page,
        40,
        "team",
        title="Leadership Messages",
        subtitle="Words from the principal and proprietor.",
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
            "header_subtitle": "Broad, balanced and future-focused",
            "meta_title": f"Academics | {SCHOOL_NAME}",
            "meta_description": "Explore the junior and senior secondary curriculum, departments and co-curricular programmes at Dan-Gracious Land High School.",
        },
        header_asset="classroom.jpg",
        skip_images=skip_images,
    )
    _section(
        page,
        0,
        "hero",
        hero_variant="morphism",
        title="Broad, balanced and future-focused",
        subtitle="Our Curriculum",
        asset="classroom.jpg",
        asset_field="background_image",
        skip_images=skip_images,
    )
    _section(
        page,
        10,
        "rich_text",
        title="Our Curriculum",
        body=_bullet_list(
            [
                "Junior Secondary School (JSS 1–3).",
                "Senior Secondary School (SSS 1–3) with academic and career guidance.",
                "Science, Arts and Commercial departments aligned with students’ strengths and interests.",
                "Practical learning in ICT, laboratories and skill-building programmes.",
            ],
            intro="We blend strong academic foundations with practical learning experiences.",
        ),
        asset="classroom.jpg",
        skip_images=skip_images,
    )
    departments = _section(
        page,
        20,
        "cards",
        title="Academic Departments",
        subtitle="Learning pathways that support different strengths and career interests.",
        background_color="#f8fafc",
        skip_images=skip_images,
    )
    _items(
        departments,
        [
            {
                "title": "Science Department",
                "subtitle": "Physics, Chemistry and Biology supported by practical laboratory learning.",
                "asset": "classroom.jpg",
            },
            {
                "title": "Arts Department",
                "subtitle": "Literature, History, Government and Languages with emphasis on critical thinking and expression.",
                "asset": "building.jpg",
            },
            {
                "title": "Commercial Department",
                "subtitle": "Accounting, Economics, Commerce and Business Studies for future entrepreneurs and professionals.",
                "asset": "club.jpeg",
            },
        ],
        skip_images=skip_images,
    )
    stats = _section(
        page,
        30,
        "stats",
        title="Academic Achievements",
        skip_images=skip_images,
    )
    _items(
        stats,
        [
            {"title": "98%", "subtitle": "WAEC average pass rate"},
            {"title": "100%", "subtitle": "NECO pass rate in core subjects"},
            {"title": "50+", "subtitle": "University admissions yearly"},
        ],
        skip_images=skip_images,
    )
    beyond = _section(
        page,
        40,
        "cards",
        title="Beyond the Classroom",
        subtitle="Total development through sports, clubs, arts and service.",
        skip_images=skip_images,
    )
    _items(
        beyond,
        [
            {"title": "Sports", "subtitle": "Football, basketball and athletics build teamwork, discipline and resilience.", "icon_class": "fas fa-futbol"},
            {"title": "Clubs", "subtitle": "Robotics, JETS Club, Literary and Debating Society and other interest groups.", "icon_class": "fas fa-robot"},
            {"title": "Music and Arts", "subtitle": "Choir, drama and cultural groups help students express their talents.", "asset": "music.jpg"},
            {"title": "Societies", "subtitle": "Red Cross, Boys Scouts, Girls Guide and other groups build leadership and service.", "icon_class": "fas fa-people-group"},
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
            "header_subtitle": "Begin your child’s journey at Dan-Gracious Land High School",
            "meta_title": f"Admissions | {SCHOOL_NAME}",
            "meta_description": "Admission steps and inquiry information for Dan-Gracious Land High School.",
        },
        header_asset="building.jpg",
        skip_images=skip_images,
    )
    _section(
        page,
        0,
        "hero",
        hero_variant="morphism",
        title="Begin the journey",
        subtitle="Admissions",
        asset="building.jpg",
        asset_field="background_image",
        skip_images=skip_images,
    )
    steps = _section(
        page,
        10,
        "cards",
        title="How to Apply",
        subtitle="Four steps from inquiry to admission.",
        skip_images=skip_images,
    )
    _items(
        steps,
        [
            {"title": "1. Purchase Application Form", "subtitle": "Visit the school administrative office to obtain an admission form.", "icon_class": "fas fa-file-pen"},
            {"title": "2. Submit Documents", "subtitle": "Return the completed form with the birth certificate, previous results, passport photographs and other required documents.", "icon_class": "fas fa-folder-open"},
            {"title": "3. Entrance Examination", "subtitle": "The applicant sits an entrance examination on the scheduled date.", "icon_class": "fas fa-clipboard-check"},
            {"title": "4. Interview and Admission", "subtitle": "Successful candidates are invited for an interview before admission letters are issued.", "icon_class": "fas fa-user-check"},
        ],
        skip_images=skip_images,
    )
    _section(
        page,
        20,
        "rich_text",
        title="Tuition and Fees",
        body=_paragraphs(
            "The school strives to make quality child education affordable.",
            "See the School Fees page for the figures supplied for the 2025/2026 session, and confirm current charges with the school office before payment.",
        ),
        button_label="View School Fees",
        button_url="/school-fees/",
        background_color="#f8fafc",
        skip_images=skip_images,
    )
    _section(
        page,
        30,
        "admissions",
        title="Admission Inquiry",
        subtitle="Contact the school by email or WhatsApp to begin.",
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
            "header_title": "Campus Gallery",
            "header_subtitle": "Learning, friendship and achievement at DGLHS",
            "meta_title": f"Gallery | {SCHOOL_NAME}",
            "meta_description": "View classroom, activity, leadership and student-life photographs from Dan-Gracious Land High School.",
        },
        header_asset="music.jpg",
        skip_images=skip_images,
    )
    _section(
        page,
        0,
        "hero",
        hero_variant="morphism",
        title="Campus Gallery",
        subtitle="Our school community in pictures",
        asset="music.jpg",
        asset_field="background_image",
        skip_images=skip_images,
    )
    _section(
        page,
        10,
        "gallery",
        title="Life at Dan-Gracious Land",
        subtitle="Classroom learning, practical activities, counselling, music and recognition.",
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
            "header_subtitle": "Fee and payment information supplied for the 2025/2026 session",
            "meta_title": f"School Fees | {SCHOOL_NAME}",
            "meta_description": "School fee figures, bank information and compulsory requirements supplied for Dan-Gracious Land High School.",
        },
        header_asset="building.jpg",
        skip_images=skip_images,
    )
    _section(
        page,
        0,
        "hero",
        hero_variant="morphism",
        title="School Fees",
        subtitle="Confirm current charges with the school office before payment",
        asset="building.jpg",
        asset_field="background_image",
        skip_images=skip_images,
    )
    fees = _section(
        page,
        10,
        "cards",
        title="Fee Bills Supplied",
        subtitle="These figures came from the supplied 2025/2026 website information and should be confirmed before payment.",
        skip_images=skip_images,
    )
    _items(
        fees,
        [
            {
                "title": "New Student Bill — ₦150,000",
                "subtitle": "For students newly admitted into JSS 1–SSS 3.",
                "icon_class": "fas fa-user-plus",
            },
            {
                "title": "Returning Student Bill — ₦80,000",
                "subtitle": "For existing JSS 1–SSS 3 students, 1st Term 2025/2026.",
                "icon_class": "fas fa-user-graduate",
            },
        ],
        skip_images=skip_images,
    )
    bank = _section(
        page,
        20,
        "cards",
        title="Bank Account Information",
        subtitle="Verify the account with the school office before making a transfer.",
        background_color="#f8fafc",
        skip_images=skip_images,
    )
    _items(
        bank,
        [
            {
                "title": "FCMB",
                "subtitle": "Account name: Dangracious Land School LTD",
                "body": _paragraphs("Account number: 2005478300"),
                "icon_class": "fas fa-building-columns",
            }
        ],
        skip_images=skip_images,
    )
    _section(
        page,
        30,
        "rich_text",
        title="Compulsory School Requirements",
        body=_bullet_list(
            [
                "Complete school-approved textbooks.",
                "Exercise books with the school logo.",
                "A pair of black shoes.",
                "Black belt.",
                "White canvas shoes with white socks for sports.",
                "Blue or black jeans skirt for girls.",
                "Blue or black jeans trousers for boys.",
            ]
        ),
        skip_images=skip_images,
    )
    faq_section = _section(
        page,
        40,
        "cards",
        title="School Fees FAQs",
        background_color="#f8fafc",
        skip_images=skip_images,
    )
    _items(
        faq_section,
        [
            {
                "title": "What is the difference between the two bills?",
                "subtitle": "The new-student bill is for newly admitted students; the returning-student bill is for existing students continuing their studies.",
            },
            {
                "title": "When is payment due?",
                "subtitle": "Payment should be made before the resumption date of each term. Contact the school office for the applicable deadline.",
            },
            {
                "title": "Who can help with a payment issue?",
                "subtitle": f"Contact the school office on {PHONE} or email {EMAIL}.",
            },
        ],
        skip_images=skip_images,
    )
    return page


def _seed_faq_records(school):
    values = [
        (
            "What is the difference between the new and returning student bills?",
            "The new-student bill is for newly admitted students. The returning-student bill is for existing students continuing their studies.",
        ),
        (
            "When is school fee payment due?",
            "Payment should be made before the resumption date of each term. Contact the school office for the applicable deadline.",
        ),
        (
            "Who can help with a school fee payment issue?",
            f"Contact the school office on {PHONE} or email {EMAIL}.",
        ),
    ]
    records = []
    for order, (question, answer) in enumerate(values):
        record, _ = Faq.objects.update_or_create(
            school=school,
            question=question,
            defaults={"answer": _paragraphs(answer), "published": True, "order": order},
        )
        records.append(record)
    return records


@transaction.atomic
def seed_dan_gracious_website(school, *, skip_images: bool = False):
    """Replace the six public CMS pages with curated Dan-Gracious content."""
    settings, profile = _seed_identity(school, skip_images=skip_images)
    team = _seed_team(school, skip_images=skip_images)
    gallery = _seed_gallery(school, skip_images=skip_images)
    pages = [
        _seed_home(school, skip_images=skip_images),
        _seed_about(school, skip_images=skip_images),
        _seed_academics(school, skip_images=skip_images),
        _seed_admissions(school, skip_images=skip_images),
        _seed_gallery_page(school, skip_images=skip_images),
        _seed_fees(school, skip_images=skip_images),
    ]
    faqs = _seed_faq_records(school)
    return {
        "school": school,
        "settings": settings,
        "profile": profile,
        "pages": pages,
        "team": team,
        "gallery": gallery,
        "faqs": faqs,
    }
