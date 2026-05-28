from datetime import date, timedelta

from django.utils import timezone

from .models import SchoolSettings, SchoolTenant, Student
from .models_biodata import StaffBioData


ROLE_DASHBOARDS = {
    'super_admin': {
        'role': 'super_admin',
        'label': 'Admin Dashboard',
        'icon': 'fas fa-user-shield',
    },
    'subject_teacher': {
        'role': 'subject_teacher',
        'label': 'Teacher Dashboard',
        'icon': 'fas fa-chalkboard-teacher',
    },
    'class_teacher': {
        'role': 'class_teacher',
        'label': 'Class Teacher Dashboard',
        'icon': 'fas fa-user-tie',
    },
    'accountant': {
        'role': 'accountant',
        'label': 'Accounting',
        'icon': 'fas fa-calculator',
    },
    'bursar': {
        'role': 'bursar',
        'label': 'Bursary',
        'icon': 'fas fa-cash-register',
    },
    'librarian': {
        'role': 'librarian',
        'label': 'Library',
        'icon': 'fas fa-book',
    },
    'security': {
        'role': 'security',
        'label': 'Security',
        'icon': 'fas fa-shield-alt',
    },
    'student': {
        'role': 'student',
        'label': 'Student Dashboard',
        'icon': 'fas fa-user-graduate',
    },
    'parent': {
        'role': 'parent',
        'label': 'Parent Dashboard',
        'icon': 'fas fa-users',
    },
}


def _next_birthday(birth_date, today):
    try:
        next_date = birth_date.replace(year=today.year)
    except ValueError:
        next_date = date(today.year, 2, 28)
    if next_date < today:
        try:
            next_date = birth_date.replace(year=today.year + 1)
        except ValueError:
            next_date = date(today.year + 1, 2, 28)
    return next_date


def _birthday_label(days_until):
    if days_until == 0:
        return 'Today'
    if days_until == 1:
        return 'Tomorrow'
    return f'In {days_until} days'


def _portal_birthdays(active_school):
    if not active_school:
        return []

    today = timezone.localdate()
    end_date = today + timedelta(days=30)
    birthdays = []

    try:
        students = Student.all_objects.filter(
            school=active_school,
            date_of_birth__isnull=False,
        ).select_related('user', 'school_class', 'bio_data')
        for student in students:
            birth_date = getattr(getattr(student, 'bio_data', None), 'date_of_birth', None) or student.date_of_birth
            next_date = _next_birthday(birth_date, today)
            if next_date > end_date:
                continue
            photo = getattr(getattr(student, 'bio_data', None), 'passport_photo', None) or student.passport_photo
            birthdays.append({
                'name': student.user.get_full_name() or student.user.username,
                'role': 'Learner',
                'meta': str(student.school_class),
                'photo': photo,
                'date': next_date,
                'date_label': next_date.strftime('%b %d'),
                'days_until': (next_date - today).days,
            })
    except Exception:
        pass

    try:
        staff_bios = StaffBioData.objects.filter(
            teacher__school=active_school,
            date_of_birth__isnull=False,
        ).select_related('teacher__user')
        for bio in staff_bios:
            next_date = _next_birthday(bio.date_of_birth, today)
            if next_date > end_date:
                continue
            birthdays.append({
                'name': bio.teacher.user.get_full_name() or bio.teacher.user.username,
                'role': 'Staff',
                'meta': bio.position or bio.department or bio.teacher.employee_id,
                'photo': bio.passport_photo,
                'date': next_date,
                'date_label': next_date.strftime('%b %d'),
                'days_until': (next_date - today).days,
            })
    except Exception:
        pass

    birthdays.sort(key=lambda item: (item['days_until'], item['name']))
    for item in birthdays:
        item['is_today'] = item['days_until'] == 0
        item['when'] = _birthday_label(item['days_until'])
    return birthdays


def school_settings(request):
    """Expose the active school settings to all templates."""
    active_school = getattr(request, 'school', None)
    user = getattr(request, 'user', None)
    user_is_authenticated = bool(getattr(user, 'is_authenticated', False))
    accessible_dashboards = []
    accessible_schools = []
    active_membership = None
    can_manage_school_admin = False
    if user_is_authenticated:
        for role in user.get_all_roles():
            if role == 'student' and not hasattr(user, 'student'):
                continue
            if role in ['subject_teacher', 'class_teacher'] and not hasattr(user, 'teacher'):
                continue
            dashboard = ROLE_DASHBOARDS.get(role)
            if dashboard and dashboard not in accessible_dashboards:
                accessible_dashboards.append(dashboard)

        try:
            if user.is_superuser:
                accessible_schools = list(SchoolTenant.objects.filter(is_active=True))
            else:
                memberships = user.school_memberships.filter(is_active=True).select_related('school')
                accessible_schools = [
                    membership.school for membership in memberships
                    if membership.school.is_active
                ]
                active_membership = next(
                    (membership for membership in memberships if membership.school_id == getattr(active_school, 'id', None)),
                    None
                )
        except Exception:
            accessible_schools = []
            active_membership = None

        try:
            if user.is_superuser or user.has_role('super_admin'):
                can_manage_school_admin = True
            elif active_membership and 'super_admin' in active_membership.get_all_roles():
                can_manage_school_admin = True
        except Exception:
            can_manage_school_admin = False

    settings = SchoolSettings.get_for_school(active_school)
    portal_birthdays = _portal_birthdays(active_school) if user_is_authenticated else []

    def _safe_hex(value, fallback):
        value = (value or '').strip()
        if len(value) == 7 and value.startswith('#') and all(ch in '0123456789abcdefABCDEF' for ch in value[1:]):
            return value
        return fallback

    return {
        'active_school': active_school,
        'active_membership': active_membership,
        'accessible_schools': accessible_schools,
        'school_settings': settings,
        'theme_primary_color': _safe_hex(getattr(settings, 'primary_color', None), '#2563eb'),
        'theme_secondary_color': _safe_hex(getattr(settings, 'secondary_color', None), '#1d4ed8'),
        'theme_accent_color': _safe_hex(getattr(settings, 'accent_color', None), '#f97316'),
        'accessible_dashboards': accessible_dashboards,
        'can_manage_school_admin': can_manage_school_admin,
        'portal_birthdays': portal_birthdays,
        'portal_birthday_count': len(portal_birthdays),
        'portal_birthday_today_count': len([item for item in portal_birthdays if item.get('is_today')]),
    }
