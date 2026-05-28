from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import *
from datetime import date, datetime, timedelta
from django.utils import timezone

User = get_user_model()

class Command(BaseCommand):
    help = 'Setup demo data for the school management system'

    def handle(self, *args, **options):
        self.stdout.write('Setting up demo data...')

        # Create superuser
        if not User.objects.filter(username='admin').exists():
            admin = User.objects.create_superuser(
                username='admin',
                email='admin@school.com',
                password='password123',
                first_name='System',
                last_name='Administrator',
                role='super_admin'
            )
            self.stdout.write('Created admin user')

        # Create classes
        classes_data = ['Class 9A', 'Class 9B', 'Class 10A', 'Class 10B', 'Class 11A', 'Class 11B']
        for class_name in classes_data:
            SchoolClass.objects.get_or_create(name=class_name)
        self.stdout.write('Created classes')

        # Create subjects
        subjects_data = [
            ('Mathematics', 'MATH'),
            ('English Language', 'ENG'),
            ('Physics', 'PHY'),
            ('Chemistry', 'CHEM'),
            ('Biology', 'BIO'),
            ('History', 'HIST'),
            ('Geography', 'GEO'),
            ('Computer Science', 'CS')
        ]
        for name, code in subjects_data:
            Subject.objects.get_or_create(name=name, code=code)
        self.stdout.write('Created subjects')

        # Create term
        Term.objects.get_or_create(
            name='First Term 2024',
            defaults={
                'start_date': date(2024, 1, 15),
                'end_date': date(2024, 4, 15),
                'is_active': True
            }
        )
        self.stdout.write('Created term')

        # Create teachers
        teachers_data = [
            ('teacher1', 'John', 'Smith', 'T001', ['MATH', 'PHY'], ['Class 9A', 'Class 10A']),
            ('teacher2', 'Jane', 'Doe', 'T002', ['ENG', 'HIST'], ['Class 9B', 'Class 10B']),
            ('teacher3', 'Mike', 'Johnson', 'T003', ['CHEM', 'BIO'], ['Class 11A', 'Class 11B']),
        ]

        for username, first_name, last_name, emp_id, subject_codes, class_names in teachers_data:
            if not User.objects.filter(username=username).exists():
                user = User.objects.create_user(
                    username=username,
                    email=f'{username}@school.com',
                    password='password123',
                    first_name=first_name,
                    last_name=last_name,
                    role='subject_teacher'
                )
                
                teacher = Teacher.objects.create(
                    user=user,
                    employee_id=emp_id
                )
                
                # Assign subjects
                for code in subject_codes:
                    subject = Subject.objects.get(code=code)
                    teacher.subjects.add(subject)
                
                # Assign classes
                for class_name in class_names:
                    school_class = SchoolClass.objects.get(name=class_name)
                    teacher.classes.add(school_class)

        self.stdout.write('Created teachers')

        # Create class teachers
        class_teacher_data = [
            ('classteacher1', 'Sarah', 'Wilson', 'CT001', 'Class 9A'),
            ('classteacher2', 'David', 'Brown', 'CT002', 'Class 10A'),
        ]

        for username, first_name, last_name, emp_id, class_name in class_teacher_data:
            if not User.objects.filter(username=username).exists():
                user = User.objects.create_user(
                    username=username,
                    email=f'{username}@school.com',
                    password='password123',
                    first_name=first_name,
                    last_name=last_name,
                    role='class_teacher'
                )
                
                teacher = Teacher.objects.create(
                    user=user,
                    employee_id=emp_id
                )
                
                school_class = SchoolClass.objects.get(name=class_name)
                ClassTeacher.objects.create(
                    teacher=teacher,
                    school_class=school_class
                )

        self.stdout.write('Created class teachers')

        # Create students
        students_data = [
            ('student1', 'Alice', 'Johnson', 'S001', 'Class 9A'),
            ('student2', 'Bob', 'Smith', 'S002', 'Class 9A'),
            ('student3', 'Charlie', 'Brown', 'S003', 'Class 10A'),
            ('student4', 'Diana', 'Wilson', 'S004', 'Class 10A'),
            ('student5', 'Eve', 'Davis', 'S005', 'Class 9B'),
        ]

        for username, first_name, last_name, student_id, class_name in students_data:
            if not User.objects.filter(username=username).exists():
                user = User.objects.create_user(
                    username=username,
                    email=f'{username}@school.com',
                    password='password123',
                    first_name=first_name,
                    last_name=last_name,
                    role='student'
                )
                
                school_class = SchoolClass.objects.get(name=class_name)
                Student.objects.create(
                    user=user,
                    student_id=student_id,
                    school_class=school_class,
                    date_of_birth=date(2008, 1, 1)
                )

        self.stdout.write('Created students')

        # Create sample results
        term = Term.objects.get(name='First Term 2024')
        students = Student.objects.all()
        subjects = Subject.objects.all()

        for student in students:
            for subject in subjects:
                if not Result.objects.filter(student=student, subject=subject, term=term).exists():
                    import random
                    ca_score = random.randint(15, 30)
                    exam_score = random.randint(40, 70)
                    
                    Result.objects.create(
                        student=student,
                        subject=subject,
                        term=term,
                        ca_score=ca_score,
                        exam_score=exam_score
                    )

        self.stdout.write('Created sample results')

        # Create a sample quiz
        teacher = Teacher.objects.first()
        if teacher and not Quiz.objects.filter(title='Sample Math Quiz').exists():
            quiz = Quiz.objects.create(
                title='Sample Math Quiz',
                subject=Subject.objects.get(code='MATH'),
                school_class=SchoolClass.objects.get(name='Class 9A'),
                teacher=teacher,
                start_time=timezone.now() + timedelta(hours=1),
                end_time=timezone.now() + timedelta(hours=2),
                status='scheduled',
                instructions='Answer all questions carefully.'
            )
            
            # Add sample questions
            questions_data = [
                ('What is 2 + 2?', '3', '4', '5', '6', 'B'),
                ('What is 5 × 3?', '15', '12', '18', '20', 'A'),
                ('What is 10 ÷ 2?', '3', '4', '5', '6', 'C'),
            ]
            
            for q_text, opt_a, opt_b, opt_c, opt_d, correct in questions_data:
                Question.objects.create(
                    quiz=quiz,
                    question_text=q_text,
                    option_a=opt_a,
                    option_b=opt_b,
                    option_c=opt_c,
                    option_d=opt_d,
                    correct_answer=correct
                )

        self.stdout.write('Created sample quiz')
        self.stdout.write(self.style.SUCCESS('Demo data setup completed!'))
        self.stdout.write('Login credentials:')
        self.stdout.write('Admin: admin / password123')
        self.stdout.write('Teacher: teacher1 / password123')
        self.stdout.write('Class Teacher: classteacher1 / password123')
        self.stdout.write('Student: student1 / password123')