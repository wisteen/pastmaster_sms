from itertools import chain

from .models import Assignment, AssignmentSubmission, FinancialAuditLog, QuizAttempt, Result, Student, Teacher


def _user_name(user):
    if not user:
        return 'System'
    return user.get_full_name() or user.username


def _activity(message, timestamp, actor=None, color='blue', icon='fas fa-circle', category='General'):
    return {
        'message': message,
        'timestamp': timestamp,
        'actor': actor or 'System',
        'color': color,
        'icon': icon,
        'category': category,
    }


def _latest(items, limit):
    activities = sorted(
        (item for item in items if item and item.get('timestamp')),
        key=lambda item: item['timestamp'],
        reverse=True
    )
    return activities[:limit] if limit else activities


def _take(queryset, limit):
    return queryset[:limit] if limit else queryset


def _result_actor(result):
    teacher = Teacher.objects.filter(
        subjects=result.subject,
        classes=result.student.school_class
    ).select_related('user').first()
    return _user_name(teacher.user) if teacher else 'System'


def get_recent_system_activity(limit=8):
    student_registrations = (
        _activity(
            f"New student registration: {student.user.get_full_name() or student.user.username}"
            f" ({student.school_class})",
            student.user.date_joined,
            _user_name(student.user),
            'blue',
            'fas fa-user-plus',
            'Student'
        )
        for student in _take(Student.objects.select_related('user', 'school_class')
        .order_by('-user__date_joined'), limit)
    )

    quiz_completions = (
        _activity(
            f"Quiz completed: {attempt.quiz.title} - {attempt.quiz.school_class}",
            attempt.end_time or attempt.start_time,
            _user_name(attempt.student.user),
            'green',
            'fas fa-check-circle',
            'Quiz'
        )
        for attempt in _take(QuizAttempt.objects.filter(is_submitted=True)
        .select_related('student__user', 'quiz__school_class')
        .order_by('-end_time', '-start_time'), limit)
    )

    result_updates = (
        _activity(
            f"Results updated: {result.subject.name} - {result.term.name}",
            result.updated_at,
            _result_actor(result),
            'yellow',
            'fas fa-chart-line',
            'Result'
        )
        for result in _take(Result.objects.select_related('student__school_class', 'subject', 'term')
        .order_by('-updated_at'), limit)
    )

    assignment_posts = (
        _activity(
            f"Assignment posted: {assignment.title} - {assignment.subject.name}",
            assignment.created_at,
            _user_name(assignment.teacher.user),
            'purple',
            'fas fa-tasks',
            'Assignment'
        )
        for assignment in _take(Assignment.objects.select_related('teacher__user', 'subject')
        .order_by('-created_at'), limit)
    )

    financial_logs = (
        _activity(
            f"{log.get_operation_display()} {log.get_model_name_display()}",
            log.timestamp,
            _user_name(log.user),
            'red',
            'fas fa-file-invoice-dollar',
            'Financial'
        )
        for log in _take(FinancialAuditLog.objects.select_related('user')
        .order_by('-timestamp'), limit)
    )

    return _latest(
        chain(student_registrations, quiz_completions, result_updates, assignment_posts, financial_logs),
        limit
    )


def get_teacher_activity(teacher, limit=6):
    classes = teacher.classes.all()
    subjects = teacher.subjects.all()

    quiz_completions = (
        _activity(
            f"{attempt.student.user.get_full_name() or attempt.student.user.username} completed {attempt.quiz.title}",
            attempt.end_time or attempt.start_time,
            _user_name(attempt.student.user),
            'green',
            'fas fa-check-circle',
            'Quiz'
        )
        for attempt in _take(QuizAttempt.objects.filter(
            is_submitted=True,
            quiz__teacher=teacher,
        ).select_related('student__user', 'quiz')
        .order_by('-end_time', '-start_time'), limit)
    )

    result_updates = (
        _activity(
            f"Results updated for {result.student.user.get_full_name() or result.student.user.username}"
            f" in {result.subject.name}",
            result.updated_at,
            _result_actor(result),
            'blue',
            'fas fa-chart-line',
            'Result'
        )
        for result in _take(Result.objects.filter(
            student__school_class__in=classes,
            subject__in=subjects,
        ).select_related('student__user', 'subject')
        .order_by('-updated_at'), limit)
    )

    assignment_submissions = (
        _activity(
            f"{submission.student.user.get_full_name() or submission.student.user.username}"
            f" submitted {submission.assignment.title}",
            submission.submitted_at,
            _user_name(submission.student.user),
            'purple',
            'fas fa-file-upload',
            'Assignment'
        )
        for submission in _take(AssignmentSubmission.objects.filter(
            assignment__teacher=teacher,
        ).select_related('student__user', 'assignment')
        .order_by('-submitted_at'), limit)
    )

    assignments = (
        _activity(
            f"Assignment posted: {assignment.title}",
            assignment.created_at,
            _user_name(assignment.teacher.user),
            'yellow',
            'fas fa-tasks',
            'Assignment'
        )
        for assignment in _take(Assignment.objects.filter(teacher=teacher).select_related('teacher__user')
        .order_by('-created_at'), limit)
    )

    return _latest(
        chain(quiz_completions, result_updates, assignment_submissions, assignments),
        limit
    )
