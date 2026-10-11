from django.db import migrations


def apply_recorded_promotions(apps, schema_editor):
    Student = apps.get_model('core', 'Student')
    students = Student.objects.filter(is_promoted=True, promoted_to__isnull=False)
    for student in students.iterator():
        if student.school_class_id == student.promoted_to_id:
            continue
        student.promoted_from_id = student.school_class_id
        student.school_class_id = student.promoted_to_id
        student.save(update_fields=['promoted_from', 'school_class'])


def reverse_recorded_promotions(apps, schema_editor):
    Student = apps.get_model('core', 'Student')
    for student in Student.objects.filter(promoted_from__isnull=False).iterator():
        if student.school_class_id != student.promoted_to_id:
            continue
        student.school_class_id = student.promoted_from_id
        student.save(update_fields=['school_class'])


class Migration(migrations.Migration):
    dependencies = [('core', '0065_student_promoted_from_and_apply_promotions')]

    operations = [
        migrations.RunPython(apply_recorded_promotions, reverse_recorded_promotions),
    ]


