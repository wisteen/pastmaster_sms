from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('core', '0066_apply_recorded_student_promotions')]
    operations = [
        migrations.CreateModel(
            name='StudentTermPlacement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('teacher_name', models.CharField(blank=True, max_length=255)),
                ('teacher_signature', models.ImageField(blank=True, upload_to='signatures/')),
                ('signatory_frozen', models.BooleanField(default=False)),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='term_placements', to='core.student')),
                ('term', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.term')),
                ('school_class', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.schoolclass')),
                ('class_teacher', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.teacher')),
            ],
            options={'unique_together': {('student', 'term')}},
        ),
    ]


