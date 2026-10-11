from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import PastMasterConnection
from core.pastmaster_client import PastMasterApiError, PastMasterClient


class Command(BaseCommand):
    help = "Synchronize PastMaster rosters and learning-intelligence events for connected schools."

    def add_arguments(self, parser):
        parser.add_argument("--school", help="Only synchronize this SchoolTenant slug.")
        parser.add_argument("--full-roster", action="store_true", help="Force a roster synchronization now.")
        parser.add_argument("--full-reports", action="store_true", help="Refresh every learner report instead of changed learners only.")

    def handle(self, *args, **options):
        connections = PastMasterConnection.objects.select_related("school").exclude(
            status=PastMasterConnection.Status.DISCONNECTED
        )
        if options["school"]:
            connections = connections.filter(school__slug=options["school"])
        total_events = total_reports = failures = 0
        for connection in connections:
            if not connection.is_configured:
                continue
            client = PastMasterClient(connection, timeout=30)
            try:
                roster_due = (
                    options["full_roster"]
                    or connection.last_roster_sync_at is None
                    or connection.last_roster_sync_at <= timezone.now() - timedelta(hours=24)
                )
                if roster_due:
                    roster = client.sync_roster()
                    connection.last_roster_sync_at = timezone.now()
                    self.stdout.write(
                        f"{connection.school.slug}: roster {roster['succeeded']} succeeded, {roster['failed']} failed"
                    )
                if options["full_reports"]:
                    result = client.sync_all_reports()
                    total_reports += result["succeeded"]
                    self.stdout.write(
                        f"{connection.school.slug}: reports {result['succeeded']} updated, {result['failed']} failed"
                    )
                else:
                    result = client.sync_changed_reports()
                    total_events += result["events"]
                    total_reports += result["succeeded"]
                    self.stdout.write(
                        f"{connection.school.slug}: {result['events']} events, {result['succeeded']} reports refreshed"
                    )
                connection.status = PastMasterConnection.Status.ACTIVE
                connection.last_report_sync_at = timezone.now()
                connection.last_error = ""
                connection.save()
            except (PastMasterApiError, ValueError) as exc:
                failures += 1
                connection.status = PastMasterConnection.Status.ERROR
                connection.last_error = str(exc)
                connection.save(update_fields=["status", "last_error", "updated_at"])
                self.stderr.write(f"{connection.school.slug}: {exc}")
        self.stdout.write(
            self.style.SUCCESS(
                f"PastMaster sync finished: {total_events} events, {total_reports} reports, {failures} failed schools."
            )
        )
