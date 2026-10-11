from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from core.models import ClassTeacher, SchoolTenant, Subject, Teacher


class Command(BaseCommand):
    help = (
        'Compare each teacher\'s explicit subjects with subjects inherited from '
        'class assessment setup. This is a read-only audit; no data is changed.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--school',
            dest='school_slug',
            required=True,
            help='School slug to audit, for example jewels-of-calvary-school.',
        )
        parser.add_argument(
            '--fail-on-inflation',
            action='store_true',
            help='Exit with an error when the previous dashboard logic would add subjects.',
        )

    def handle(self, *args, **options):
        school_slug = options['school_slug'].strip()
        school = SchoolTenant.objects.filter(slug=school_slug).first()
        if not school:
            raise CommandError(f'No school found with slug "{school_slug}".')

        teachers = Teacher.all_objects.filter(
            school=school,
            status='active',
        ).select_related('user').prefetch_related('subjects', 'classes').order_by(
            'employee_id', 'user__first_name', 'user__last_name',
        )

        issue_count = 0
        self.stdout.write(f'School: {school.name} ({school.slug})')
        self.stdout.write(f'Active teachers: {teachers.count()}')
        for teacher in teachers:
            assigned_class_ids = list(ClassTeacher.all_objects.filter(
                teacher=teacher,
                school_class__school=school,
            ).values_list('school_class_id', flat=True))
            class_ids = set(teacher.classes.filter(school=school).values_list('id', flat=True))
            class_ids.update(assigned_class_ids)

            direct_subject_ids = set(teacher.subjects.filter(
                school=school,
                subject_type='academic',
            ).values_list('id', flat=True))
            class_subject_ids = set(Subject.all_objects.filter(
                school=school,
                subject_type='academic',
            ).filter(
                Q(resultcomponent__school_class_id__in=class_ids) |
                Q(timetable__school_class_id__in=class_ids)
            ).values_list('id', flat=True))
            inherited_extras = class_subject_ids - direct_subject_ids
            if direct_subject_ids and inherited_extras:
                issue_count += 1

            user = teacher.user
            name = user.get_full_name() or user.username
            fixed_count = len(direct_subject_ids) if direct_subject_ids else len(class_subject_ids)
            previous_count = len(direct_subject_ids | class_subject_ids)
            marker = ' REVIEW' if direct_subject_ids and inherited_extras else ''
            self.stdout.write(
                f'  {teacher.employee_id or teacher.id}: {name} | '
                f'explicit={len(direct_subject_ids)} class-derived={len(class_subject_ids)} '
                f'previous={previous_count} corrected={fixed_count} '
                f'extra={len(inherited_extras)}{marker}'
            )

        if issue_count and options.get('fail_on_inflation'):
            raise CommandError(
                f'{issue_count} teacher(s) had explicit subjects expanded by class subjects.'
            )
        if issue_count:
            self.stdout.write(self.style.WARNING(
                f'{issue_count} teacher(s) were affected by dashboard subject expansion. '
                'No records were changed.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                'No active teacher with explicit subjects was expanded by class subjects.'
            ))
