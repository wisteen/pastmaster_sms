from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0070_curriculuminstallation_globaladvertisement'),
    ]

    operations = [
        migrations.AddField(
            model_name='teacher',
            name='archive_note',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='teacher',
            name='archived_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='teacher',
            name='status',
            field=models.CharField(
                choices=[
                    ('active', 'Active'),
                    ('former', 'Former Staff'),
                    ('retired', 'Retired'),
                ],
                default='active',
                max_length=20,
            ),
        ),
    ]
