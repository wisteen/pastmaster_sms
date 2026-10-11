from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0062_onboardingrecord_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='lessonplan',
            name='average_age',
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text='Approximate average learner age in years.',
                null=True,
                validators=[MinValueValidator(2), MaxValueValidator(30)],
            ),
        ),
        migrations.AddField(
            model_name='lessonplan',
            name='previous_knowledge',
            field=models.TextField(
                blank=True,
                help_text='Relevant knowledge or skills learners already have.',
            ),
        ),
        migrations.AddField(
            model_name='lessonplan',
            name='reference_book',
            field=models.TextField(
                blank=True,
                help_text='Textbook title, author, edition, and relevant pages.',
            ),
        ),
        migrations.AddField(
            model_name='lessonplan',
            name='week_number',
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text='Teaching week within the term or academic calendar.',
                null=True,
                validators=[MinValueValidator(1), MaxValueValidator(53)],
            ),
        ),
    ]
