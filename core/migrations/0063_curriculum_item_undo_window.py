from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0062_lessonplan_teaching_context'),
    ]

    operations = [
        migrations.AddField(
            model_name='learningobjective',
            name='pending_deletion_at',
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name='syllabuscontent',
            name='pending_deletion_at',
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
    ]
