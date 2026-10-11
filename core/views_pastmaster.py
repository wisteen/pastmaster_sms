from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .decorators import role_required
from .models import ClassTeacher, PastMasterConnection, PastMasterLearnerSnapshot, Student, Teacher
from .pastmaster_client import PastMasterApiError, PastMasterClient


def _school(request):
    return getattr(request, "school", None)


def _connection(request):
    school = _school(request)
    if not school:
        return None
    return PastMasterConnection.objects.filter(school=school).first()


@login_required
@role_required(["super_admin", "administrator"])
@require_http_methods(["GET", "POST"])
def pastmaster_connection(request):
    school = _school(request)
    if not school:
        messages.error(request, "Select a school first.")
        return redirect("core:dashboard")
    connection = _connection(request)
    if request.method == "POST":
        action = request.POST.get("action", "save")
        if action == "disconnect":
            if connection:
                connection.client_id = ""
                connection.client_secret_encrypted = ""
                connection.status = PastMasterConnection.Status.DISCONNECTED
                connection.last_error = ""
                connection.save()
            messages.success(request, "PastMaster was disconnected. Cached reports were retained.")
            return redirect("core:pastmaster_connection")

        if connection is None:
            connection = PastMasterConnection(school=school)
        if action == "save":
            connection.base_url = request.POST.get("base_url", "").strip().rstrip("/")
            connection.client_id = request.POST.get("client_id", "").strip()
            secret = request.POST.get("client_secret", "")
            if secret:
                connection.set_client_secret(secret)
            try:
                connection.full_clean()
                connection.save()
                messages.success(request, "PastMaster connection settings were saved.")
            except (ValidationError, ValueError) as exc:
                messages.error(request, "; ".join(getattr(exc, "messages", [str(exc)])))
                return _render_connection(request, connection)
            return redirect("core:pastmaster_connection")

        if not connection or not connection.is_configured:
            messages.error(request, "Save the Client ID and Client Secret first.")
            return redirect("core:pastmaster_connection")
        try:
            client = PastMasterClient(connection)
            if action == "test":
                client.test_connection()
                connection.status = PastMasterConnection.Status.ACTIVE
                connection.last_error = ""
                messages.success(request, "Connection successful. PastMaster accepted these credentials.")
            elif action == "sync_roster":
                result = client.sync_roster()
                connection.status = PastMasterConnection.Status.ACTIVE
                connection.last_roster_sync_at = timezone.now()
                connection.last_error = ""
                messages.success(request, f"Learner sync complete: {result['succeeded']} succeeded, {result['failed']} failed.")
            elif action == "sync_reports":
                result = client.sync_all_reports()
                connection.status = PastMasterConnection.Status.ACTIVE
                connection.last_report_sync_at = timezone.now()
                connection.last_error = ""
                messages.success(request, f"Intelligence refresh complete: {result['succeeded']} learners updated, {result['failed']} failed.")
            elif action == "sync_events":
                result = client.sync_changed_reports()
                connection.status = PastMasterConnection.Status.ACTIVE
                connection.last_report_sync_at = timezone.now()
                connection.last_error = ""
                messages.success(request, f"Processed {result['events']} PastMaster events and refreshed {result['succeeded']} learners.")
            connection.save()
        except (PastMasterApiError, ValueError) as exc:
            connection.status = PastMasterConnection.Status.ERROR
            connection.last_error = str(exc)
            connection.save(update_fields=["status", "last_error", "updated_at"])
            messages.error(request, str(exc))
        return redirect("core:pastmaster_connection")
    return _render_connection(request, connection)


def _render_connection(request, connection):
    school = _school(request)
    return render(
        request,
        "pastmaster/connection.html",
        {
            "connection": connection,
            "student_count": Student.all_objects.filter(school=school).count(),
            "snapshot_count": PastMasterLearnerSnapshot.objects.filter(school=school).count(),
        },
    )


@login_required
@role_required(["student"])
def pastmaster_student_launch(request):
    school = _school(request)
    student = get_object_or_404(Student.all_objects.select_related("user"), school=school, user=request.user)
    connection = _connection(request)
    if not connection or not connection.is_configured or connection.status == PastMasterConnection.Status.DISCONNECTED:
        messages.error(request, "Your school has not connected PastMaster yet.")
        return redirect("core:dashboard")
    try:
        launch = PastMasterClient(connection).create_student_launch(student.student_id)
    except (PastMasterApiError, ValueError) as exc:
        messages.error(request, str(exc))
        return redirect("core:dashboard")
    return redirect(launch["launch_url"])


@login_required
@role_required(["super_admin", "administrator", "subject_teacher", "class_teacher"])
def pastmaster_learner_report(request, student_id):
    school = _school(request)
    student = get_object_or_404(Student.all_objects.select_related("user", "school_class"), pk=student_id, school=school)
    is_admin = request.user.is_superuser or request.user.has_any_role(["super_admin", "administrator"])
    if not is_admin:
        teacher = Teacher.all_objects.filter(school=school, user=request.user, status="active").first()
        allowed_class_ids = set(teacher.classes.values_list("id", flat=True)) if teacher else set()
        if teacher:
            allowed_class_ids.update(
                ClassTeacher.objects.filter(teacher=teacher).values_list("school_class_id", flat=True)
            )
        if student.school_class_id not in allowed_class_ids:
            return get_object_or_404(Student.objects.none(), pk=student_id)
    snapshot = PastMasterLearnerSnapshot.objects.filter(school=school, student=student).first()
    return render(request, "pastmaster/learner_report.html", {"student": student, "snapshot": snapshot})


@login_required
@role_required(["super_admin", "administrator"])
def pastmaster_guide(request):
    return render(request, "pastmaster/guide.html")
