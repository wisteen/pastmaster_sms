"""Shared active-person and staff-role rules.

Keep operational counts and staff workflows on these helpers so deactivated
accounts or memberships cannot silently reappear in another dashboard.
"""
from django.db.models import Q


STAFF_ROLES = frozenset({
    'subject_teacher', 'class_teacher', 'super_admin', 'administrator',
    'security', 'cleaner', 'clerk', 'driver', 'nurse', 'maintenance', 'staff',
    'librarian', 'accountant', 'bursar',
})

TEACHING_ROLES = frozenset({'subject_teacher', 'class_teacher'})
GENERIC_STAFF_ROLES = frozenset({
    'cleaner', 'clerk', 'driver', 'nurse', 'maintenance', 'staff',
})

ROLE_LABELS = {
    'subject_teacher': 'Subject Teacher',
    'class_teacher': 'Class Teacher',
    'super_admin': 'Administrator',
    'administrator': 'Administrator',
    'security': 'Security',
    'cleaner': 'Cleaner',
    'clerk': 'Clerk',
    'driver': 'Driver',
    'nurse': 'Nurse',
    'maintenance': 'Maintenance Staff',
    'staff': 'Non-teaching Staff',
    'librarian': 'Librarian',
    'accountant': 'Accountant',
    'bursar': 'Bursar',
}


def membership_roles(membership):
    return set(membership.get_all_roles()) if membership else set()


def is_staff_membership(membership):
    return bool(
        membership
        and membership.is_active
        and membership.user.is_active
        and membership.school.is_active
        and membership_roles(membership).intersection(STAFF_ROLES)
    )


def active_memberships(school, roles=None):
    from .models import SchoolMembership

    memberships = SchoolMembership.objects.filter(
        school=school,
        school__is_active=True,
        is_active=True,
        user__is_active=True,
    ).select_related('user', 'school')
    if roles is None:
        return memberships
    roles = set(roles)
    ids = [item.pk for item in memberships if membership_roles(item).intersection(roles)]
    return memberships.filter(pk__in=ids)


def active_students(school=None):
    from .models import SchoolMembership, Student

    candidates = Student.all_objects.filter(status='active', user__is_active=True)
    if school is not None:
        candidates = candidates.filter(school=school, school__is_active=True)
    else:
        candidates = candidates.filter(Q(school__isnull=True) | Q(school__is_active=True))
    memberships = SchoolMembership.objects.filter(
        user_id__in=candidates.values_list('user_id', flat=True),
        school_id__in=candidates.values_list('school_id', flat=True),
    ).select_related('user', 'school')
    by_pair = {}
    for item in memberships:
        by_pair.setdefault((item.user_id, item.school_id), []).append(item)
    eligible_ids = []
    for profile in candidates.only('pk', 'user_id', 'school_id'):
        pair_memberships = by_pair.get((profile.user_id, profile.school_id), [])
        if not pair_memberships or any(
            item.is_active and item.user.is_active and item.school.is_active
            and 'student' in membership_roles(item)
            for item in pair_memberships
        ):
            eligible_ids.append(profile.pk)
    return candidates.filter(pk__in=eligible_ids).distinct()


def active_staff(school=None):
    from .models import SchoolMembership, Teacher

    candidates = Teacher.all_objects.filter(status='active', user__is_active=True)
    if school is not None:
        candidates = candidates.filter(school=school, school__is_active=True)
    else:
        candidates = candidates.filter(Q(school__isnull=True) | Q(school__is_active=True))
    memberships = SchoolMembership.objects.filter(
        user_id__in=candidates.values_list('user_id', flat=True),
        school_id__in=candidates.values_list('school_id', flat=True),
    ).select_related('user', 'school')
    by_pair = {}
    for item in memberships:
        by_pair.setdefault((item.user_id, item.school_id), []).append(item)
    eligible_ids = []
    for profile in candidates.only('pk', 'user_id', 'school_id'):
        pair_memberships = by_pair.get((profile.user_id, profile.school_id), [])
        if not pair_memberships or any(
            is_staff_membership(item) for item in pair_memberships
        ):
            eligible_ids.append(profile.pk)
    return candidates.filter(pk__in=eligible_ids).distinct()


def active_teachers(school=None):
    queryset = active_staff(school)
    if school is None:
        return queryset.filter(
            user_id__in=active_memberships_for_all_schools(TEACHING_ROLES)
        )
    user_ids = active_memberships(school, TEACHING_ROLES).values_list('user_id', flat=True)
    return queryset.filter(user_id__in=user_ids)


def active_memberships_for_all_schools(roles):
    from .models import SchoolMembership

    memberships = SchoolMembership.objects.filter(
        school__is_active=True, is_active=True, user__is_active=True,
    ).select_related('user', 'school')
    return [item.user_id for item in memberships if membership_roles(item).intersection(set(roles))]


def active_parent_users(school):
    from .models import User

    user_ids = active_memberships(school, {'parent'}).values_list('user_id', flat=True)
    return User.objects.filter(
        pk__in=user_ids,
        is_active=True,
        is_superuser=False,
    ).distinct().order_by('first_name', 'last_name', 'username')


def staff_membership_for(profile):
    if not profile or not profile.school_id:
        return None
    return profile.user.school_memberships.filter(
        school=profile.school,
        is_active=True,
        user__is_active=True,
    ).select_related('school', 'user').first()


def staff_title(profile):
    if not profile:
        return 'Staff'
    membership = staff_membership_for(profile)
    roles = membership_roles(membership)
    if not roles:
        roles = {profile.user.role, *(profile.user.extra_roles or [])}
    if 'staff' in roles and (profile.custom_job_title or '').strip():
        return profile.custom_job_title.strip()
    priority = (
        'class_teacher', 'subject_teacher', 'administrator', 'super_admin',
        'security', 'cleaner', 'clerk', 'driver', 'nurse', 'maintenance',
        'librarian', 'accountant', 'bursar', 'staff',
    )
    for role in priority:
        if role in roles:
            return ROLE_LABELS[role]
    return (profile.custom_job_title or '').strip() or 'Staff'


def ensure_staff_profile(school, user, roles=None, custom_job_title='', active=True):
    """Create/update the legacy Teacher record used as the shared staff profile."""
    from .models import Teacher

    roles = set(roles or [])
    eligible = bool(roles.intersection(STAFF_ROLES))
    profile = Teacher.all_objects.filter(user=user).first()
    if not eligible or not active or not user.is_active or not school.is_active:
        if profile and profile.school_id == school.id and profile.status == 'active':
            profile.status = 'inactive'
            profile.save(update_fields=['status'])
        return profile, False

    if profile and profile.school_id != school.id:
        # Teacher is a legacy one-to-one profile. Never move it across tenants.
        return profile, False

    created = False
    if profile is None:
        profile = Teacher.all_objects.create(school=school, user=user)
        created = True

    updates = []
    if profile.status != 'active':
        profile.status = 'active'
        updates.append('status')
    title = (custom_job_title or '').strip() if 'staff' in roles else ''
    if profile.custom_job_title != title:
        profile.custom_job_title = title
        updates.append('custom_job_title')
    if updates:
        profile.save(update_fields=updates)
    return profile, created
