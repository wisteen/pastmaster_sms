from django.db.models import Q
from django.utils.text import slugify

from .models_attendance import IDCard
from .staffing import active_staff, active_students


def tenant_card_code(school):
    """Return the stable tenant prefix used when ID cards are generated."""
    if not school:
        return ''
    school_key = f'S{school.pk}'
    school_slug = slugify(getattr(school, 'slug', '') or getattr(school, 'name', '')).replace('-', '').upper()
    if not school_slug:
        return school_key
    max_slug_length = max(0, 20 - len(school_key) - 1)
    return f'{school_key}-{school_slug[:max_slug_length]}'


def _holder_reference(value, school):
    """Extract a holder type and school ID from current or legacy card text."""
    upper_value = value.upper()
    expected_tenant = tenant_card_code(school).upper()

    if ':' in value:
        prefix, separator, remainder = value.partition(':')
        holder_type, second_separator, holder_code = remainder.partition(':')
        if separator and second_separator and holder_type.upper() in {'STUDENT', 'TEACHER', 'STAFF'}:
            if expected_tenant and prefix.upper() != expected_tenant:
                return None, None, True
            normalized_type = 'teacher' if holder_type.upper() in {'TEACHER', 'STAFF'} else 'student'
            return normalized_type, holder_code.strip(), False

    for prefix, holder_type in (('STUDENT-', 'student'), ('TEACHER-', 'teacher'), ('STAFF-', 'teacher')):
        if upper_value.startswith(prefix):
            return holder_type, value[len(prefix):].strip(), False

    if expected_tenant:
        for token, holder_type in (('-STU-', 'student'), ('-TCH-', 'teacher'), ('-STF-', 'teacher')):
            prefix = f'{expected_tenant}{token}'
            if upper_value.startswith(prefix):
                return holder_type, value[len(prefix):].strip(), False

        # A tenant-prefixed printed number must never fall back to a holder in
        # another school that happens to use the same student or employee ID.
        if upper_value.startswith('S') and any(token in upper_value for token in ('-STU-', '-TCH-', '-STF-')):
            return None, None, True

    for prefix, holder_type in (('STU-', 'student'), ('TCH-', 'teacher'), ('STF-', 'teacher')):
        if upper_value.startswith(prefix):
            return holder_type, value[len(prefix):].strip(), False

    return None, None, False


def id_cards_for_school(school=None):
    """Return ID cards with their holders, restricted to one tenant when known."""
    cards = IDCard.all_objects.select_related(
        'student__user',
        'student__school',
        'teacher__user',
        'teacher__school',
    )
    if school is not None:
        cards = cards.filter(
            Q(student__school=school) | Q(teacher__school=school)
        ).distinct()
    return cards


def resolve_id_card(
    identifier,
    *,
    school=None,
    student_only=False,
    allow_student_number=False,
    allow_teacher_number=False,
    active_only=True,
):
    """Resolve the value read from a QR/barcode without crossing school boundaries.

    Generated cards encode ``barcode_data``. Some scanners and manual-entry
    workflows submit the printed ``card_number`` or the learner's student number,
    so those supported representations are deliberately handled in one place.
    """
    value = str(identifier or '').strip()
    if not value:
        return None

    cards = id_cards_for_school(school)
    if active_only:
        student_ids = active_students(school).values_list('pk', flat=True)
        staff_ids = active_staff(school).values_list('pk', flat=True)
        cards = cards.filter(is_active=True).filter(
            Q(card_type='student', student_id__in=student_ids) |
            Q(card_type__in=['teacher', 'staff'], teacher_id__in=staff_ids)
        )
    if student_only:
        cards = cards.filter(
            card_type='student',
            student__isnull=False,
            student_id__in=active_students(school).values_list('pk', flat=True),
        )

    identity = Q(barcode_data__iexact=value) | Q(card_number__iexact=value)
    if allow_student_number:
        identity |= Q(student__student_id__iexact=value)
    if allow_teacher_number and not student_only:
        identity |= Q(teacher__employee_id__iexact=value)

    card = cards.filter(identity).order_by('pk').first()
    if card or school is None:
        return card

    holder_type, holder_code, tenant_mismatch = _holder_reference(value, school)
    if tenant_mismatch or not holder_code:
        return None
    if holder_type == 'student':
        return cards.filter(
            card_type='student',
            student__student_id__iexact=holder_code,
        ).order_by('pk').first()
    if holder_type == 'teacher' and not student_only:
        return cards.filter(
            card_type__in=['teacher', 'staff'],
            teacher__employee_id__iexact=holder_code,
        ).order_by('pk').first()

    return None
