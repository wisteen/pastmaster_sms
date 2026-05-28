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

        # Check if JSS 1 B already has a class teacher
        if ClassTeacher.objects.filter(school_class=class_jss1b).exists():
            ct = ClassTeacher.objects.get(school_class=class_jss1b)
            self.stdout.write(f'Class JSS 1 B already has a class teacher: {ct.teacher}')
            if ct.teacher != teacher2:
                self.stdout.write('Removing existing class teacher assignment for JSS 1 B to assign teacher2.')
                ct.delete()
            else:
                self.stdout.write('teacher2 is already the class teacher for JSS 1 B.')
                return

        # Check if teacher2 is already a class teacher for another class
        if ClassTeacher.objects.filter(teacher=teacher2).exists():
            ct = ClassTeacher.objects.get(teacher=teacher2)
            self.stdout.write(f'teacher2 is already class teacher for {ct.school_class}. Removing assignment.')
            ct.delete()

        # Assign teacher2 as class teacher for JSS 1 B
        ClassTeacher.objects.create(
            teacher=teacher2,
            school_class=class_jss1b
        )
        self.stdout.write(self.style.SUCCESS(f'Successfully assigned {teacher2} as Class Teacher for {class_jss1b}'))
        
        # Verify role is still subject_teacher
        self.stdout.write(f'User role: {teacher2.user.role}')
