# Generated manually for tenant-aware website content.

import ckeditor.fields
import django.db.models.deletion
from django.db import migrations, models


def create_default_website_pages(apps, schema_editor):
    SchoolTenant = apps.get_model('core', 'SchoolTenant')
    SchoolSettings = apps.get_model('core', 'SchoolSettings')
    WebsiteProfile = apps.get_model('website', 'WebsiteProfile')
    WebsitePage = apps.get_model('website', 'WebsitePage')
    WebsiteSection = apps.get_model('website', 'WebsiteSection')
    WebsiteContentItem = apps.get_model('website', 'WebsiteContentItem')

    for school in SchoolTenant.objects.filter(is_active=True):
        settings = SchoolSettings.objects.filter(school=school).first() or SchoolSettings.objects.filter(school__isnull=True).first()
        school_name = getattr(settings, 'school_name', '') or school.name
        tagline = getattr(settings, 'school_motto', '') or 'Learning for today and tomorrow'
        address = getattr(settings, 'school_address', '') or ''

        WebsiteProfile.objects.get_or_create(
            school=school,
            defaults={
                'site_name': school_name,
                'tagline': tagline,
                'description': f'{school_name} official school website.',
                'address': address,
                'footer_note': 'Powered by Finpalix SMS.',
            },
        )

        home, _ = WebsitePage.objects.get_or_create(
            school=school,
            slug='home',
            defaults={
                'title': 'Home',
                'nav_label': 'Home',
                'is_homepage': True,
                'order': 0,
                'header_title': school_name,
                'header_subtitle': tagline,
                'meta_title': f'{school_name} | Official Website',
                'meta_description': f'Official website for {school_name}.',
            },
        )
        hero, _ = WebsiteSection.objects.get_or_create(
            page=home,
            section_type='hero',
            order=0,
            defaults={
                'title': school_name,
                'subtitle': tagline,
                'body': '<p>Welcome to our official school website.</p>',
                'button_label': 'Portal Login',
                'button_url': '/role-selection/',
            },
        )
        cards, _ = WebsiteSection.objects.get_or_create(
            page=home,
            section_type='cards',
            order=10,
            defaults={
                'title': 'Our School',
                'subtitle': 'Update these sections from Django admin.',
                'background_color': '#f8fafc',
            },
        )
        for order, title, subtitle, icon in [
            (0, 'Academics', 'Manage academic information and highlights.', 'fas fa-book-open'),
            (1, 'Admissions', 'Share enrollment details and requirements.', 'fas fa-user-plus'),
            (2, 'Community', 'Showcase school life, events, and achievements.', 'fas fa-users'),
        ]:
            WebsiteContentItem.objects.get_or_create(
                section=cards,
                title=title,
                defaults={'order': order, 'subtitle': subtitle, 'icon_class': icon},
            )

        about, _ = WebsitePage.objects.get_or_create(
            school=school,
            slug='about',
            defaults={
                'title': 'About Us',
                'nav_label': 'About',
                'order': 10,
                'header_title': f'About {school_name}',
                'meta_title': f'About {school_name}',
                'meta_description': f'Learn more about {school_name}.',
            },
        )
        WebsiteSection.objects.get_or_create(
            page=about,
            section_type='rich_text',
            order=0,
            defaults={
                'title': f'About {school_name}',
                'body': '<p>Edit this page from Django admin to add the school history, mission, vision, and values.</p>',
            },
        )

        admissions, _ = WebsitePage.objects.get_or_create(
            school=school,
            slug='admissions',
            defaults={
                'title': 'Admissions',
                'nav_label': 'Admissions',
                'template_type': 'admissions',
                'order': 20,
                'header_title': 'Admissions',
                'meta_title': f'Admissions | {school_name}',
                'meta_description': f'Admissions information for {school_name}.',
            },
        )
        WebsiteSection.objects.get_or_create(
            page=admissions,
            section_type='admissions',
            order=0,
            defaults={
                'title': 'Admissions',
                'subtitle': 'Use this page for admission requirements, forms, and inquiries.',
                'body': '<p>Add admission steps, fees, required documents, and enrollment instructions here.</p>',
            },
        )

        gallery, _ = WebsitePage.objects.get_or_create(
            school=school,
            slug='gallery',
            defaults={
                'title': 'Gallery',
                'nav_label': 'Gallery',
                'template_type': 'gallery',
                'order': 30,
                'header_title': 'Gallery',
                'meta_title': f'Gallery | {school_name}',
                'meta_description': f'Photo gallery for {school_name}.',
            },
        )
        WebsiteSection.objects.get_or_create(
            page=gallery,
            section_type='gallery',
            order=0,
            defaults={'title': 'Gallery', 'subtitle': 'Add school pictures from Django admin.'},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0041_alter_attendancesession_unique_together_and_more'),
        ('website', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='downloadableform',
            name='school',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='website_forms', to='core.schooltenant'),
        ),
        migrations.AddField(
            model_name='faq',
            name='school',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='website_faqs', to='core.schooltenant'),
        ),
        migrations.AddField(
            model_name='galleryimage',
            name='school',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='website_gallery_images', to='core.schooltenant'),
        ),
        migrations.AddField(
            model_name='inquiry',
            name='school',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='website_inquiries', to='core.schooltenant'),
        ),
        migrations.AddField(
            model_name='newsletterissue',
            name='school',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='website_newsletter_issues', to='core.schooltenant'),
        ),
        migrations.AddField(
            model_name='newslettersubscriber',
            name='school',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='website_newsletter_subscribers', to='core.schooltenant'),
        ),
        migrations.AlterField(
            model_name='newslettersubscriber',
            name='email',
            field=models.EmailField(max_length=254),
        ),
        migrations.AddField(
            model_name='newspost',
            name='school',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='website_news', to='core.schooltenant'),
        ),
        migrations.CreateModel(
            name='WebsiteProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('site_name', models.CharField(blank=True, max_length=200)),
                ('tagline', models.CharField(blank=True, max_length=255)),
                ('description', models.TextField(blank=True)),
                ('logo', models.ImageField(blank=True, upload_to='website/branding/')),
                ('favicon', models.ImageField(blank=True, upload_to='website/branding/')),
                ('default_og_image', models.ImageField(blank=True, upload_to='website/seo/')),
                ('phone', models.CharField(blank=True, max_length=40)),
                ('phone_alt', models.CharField(blank=True, max_length=40)),
                ('whatsapp_number', models.CharField(blank=True, help_text='Use international format, e.g. 2348030000000', max_length=40)),
                ('email', models.EmailField(blank=True, max_length=254)),
                ('address', models.TextField(blank=True)),
                ('office_hours', models.CharField(blank=True, max_length=120)),
                ('facebook_url', models.URLField(blank=True)),
                ('instagram_url', models.URLField(blank=True)),
                ('twitter_url', models.URLField(blank=True)),
                ('youtube_url', models.URLField(blank=True)),
                ('footer_note', models.CharField(blank=True, max_length=255)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('school', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='website_profile', to='core.schooltenant')),
            ],
            options={
                'ordering': ['school__name'],
            },
        ),
        migrations.CreateModel(
            name='WebsitePage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('slug', models.SlugField(blank=True, max_length=120)),
                ('nav_label', models.CharField(blank=True, max_length=80)),
                ('template_type', models.CharField(choices=[('standard', 'Standard content page'), ('gallery', 'Gallery page'), ('admissions', 'Admissions page'), ('contact', 'Contact page'), ('news', 'News page')], default='standard', max_length=20)),
                ('is_homepage', models.BooleanField(default=False)),
                ('is_published', models.BooleanField(default=True)),
                ('show_in_nav', models.BooleanField(default=True)),
                ('order', models.PositiveIntegerField(default=0)),
                ('header_title', models.CharField(blank=True, max_length=200)),
                ('header_subtitle', models.CharField(blank=True, max_length=255)),
                ('header_image', models.ImageField(blank=True, upload_to='website/page_headers/')),
                ('meta_title', models.CharField(blank=True, max_length=255)),
                ('meta_description', models.TextField(blank=True)),
                ('meta_keywords', models.CharField(blank=True, max_length=500)),
                ('og_title', models.CharField(blank=True, max_length=255)),
                ('og_description', models.TextField(blank=True)),
                ('og_image', models.ImageField(blank=True, upload_to='website/seo/')),
                ('canonical_url', models.URLField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='website_pages', to='core.schooltenant')),
            ],
            options={
                'ordering': ['order', 'title'],
            },
        ),
        migrations.CreateModel(
            name='WebsiteSection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('section_type', models.CharField(choices=[('hero', 'Hero'), ('rich_text', 'Rich text'), ('cards', 'Cards / features'), ('stats', 'Stats'), ('team', 'Team'), ('gallery', 'Gallery'), ('admissions', 'Admissions resources'), ('contact', 'Contact block'), ('news', 'News posts'), ('html', 'Custom HTML')], default='rich_text', max_length=20)),
                ('title', models.CharField(blank=True, max_length=200)),
                ('subtitle', models.CharField(blank=True, max_length=255)),
                ('body', ckeditor.fields.RichTextField(blank=True)),
                ('image', models.ImageField(blank=True, upload_to='website/sections/')),
                ('background_image', models.ImageField(blank=True, upload_to='website/sections/backgrounds/')),
                ('button_label', models.CharField(blank=True, max_length=80)),
                ('button_url', models.CharField(blank=True, max_length=255)),
                ('background_color', models.CharField(blank=True, help_text='Optional hex color, e.g. #f8fafc', max_length=7)),
                ('extra', models.JSONField(blank=True, default=dict, help_text='Optional advanced settings as JSON.')),
                ('is_visible', models.BooleanField(default=True)),
                ('order', models.PositiveIntegerField(default=0)),
                ('page', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sections', to='website.websitepage')),
            ],
            options={
                'ordering': ['order', 'id'],
            },
        ),
        migrations.CreateModel(
            name='WebsiteTeamMember',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=160)),
                ('role', models.CharField(max_length=120)),
                ('photo', models.ImageField(blank=True, upload_to='website/team/')),
                ('bio', ckeditor.fields.RichTextField(blank=True)),
                ('email', models.EmailField(blank=True, max_length=254)),
                ('phone', models.CharField(blank=True, max_length=40)),
                ('order', models.PositiveIntegerField(default=0)),
                ('is_visible', models.BooleanField(default=True)),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='website_team_members', to='core.schooltenant')),
            ],
            options={
                'ordering': ['order', 'name'],
            },
        ),
        migrations.CreateModel(
            name='WebsiteContentItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('subtitle', models.CharField(blank=True, max_length=255)),
                ('body', ckeditor.fields.RichTextField(blank=True)),
                ('image', models.ImageField(blank=True, upload_to='website/items/')),
                ('icon_class', models.CharField(blank=True, help_text='Font Awesome class, e.g. fas fa-graduation-cap', max_length=80)),
                ('button_label', models.CharField(blank=True, max_length=80)),
                ('button_url', models.CharField(blank=True, max_length=255)),
                ('order', models.PositiveIntegerField(default=0)),
                ('is_visible', models.BooleanField(default=True)),
                ('section', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='website.websitesection')),
            ],
            options={
                'ordering': ['order', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='newslettersubscriber',
            constraint=models.UniqueConstraint(fields=('school', 'email'), name='unique_newsletter_subscriber_per_school'),
        ),
        migrations.AddConstraint(
            model_name='websitepage',
            constraint=models.UniqueConstraint(fields=('school', 'slug'), name='unique_website_page_slug_per_school'),
        ),
        migrations.RunPython(create_default_website_pages, migrations.RunPython.noop),
    ]
