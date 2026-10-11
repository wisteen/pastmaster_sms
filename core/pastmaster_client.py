"""Small dependency-free HTTP client for the PastMaster integration API."""

import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from django.utils import timezone

from .models import PastMasterLearnerSnapshot, Student


class PastMasterApiError(Exception):
    pass


class PastMasterClient:
    ROSTER_RETENTION_CAPABILITY = "roster_retained_external_ids"

    def __init__(self, connection, timeout=15):
        self.connection = connection
        self.base_url = connection.base_url.rstrip("/")
        self.timeout = timeout
        self._token = ""
        self._capabilities = set()

    def _request(self, method, path, payload=None, authenticated=True):
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if authenticated:
            headers["Authorization"] = f"Bearer {self._access_token()}"
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(f"{self.base_url}{path}", data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except HTTPError as exc:
            try:
                details = json.loads(exc.read().decode("utf-8"))
                message = details.get("detail") or details.get("error") or str(exc)
            except (UnicodeDecodeError, json.JSONDecodeError):
                message = str(exc)
            raise PastMasterApiError(f"PastMaster rejected the request: {message}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise PastMasterApiError(f"Could not reach PastMaster: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise PastMasterApiError("PastMaster returned an unreadable response.") from exc

    def _access_token(self):
        if self._token:
            return self._token
        response = self._request(
            "POST",
            "/api/integrations/oauth/token/",
            {
                "client_id": self.connection.client_id,
                "client_secret": self.connection.get_client_secret(),
            },
            authenticated=False,
        )
        self._token = response["access_token"]
        capabilities = response.get("capabilities", [])
        if isinstance(capabilities, list):
            self._capabilities = {str(value) for value in capabilities}
        return self._token

    def test_connection(self):
        self._access_token()
        return True

    def sync_roster(self):
        self._access_token()
        supports_retained_ids = self.ROSTER_RETENTION_CAPABILITY in self._capabilities
        students = list(
            Student.all_objects.filter(school=self.connection.school)
            .select_related("user", "school_class")
            .order_by("id")
        )
        retained_external_ids = [str(student.student_id) for student in students]
        if not students:
            if not supports_retained_ids:
                return {"received": 0, "succeeded": 0, "failed": 0, "students": []}
            return self._request(
                "POST",
                "/api/integrations/v1/students/sync/",
                {
                    "students": [],
                    "deactivate_missing": True,
                    "retained_external_ids": [],
                },
            )
        combined = {"received": 0, "succeeded": 0, "failed": 0, "students": []}
        for offset in range(0, len(students), 500):
            chunk = students[offset:offset + 500]
            final_chunk = offset + len(chunk) == len(students)
            complete_roster = final_chunk and (
                len(students) <= 500 or supports_retained_ids
            )
            payload = {
                "students": [self._student_payload(student) for student in chunk],
                "deactivate_missing": complete_roster,
            }
            if final_chunk and supports_retained_ids:
                payload["retained_external_ids"] = retained_external_ids
            response = self._request("POST", "/api/integrations/v1/students/sync/", payload)
            for key in ("received", "succeeded", "failed"):
                combined[key] += int(response.get(key, 0))
            combined["students"].extend(response.get("students", []))
        return combined

    @staticmethod
    def _student_payload(student):
        return {
            "external_id": student.student_id,
            "admission_no": student.student_id,
            "first_name": student.user.first_name,
            "last_name": student.user.last_name,
            "email": student.user.email,
            "class_name": str(student.school_class),
            "active": student.status == "active" and student.user.is_active,
        }

    def create_student_launch(self, external_student_id):
        return self._request(
            "POST",
            "/api/integrations/v1/sso/launch/",
            {"external_student_id": external_student_id},
        )

    def learner_report(self, external_student_id):
        encoded = quote(str(external_student_id), safe="")
        return self._request("GET", f"/api/integrations/v1/students/{encoded}/report/")

    def events(self, after=0, limit=100):
        return self._request("GET", f"/api/integrations/v1/events/?after={int(after)}&limit={int(limit)}")

    def acknowledge_events(self, event_ids):
        return self._request(
            "POST",
            "/api/integrations/v1/events/acknowledge/",
            {"event_ids": list(event_ids)},
        )

    def sync_all_reports(self):
        students = Student.all_objects.filter(school=self.connection.school).order_by("id")
        succeeded = 0
        errors = []
        for student in students:
            if not student.student_id:
                continue
            try:
                report = self.learner_report(student.student_id)
                self._save_snapshot(student, report)
                succeeded += 1
            except PastMasterApiError as exc:
                errors.append({"student_id": student.student_id, "detail": str(exc)})
        return {"succeeded": succeeded, "failed": len(errors), "errors": errors[:20]}

    def sync_changed_reports(self):
        response = self.events(after=self.connection.last_event_id)
        events = response.get("events", [])
        event_ids = [int(event["id"]) for event in events]
        external_ids = {str(event.get("external_student_id", "")) for event in events}
        succeeded = 0
        errors = []
        for external_id in external_ids:
            student = Student.all_objects.filter(
                school=self.connection.school, student_id=external_id
            ).first()
            if not student:
                continue
            try:
                self._save_snapshot(student, self.learner_report(external_id))
                succeeded += 1
            except PastMasterApiError as exc:
                errors.append({"student_id": external_id, "detail": str(exc)})
        if event_ids and not errors:
            self.acknowledge_events(event_ids)
            self.connection.last_event_id = max(event_ids)
            self.connection.save(update_fields=["last_event_id", "updated_at"])
        return {"events": len(events), "succeeded": succeeded, "failed": len(errors), "errors": errors}

    def _save_snapshot(self, student, report):
        PastMasterLearnerSnapshot.objects.update_or_create(
            school=self.connection.school,
            student=student,
            defaults={
                "external_student_id": student.student_id,
                "report": report,
                "synced_at": timezone.now(),
            },
        )
