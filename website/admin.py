from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mass_mail
from .models import (
    DownloadableForm,
    Faq,
    GalleryImage,
    Inquiry,
    NewsPost,
    NewsletterIssue,
    NewsletterSubscriber,
    WebsiteContentItem,
    WebsitePage,
    WebsiteProfile,
    WebsiteSection,
    WebsiteTeamMember,
)


class TenantWebsiteAdminMixin:
    list_filter = ('school',)
    search_fields = ()


@admin.register(NewsPost)
class NewsPostAdmin(TenantWebsiteAdminMixin, admin.ModelAdmin):
    list_display = ("title", "school", "published", "created_at")
    list_filter = ("school", "published", "created_at")
    search_fields = ("title", "excerpt")
    prepopulated_fields = {"slug": ("title",)}

@admin.register(GalleryImage)
class GalleryImageAdmin(TenantWebsiteAdminMixin, admin.ModelAdmin):
    list_display = ("thumb", "caption", "school", "is_featured", "order", "created_at")
    list_editable = ("is_featured", "order")
    list_filter = ("school", "is_featured", "created_at")

    def thumb(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="height:40px;border-radius:6px;object-fit:cover;"/>', obj.image.url)
        return "-"

@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(TenantWebsiteAdminMixin, admin.ModelAdmin):
    list_display = ("email", "school", "full_name", "is_active", "subscribed_at")
    list_filter = ("school", "is_active", "subscribed_at")
    search_fields = ("email", "full_name")

@admin.action(description="Send this issue to all active subscribers")
def send_issue(modeladmin, request, queryset):
    for issue in queryset:
        subs = NewsletterSubscriber.objects.filter(is_active=True)
        if issue.school_id:
            subs = subs.filter(school=issue.school)
        subs = subs.values_list("email", flat=True)
        if not subs:
            continue
        subject = issue.title
        # Strip basic HTML for plain-text fallback
        from django.utils.html import strip_tags
        message_plain = strip_tags(issue.body)
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@example.com')
        datatuple = [(subject, message_plain, from_email, [email]) for email in subs]
        send_mass_mail(datatuple, fail_silently=True)
        issue.sent = True
        issue.sent_at = timezone.now()
        issue.save()

@admin.register(NewsletterIssue)
class NewsletterIssueAdmin(TenantWebsiteAdminMixin, admin.ModelAdmin):
    list_display = ("title", "school", "created_at", "sent", "sent_at")
    actions = [send_issue]

@admin.register(Faq)
class FaqAdmin(TenantWebsiteAdminMixin, admin.ModelAdmin):
    list_display = ("question", "school", "published", "order", "created_at")
    list_filter = ("school", "published", "created_at")
    list_editable = ("published", "order")
    search_fields = ("question",)

@admin.register(DownloadableForm)
class DownloadableFormAdmin(TenantWebsiteAdminMixin, admin.ModelAdmin):
    list_display = ("title", "school", "active", "order", "created_at")
    list_filter = ("school", "active", "created_at")
    list_editable = ("active", "order")
    search_fields = ("title", "description")

@admin.action(description="Mark selected inquiries as processed")
def mark_processed(modeladmin, request, queryset):
    queryset.update(processed=True)

@admin.register(Inquiry)
class InquiryAdmin(TenantWebsiteAdminMixin, admin.ModelAdmin):
    list_display = ("name", "email", "school", "processed", "created_at")
    list_filter = ("school", "processed", "created_at")
    search_fields = ("name", "email", "message")
    actions = [mark_processed]


@admin.register(WebsiteProfile)
class WebsiteProfileAdmin(admin.ModelAdmin):
    list_display = ("display_name", "school", "email", "phone", "updated_at")
    list_filter = ("school",)
    search_fields = ("site_name", "school__name", "email", "phone")
    fieldsets = (
        ("School", {"fields": ("school",)}),
        ("Branding", {"fields": ("site_name", "tagline", "description", "logo", "favicon", "default_og_image")}),
        ("Contact", {"fields": ("phone", "phone_alt", "whatsapp_number", "email", "address", "office_hours")}),
        ("Social", {"fields": ("facebook_url", "instagram_url", "twitter_url", "youtube_url")}),
        ("Footer", {"fields": ("footer_note",)}),
    )


class WebsiteSectionInline(admin.TabularInline):
    model = WebsiteSection
    extra = 1
    fields = ("order", "section_type", "hero_variant", "title", "subtitle", "is_visible")
    show_change_link = True


@admin.register(WebsitePage)
class WebsitePageAdmin(admin.ModelAdmin):
    list_display = ("title", "school", "slug", "template_type", "is_homepage", "show_in_nav", "is_published", "order")
    list_filter = ("school", "template_type", "is_homepage", "show_in_nav", "is_published")
    list_editable = ("show_in_nav", "is_published", "order")
    search_fields = ("title", "slug", "nav_label", "school__name", "meta_title", "meta_description")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [WebsiteSectionInline]
    fieldsets = (
        ("Page", {"fields": ("school", "title", "slug", "nav_label", "template_type", "is_homepage", "is_published", "show_in_nav", "order")}),
        ("Header", {"fields": ("header_title", "header_subtitle", "header_image")}),
        ("SEO", {"fields": ("meta_title", "meta_description", "meta_keywords", "og_title", "og_description", "og_image", "canonical_url")}),
    )


class WebsiteContentItemInline(admin.TabularInline):
    model = WebsiteContentItem
    extra = 1
    fields = ("order", "title", "subtitle", "icon_class", "image", "button_label", "button_url", "is_visible")
    show_change_link = True


@admin.register(WebsiteSection)
class WebsiteSectionAdmin(admin.ModelAdmin):
    list_display = ("title", "page", "school", "section_type", "hero_variant", "is_visible", "order")
    list_filter = ("page__school", "section_type", "hero_variant", "is_visible")
    list_editable = ("hero_variant", "is_visible", "order")
    search_fields = ("title", "subtitle", "body", "page__title", "page__school__name")
    inlines = [WebsiteContentItemInline]
    fieldsets = (
        ("Placement", {"fields": ("page", "section_type", "hero_variant", "order", "is_visible")}),
        ("Content", {"fields": ("title", "subtitle", "body", "image", "background_image", "button_label", "button_url")}),
        ("Display", {"fields": ("background_color", "extra")}),
    )

    def school(self, obj):
        return obj.page.school


@admin.register(WebsiteContentItem)
class WebsiteContentItemAdmin(admin.ModelAdmin):
    list_display = ("title", "section", "school", "is_visible", "order")
    list_filter = ("section__page__school", "section__section_type", "is_visible")
    list_editable = ("is_visible", "order")
    search_fields = ("title", "subtitle", "body", "section__title", "section__page__title")

    def school(self, obj):
        return obj.section.page.school


@admin.register(WebsiteTeamMember)
class WebsiteTeamMemberAdmin(TenantWebsiteAdminMixin, admin.ModelAdmin):
    list_display = ("name", "role", "school", "is_visible", "order")
    list_filter = ("school", "is_visible")
    list_editable = ("is_visible", "order")
    search_fields = ("name", "role", "bio", "school__name")
