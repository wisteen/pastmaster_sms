from datetime import datetime, time
from html import escape

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .management import lagos_basic_2026_2027_data as primary_data
from .management import lagos_basic_6_2026_2027_data as basic_six_data
from .management import lagos_secondary_2026_2027_data as secondary_data
from .models import (
    AcademicEvent,
    Curriculum,
    CurriculumInstallation,
    Holiday,
    LearningObjective,
    SchoolTenant,
    Subject,
    SyllabusContent,
    Term,
)
from .tenant_context import clear_current_school, get_current_school, set_current_school


ACADEMIC_YEAR = primary_data.ACADEMIC_YEAR
TERM_NAMES = primary_data.TERM_NAMES
SOURCE_LINKS = (
    ('NERDC curriculum', primary_data.CURRICULUM_SOURCE_URL),
    ('Federal subject offering', primary_data.SUBJECT_OFFERING_SOURCE_URL),
    ('Lagos calendar reference', primary_data.CALENDAR_SOURCE_URL),
)

LEVEL_CHOICES = (
    ('Basic 1', 'Basic 1'),
    ('Basic 2', 'Basic 2'),
    ('Basic 3', 'Basic 3'),
    ('Basic 4', 'Basic 4'),
    ('Basic 5', 'Basic 5'),
    ('Basic 6', 'Basic 6'),
    ('JSS 1', 'JSS 1'),
    ('JSS 2', 'JSS 2'),
    ('JSS 3', 'JSS 3'),
    ('SS 1', 'SS 1'),
    ('SS 2', 'SS 2'),
    ('SS 3', 'SS 3'),
)


class CurriculumInstallError(Exception):
    pass


def _level_definition(level):
    if level.startswith('Basic '):
        grade = int(level.split()[-1])
        data = basic_six_data if grade == 6 else primary_data
    else:
        grade = level
        data = secondary_data
    return {
        'level': level,
        'grade': grade,
        'subjects': data.SUBJECTS,
        'grade_subjects': data.GRADE_SUBJECTS[grade],
        'topic_banks': data.TOPIC_BANKS,
    }


def _validate_requested_data(levels):
    primary_needed = any(level in {f'Basic {number}' for number in range(1, 6)} for level in levels)
    if primary_needed:
        primary_data.validate_seed_data()
    if 'Basic 6' in levels:
        basic_six_data.validate_seed_data()
    if any(level.startswith(('JSS ', 'SS ')) for level in levels):
        secondary_data.validate_seed_data()


def _provider_title(provider, level):
    prefix = 'Lagos State' if provider == 'lagos' else 'Federal NERDC'
    return f'{prefix} {level} Curriculum'


def _provider_description(provider, level):
    if provider == 'lagos':
        source = 'the revised Federal/NERDC curriculum and Lagos State guidance'
    else:
        source = 'the revised Federal/NERDC curriculum'
    optional_note = (
        'The catalogue includes optional and alternative subjects; the school should '
        'retain and assign only the offerings it teaches.'
    )
    return f'{level} working curriculum aligned with {source} for {ACADEMIC_YEAR}. {optional_note}'


def _objective_description(level, term_name, topics):
    topic_text = ', '.join(topics[:-1]) + f', and {topics[-1]}'
    return (
        f'By the end of {term_name}, {level} learners should be able to identify, '
        f'explain, demonstrate, and apply age-appropriate knowledge and skills relating '
        f'to {topic_text}; communicate what they learned; and complete guided practical '
        'and written assessment tasks.'
    )


def _syllabus_html(term_name, topics):
    week_ranges = ('Weeks 1-2', 'Weeks 3-5', 'Weeks 6-8', 'Weeks 9-11')
    rows = ''.join(
        f'<li><strong>{week_range}:</strong> {escape(topic.title())}</li>'
        for week_range, topic in zip(week_ranges, topics)
    )
    return (
        f'<h3>{escape(term_name)}</h3><ol>{rows}'
        '<li><strong>Week 12:</strong> Revision, practical application, remediation '
        'and end-of-term assessment.</li></ol>'
    )


def _subject_for_code(school, code, name, counts):
    by_code = Subject.all_objects.filter(school=school, code=code).first()
    by_name = Subject.all_objects.filter(school=school, name=name).first()
    if by_code and by_name and by_code.pk != by_name.pk:
        raise CurriculumInstallError(
            f"Subject conflict: code {code} and name '{name}' belong to different records. "
            'Ask the school administrator to resolve the duplicate before installing.'
        )
    subject = by_code or by_name
    if subject:
        counts['subjects_reused'] += 1
        return subject
    counts['subjects_created'] += 1
    return Subject.all_objects.create(
        school=school,
        code=code,
        name=name,
        subject_type='academic',
        pass_mark=50,
    )


def _install_level(school, creator, provider, definition, counts):
    subjects = {}
    for code in definition['grade_subjects']:
        subjects[code] = _subject_for_code(
            school,
            code,
            definition['subjects'][code],
            counts,
        )

    title = _provider_title(provider, definition['level'])
    curriculum, created = Curriculum.all_objects.get_or_create(
        school=school,
        title=title,
        academic_year=ACADEMIC_YEAR,
        defaults={
            'description': _provider_description(provider, definition['level']),
            'created_by': creator,
            'is_published': False,
        },
    )
    counts['curricula_created' if created else 'curricula_reused'] += 1
    curriculum.subjects.add(*subjects.values())

    for subject_order, code in enumerate(definition['grade_subjects'], start=1):
        subject = subjects[code]
        canonical_subject_name = definition['subjects'][code]
        all_topics = definition['topic_banks'][code][definition['grade']]
        for term_index, term_name in enumerate(TERM_NAMES, start=1):
            topics = all_topics[(term_index - 1) * 4:term_index * 4]
            order = subject_order * 10 + term_index
            _, objective_created = LearningObjective.all_objects.get_or_create(
                curriculum=curriculum,
                title=f'{term_name} - {canonical_subject_name} competencies',
                defaults={
                    'description': _objective_description(definition['level'], term_name, topics),
                    'subject': subject,
                    'grade_level': definition['level'],
                    'order': order,
                },
            )
            counts['objectives_created' if objective_created else 'objectives_reused'] += 1

            _, syllabus_created = SyllabusContent.all_objects.get_or_create(
                curriculum=curriculum,
                subject=subject,
                order=order,
                defaults={'content': _syllabus_html(term_name, topics)},
            )
            counts['syllabus_created' if syllabus_created else 'syllabus_reused'] += 1

    if not curriculum.is_published and curriculum.learning_objectives.exists():
        curriculum.is_published = True
        curriculum.save(update_fields=['is_published', 'updated_at'])


def _aware_at(day, clock_time):
    value = datetime.combine(day, clock_time)
    return timezone.make_aware(value, timezone.get_current_timezone())


def _install_lagos_calendar(school, creator, activate_first_term, counts):
    terms = {}
    for row in primary_data.TERMS:
        term, created = Term.all_objects.get_or_create(
            school=school,
            name=row['name'],
            session=ACADEMIC_YEAR,
            defaults={
                'start_date': row['start_date'],
                'end_date': row['end_date'],
                'vacation_date': row['vacation_date'],
                'resumption_date': row['resumption_date'],
                'school_opened_days': row['school_opened_days'],
                'is_active': False,
            },
        )
        terms[row['name']] = term
        counts['terms_created' if created else 'terms_reused'] += 1

    if activate_first_term:
        first_term = terms['First Term']
        Term.all_objects.filter(school=school, is_active=True).exclude(pk=first_term.pk).update(is_active=False)
        if not first_term.is_active:
            first_term.is_active = True
            first_term.save(update_fields=['is_active'])

    for title, event_type, start, end, term_name, description in primary_data.EVENTS:
        event_title = f'Lagos {ACADEMIC_YEAR} - {title}'
        event = AcademicEvent.all_objects.filter(
            school=school,
            title=event_title,
            academic_year=ACADEMIC_YEAR,
        ).order_by('pk').first()
        if event:
            counts['events_reused'] += 1
        else:
            event = AcademicEvent.all_objects.create(
                school=school,
                title=event_title,
                academic_year=ACADEMIC_YEAR,
                description=description,
                event_type=event_type,
                start_date=_aware_at(start, time.min),
                end_date=_aware_at(end, time.max),
                is_recurring=False,
                recurrence_pattern='',
                created_by=creator,
            )
            counts['events_created'] += 1
        if term_name:
            event.terms.add(terms[term_name])

    for name, holiday_date in primary_data.HOLIDAYS:
        _, created = Holiday.all_objects.get_or_create(
            school=school,
            name=name,
            date=holiday_date,
            academic_year=ACADEMIC_YEAR,
            defaults={'is_recurring': False},
        )
        counts['holidays_created' if created else 'holidays_reused'] += 1


def install_curriculum_bundle(
    *, school, creator, provider, levels, include_calendar=False, activate_first_term=False,
):
    """Install selected curriculum levels atomically without overwriting school edits."""

    valid_levels = {value for value, _ in LEVEL_CHOICES}
    levels = list(dict.fromkeys(levels or []))
    if provider not in {'federal', 'lagos'}:
        raise CurriculumInstallError('Choose Federal / NERDC or Lagos State.')
    if not levels or any(level not in valid_levels for level in levels):
        raise CurriculumInstallError('Choose at least one valid class level.')
    if include_calendar and provider != 'lagos':
        raise CurriculumInstallError('The harmonised calendar is available only with Lagos State.')
    if activate_first_term and not include_calendar:
        raise CurriculumInstallError('Install the Lagos calendar before activating its First Term.')
    if not school or not SchoolTenant.objects.filter(pk=school.pk, is_active=True).exists():
        raise CurriculumInstallError('An active school is required.')

    try:
        _validate_requested_data(levels)
    except (KeyError, TypeError, ValueError) as exc:
        raise CurriculumInstallError(str(exc)) from exc

    counts = {
        key: 0 for key in (
            'subjects_created', 'subjects_reused', 'curricula_created', 'curricula_reused',
            'objectives_created', 'objectives_reused', 'syllabus_created', 'syllabus_reused',
            'terms_created', 'terms_reused', 'events_created', 'events_reused',
            'holidays_created', 'holidays_reused',
        )
    }

    previous_school = get_current_school()
    set_current_school(school)
    try:
        with transaction.atomic():
            locked_school = SchoolTenant.objects.select_for_update().get(pk=school.pk, is_active=True)
            for level in levels:
                _install_level(locked_school, creator, provider, _level_definition(level), counts)
            if include_calendar:
                _install_lagos_calendar(locked_school, creator, activate_first_term, counts)
            CurriculumInstallation.all_objects.create(
                school=locked_school,
                provider=provider,
                levels=levels,
                academic_year=ACADEMIC_YEAR,
                installed_by=creator,
                include_calendar=include_calendar,
                activated_first_term=activate_first_term,
                summary=counts,
            )
    except CurriculumInstallError:
        raise
    except (ValidationError, SchoolTenant.DoesNotExist) as exc:
        raise CurriculumInstallError(str(exc)) from exc
    finally:
        if previous_school is None:
            clear_current_school()
        else:
            set_current_school(previous_school)

    return counts
