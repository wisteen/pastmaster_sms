from django.db.models import Exists, OuterRef, Q

from .models import (
    Attendance,
    ClassTeacher,
    Comment,
    ComponentResult,
    EffectiveDomain,
    LearnerDomainRating,
    Psychomotor,
    Result,
    SchoolClass,
    Student,
    StudentTermPlacement,
    Term,
)


def placement_for_term(student, term):
    return StudentTermPlacement.all_objects.filter(
        student=student, term=term, term__school=student.school,
        school_class__school=student.school,
    ).select_related('school_class', 'class_teacher__user').first()


def report_class_for_term(student, term):
    if term.school_id != student.school_id:
        return None
    placement = placement_for_term(student, term)
    if placement:
        return placement.school_class
    class_ids = list(ComponentResult.all_objects.filter(
        student=student, term=term, component__school_class__school=student.school,
        component__subject__school=student.school,
    ).values_list('component__school_class_id', flat=True).distinct())
    if len(class_ids) == 1:
        return SchoolClass.all_objects.get(pk=class_ids[0], school=student.school)
    if len(class_ids) > 1:
        return None
    # An old total alone cannot establish which class it was earned in after
    # promotion. Do not silently put a new teacher's signature on that report.
    if student.is_promoted and Result.all_objects.filter(student=student, term=term).exists():
        return None
    return student.school_class


def students_for_term(school, school_class, term):
    students = Student.all_objects.filter(school=school)
    if not school_class or school_class.school_id != getattr(school, 'id', None):
        return students.none()
    if not term:
        return students.filter(school_class=school_class)
    if term.school_id != school.id:
        return students.none()
    placements = StudentTermPlacement.all_objects.filter(student__school=school, term=term)
    marks = ComponentResult.all_objects.filter(
        student__school=school, term=term, component__school_class__school=school,
        component__subject__school=school,
    )
    historical = Q(pk__in=placements.filter(school_class=school_class).values('student_id'))
    inferred = Q(pk__in=marks.filter(component__school_class=school_class).values('student_id')) & ~Q(
        pk__in=placements.values('student_id')
    )
    current = Q(school_class=school_class) & ~Q(pk__in=placements.values('student_id')) & ~Q(
        pk__in=marks.values('student_id')
    )
    # Promoted learners with only a legacy total need an explicit placement.
    current &= ~Q(is_promoted=True, pk__in=Result.all_objects.filter(term=term).values('student_id'))
    return students.filter(historical | inferred | current).distinct()


def capture_term_placement(student, term, school_class=None, freeze_teacher=False):
    existing = placement_for_term(student, term)
    if existing and (existing.signatory_frozen or not freeze_teacher):
        return existing
    school_class = existing.school_class if existing else (school_class or report_class_for_term(student, term))
    if not school_class or school_class.school_id != student.school_id or term.school_id != student.school_id:
        return None
    assignments = list(ClassTeacher.all_objects.filter(
        school_class=school_class,
        teacher__school=student.school,
        teacher__status='active',
    ).select_related('teacher__user')[:2])
    # Multiple class teachers need explicit school review; never guess a name.
    teacher = assignments[0].teacher if len(assignments) == 1 else None
    placement, _ = StudentTermPlacement.all_objects.update_or_create(
        student=student, term=term,
        defaults={
            'school_class': school_class, 'class_teacher': teacher,
            'teacher_name': teacher.user.get_full_name() if teacher else '',
            'teacher_signature': teacher.signature.name if teacher else '',
            'signatory_frozen': freeze_teacher,
        },
    )
    return placement


def results_for_class(school, school_class):
    """Filter each result by its own term's placement, including in exports."""
    placements = StudentTermPlacement.all_objects.filter(
        student_id=OuterRef('student_id'), term_id=OuterRef('term_id'),
    )
    marks = ComponentResult.all_objects.filter(
        student_id=OuterRef('student_id'), term_id=OuterRef('term_id'),
        component__school_class__school=school, component__subject__school=school,
    )
    return Result.all_objects.filter(student__school=school, subject__school=school, term__school=school).annotate(
        _has_placement=Exists(placements),
        _in_placement=Exists(placements.filter(school_class=school_class)),
        _has_marks=Exists(marks),
        _in_marks=Exists(marks.filter(component__school_class=school_class)),
    ).filter(
        Q(_in_placement=True) |
        Q(_has_placement=False, _in_marks=True) |
        Q(_has_placement=False, _has_marks=False, student__is_promoted=False, student__school_class=school_class)
    )


def capture_before_promotion(student):
    term_ids = set(Result.all_objects.filter(student=student).values_list('term_id', flat=True))
    term_ids.update(ComponentResult.all_objects.filter(student=student).values_list('term_id', flat=True))
    for model in (Attendance, Comment, Psychomotor, EffectiveDomain, LearnerDomainRating):
        term_ids.update(model.all_objects.filter(student=student).values_list('term_id', flat=True))
    term_ids.update(
        Term.all_objects.filter(
            school=student.school,
            is_active=True,
        ).values_list('id', flat=True)
    )
    terms = list(Term.all_objects.filter(school=student.school, pk__in=term_ids).order_by('-start_date'))
    for term in terms:
        historical_class = report_class_for_term(student, term)
        capture_term_placement(student, term, historical_class, freeze_teacher=True)
