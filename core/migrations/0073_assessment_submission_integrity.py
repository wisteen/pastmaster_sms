from django.db import migrations, models
from django.db.models import Count, F
from django.utils import timezone


def preserve_existing_grades(apps, schema_editor):
    Answer = apps.get_model('core', 'QuizAnswer')
    Submission = apps.get_model('core', 'AssignmentSubmission')
    alias = schema_editor.connection.alias
    answers = Answer.objects.using(alias)
    duplicates = answers.values('attempt_id', 'question_id').annotate(n=Count('id')).filter(n__gt=1)
    for row in list(duplicates):
        records = answers.filter(attempt_id=row['attempt_id'], question_id=row['question_id'])
        keep = records.order_by('-id').first()
        records.exclude(pk=keep.pk).delete()
    answers.filter(question__question_type='theory', attempt__is_graded=True).update(graded_at=timezone.now())
    answers.filter(question__question_type='theory', manual_score__gt=0, graded_at__isnull=True).update(graded_at=timezone.now())
    submissions = Submission.objects.using(alias)
    submissions.update(updated_at=F('submitted_at'))
    submissions.filter(score__isnull=False).update(raw_score=F('score'), graded_at=timezone.now())


class Migration(migrations.Migration):
    dependencies = [('core', '0072_active_staff_roles')]
    operations = [
        migrations.AddField(model_name='quizanswer', name='graded_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='assignmentsubmission', name='updated_at', field=models.DateTimeField(auto_now=True)),
        migrations.AddField(model_name='assignmentsubmission', name='graded_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='assignmentsubmission', name='raw_score', field=models.DecimalField(blank=True, null=True, max_digits=5, decimal_places=2)),
        migrations.RunPython(preserve_existing_grades, migrations.RunPython.noop),
        migrations.AddConstraint(model_name='quizanswer', constraint=models.UniqueConstraint(fields=('attempt', 'question'), name='unique_quiz_answer')),
    ]
