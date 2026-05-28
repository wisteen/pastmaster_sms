from django.core.management.base import BaseCommand
from core.models import TimeSlot, RoomAssignment
from datetime import time


class Command(BaseCommand):
    help = 'Set up initial time slots and rooms for timetable system'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing time slots and rooms before creating new ones',
        )

    def handle(self, *args, **options):
        if options['reset']:
            self.stdout.write('Deleting existing time slots and rooms...')
            TimeSlot.objects.all().delete()
            RoomAssignment.objects.all().delete()

        # Create standard time slots for Monday to Friday
        time_slots = [
            # Monday (0)
            {'name': 'Period 1', 'start_time': time(8, 0), 'end_time': time(8, 40), 'day_of_week': 0},
            {'name': 'Period 2', 'start_time': time(8, 40), 'end_time': time(9, 20), 'day_of_week': 0},
            {'name': 'Break', 'start_time': time(9, 20), 'end_time': time(9, 40), 'day_of_week': 0},
            {'name': 'Period 3', 'start_time': time(9, 40), 'end_time': time(10, 20), 'day_of_week': 0},
            {'name': 'Period 4', 'start_time': time(10, 20), 'end_time': time(11, 0), 'day_of_week': 0},
            {'name': 'Period 5', 'start_time': time(11, 0), 'end_time': time(11, 40), 'day_of_week': 0},
            {'name': 'Period 6', 'start_time': time(11, 40), 'end_time': time(12, 20), 'day_of_week': 0},
            {'name': 'Lunch Break', 'start_time': time(12, 20), 'end_time': time(13, 0), 'day_of_week': 0},
            {'name': 'Period 7', 'start_time': time(13, 0), 'end_time': time(13, 40), 'day_of_week': 0},
            {'name': 'Period 8', 'start_time': time(13, 40), 'end_time': time(14, 20), 'day_of_week': 0},
        ]

        # Replicate for Tuesday to Friday
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        
        created_slots = 0
        for day_num in range(5):  # Monday to Friday
            for slot in time_slots:
                time_slot, created = TimeSlot.objects.get_or_create(
                    name=slot['name'],
                    start_time=slot['start_time'],
                    end_time=slot['end_time'],
                    day_of_week=day_num,
                    defaults={'is_active': True}
                )
                if created:
                    created_slots += 1

        self.stdout.write(
            self.style.SUCCESS(f'Successfully created {created_slots} time slots')
        )

        # Create sample rooms
        rooms = [
            {'room_name': 'Room A1', 'capacity': 40, 'room_type': 'Classroom'},
            {'room_name': 'Room A2', 'capacity': 40, 'room_type': 'Classroom'},
            {'room_name': 'Room B1', 'capacity': 35, 'room_type': 'Classroom'},
            {'room_name': 'Room B2', 'capacity': 35, 'room_type': 'Classroom'},
            {'room_name': 'Science Lab 1', 'capacity': 30, 'room_type': 'Laboratory'},
            {'room_name': 'Science Lab 2', 'capacity': 30, 'room_type': 'Laboratory'},
            {'room_name': 'Computer Lab', 'capacity': 25, 'room_type': 'Computer Lab'},
            {'room_name': 'Library', 'capacity': 50, 'room_type': 'Library'},
            {'room_name': 'Assembly Hall', 'capacity': 200, 'room_type': 'Hall'},
            {'room_name': 'Music Room', 'capacity': 20, 'room_type': 'Special Room'},
        ]

        created_rooms = 0
        for room_data in rooms:
            room, created = RoomAssignment.objects.get_or_create(
                room_name=room_data['room_name'],
                defaults={
                    'capacity': room_data['capacity'],
                    'room_type': room_data['room_type'],
                    'is_available': True
                }
            )
            if created:
                created_rooms += 1

        self.stdout.write(
            self.style.SUCCESS(f'Successfully created {created_rooms} rooms')
        )

        self.stdout.write(
            self.style.SUCCESS(
                'Timetable setup complete! You can now create timetable entries.'
            )
        )