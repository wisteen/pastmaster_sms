from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('core', '0064_lesson_curriculum_optional')]

    operations = [
        migrations.AddField(
            model_name='student',
            name='promoted_from',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='students_promoted_from',
                to='core.schoolclass',
            ),
        ),
    ]


