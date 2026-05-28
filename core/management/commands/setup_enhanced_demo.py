from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import *
from datetime import date, datetime, timedelta
from django.utils import timezone

User = get_user_model()

class Command(BaseCommand):
    help = 'Setup enhanced demo data with grading system and result components'

    def handle(self, *args, **options):
        self.stdout.write('Setting up enhanced demo data...')

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

        # Create grading system
        grading_data = [
            (90, 100, 'A+', 4.0, 'Excellent'),
            (80, 89, 'A', 3.7, 'Very Good'),
            (70, 79, 'B', 3.0, 'Good'),
            (60, 69, 'C', 2.0, 'Fair'),
            (50, 59, 'D', 1.0, 'Pass'),
            (0, 49, 'F', 0.0, 'Fail'),
        ]
        
        for min_score, max_score, grade, grade_point, remark in grading_data:
            GradingSystem.objects.get_or_create(
                min_score=min_score,
                max_score=max_score,
                defaults={
                    'grade': grade,
                    'grade_point': grade_point,
                    'remark': remark
                }
            )
        self.stdout.write('Created grading system')

        # Create classes with streams
        classes_data = [
            ('JSS 1', 'A'),
            ('JSS 1', 'B'),
            ('JSS 2', 'A'),
            ('SS 1', 'Science'),
            ('SS 1', 'Arts'),
            ('SS 2', 'Science'),
            ('SS 3', 'Science'),
        ]
        
        for name, stream in classes_data:
            SchoolClass.objects.get_or_create(name=name, stream=stream)
        self.stdout.write('Created classes with streams')

        # Create subjects
        subjects_data = [
            ('Mathematics', 'MATH', 50),
            ('English Language', 'ENG', 50),
            ('Physics', 'PHY', 50),
            ('Chemistry', 'CHEM', 50),
            ('Biology', 'BIO', 50),
            ('History', 'HIST', 45),
            ('Geography', 'GEO', 45),
            ('Computer Science', 'CS', 50)
        ]
        
        for name, code, pass_mark in subjects_data:
            Subject.objects.get_or_create(
                name=name, 
                code=code,
                defaults={'pass_mark': pass_mark}
            )
        self.stdout.write('Created subjects')

        # Create result components for different classes
        jss1_a = SchoolClass.objects.get(name='JSS 1', stream='A')
        ss1_science = SchoolClass.objects.get(name='SS 1', stream='Science')
        
        # JSS 1 components (simpler structure)
        jss_components = [
            ('First Test', 15),
            ('Second Test', 15),
            ('Exam', 70),
        ]
        
        # SS 1 components (more complex)
        ss_components = [
            ('First Test', 10),
            ('Second Test', 10),
            ('Project', 10),
            ('Exam', 70),
        ]
        
        for subject in Subject.objects.all():
            # JSS 1 A components
            for comp_name, weight in jss_components:
                ResultComponent.objects.get_or_create(
                    school_class=jss1_a,
                    subject=subject,
                    component_name=comp_name,
                    defaults={'weight': weight}
                )
            
            # SS 1 Science components
            for comp_name, weight in ss_components:
                ResultComponent.objects.get_or_create(
                    school_class=ss1_science,
                    subject=subject,
                    component_name=comp_name,
                    defaults={'weight': weight}
                )
        
        self.stdout.write('Created result components')

        # Create term
        Term.objects.get_or_create(
            name='First Term 2024',
            defaults={
                'start_date': date(2024, 1, 15),
                'end_date': date(2024, 4, 15),
                'is_active': True
            }
        )

        # Create teachers
        teachers_data = [
            ('teacher1', 'John', 'Smith', 'T001', ['MATH', 'PHY'], ['JSS 1', 'SS 1']),
            ('teacher2', 'Jane', 'Doe', 'T002', ['ENG', 'HIST'], ['JSS 1', 'SS 1']),
            ('teacher3', 'Mike', 'Johnson', 'T003', ['CHEM', 'BIO'], ['SS 1', 'SS 2']),
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
                    school_classes = SchoolClass.objects.filter(name=class_name)
                    for school_class in school_classes:
                        teacher.classes.add(school_class)

        # Create class teachers
        class_teacher_data = [
            ('classteacher1', 'Sarah', 'Wilson', 'CT001', 'JSS 1', 'A'),
            ('classteacher2', 'David', 'Brown', 'CT002', 'SS 1', 'Science'),
        ]

        for username, first_name, last_name, emp_id, class_name, stream in class_teacher_data:
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
                
                school_class = SchoolClass.objects.get(name=class_name, stream=stream)
                ClassTeacher.objects.create(
                    teacher=teacher,
                    school_class=school_class
                )

        # Create students
        students_data = [
            ('student1', 'Alice', 'Johnson', 'S001', 'JSS 1', 'A'),
            ('student2', 'Bob', 'Smith', 'S002', 'JSS 1', 'A'),
            ('student3', 'Charlie', 'Brown', 'S003', 'SS 1', 'Science'),
            ('student4', 'Diana', 'Wilson', 'S004', 'SS 1', 'Science'),
            ('student5', 'Eve', 'Davis', 'S005', 'JSS 1', 'B'),
        ]

        for username, first_name, last_name, student_id, class_name, stream in students_data:
            if not User.objects.filter(username=username).exists():
                user = User.objects.create_user(
                    username=username,
                    email=f'{username}@school.com',
                    password='password123',
                    first_name=first_name,
                    last_name=last_name,
                    role='student'
                )
                
                school_class = SchoolClass.objects.get(name=class_name, stream=stream)
                Student.objects.create(
                    user=user,
                    student_id=student_id,
                    school_class=school_class,
                    date_of_birth=date(2008, 1, 1)
                )

        self.stdout.write('Created users')

        # Create sample component results
        term = Term.objects.get(name='First Term 2024')
        students = Student.objects.all()
        
        for student in students:
            components = ResultComponent.objects.filter(school_class=student.school_class)
            
            for component in components:
                if not ComponentResult.objects.filter(
                    student=student, 
                    component=component, 
                    term=term
                ).exists():
                    import random
                    # Generate realistic scores based on component type
                    if 'Test' in component.component_name:
                        score = random.randint(60, 95)
                    elif 'Project' in component.component_name:
                        score = random.randint(70, 100)
                    else:  # Exam
                        score = random.randint(45, 85)
                    
                    ComponentResult.objects.create(
                        student=student,
                        component=component,
                        term=term,
                        score=score
                    )

        # Calculate final results
        for student in students:
            subjects = Subject.objects.all()
            for subject in subjects:
                if not Result.objects.filter(
                    student=student, 
                    subject=subject, 
                    term=term
                ).exists():
                    result = Result.objects.create(
                        student=student,
                        subject=subject,
                        term=term
                    )
                    result.calculate_total()

        self.stdout.write('Created sample results')

        # Create enhanced quiz
        teacher = Teacher.objects.first()
        if teacher:
            quiz = Quiz.objects.create(
                title='Advanced Physics Quiz',
                subject=Subject.objects.get(code='PHY'),
                school_class=SchoolClass.objects.get(name='SS 1', stream='Science'),
                teacher=teacher,
                start_time=timezone.now() + timedelta(hours=1),
                end_time=timezone.now() + timedelta(hours=3),
                status='scheduled',
                instructions='Answer all questions. Mix of objective and theory.',
                shuffle_questions=True,
                shuffle_options=True,
                full_screen_mode=True,
                detect_tab_switching=True,
                max_tab_switches=2
            )
            
            # Add objective questions
            objective_questions = [
                ('What is the SI unit of force?', 'Joule', 'Newton', 'Watt', 'Pascal', 'B', 2),
                ('Which law states F=ma?', 'First Law', 'Second Law', 'Third Law', 'Zeroth Law', 'B', 2),
                ('What is acceleration due to gravity?', '9.8 m/s²', '10 m/s²', '9.6 m/s²', '8.9 m/s²', 'A', 2),
            ]
            
            for i, (q_text, opt_a, opt_b, opt_c, opt_d, correct, marks) in enumerate(objective_questions):
                Question.objects.create(
                    quiz=quiz,
                    question_type='objective',
                    question_text=q_text,
                    option_a=opt_a,
                    option_b=opt_b,
                    option_c=opt_c,
                    option_d=opt_d,
                    correct_answer=correct,
                    max_marks=marks,
                    order=i
                )
            
            # Add theory question
            Question.objects.create(
                quiz=quiz,
                question_type='theory',
                question_text='Explain Newton\'s Third Law of Motion with three real-world examples. Discuss how this law applies in each example.',
                max_marks=20,
                order=len(objective_questions)
            )

        self.stdout.write('Created enhanced quiz')
        self.stdout.write(self.style.SUCCESS('Enhanced demo data setup completed!'))
        self.stdout.write('Login credentials:')
        self.stdout.write('Admin: admin / password123')
        self.stdout.write('Teacher: teacher1 / password123')
        self.stdout.write('Class Teacher: classteacher1 / password123')
        self.stdout.write('Student: student1 / password123')