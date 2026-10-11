from django.core.management.base import BaseCommand, CommandError
from django.db.models import Exists, OuterRef

from core.models import ComponentResult, Result, SchoolTenant, StudentTermPlacement


class Command(BaseCommand):
    help = (
        'Report promoted learners with result terms lacking historical placements '
        'and component marks outside a recorded historical class. No data is changed.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--school',
            dest='school_slug',
            help='Limit the audit to one school slug.',
        )
        parser.add_argument(
            '--fail-on-issues',
            action='store_true',
            help='Exit with an error when review items are found.',
        )

    def handle(self, *args, **options):
        schools = SchoolTenant.objects.all()
        school_slug = (options.get('school_slug') or '').strip()
        if school_slug:
            schools = schools.filter(slug=school_slug)
            if not schools.exists():
                raise CommandError(f'No school found with slug "{school_slug}".')

        placement_for_result = StudentTermPlacement.all_objects.filter(
            student_id=OuterRef('student_id'),
            term_id=OuterRef('term_id'),
        )
        missing_placements = list(
            Result.all_objects.filter(
                student__school__in=schools,
                student__is_promoted=True,
                term__school__in=schools,
            )
            .annotate(_has_placement=Exists(placement_for_result))
            .filter(_has_placement=False)
            .values(
                'student_id',
                'student__student_id',
                'student__school__slug',
                'term_id',
                'term__name',
                'term__session',
            )
            .distinct()
            .order_by('student__school__slug', 'student__student_id', 'term_id')
        )

        mismatched_placement = StudentTermPlacement.all_objects.filter(
            student_id=OuterRef('student_id'),
            term_id=OuterRef('term_id'),
        ).exclude(school_class_id=OuterRef('component__school_class_id'))
        mismatched_marks = list(
            ComponentResult.all_objects.filter(
                student__school__in=schools,
                term__school__in=schools,
                component__school_class__school__in=schools,
            )
            .annotate(_outside_placement=Exists(mismatched_placement))
            .filter(_outside_placement=True)
            .values(
                'id',
                'student_id',
                'student__student_id',
                'student__school__slug',
                'term_id',
                'component_id',
                'component__school_class_id',
                'component__school_class__name',
            )
            .order_by('student__school__slug', 'student__student_id', 'term_id', 'id')
        )

        self.stdout.write(
            f'Promoted result terms without placements: {len(missing_placements)}'
        )
        for row in missing_placements:
            self.stdout.write(
                '  school={student__school__slug} student={student__student_id} '
                '(id={student_id}) term={term__session} {term__name} '
                '(id={term_id})'.format(**row)
            )

        self.stdout.write(
            f'Component marks outside recorded placements: {len(mismatched_marks)}'
        )
        for row in mismatched_marks:
            self.stdout.write(
                '  school={student__school__slug} student={student__student_id} '
                '(id={student_id}) term_id={term_id} mark_id={id} '
                'component_id={component_id} component_class='
                '{component__school_class__name} '
                '(id={component__school_class_id})'.format(**row)
            )

        issue_count = len(missing_placements) + len(mismatched_marks)
        if issue_count and options.get('fail_on_issues'):
            raise CommandError(
                f'Historical result audit found {issue_count} item(s) requiring review.'
            )
        if issue_count:
            self.stdout.write(self.style.WARNING(
                f'Historical result audit found {issue_count} item(s) requiring review. '
                'No records were changed.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                'Historical result audit found no placement inconsistencies.'
            ))
