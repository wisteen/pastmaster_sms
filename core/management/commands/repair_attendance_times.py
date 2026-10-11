"""Repair gate clock-outs recorded less than 10 minutes after clock-in."""

from datetime import timedelta

from django.core.management.base import BaseCommand

from core.models_attendance import AttendanceMovement, AttendanceRecord


MIN_GAP = timedelta(minutes=10)


class Command(BaseCommand):
    help = 'Clear gate clock-out times recorded less than 10 minutes after clock-in'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        bad_ids = []
        for record in AttendanceRecord.objects.filter(check_out_time__isnull=False).iterator():
            if record.check_out_time - record.check_in_time < MIN_GAP:
                bad_ids.append(record.id)

        self.stdout.write(f'Gate attendance records with invalid clock-out: {len(bad_ids)}')
        if options['dry_run']:
            self.stdout.write(self.style.WARNING('Dry run - no changes made.'))
            return

        if bad_ids:
            updated = AttendanceRecord.objects.filter(id__in=bad_ids).update(check_out_time=None)
            AttendanceMovement.objects.filter(record_id__in=bad_ids, action='out').delete()
            self.stdout.write(self.style.SUCCESS(f'Cleared {updated} invalid gate clock-out(s).'))
        else:
            self.stdout.write(self.style.SUCCESS('No invalid gate clock-out times found.'))
