from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from ckeditor.fields import RichTextField
from core.models_features import SchoolTenant

class NewsPost(models.Model):
    school = models.ForeignKey(SchoolTenant, on_delete=models.CASCADE, related_name='website_news', null=True, blank=True)
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    excerpt = models.TextField(blank=True)
    content = RichTextField()
    cover_image = models.ImageField(upload_to='website/news/', blank=True)
    published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)[:220]
        super().save(*args, **kwargs)

class GalleryImage(models.Model):
    school = models.ForeignKey(SchoolTenant, on_delete=models.CASCADE, related_name='website_gallery_images', null=True, blank=True)
    image = models.ImageField(upload_to='website/gallery/')
    caption = models.CharField(max_length=200, blank=True)
    is_featured = models.BooleanField(default=False)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', '-created_at']

    def __str__(self):
        return self.caption or f"Image #{self.id}"

class NewsletterSubscriber(models.Model):
    school = models.ForeignKey(SchoolTenant, on_delete=models.CASCADE, related_name='website_newsletter_subscribers', null=True, blank=True)
    email = models.EmailField()
    full_name = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['school', 'email'], name='unique_newsletter_subscriber_per_school'),
        ]

    def __str__(self):
        return self.email

class NewsletterIssue(models.Model):
    school = models.ForeignKey(SchoolTenant, on_delete=models.CASCADE, related_name='website_newsletter_issues', null=True, blank=True)
    title = models.CharField(max_length=200)
    body = RichTextField()
    created_at = models.DateTimeField(auto_now_add=True)
    sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

class Faq(models.Model):
    school = models.ForeignKey(SchoolTenant, on_delete=models.CASCADE, related_name='website_faqs', null=True, blank=True)
    question = models.CharField(max_length=255)
    answer = RichTextField()
    published = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', '-created_at']
        verbose_name = 'FAQ'
        verbose_name_plural = 'FAQs'

    def __str__(self):
        return self.question

class DownloadableForm(models.Model):
    school = models.ForeignKey(SchoolTenant, on_delete=models.CASCADE, related_name='website_forms', null=True, blank=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    document = models.FileField(upload_to='website/forms/')
    active = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', '-created_at']

    def __str__(self):
        return self.title

class Inquiry(models.Model):
    school = models.ForeignKey(SchoolTenant, on_delete=models.CASCADE, related_name='website_inquiries', null=True, blank=True)
    name = models.CharField(max_length=120)
    email = models.EmailField()
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} <{self.email}>"


class WebsiteProfile(models.Model):
    """School-wide public website settings for the active tenant domain."""
    school = models.OneToOneField(SchoolTenant, on_delete=models.CASCADE, related_name='website_profile')
    site_name = models.CharField(max_length=200, blank=True)
    tagline = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to='website/branding/', blank=True)
    favicon = models.ImageField(upload_to='website/branding/', blank=True)
    default_og_image = models.ImageField(upload_to='website/seo/', blank=True)
    phone = models.CharField(max_length=40, blank=True)
    phone_alt = models.CharField(max_length=40, blank=True)
    whatsapp_number = models.CharField(max_length=40, blank=True, help_text='Use international format, e.g. 2348030000000')
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    office_hours = models.CharField(max_length=120, blank=True)
    facebook_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    twitter_url = models.URLField(blank=True)
    youtube_url = models.URLField(blank=True)
    footer_note = models.CharField(max_length=255, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['school__name']

    def __str__(self):
        return self.site_name or self.school.name

    @property
    def display_name(self):
        return self.site_name or self.school.name


class WebsitePage(models.Model):
    PAGE_TEMPLATE_CHOICES = [
        ('standard', 'Standard content page'),
        ('gallery', 'Gallery page'),
        ('admissions', 'Admissions page'),
        ('contact', 'Contact page'),
        ('news', 'News page'),
    ]

    school = models.ForeignKey(SchoolTenant, on_delete=models.CASCADE, related_name='website_pages')
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=120, blank=True)
    nav_label = models.CharField(max_length=80, blank=True)
    template_type = models.CharField(max_length=20, choices=PAGE_TEMPLATE_CHOICES, default='standard')
    is_homepage = models.BooleanField(default=False)
    is_published = models.BooleanField(default=True)
    show_in_nav = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    header_title = models.CharField(max_length=200, blank=True)
    header_subtitle = models.CharField(max_length=255, blank=True)
    header_image = models.ImageField(upload_to='website/page_headers/', blank=True)
    meta_title = models.CharField(max_length=255, blank=True)
    meta_description = models.TextField(blank=True)
    meta_keywords = models.CharField(max_length=500, blank=True)
    og_title = models.CharField(max_length=255, blank=True)
    og_description = models.TextField(blank=True)
    og_image = models.ImageField(upload_to='website/seo/', blank=True)
    canonical_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'title']
        constraints = [
            models.UniqueConstraint(fields=['school', 'slug'], name='unique_website_page_slug_per_school'),
        ]

    def __str__(self):
        return f"{self.school} - {self.title}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)[:120]
        if self.is_homepage:
            WebsitePage.objects.filter(school=self.school, is_homepage=True).exclude(pk=self.pk).update(is_homepage=False)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        if self.is_homepage or self.slug == 'home':
            return reverse('website:home')
        if self.slug == 'about':
            return reverse('website:about')
        if self.slug == 'admissions':
            return reverse('website:admissions')
        if self.slug == 'gallery':
            return reverse('website:gallery')
        return reverse('website:page_detail', kwargs={'slug': self.slug})

    @property
    def display_nav_label(self):
        return self.nav_label or self.title


class WebsiteSection(models.Model):
    SECTION_TYPE_CHOICES = [
        ('hero', 'Hero'),
        ('rich_text', 'Rich text'),
        ('cards', 'Cards / features'),
        ('stats', 'Stats'),
        ('team', 'Team'),
        ('gallery', 'Gallery'),
        ('admissions', 'Admissions resources'),
        ('contact', 'Contact block'),
        ('news', 'News posts'),
        ('html', 'Custom HTML'),
    ]
    HERO_VARIANT_CHOICES = [
        ('full_width', 'Full-width background hero'),
        ('carousel', 'Carousel slider hero'),
        ('morphism', 'Morphism / glass panel hero'),
    ]

    page = models.ForeignKey(WebsitePage, on_delete=models.CASCADE, related_name='sections')
    section_type = models.CharField(max_length=20, choices=SECTION_TYPE_CHOICES, default='rich_text')
    hero_variant = models.CharField(max_length=20, choices=HERO_VARIANT_CHOICES, default='full_width', help_text='Used only when section type is Hero.')
    title = models.CharField(max_length=200, blank=True)
    subtitle = models.CharField(max_length=255, blank=True)
    body = RichTextField(blank=True)
    image = models.ImageField(upload_to='website/sections/', blank=True)
    background_image = models.ImageField(upload_to='website/sections/backgrounds/', blank=True)
    button_label = models.CharField(max_length=80, blank=True)
    button_url = models.CharField(max_length=255, blank=True)
    background_color = models.CharField(max_length=7, blank=True, help_text='Optional hex color, e.g. #f8fafc')
    extra = models.JSONField(default=dict, blank=True, help_text='Optional advanced settings as JSON.')
    is_visible = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f"{self.page.title} - {self.title or self.get_section_type_display()}"


class WebsiteContentItem(models.Model):
    section = models.ForeignKey(WebsiteSection, on_delete=models.CASCADE, related_name='items')
    title = models.CharField(max_length=200)
    subtitle = models.CharField(max_length=255, blank=True)
    body = RichTextField(blank=True)
    image = models.ImageField(upload_to='website/items/', blank=True)
    icon_class = models.CharField(max_length=80, blank=True, help_text='Font Awesome class, e.g. fas fa-graduation-cap')
    button_label = models.CharField(max_length=80, blank=True)
    button_url = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)
    is_visible = models.BooleanField(default=True)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return self.title


class WebsiteTeamMember(models.Model):
    school = models.ForeignKey(SchoolTenant, on_delete=models.CASCADE, related_name='website_team_members')
    name = models.CharField(max_length=160)
    role = models.CharField(max_length=120)
    photo = models.ImageField(upload_to='website/team/', blank=True)
    bio = RichTextField(blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    order = models.PositiveIntegerField(default=0)
    is_visible = models.BooleanField(default=True)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return f"{self.name} - {self.role}"
