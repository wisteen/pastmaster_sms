from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0023_attendance_system'),
    ]

    operations = [
        migrations.CreateModel(
            name='SystemLicense',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('school_name', models.CharField(max_length=200)),
                ('license_key', models.CharField(max_length=100, unique=True)),
                ('activation_date', models.DateField(default=django.utils.timezone.now)),
                ('expiry_date', models.DateField()),
                ('is_active', models.BooleanField(default=True)),
                ('grace_period_days', models.IntegerField(default=7)),
                ('contact_email', models.EmailField(blank=True, max_length=254)),
                ('contact_phone', models.CharField(blank=True, max_length=20)),
                ('admin_message', models.TextField(blank=True, help_text='Message to display when system is expired')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'System License',
                'verbose_name_plural': 'System Licenses',
            },
        ),
    ]
