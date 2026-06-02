from django.db import migrations


def normalize_remaining_term_sessions(apps, schema_editor):
    Term = apps.get_model('core', 'Term')

    for term in Term.objects.all():
        session = (term.session or '').strip().replace('/', '-')
        parts = session.split('-')
        if len(parts) != 2 or not all(part.isdigit() and len(part) == 4 for part in parts):
            continue
        if int(parts[1]) != int(parts[0]) + 1:
            continue
        conflict = Term.objects.filter(
            school_id=term.school_id,
            name=term.name,
            session=session,
        ).exclude(pk=term.pk).exists()
        if not conflict:
            Term.objects.filter(pk=term.pk).update(session=session)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0046_alter_term_name'),
    ]

    operations = [
        migrations.RunPython(normalize_remaining_term_sessions, migrations.RunPython.noop),
    ]
