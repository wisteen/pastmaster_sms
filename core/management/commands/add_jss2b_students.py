from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import Student, SchoolClass, Subject, Term, Result, ComponentResult, ResultComponent
from datetime import date
import random

User = get_user_model()

class Command(BaseCommand):
    help = 'Add 10 students to JSS2 B with scores in all subjects'

    def handle(self, *args, **kwargs):
        # Get JSS 2 B class - create if not exists
        jss2b, created = SchoolClass.objects.get_or_create(name='JSS 2', stream='B')
        if created:
            self.stdout.write(self.style.SUCCESS('Created JSS 2 B class'))

        # Get active term
        term = Term.objects.filter(is_active=True).first()
        if not term:
            self.stdout.write(self.style.ERROR('No active term found'))
            return

        # Get all subjects
        subjects = Subject.objects.filter(subject_type='academic')
        if not subjects.exists():
            self.stdout.write(self.style.ERROR('No subjects found'))
            return

        # Student names
        students_data = [
            ('Adebayo', 'Oluwaseun', 'M'),
            ('Chioma', 'Nkechi', 'F'),
            ('Ibrahim', 'Musa', 'M'),
            ('Fatima', 'Aisha', 'F'),
            ('Emeka', 'Chukwudi', 'M'),
            ('Blessing', 'Chiamaka', 'F'),
            ('Tunde', 'Babatunde', 'M'),
            ('Ngozi', 'Adaeze', 'F'),
            ('Yusuf', 'Abdullahi', 'M'),
            ('Amina', 'Zainab', 'F'),
        ]

        created_count = 0
        for first_name, last_name, gender in students_data:
            username = f"{first_name.lower()}.{last_name.lower()}"
            
            # Check if user exists
            if User.objects.filter(username=username).exists():
                self.stdout.write(self.style.WARNING(f'User {username} already exists, skipping'))
                continue

            # Create user
            user = User.objects.create_user(
                username=username,
                first_name=first_name,
                last_name=last_name,
                email=f"{username}@school.com",
                password='student123',
                role='student'
            )

            # Create student
            student = Student.objects.create(
                user=user,
                school_class=jss2b,
                date_of_birth=date(2010, random.randint(1, 12), random.randint(1, 28)),
                gender=gender
            )

            # Add scores for each subject
            for subject in subjects:
                # Get result components for this class and subject
                components = ResultComponent.objects.filter(
                    school_class=jss2b,
                    subject=subject
                )

                if components.exists():
                    # Create component results
                    for component in components:
                        score = random.randint(int(component.max_score * 0.4), component.max_score)
                        ComponentResult.objects.create(
                            student=student,
                            component=component,
                            term=term,
                            score=score
                        )

                    # Create or update result
                    result, created = Result.objects.get_or_create(
                        student=student,
                        subject=subject,
                        term=term
                    )
                    result.calculate_total()

            created_count += 1
            self.stdout.write(self.style.SUCCESS(f'Created student: {student.user.get_full_name()} ({student.student_id})'))

        self.stdout.write(self.style.SUCCESS(f'\nSuccessfully added {created_count} students to JSS2 B with scores'))
