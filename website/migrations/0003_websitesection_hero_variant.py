# Generated manually for configurable CMS hero layouts.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('website', '0002_tenant_website_cms'),
    ]

    operations = [
        migrations.AddField(
            model_name='websitesection',
            name='hero_variant',
            field=models.CharField(
                choices=[
                    ('full_width', 'Full-width background hero'),
                    ('carousel', 'Carousel slider hero'),
                    ('morphism', 'Morphism / glass panel hero'),
                ],
                default='full_width',
                help_text='Used only when section type is Hero.',
                max_length=20,
            ),
        ),
    ]
