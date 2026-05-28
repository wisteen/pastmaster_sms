from django.db import transaction

from core.models import SchoolSettings
from .models import (
    GalleryImage,
    WebsiteContentItem,
    WebsitePage,
    WebsiteProfile,
    WebsiteSection,
    WebsiteTeamMember,
)


STATIC_IMAGE_BASE = "/static/new_static/images"


def _school_identity(school):
    settings = SchoolSettings.objects.filter(school=school).first()
    school_name = getattr(settings, "school_name", "") or school.name
    motto = getattr(settings, "school_motto", "") or "Raising future leaders"
    address = getattr(settings, "school_address", "") or ""
    return settings, school_name, motto, address


def _set_attrs(instance, attrs, overwrite=False):
    changed = False
    for field, value in attrs.items():
        if overwrite or not getattr(instance, field):
            if getattr(instance, field) != value:
                setattr(instance, field, value)
                changed = True
    if changed:
        instance.save()


def _page(school, slug, defaults, overwrite=False):
    page, _ = WebsitePage.objects.get_or_create(
        school=school,
        slug=slug,
        defaults=defaults,
    )
    _set_attrs(page, defaults, overwrite=overwrite)
    return page


def _section(page, order, section_type, defaults, overwrite=False):
    existing = WebsiteSection.objects.filter(page=page, order=order).order_by("id")
    section = existing.filter(section_type=section_type).first() or existing.first()
    if not section:
        section = WebsiteSection.objects.create(
            page=page,
            order=order,
            section_type=section_type,
            **defaults,
        )
    _set_attrs(section, {"section_type": section_type, **defaults}, overwrite=overwrite)
    return section


def _replace_items(section, items):
    section.items.all().delete()
    WebsiteContentItem.objects.bulk_create(
        WebsiteContentItem(section=section, order=index, **item)
        for index, item in enumerate(items)
    )


def _cards(page, order, title, subtitle, items, background_color="#ffffff", overwrite=False):
    section = _section(
        page,
        order,
        "cards",
        {
            "title": title,
            "subtitle": subtitle,
            "background_color": background_color,
            "is_visible": True,
        },
        overwrite=overwrite,
    )
    if overwrite or not section.items.exists():
        _replace_items(section, items)
    return section


def _parallax_footer(title, body, button_label="", button_url=""):
    button_html = ""
    if button_label and button_url:
        button_html = f'<a class="tenant-btn mt-3" href="{button_url}">{button_label}</a>'
    return f"""
<div style="width:100vw;margin-left:calc(50% - 50vw);margin-right:calc(50% - 50vw);min-height:380px;background-image:linear-gradient(rgba(5,12,26,.78),rgba(5,12,26,.78)),url('{STATIC_IMAGE_BASE}/bg/bg8.jpg');background-size:cover;background-position:center;background-attachment:fixed;color:#fff;display:flex;align-items:center;border-radius:0;">
  <div style="max-width:760px;margin:0 auto;text-align:center;padding:60px 18px;">
    <h2 style="font-size:clamp(32px,5vw,54px);font-weight:900;color:var(--tenant-primary);text-shadow:0 0 10px rgba(255,255,255,.95),0 0 24px rgba(255,255,255,.75);margin-bottom:16px;">{title}</h2>
    <p style="font-size:18px;line-height:1.8;color:rgba(255,255,255,.9);">{body}</p>
    {button_html}
  </div>
</div>
"""


def _home_html_about(school_name):
    return f"""
<div class="row align-items-center g-5">
  <div class="col-lg-5">
    <img src="{STATIC_IMAGE_BASE}/about/1.jpg" alt="{school_name}" class="img-fluid rounded" style="width:100%;min-height:320px;object-fit:cover;">
  </div>
  <div class="col-lg-7">
    <div style="border:1px solid var(--tenant-line);border-radius:8px;background:#fff;padding:30px;box-shadow:0 16px 40px rgba(15,23,42,.08);">
      <h2 style="font-weight:900;margin-bottom:14px;">A place where every child can grow</h2>
      <p>We provide a caring learning environment where children are guided to build strong academic foundations, good character, confidence, and practical life skills.</p>
      <p>Use this starter section as your short About Us summary, then update the text and image from Django admin.</p>
      <a class="tenant-btn mt-2" href="/about/">Learn More</a>
    </div>
  </div>
</div>
"""


def _gallery_preview_html():
    return f"""
<div class="tenant-section-title">
  <h2>Gallery</h2>
  <p>Moments from our classrooms, school life, events, and activities.</p>
</div>
<div class="row g-4">
  <div class="col-md-4"><img src="{STATIC_IMAGE_BASE}/services/1.jpg" alt="School gallery" class="img-fluid rounded" style="width:100%;height:260px;object-fit:cover;"></div>
  <div class="col-md-4"><img src="{STATIC_IMAGE_BASE}/services/2.jpg" alt="School gallery" class="img-fluid rounded" style="width:100%;height:260px;object-fit:cover;"></div>
  <div class="col-md-4"><img src="{STATIC_IMAGE_BASE}/services/3.jpg" alt="School gallery" class="img-fluid rounded" style="width:100%;height:260px;object-fit:cover;"></div>
</div>
<div class="text-center mt-4">
  <a class="tenant-btn" href="/gallery/">View More</a>
</div>
"""


def _about_intro_html(school_name, about_body):
    return f"""
<div class="row align-items-center g-5">
  <div class="col-lg-5">
    <img src="{STATIC_IMAGE_BASE}/about/3.jpg" alt="About {school_name}" class="img-fluid rounded" style="width:100%;min-height:360px;object-fit:cover;">
  </div>
  <div class="col-lg-7">
    <div style="border:1px solid var(--tenant-line);border-radius:8px;background:#fff;padding:30px;box-shadow:0 16px 40px rgba(15,23,42,.08);">
      <h2 style="font-weight:900;margin-bottom:14px;">About {school_name}</h2>
      {about_body}
    </div>
  </div>
</div>
"""


def _vision_mission_html():
    return """
<div class="row g-4">
  <div class="col-lg-6">
    <div class="tenant-card h-100"><div class="tenant-card-body">
      <span class="tenant-icon"><i class="fas fa-eye"></i></span>
      <h3>Our Vision</h3>
      <p>To help pupils and students unlock their greatest potential as they walk the path to greatness and excellence in all spheres of life.</p>
    </div></div>
  </div>
  <div class="col-lg-6">
    <div class="tenant-card h-100"><div class="tenant-card-body">
      <span class="tenant-icon"><i class="fas fa-bullseye"></i></span>
      <h3>Our Mission</h3>
      <p>It is our mission to nurture pupils and students for greatness in all spheres of life.</p>
    </div></div>
  </div>
</div>
"""


def _anthem_pledge_html(school_name):
    return f"""
<div class="row g-4">
  <div class="col-lg-6">
    <div class="tenant-card h-100"><div class="tenant-card-body">
      <span class="tenant-icon"><i class="fas fa-music"></i></span>
      <h3>Our Anthem</h3>
      <p>Add the official anthem for {school_name} here from Django admin. This placeholder is created so the section is ready for editing.</p>
    </div></div>
  </div>
  <div class="col-lg-6">
    <div class="tenant-card h-100"><div class="tenant-card-body">
      <span class="tenant-icon"><i class="fas fa-hand-holding-heart"></i></span>
      <h3>Our Pledge</h3>
      <p>Add the school pledge here. Keep it short, memorable, and aligned with the values you want learners to live by.</p>
    </div></div>
  </div>
</div>
"""


DEFAULT_ABOUT_PARAGRAPHS = """
<p>Welcome to our school, where we are committed to raising confident, responsible, and globally relevant learners for the future.</p>
<p>We provide quality education that prepares and equips children with the knowledge, skills, and values needed to excel in an ever-changing world.</p>
<p>Every journey to greatness starts with a step, and choosing the right school is one of the most important steps a family can take.</p>
"""


JEWELS_ABOUT_PARAGRAPHS = """
<p>Welcome to Jewels of Calvary Schools, where we are committed to raising wholesome children who are globally relevant for the future. We provide quality education that prepares and equips children with the knowledge, skills, and values needed to excel in an ever-changing world.</p>
<p>Since our establishment in September 2016, we have been dedicated to grooming and building our pupils and students into the best version of themselves. At Jewels of Calvary Schools, every journey to greatness starts with a step, and choosing us is the first and best step to take.</p>
<p>We offer comprehensive educational services including Creche and Daycare, Kindergarten with Montessori method, and Basic Education (Class 1-6). Our extra-curricular activities include Music Club, Ballet Dance, Coding and Robotics, Craft and Art, and Home Makers Club.</p>
<p><strong>Jewels of Calvary Schools - The Place of New Beginnings</strong></p>
"""


OFFER_ITEMS = [
    {
        "title": "Creche and Daycare Services",
        "subtitle": "Safe and nurturing environment for your little ones with professional care.",
        "icon_class": "fas fa-baby",
    },
    {
        "title": "Kindergarten - Montessori Method",
        "subtitle": "Hands-on learning approach that develops independence and critical thinking.",
        "icon_class": "fas fa-child-reaching",
    },
    {
        "title": "Basic Education (Class 1-6)",
        "subtitle": "Strong academic foundation with practical teaching methods.",
        "icon_class": "fas fa-graduation-cap",
    },
]


EXTRA_CURRICULAR_ITEMS = [
    {"title": "Music Club", "subtitle": "Building creativity, rhythm, and confidence.", "icon_class": "fas fa-music"},
    {"title": "Ballet Dance", "subtitle": "Graceful movement, discipline, and expression.", "icon_class": "fas fa-shoe-prints"},
    {"title": "Coding and Robotics", "subtitle": "Preparing students for the digital future.", "icon_class": "fas fa-robot"},
    {"title": "Craft and Art", "subtitle": "Hands-on creativity and visual expression.", "icon_class": "fas fa-palette"},
    {"title": "Home Makers Club", "subtitle": "Practical life skills for responsible living.", "icon_class": "fas fa-house-user"},
]


FACILITY_ITEMS = [
    {"title": "Spacious and Conducive Classrooms", "subtitle": "Well-ventilated learning spaces designed for comfort.", "icon_class": "fas fa-school"},
    {"title": "State-of-the-Art Playground", "subtitle": "Modern play equipment for physical development.", "icon_class": "fas fa-futbol"},
    {"title": "Standby Power Supply", "subtitle": "Uninterrupted learning environment.", "icon_class": "fas fa-bolt"},
    {"title": "Conducive School Bus Services", "subtitle": "Safe and comfortable transportation.", "icon_class": "fas fa-bus"},
    {"title": "Safe and Secured Environment", "subtitle": "Your child's safety is our priority.", "icon_class": "fas fa-shield-alt"},
    {"title": "Ballet Dance Floor Space", "subtitle": "Dedicated space for dance practice.", "icon_class": "fas fa-person-running"},
    {"title": "Healing Bay Corner", "subtitle": "First aid and health care facility.", "icon_class": "fas fa-kit-medical"},
    {"title": "Practical Teaching Methods", "subtitle": "Montessori method for effective learning.", "icon_class": "fas fa-hands-helping"},
    {"title": "Hands-on Coding and Robotics Classes", "subtitle": "Preparing students for the digital future.", "icon_class": "fas fa-laptop-code"},
]


def seed_website_for_school(school, overwrite=False, jewels_about=False):
    settings, school_name, motto, address = _school_identity(school)
    about_body = JEWELS_ABOUT_PARAGRAPHS if jewels_about else DEFAULT_ABOUT_PARAGRAPHS
    profile_defaults = {
        "site_name": school_name,
        "tagline": motto,
        "description": f"{school_name} official school website.",
        "address": address,
        "phone": getattr(school, "contact_phone", "") or "",
        "email": getattr(school, "contact_email", "") or "",
        "footer_note": "Powered by Finpalix SMS.",
    }
    if jewels_about:
        profile_defaults.update(
            {
                "site_name": "Jewels of Calvary Schools",
                "tagline": "Raising Wholesome Children",
                "description": (
                    "Jewels of Calvary Schools is committed to raising wholesome children who are globally "
                    "relevant for the future. We provide quality education that prepares and equips children "
                    "with the knowledge, skills, and values needed to excel in an ever-changing world."
                ),
                "address": "1-5 Anjorin Street, off Ikotun-Idimu Road,\nCalvary Bus Stop, Idimu, Lagos",
                "phone": "+234 803 503 0958",
                "phone_alt": "0805 417 5108",
                "email": "jewelsofcalvaryschools@gmail.com",
                "office_hours": "Mon - Fri: 7:30 AM - 3:00 PM",
                "footer_note": "All rights reserved.",
            }
        )

    with transaction.atomic():
        profile, _ = WebsiteProfile.objects.get_or_create(
            school=school,
            defaults=profile_defaults,
        )
        _set_attrs(profile, profile_defaults, overwrite=overwrite)

        home = _page(
            school,
            "home",
            {
                "title": "Home",
                "nav_label": "Home",
                "is_homepage": True,
                "is_published": True,
                "show_in_nav": True,
                "order": 0,
                "header_title": school_name,
                "header_subtitle": motto,
                "meta_title": f"{school_name} | Official Website",
                "meta_description": f"Official website for {school_name}.",
            },
            overwrite=overwrite,
        )
        hero = _section(
            home,
            0,
            "hero",
            {
                "hero_variant": "carousel",
                "title": school_name,
                "subtitle": motto,
                "button_label": "Portal Login",
                "button_url": "/role-selection/",
                "is_visible": True,
            },
            overwrite=overwrite,
        )
        if overwrite or not hero.items.exists():
            _replace_items(
                hero,
                [
                    {
                        "title": school_name,
                        "subtitle": motto,
                        "body": "<p>Welcome to our school community, where learners are nurtured for excellence.</p>",
                        "button_label": "About Us",
                        "button_url": "/about/",
                    },
                    {
                        "title": "Learning for Greatness",
                        "subtitle": "Strong academics, character, and confidence",
                        "body": "<p>We help children build knowledge, values, and practical skills for the future.</p>",
                        "button_label": "Admissions",
                        "button_url": "/admissions/",
                    },
                    {
                        "title": "A Caring School Family",
                        "subtitle": "Safe, supportive, and learner-focused",
                        "body": "<p>Our environment supports discovery, creativity, discipline, and growth.</p>",
                        "button_label": "Gallery",
                        "button_url": "/gallery/",
                    },
                    {
                        "title": "Begin the Journey",
                        "subtitle": "Your child's future starts here",
                        "body": "<p>Take the first step toward a strong educational foundation.</p>",
                        "button_label": "Contact Us",
                        "button_url": "/admissions/",
                    },
                ],
            )

        _section(
            home,
            10,
            "html",
            {
                "title": "About Us",
                "body": _home_html_about(school_name),
                "background_color": "#ffffff",
                "is_visible": True,
            },
            overwrite=overwrite,
        )
        _cards(
            home,
            20,
            f"Why {school_name}",
            "A school experience designed for the total development of every child.",
            [
                {"title": "Quality Education", "subtitle": "A balanced curriculum that builds strong academic confidence.", "icon_class": "fas fa-award"},
                {"title": "Caring Teachers", "subtitle": "Dedicated educators who guide learners with patience and purpose.", "icon_class": "fas fa-chalkboard-teacher"},
                {"title": "Safe Environment", "subtitle": "A structured and secure atmosphere for learning and growth.", "icon_class": "fas fa-shield-alt"},
                {"title": "Practical Learning", "subtitle": "Hands-on activities that make learning meaningful.", "icon_class": "fas fa-hands-helping"},
                {"title": "Future Skills", "subtitle": "Exposure to creativity, technology, leadership, and collaboration.", "icon_class": "fas fa-lightbulb"},
                {"title": "Strong Values", "subtitle": "Character formation for responsible and confident children.", "icon_class": "fas fa-heart"},
            ],
            background_color="#f8fafc",
            overwrite=overwrite,
        )
        _section(
            home,
            30,
            "gallery",
            {
                "title": "Gallery",
                "subtitle": "Moments from our classrooms, school life, events, and activities.",
                "background_color": "#ffffff",
                "button_label": "View More",
                "button_url": "/gallery/",
                "extra": {"featured_only": True, "is_featured_only": True, "limit": 3},
                "is_visible": True,
            },
            overwrite=overwrite,
        )
        _section(
            home,
            40,
            "html",
            {
                "title": "Call to Action",
                "body": _parallax_footer(
                    "Start a new beginning with us",
                    "Give your child a school experience built on excellence, care, discovery, and strong values.",
                    "Contact Admissions",
                    "/admissions/",
                ),
                "background_color": "#ffffff",
                "is_visible": True,
            },
            overwrite=overwrite,
        )
        _section(
            home,
            50,
            "team",
            {
                "title": "School Leadership",
                "subtitle": "Meet the people guiding our school vision.",
                "background_color": "#f8fafc",
                "is_visible": True,
            },
            overwrite=overwrite,
        )
        for order, name, role in [
            (0, "School Director", "Director"),
            (1, "Head Teacher", "Head Teacher"),
            (2, "Administrative Lead", "Administrator"),
        ]:
            WebsiteTeamMember.objects.get_or_create(
                school=school,
                name=name,
                defaults={"role": role, "order": order, "bio": "Update this profile from Django admin.", "is_visible": True},
            )
        _section(
            home,
            60,
            "html",
            {
                "title": "Footer Highlight",
                "body": _parallax_footer(
                    f"{school_name}",
                    "Learning, character, creativity, and leadership in a safe school community.",
                    "Visit Our Portal",
                    "/role-selection/",
                ),
                "background_color": "#ffffff",
                "is_visible": True,
            },
            overwrite=overwrite,
        )

        about = _page(
            school,
            "about",
            {
                "title": "About Us",
                "nav_label": "About",
                "is_published": True,
                "show_in_nav": True,
                "order": 10,
                "header_title": f"About {school_name}",
                "header_subtitle": motto,
                "meta_title": f"About {school_name}",
                "meta_description": f"Learn more about {school_name}.",
            },
            overwrite=overwrite,
        )
        _section(
            about,
            0,
            "hero",
            {
                "hero_variant": "morphism",
                "title": "About Us",
                "subtitle": motto,
                "body": f"<p>{school_name}</p>",
                "is_visible": True,
            },
            overwrite=overwrite,
        )
        _section(
            about,
            10,
            "html",
            {
                "title": f"About {school_name}",
                "body": _about_intro_html(school_name, about_body),
                "background_color": "#ffffff",
                "is_visible": True,
            },
            overwrite=overwrite,
        )
        _cards(about, 20, "What We Offer", "Comprehensive educational services for your child's holistic development.", OFFER_ITEMS, "#f8fafc", overwrite=overwrite)
        _cards(about, 30, "Extra-Curricular Activities", "Activities that help learners discover talent, creativity, and confidence.", EXTRA_CURRICULAR_ITEMS, "#ffffff", overwrite=overwrite)
        _cards(about, 40, "Our Facilities", "World-class infrastructure for optimal learning.", FACILITY_ITEMS, "#f8fafc", overwrite=overwrite)
        _section(
            about,
            50,
            "html",
            {
                "title": "Our Vision and Mission",
                "body": _vision_mission_html(),
                "background_color": "#ffffff",
                "is_visible": True,
            },
            overwrite=overwrite,
        )
        _section(
            about,
            60,
            "html",
            {
                "title": "Our Anthem and Pledge",
                "body": _anthem_pledge_html(school_name),
                "background_color": "#f8fafc",
                "is_visible": True,
            },
            overwrite=overwrite,
        )
        _section(
            about,
            70,
            "html",
            {
                "title": "Footer Highlight",
                "body": _parallax_footer(
                    f"{school_name}",
                    "Every journey to greatness starts with a step.",
                    "Contact Us",
                    "/admissions/",
                ),
                "background_color": "#ffffff",
                "is_visible": True,
            },
            overwrite=overwrite,
        )

        gallery = _page(
            school,
            "gallery",
            {
                "title": "Gallery",
                "nav_label": "Gallery",
                "template_type": "gallery",
                "is_published": True,
                "show_in_nav": True,
                "order": 20,
                "header_title": "Gallery",
                "header_subtitle": "Explore school life, activities, and memorable moments.",
                "meta_title": f"Gallery | {school_name}",
                "meta_description": f"Photo gallery for {school_name}.",
            },
            overwrite=overwrite,
        )
        _section(
            gallery,
            0,
            "hero",
            {
                "hero_variant": "morphism",
                "title": "Gallery",
                "subtitle": "School life in pictures",
                "is_visible": True,
            },
            overwrite=overwrite,
        )
        _section(
            gallery,
            10,
            "gallery",
            {
                "title": "Our Gallery",
                "subtitle": "Upload school pictures from Django admin to replace these placeholders.",
                "background_color": "#f8fafc",
                "is_visible": True,
            },
            overwrite=overwrite,
        )
        GalleryImage.objects.filter(school=school, image="").delete()

        admissions = _page(
            school,
            "admissions",
            {
                "title": "Admissions and Contact",
                "nav_label": "Admissions",
                "template_type": "admissions",
                "is_published": True,
                "show_in_nav": True,
                "order": 30,
                "header_title": "Admissions and Contact",
                "header_subtitle": "Reach us for admission inquiries, visits, and enrollment information.",
                "meta_title": f"Admissions and Contact | {school_name}",
                "meta_description": f"Contact and admissions information for {school_name}.",
            },
            overwrite=overwrite,
        )
        _section(
            admissions,
            0,
            "hero",
            {
                "hero_variant": "morphism",
                "title": "Admissions and Contact",
                "subtitle": "We are ready to hear from you.",
                "is_visible": True,
            },
            overwrite=overwrite,
        )
        _section(
            admissions,
            10,
            "admissions",
            {
                "title": "Contact Admissions",
                "subtitle": "Send an inquiry or visit the school office for more information.",
                "body": "<p>Use this page as both the admissions and contact page. Add admission steps, fees, required documents, office hours, and contact details from Django admin.</p>",
                "background_color": "#f8fafc",
                "is_visible": True,
            },
            overwrite=overwrite,
        )

        academics = _page(
            school,
            "academics",
            {
                "title": "Academics",
                "nav_label": "Academics",
                "template_type": "standard",
                "is_published": True,
                "show_in_nav": True,
                "order": 40,
                "header_title": "Academics",
                "header_subtitle": "A practical and balanced learning experience.",
                "meta_title": f"Academics | {school_name}",
                "meta_description": f"Academic programmes at {school_name}.",
            },
            overwrite=overwrite,
        )
        _cards(
            academics,
            10,
            "Academic Programmes",
            "Update these programmes from Django admin to match the school structure.",
            OFFER_ITEMS,
            "#f8fafc",
            overwrite=overwrite,
        )

        school_fees = _page(
            school,
            "school-fees",
            {
                "title": "School Fees",
                "nav_label": "School Fees",
                "template_type": "standard",
                "is_published": True,
                "show_in_nav": True,
                "order": 50,
                "header_title": "School Fees",
                "header_subtitle": "Fee information and payment guidance.",
                "meta_title": f"School Fees | {school_name}",
                "meta_description": f"School fees information for {school_name}.",
            },
            overwrite=overwrite,
        )
        _section(
            school_fees,
            10,
            "rich_text",
            {
                "title": "School Fees",
                "body": "<p>Add current school fee details, payment instructions, account details, and deadlines from Django admin.</p>",
                "background_color": "#f8fafc",
                "is_visible": True,
            },
            overwrite=overwrite,
        )

    return {
        "school": school,
        "pages": [home, about, gallery, admissions, academics, school_fees],
    }
