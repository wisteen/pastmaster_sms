import re

from django.core.exceptions import ValidationError
from django.utils import timezone


SESSION_PATTERN = re.compile(r'^\s*(\d{4})\s*[-/]\s*(\d{4})\s*$')


def normalize_session(value):
    match = SESSION_PATTERN.match(str(value or ''))
    if not match:
        raise ValidationError('Select a valid academic session such as 2025-2026.')

    start_year, end_year = (int(part) for part in match.groups())
    if end_year != start_year + 1:
        raise ValidationError('An academic session must contain consecutive years.')
    return f'{start_year}-{end_year}'


def existing_session_choices(school=None, include=None):
    from .models import Term

    queryset = Term.all_objects.all()
    if school is not None:
        queryset = queryset.filter(school=school)

    sessions = set()
    for session in queryset.values_list('session', flat=True).distinct():
        try:
            sessions.add(normalize_session(session))
        except ValidationError:
            continue

    for session in include or []:
        try:
            sessions.add(normalize_session(session))
        except ValidationError:
            continue

    return [(session, session) for session in sorted(sessions, reverse=True)]


def setup_session_choices(school=None):
    choices = dict(existing_session_choices(school))
    current_year = timezone.now().year
    for start_year in range(current_year - 3, current_year + 4):
        session = f'{start_year}-{start_year + 1}'
        choices[session] = session
    return [(session, choices[session]) for session in sorted(choices, reverse=True)]
