from django.contrib import messages
from django.core.mail import mail_admins
from django.db.models import Prefetch, Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from core.models import SchoolSettings
from .models import (
    DownloadableForm,
    Faq,
    GalleryImage,
    Inquiry,
    NewsPost,
    NewsletterSubscriber,
    WebsiteContentItem,
    WebsitePage,
    WebsiteProfile,
    WebsiteSection,
    WebsiteTeamMember,
)


def _active_school(request):
    return getattr(request, 'school', None)


def _tenant_filter(school):
    return Q(school=school) if school else Q(school__isnull=True)


def _website_profile(school):
    profile = WebsiteProfile.objects.filter(school=school).first() if school else None
    school_settings = SchoolSettings.get_for_school(school)

    if profile:
        # Keep tenant school identity authoritative even if WebsiteProfile has
        # old copied branding/contact data from a previous setup.
        profile.site_name = getattr(school_settings, 'school_name', '') or profile.site_name or school.name
        profile.tagline = profile.tagline or getattr(school_settings, 'school_motto', '') or ''
        profile.description = profile.description or profile.tagline or 'School website'
        profile.email = getattr(school, 'contact_email', '') or profile.email or ''
        profile.phone = getattr(school, 'contact_phone', '') or profile.phone or ''
        profile.address = getattr(school_settings, 'school_address', '') or profile.address or ''
        if not profile.favicon:
            profile.favicon = getattr(school_settings, 'school_logo', None)
        if not profile.default_og_image:
            profile.default_og_image = getattr(school_settings, 'school_logo', None)
        return profile, school_settings

    class ProfileFallback:
        pass

    fallback = ProfileFallback()
    fallback.school = school
    fallback.site_name = getattr(school_settings, 'school_name', '') or (school.name if school else 'School Website')
    fallback.tagline = getattr(school_settings, 'school_motto', '') or ''
    fallback.description = fallback.tagline or 'School website'
    fallback.logo = getattr(school_settings, 'school_logo', None)
    fallback.favicon = getattr(school_settings, 'school_logo', None)
    fallback.default_og_image = getattr(school_settings, 'school_logo', None)
    fallback.phone = ''
    fallback.phone_alt = ''
    fallback.whatsapp_number = ''
    fallback.email = ''
    fallback.address = getattr(school_settings, 'school_address', '') or ''
    fallback.office_hours = ''
    fallback.facebook_url = ''
    fallback.instagram_url = ''
    fallback.twitter_url = ''
    fallback.youtube_url = ''
    fallback.footer_note = ''
    fallback.display_name = fallback.site_name
    return fallback, school_settings


def _visible_pages(school):
    if not school:
        return WebsitePage.objects.none()
    return WebsitePage.objects.filter(
        school=school,
        is_published=True,
        show_in_nav=True,
    ).order_by('order', 'title')


def _page_queryset(school):
    visible_items = WebsiteContentItem.objects.filter(is_visible=True).order_by('order', 'id')
    return WebsitePage.objects.filter(school=school).prefetch_related(
        Prefetch('sections', queryset=(
            WebsiteSection.objects.filter(is_visible=True).order_by('order', 'id').prefetch_related(
                Prefetch('items', queryset=visible_items)
            )
        ))
    )


def _resolve_page(request, slug=None):
    school = _active_school(request)
    if not school:
        raise Http404('No school tenant is active for this domain.')

    queryset = _page_queryset(school)
    if slug:
        page = queryset.filter(slug=slug).first()
    else:
        page = queryset.filter(is_homepage=True).first() or queryset.filter(slug='home').first()

    if page and not page.is_published:
        raise Http404('This page is not available.')
    if page:
        return page
    if not slug:
        return None
    raise Http404('Page not found.')


def _page_context(request, page):
    school = _active_school(request)
    profile, school_settings = _website_profile(school)
    galleries = (
        GalleryImage.objects
        .filter(_tenant_filter(school))
        .exclude(image='')
        .order_by('order', '-created_at')
    )

    return {
        'active_school': school,
        'website_profile': profile,
        'school_settings': school_settings,
        'nav_pages': _visible_pages(school),
        'page': page,
        'sections': page.sections.all() if page else [],
        'gallery_images': galleries,
        'featured_gallery_images': galleries.filter(is_featured=True)[:12],
        'team_members': WebsiteTeamMember.objects.filter(_tenant_filter(school), is_visible=True).order_by('order', 'name'),
        'posts': NewsPost.objects.filter(_tenant_filter(school), published=True).order_by('-created_at')[:6],
        'faqs': Faq.objects.filter(_tenant_filter(school), published=True).order_by('order', '-created_at'),
        'forms': DownloadableForm.objects.filter(_tenant_filter(school), active=True).order_by('order', '-created_at'),
        'canonical_url': page.canonical_url if page and page.canonical_url else request.build_absolute_uri(),
    }


def home(request):
    page = _resolve_page(request)
    return render(request, 'website/cms_page.html', _page_context(request, page))


def about(request):
    page = _resolve_page(request, 'about')
    return render(request, 'website/cms_page.html', _page_context(request, page))


def admissions(request):
    page = _resolve_page(request, 'admissions')
    return render(request, 'website/cms_page.html', _page_context(request, page))


def gallery(request):
    page = _resolve_page(request, 'gallery')
    return render(request, 'website/cms_page.html', _page_context(request, page))


def page_detail(request, slug):
    page = _resolve_page(request, slug)
    return render(request, 'website/cms_page.html', _page_context(request, page))


@require_POST
def admissions_inquiry(request):
    school = _active_school(request)
    name = (request.POST.get('name') or '').strip()
    email = (request.POST.get('email') or '').strip()
    message = (request.POST.get('message') or '').strip()

    if not (name and email and message):
        messages.error(request, 'Please fill in your name, email and message.')
        return redirect(request.POST.get('next') or 'website:admissions')

    Inquiry.objects.create(school=school, name=name, email=email, message=message)
    try:
        school_name = school.name if school else 'Website'
        mail_admins(
            subject=f'New admissions inquiry - {school_name}',
            message=f'School: {school_name}\nFrom: {name} <{email}>\n\n{message}',
            fail_silently=True,
        )
    except Exception:
        pass

    messages.success(request, 'Your inquiry has been received. We will get back to you shortly.')
    return redirect(request.POST.get('next') or 'website:admissions')


@require_POST
def newsletter_subscribe(request):
    school = _active_school(request)
    email = (request.POST.get('email') or '').strip().lower()
    name = (request.POST.get('name') or '').strip()

    if not email:
        messages.error(request, 'Please provide a valid email address.')
        return redirect(request.POST.get('next') or 'website:home')

    sub, created = NewsletterSubscriber.objects.get_or_create(
        school=school,
        email=email,
        defaults={'full_name': name},
    )
    if not created and name and sub.full_name != name:
        sub.full_name = name
        sub.save(update_fields=['full_name'])

    messages.success(request, 'Subscribed successfully.')
    return redirect(request.POST.get('next') or 'website:home')


def robots_txt(request):
    sitemap_url = request.build_absolute_uri('/sitemap.xml')
    content = "\n".join([
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin/",
        "Disallow: /dashboard/",
        "Disallow: /login/",
        "Disallow: /logout/",
        "Disallow: /api/",
        "Disallow: /media/private/",
        "Disallow: /static/admin/",
        "",
        f"Sitemap: {sitemap_url}",
        "",
    ])
    return HttpResponse(content, content_type='text/plain')


def sitemap_xml(request):
    from xml.sax.saxutils import escape

    school = _active_school(request)
    urls = []
    if school:
        pages = WebsitePage.objects.filter(school=school, is_published=True).order_by('order', 'title')
        for page in pages:
            urls.append({
                'loc': request.build_absolute_uri(page.get_absolute_url()),
                'lastmod': page.updated_at.date().isoformat(),
            })
    else:
        urls.append({'loc': request.build_absolute_uri('/'), 'lastmod': ''})

    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for item in urls:
        lines.append('  <url>')
        lines.append(f"    <loc>{escape(item['loc'])}</loc>")
        if item['lastmod']:
            lines.append(f"    <lastmod>{item['lastmod']}</lastmod>")
        lines.append('    <changefreq>weekly</changefreq>')
        lines.append('  </url>')
    lines.append('</urlset>')
    return HttpResponse("\n".join(lines), content_type='application/xml')


def manifest_json(request):
    school = _active_school(request)
    profile, school_settings = _website_profile(school)
    icon_url = None
    if getattr(school_settings, 'school_logo', None):
        icon_url = request.build_absolute_uri(school_settings.school_logo.url)
    elif getattr(profile, 'logo', None):
        icon_url = request.build_absolute_uri(profile.logo.url)

    manifest = {
        'name': profile.display_name,
        'short_name': profile.display_name[:12],
        'description': profile.description or profile.tagline,
        'start_url': '/',
        'display': 'standalone',
        'background_color': '#ffffff',
        'theme_color': getattr(school_settings, 'primary_color', '#2563eb'),
        'orientation': 'portrait-primary',
        'categories': ['education', 'school'],
        'lang': 'en-NG',
        'dir': 'ltr',
        'scope': '/',
    }
    if icon_url:
        manifest['icons'] = [
            {'src': icon_url, 'sizes': '192x192', 'type': 'image/png', 'purpose': 'any maskable'},
            {'src': icon_url, 'sizes': '512x512', 'type': 'image/png', 'purpose': 'any maskable'},
        ]
    return JsonResponse(manifest)
