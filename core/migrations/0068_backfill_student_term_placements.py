from django.db import migrations
from django.db.models import F


def backfill(apps, schema_editor):
    alias = schema_editor.connection.alias
    Marks = apps.get_model('core', 'ComponentResult')
    Placement = apps.get_model('core', 'StudentTermPlacement')
    Assignment = apps.get_model('core', 'ClassTeacher')
    groups = {}
    rows = Marks.objects.using(alias).filter(
        term__school_id=F('student__school_id'),
        component__school_class__school_id=F('student__school_id'),
        component__subject__school_id=F('student__school_id'),
    ).values_list('student_id', 'term_id', 'component__school_class_id', 'student__school_id', 'student__school_class_id', 'term__result_published').distinct()
    for student_id, term_id, class_id, school_id, current_class_id, published in rows.iterator():
        groups.setdefault((student_id, term_id, school_id, current_class_id, published), set()).add(class_id)
    for (student_id, term_id, school_id, current_class_id, published), class_ids in groups.items():
        if len(class_ids) != 1:
            continue
        class_id = next(iter(class_ids))
        assignments = list(Assignment.objects.using(alias).filter(
            school_class_id=class_id, teacher__school_id=school_id,
        ).select_related('teacher__user')[:2])
        teacher = assignments[0].teacher if len(assignments) == 1 else None
        name = ' '.join(filter(None, [teacher.user.first_name, teacher.user.last_name])) if teacher else ''
        Placement.objects.using(alias).get_or_create(
            student_id=student_id, term_id=term_id,
            defaults={
                'school_class_id': class_id, 'class_teacher_id': teacher.pk if teacher else None,
                'teacher_name': name, 'teacher_signature': teacher.signature.name if teacher else '',
                'signatory_frozen': published or current_class_id != class_id,
            },
        )


class Migration(migrations.Migration):
    dependencies = [('core', '0067_student_term_placement')]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]


