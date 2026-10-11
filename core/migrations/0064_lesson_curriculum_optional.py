from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0063_curriculum_item_undo_window'),
    ]

    operations = [
        migrations.AlterField(
            model_name='learningobjective',
            name='curriculum',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='learning_objectives',
                to='core.curriculum',
            ),
        ),
        migrations.AlterField(
            model_name='lessonplan',
            name='curriculum',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to='core.curriculum',
            ),
        ),
        migrations.AlterField(
            model_name='lessonnote',
            name='curriculum',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to='core.curriculum',
            ),
        ),
    ]
