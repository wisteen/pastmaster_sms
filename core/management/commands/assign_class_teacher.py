from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import *

User = get_user_model()

class Command(BaseCommand):
    help = 'Assign a subject teacher as a class teacher'

    def handle(self, *args, **options):
        self.stdout.write('Assigning subject teacher as class teacher...')

        # Find teacher2 (Jane Doe)
        try:
            teacher2_user = User.objects.get(username='teacher2')
            teacher2 = Teacher.objects.get(user=teacher2_user)
            self.stdout.write(f'Found teacher: {teacher2}')
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR('User teacher2 not found. Run setup_enhanced_demo first.'))
            return
        except Teacher.DoesNotExist:
            self.stdout.write(self.style.ERROR('Teacher profile for teacher2 not found.'))
            return

        # Find JSS 1 B
        try:
            class_jss1b = SchoolClass.objects.get(name='JSS 1', stream='B')
            self.stdout.write(f'Found class: {class_jss1b}')
        except SchoolClass.DoesNotExist:
            self.stdout.write(self.style.ERROR('Class JSS 1 B not found.'))
            return

        # Assign teacher2 as class teacher for JSS 1 B
        assignment, created = ClassTeacher.objects.get_or_create(
            teacher=teacher2,
            school_class=class_jss1b
        )
        if not created:
            self.stdout.write('teacher2 is already assigned as a class teacher for JSS 1 B.')
            return
        self.stdout.write(self.style.SUCCESS(f'Successfully assigned {teacher2} as Class Teacher for {class_jss1b}'))
        
        # Verify role is still subject_teacher
        self.stdout.write(f'User role: {teacher2.user.role}')
