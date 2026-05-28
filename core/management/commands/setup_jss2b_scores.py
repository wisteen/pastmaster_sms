from django.core.management.base import BaseCommand
from core.models import Student, SchoolClass, Subject, Term, Result, ComponentResult, ResultComponent
import random

class Command(BaseCommand):
    help = 'Setup result components and scores for JSS 2 B students'

    def handle(self, *args, **kwargs):
        jss2b = SchoolClass.objects.get(name='JSS 2', stream='B')
        term = Term.objects.filter(is_active=True).first()
        subjects = Subject.objects.filter(subject_type='academic').exclude(name__contains='_')
        students = Student.objects.filter(school_class=jss2b)

        self.stdout.write(f'Found {students.count()} students in JSS 2 B')
        self.stdout.write(f'Found {subjects.count()} subjects')

        # Create result components for JSS 2 B
        components_data = [
            ('CA1', 10, 10),
            ('CA2', 10, 10),
            ('Exam', 80, 80),
        ]

        for subject in subjects:
            for comp_name, weight, max_score in components_data:
                ResultComponent.objects.get_or_create(
                    school_class=jss2b,
                    subject=subject,
                    component_name=comp_name,
                    defaults={'weight': weight, 'max_score': max_score}
                )

        self.stdout.write(self.style.SUCCESS('Created result components'))

        # Delete existing results and component results
        ComponentResult.objects.filter(student__school_class=jss2b, term=term).delete()
        Result.objects.filter(student__school_class=jss2b, term=term).delete()

        # Add scores for all students
        for student in students:
            for subject in subjects:
                components = ResultComponent.objects.filter(school_class=jss2b, subject=subject)
                
                for component in components:
                    score = random.randint(int(component.max_score * 0.5), component.max_score)
                    ComponentResult.objects.create(
                        student=student,
                        component=component,
                        term=term,
                        score=score
                    )

                result, _ = Result.objects.get_or_create(
                    student=student,
                    subject=subject,
                    term=term
                )
                result.calculate_total()

            self.stdout.write(f'Added scores for {student.user.get_full_name()}')

        self.stdout.write(self.style.SUCCESS(f'\nCompleted! All {students.count()} students have scores in {subjects.count()} subjects'))
