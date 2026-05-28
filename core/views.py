from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.db.models import Avg, Count, Sum
from django.core.paginator import Paginator
import os
from .models import *
from .models_biodata import Guardian
from .decorators_features import feature_required
from .services_activity import get_recent_system_activity, get_teacher_activity
from .tenant_permissions import grant_school_admin_permissions

def role_selection_view(request):
    """Display role selection page"""
    return render(request, 'auth/role_selection.html')


def _role_profile_is_available(user, role):
    if role == 'student':
        return Student.objects.filter(user=user).exists()
    if role in ['subject_teacher', 'class_teacher']:
        return Teacher.objects.filter(user=user).exists()
    return True


@ensure_csrf_cookie
def login_view(request):
    # Get selected role from query parameter or POST data
    selected_role = request.GET.get('role') or request.POST.get('role')
    
    # Get role display name
    role_display_map = {
        'student': 'Student',
        'parent': 'Parent',
        'subject_teacher': 'Subject Teacher',
        'class_teacher': 'Class Teacher',
        'librarian': 'Librarian',
        'accountant': 'Accountant',
        'bursar': 'Bursar',
        'security': 'Security',
        'super_admin': 'Administrator'
    }
    
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        role = request.POST.get('role')
        
        # Authenticate user
        user = authenticate(request, username=username, password=password)
        
        if user:
            # Verify that user's role matches the selected role
            if role and not user.has_role(role):
                messages.error(request, f'Invalid credentials. This account is not registered as a {role_display_map.get(role, role)}.')
                return render(request, 'auth/login.html', {
                    'selected_role': role,
                    'selected_role_display': role_display_map.get(role, role)
                })

            if role and not _role_profile_is_available(user, role):
                messages.error(request, f'This account has {role_display_map.get(role, role)} access, but the required profile is not linked yet.')
                return render(request, 'auth/login.html', {
                    'selected_role': role,
                    'selected_role_display': role_display_map.get(role, role)
                })
            
            # Login successful
            login(request, user)
            if user.has_role('super_admin'):
                grant_school_admin_permissions(user)
                if not user.is_superuser and user.is_staff:
                    user.is_staff = False
                    user.save(update_fields=['is_staff'])
            available_roles = user.get_all_roles()
            selected_login_role = role or (available_roles[0] if available_roles else None)
            if selected_login_role:
                request.session['selected_role'] = selected_login_role
            if role in ['accountant', 'bursar']:
                return redirect('financial:financial_dashboard')
            if role == 'librarian':
                return redirect('library_dashboard')
            return redirect('core:dashboard')
        else:
            messages.error(request, 'Invalid username or password')
            return render(request, 'auth/login.html', {
                'selected_role': role,
                'selected_role_display': role_display_map.get(role, role)
            })
    
    # GET request - show login form
    return render(request, 'auth/login.html', {
        'selected_role': selected_role,
        'selected_role_display': role_display_map.get(selected_role, '') if selected_role else None
    })

@login_required
def dashboard(request):
    user = request.user
    context = {'user': user}
    selected_role = request.session.get('selected_role')

    student_profile = Student.objects.filter(user=user).select_related('school_class').first()
    teacher_profile = Teacher.objects.filter(user=user).first()

    if selected_role == 'student' and not student_profile:
        messages.warning(request, 'This user is not linked to a student profile, so the student dashboard is unavailable.')
        request.session.pop('selected_role', None)
        selected_role = None

    if selected_role in ['subject_teacher', 'class_teacher'] and not teacher_profile:
        messages.warning(request, 'This user is not linked to a teacher profile, so the teacher dashboard is unavailable.')
        request.session.pop('selected_role', None)
        selected_role = None

    if selected_role in ['accountant', 'bursar'] and user.has_any_role(['accountant', 'bursar']):
        return redirect('financial:financial_dashboard')

    if selected_role == 'librarian' and user.has_role('librarian'):
        return redirect('library_dashboard')

    if selected_role == 'parent' and user.has_role('parent'):
        return parent_dashboard(request)
    
    if user.has_role('super_admin') and selected_role in [None, 'super_admin']:
        context.update({
            'total_students': Student.objects.count(),
            'total_teachers': Teacher.objects.count(),
            'total_classes': SchoolClass.objects.count(),
            'total_subjects': Subject.objects.count(),
            'recent_system_activity': get_recent_system_activity(),
        })
        return render(request, 'dashboards/super_admin.html', context)

    if user.has_role('student') and student_profile and selected_role in [None, 'student']:
        student = student_profile
        context.update({
            'student': student,
            'live_quizzes': Quiz.objects.filter(
                school_class=student.school_class,
                status='live'
            ),
            'recent_results': Result.objects.filter(student=student).order_by('-created_at')[:5]
        })
        return render(request, 'dashboards/student.html', context)

    if user.has_role('parent') and selected_role in [None, 'parent']:
        return parent_dashboard(request)
    
    elif selected_role not in ['security'] and user.has_any_role(['subject_teacher', 'class_teacher']) and teacher_profile:
        teacher = teacher_profile
        
        # Check if also a class teacher
        is_class_teacher = False
        class_teacher = None
        try:
            class_teacher = ClassTeacher.objects.get(teacher=teacher)
            is_class_teacher = True
        except ClassTeacher.DoesNotExist:
            pass

        context.update({
            'teacher': teacher,
            'is_class_teacher': is_class_teacher,
            'class_teacher': class_teacher,
            'my_classes': teacher.classes.all(),
            'my_subjects': teacher.subjects.all(),
            'recent_teacher_activity': get_teacher_activity(teacher),
            'pending_results': Result.objects.filter(
                subject__in=teacher.subjects.all(),
                student__school_class__in=teacher.classes.all(),
                total_score=0
            ).count()
        })
        return render(request, 'dashboards/unified_teacher.html', context)

    elif user.has_role('super_admin'):
        context.update({
            'total_students': Student.objects.count(),
            'total_teachers': Teacher.objects.count(),
            'total_classes': SchoolClass.objects.count(),
            'total_subjects': Subject.objects.count(),
            'recent_system_activity': get_recent_system_activity(),
        })
        return render(request, 'dashboards/super_admin.html', context)
    
    elif user.has_role('librarian'):
        # Redirect librarian to library dashboard
        return redirect('library_dashboard')
    
    elif user.has_role('security'):
        from .models_attendance import AttendanceSession, AttendanceRecord
        from django.db.models import Count, Q
        
        today = timezone.now().date()
        today_session = AttendanceSession.objects.filter(date=today).first()
        
        if today_session:
            today_records = AttendanceRecord.objects.filter(session=today_session)
            today_total = today_records.count()
            today_students = today_records.filter(student__isnull=False).count()
            today_teachers = today_records.filter(teacher__isnull=False).count()
            fees_owing = today_records.filter(student__isnull=False).filter(
                Q(student__studentfee__status='pending') | 
                Q(student__studentfee__status='partial') | 
                Q(student__studentfee__status='overdue')
            ).distinct().count()
            recent_records = today_records.order_by('-check_in_time')[:10]
        else:
            today_total = today_students = today_teachers = fees_owing = 0
            recent_records = []
        
        context.update({
            'today_total': today_total,
            'today_students': today_students,
            'today_teachers': today_teachers,
            'fees_owing': fees_owing,
            'recent_records': recent_records,
        })
        return render(request, 'dashboards/security.html', context)
    
    # Fallback for any other roles
    messages.warning(request, 'Your role does not have a specific dashboard. Please contact administrator.')
    return redirect('core:login')


@login_required
def switch_role(request, role):
    if not request.user.has_role(role):
        messages.error(request, 'You do not have access to that role.')
        return redirect('core:dashboard')

    if not _role_profile_is_available(request.user, role):
        messages.error(request, 'That dashboard is unavailable because this user is not linked to the required profile.')
        return redirect('core:dashboard')

    request.session['selected_role'] = role

    if role in ['accountant', 'bursar']:
        return redirect('financial:financial_dashboard')
    if role == 'librarian':
        return redirect('library_dashboard')
    if role == 'security':
        return redirect('core:dashboard')
    return redirect('core:dashboard')


@login_required
def switch_school(request, slug):
    school = get_object_or_404(SchoolTenant, slug=slug, is_active=True)
    membership = SchoolMembership.objects.filter(
        school=school,
        user=request.user,
        is_active=True
    ).first()

    if not membership and not request.user.is_superuser:
        messages.error(request, 'You do not have access to that school portal.')
        return redirect('core:dashboard')

    request.session['active_school_id'] = school.id
    if membership:
        request.session['selected_role'] = membership.primary_role
    else:
        request.session.pop('selected_role', None)

    messages.success(request, f'Switched to {school.name}.')
    return redirect('core:dashboard')


@login_required
def parent_dashboard(request):
    user = request.user
    if not user.has_role('parent'):
        messages.error(request, 'You do not have access to the parent dashboard.')
        return redirect('core:dashboard')

    guardian_links = Guardian.objects.filter(user=user).select_related('student__user', 'student__school_class')
    if user.email:
        guardian_links = guardian_links | Guardian.objects.filter(
            user__isnull=True,
            email__iexact=user.email
        ).select_related('student__user', 'student__school_class')

    wards = Student.objects.filter(guardians__in=guardian_links).select_related('user', 'school_class').distinct()
    ward_cards = []

    for ward in wards:
        recent_results = Result.objects.filter(student=ward).select_related('subject', 'term').order_by('-updated_at')[:5]
        average_score = Result.objects.filter(student=ward).aggregate(avg=Avg('total_score'))['avg'] or 0
        quiz_attempts = QuizAttempt.objects.filter(student=ward).select_related('quiz__subject').order_by('-end_time', '-start_time')[:5]
        latest_attendance = Attendance.objects.filter(student=ward).select_related('term').order_by('-term__start_date')[:1].first()
        fees = StudentFee.objects.filter(student=ward).select_related('fee_structure__term').order_by('-created_at')[:3]

        ward_cards.append({
            'student': ward,
            'recent_results': recent_results,
            'average_score': average_score,
            'quiz_attempts': quiz_attempts,
            'latest_attendance': latest_attendance,
            'fees': fees,
        })

    return render(request, 'dashboards/parent.html', {
        'ward_cards': ward_cards,
        'total_wards': wards.count(),
    })


@login_required
def activity_log(request):
    user = request.user

    if user.has_role('super_admin'):
        activities = get_recent_system_activity(limit=None)
        title = 'School Activity Log'
    elif user.has_any_role(['subject_teacher', 'class_teacher']):
        teacher = get_object_or_404(Teacher, user=user)
        activities = get_teacher_activity(teacher, limit=None)
        title = 'Teacher Activity Log'
    else:
        messages.error(request, 'You do not have permission to view the activity log.')
        return redirect('core:dashboard')

    paginator = Paginator(activities, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'activity_log.html', {
        'title': title,
        'page_obj': page_obj,
    })

@login_required
def get_students_by_class(request):
    """AJAX view to get students for a specific class"""
    class_id = request.GET.get('class_id')
    if class_id:
        students = Student.objects.filter(school_class_id=class_id).select_related('user')
        student_data = [
            {
                'id': student.id,
                'name': student.user.get_full_name(),
                'student_id': student.student_id
            }
            for student in students
        ]
        return JsonResponse({'students': student_data})
    return JsonResponse({'students': []})

@login_required
def get_recent_results(request):
    """AJAX view to get recent results for a class and subject"""
    if not request.user.has_role('subject_teacher'):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    class_id = request.GET.get('class_id')
    subject_id = request.GET.get('subject_id')
    
    if class_id and subject_id:
        teacher = Teacher.objects.get(user=request.user)
        
        # Verify teacher can access this data
        if not (teacher.classes.filter(id=class_id).exists() and 
                teacher.subjects.filter(id=subject_id).exists()):
            return JsonResponse({'error': 'Unauthorized'}, status=403)
        
        results = Result.objects.filter(
            student__school_class_id=class_id,
            subject_id=subject_id
        ).select_related('student__user', 'term').order_by('-updated_at')[:10]
        
        result_data = [
            {
                'student_name': result.student.user.get_full_name(),
                'student_id': result.student.student_id,
                'total_score': float(result.total_score),
                'grade': result.grade,
                'grade_point': float(result.grade_point),
                'remark': result.remark,
                'term': result.term.name,
                'updated_at': result.updated_at.strftime('%Y-%m-%d %H:%M')
            }
            for result in results
        ]
        return JsonResponse({'results': result_data})
    
    return JsonResponse({'results': []})

@login_required
def student_results(request):
    if not request.user.has_role('student'):
        return redirect('core:dashboard')
    
    student = Student.objects.get(user=request.user)
    results = Result.objects.filter(student=student).order_by('-term__start_date', 'subject__name')
    return render(request, 'student/results.html', {'results': results})

@login_required
@feature_required('cbt_quiz')
def take_quiz(request, quiz_id):
    if not request.user.has_role('student'):
        return redirect('core:dashboard')
    
    quiz = get_object_or_404(Quiz, id=quiz_id)
    student = Student.objects.get(user=request.user)
    
    if not quiz.is_live():
        messages.error(request, 'Quiz is not currently available')
        return redirect('core:dashboard')
    
    attempt, created = QuizAttempt.objects.get_or_create(
        quiz=quiz, student=student,
        defaults={'start_time': timezone.now()}
    )
    
    if attempt.is_submitted:
        messages.info(request, 'You have already submitted this quiz')
        return redirect('core:dashboard')
    
    questions = quiz.questions.all()
    
    if request.method == 'POST':
        for question in questions:
            answer = request.POST.get(f'question_{question.id}')
            if answer:
                QuizAnswer.objects.update_or_create(
                    attempt=attempt, question=question,
                    defaults={'selected_answer': answer}
                )
        
        attempt.end_time = timezone.now()
        attempt.is_submitted = True
        
        # Calculate score
        correct_answers = attempt.answers.filter(is_correct=True).count()
        total_questions = questions.count()
        attempt.score = (correct_answers / total_questions) * 100 if total_questions > 0 else 0
        attempt.save()
        
        messages.success(request, f'Quiz submitted! Your score: {attempt.score:.1f}%')
        return redirect('core:dashboard')
    
    return render(request, 'student/quiz.html', {
        'quiz': quiz,
        'questions': questions,
        'attempt': attempt
    })

@login_required
@feature_required('reports_results')
def manage_results(request):
    if not request.user.has_role('subject_teacher'):
        return redirect('core:dashboard')
    
    teacher = Teacher.objects.get(user=request.user)
    
    if request.method == 'POST':
        messages.info(request, 'Please use the Component Results system for entering scores.')
        return redirect('core:component_results')
    
    classes = teacher.classes.all()
    subjects = teacher.subjects.all()
    active_term = Term.objects.filter(is_active=True).first()
    
    return render(request, 'teacher/manage_results.html', {
        'classes': classes,
        'subjects': subjects,
        'active_term': active_term
    })

@login_required
@feature_required('cbt_quiz')
def create_quiz(request):
    if not request.user.has_role('subject_teacher'):
        return redirect('core:dashboard')
    
    teacher = Teacher.objects.get(user=request.user)
    
    if request.method == 'POST':
        quiz = Quiz.objects.create(
            title=request.POST.get('title'),
            subject_id=request.POST.get('subject'),
            school_class_id=request.POST.get('class'),
            teacher=teacher,
            start_time=request.POST.get('start_time'),
            end_time=request.POST.get('end_time'),
            duration_minutes=int(request.POST.get('duration_minutes', 60)),
            instructions=request.POST.get('instructions', ''),
            shuffle_questions=request.POST.get('shuffle_questions') == 'on',
            shuffle_options=request.POST.get('shuffle_options') == 'on',
            full_screen_mode=request.POST.get('full_screen_mode') == 'on',
            detect_tab_switching=request.POST.get('detect_tab_switching') == 'on',
            max_tab_switches=int(request.POST.get('max_tab_switches', 3)),
            status='draft'
        )
        
        messages.success(request, 'Quiz created successfully')
        return redirect('core:add_questions', quiz_id=quiz.id)
    
    return render(request, 'teacher/create_quiz.html', {
        'subjects': teacher.subjects.all(),
        'classes': teacher.classes.all()
    })

@login_required
@feature_required('cbt_quiz')
def quiz_management(request):
    if not request.user.has_role('subject_teacher'):
        return redirect('core:dashboard')
    
    teacher = Teacher.objects.get(user=request.user)
    quizzes = Quiz.objects.filter(teacher=teacher).order_by('-created_at')
    
    return render(request, 'teacher/quiz_management.html', {'quizzes': quizzes})

@login_required
@feature_required('cbt_quiz')
def edit_quiz(request, quiz_id):
    if not request.user.has_role('subject_teacher'):
        return redirect('core:dashboard')
    
    quiz = get_object_or_404(Quiz, id=quiz_id)
    teacher = Teacher.objects.get(user=request.user)
    
    if quiz.teacher != teacher:
        messages.error(request, 'Unauthorized')
        return redirect('core:quiz_management')
    
    if request.method == 'POST':
        quiz.title = request.POST.get('title')
        quiz.subject_id = request.POST.get('subject')
        quiz.school_class_id = request.POST.get('class')
        quiz.start_time = request.POST.get('start_time')
        quiz.end_time = request.POST.get('end_time')
        quiz.duration_minutes = int(request.POST.get('duration_minutes', 60))
        quiz.instructions = request.POST.get('instructions', '')
        quiz.status = request.POST.get('status', 'draft')
        quiz.shuffle_questions = request.POST.get('shuffle_questions') == 'on'
        quiz.shuffle_options = request.POST.get('shuffle_options') == 'on'
        quiz.full_screen_mode = request.POST.get('full_screen_mode') == 'on'
        quiz.detect_tab_switching = request.POST.get('detect_tab_switching') == 'on'
        quiz.max_tab_switches = int(request.POST.get('max_tab_switches', 3))
        quiz.save()
        
        messages.success(request, 'Quiz updated successfully')
        return redirect('core:quiz_management')
    
    return render(request, 'teacher/edit_quiz.html', {
        'quiz': quiz,
        'subjects': teacher.subjects.all(),
        'classes': teacher.classes.all()
    })

@login_required
@feature_required('cbt_quiz')
def quiz_results(request, quiz_id):
    if not request.user.has_role('subject_teacher'):
        return redirect('core:dashboard')
    
    quiz = get_object_or_404(Quiz, id=quiz_id)
    attempts = QuizAttempt.objects.filter(quiz=quiz, is_submitted=True).select_related('student__user')
    
    return render(request, 'teacher/quiz_results.html', {
        'quiz': quiz,
        'attempts': attempts
    })

@login_required
@feature_required('cbt_quiz')
def grade_theory(request, quiz_id):
    if not request.user.has_role('subject_teacher'):
        return redirect('core:dashboard')
    
    quiz = get_object_or_404(Quiz, id=quiz_id)
    theory_questions = quiz.questions.filter(question_type='theory')
    
    if not theory_questions.exists():
        messages.info(request, 'This quiz has no theory questions')
        return redirect('core:quiz_management')
    
    attempts = QuizAttempt.objects.filter(quiz=quiz, is_submitted=True).prefetch_related('answers__question')
    
    if request.method == 'POST':
        answer_id = request.POST.get('answer_id')
        score = float(request.POST.get('score', 0))
        feedback = request.POST.get('feedback', '')
        
        answer = QuizAnswer.objects.get(id=answer_id)
        answer.manual_score = score
        answer.teacher_feedback = feedback
        answer.save()
        
        # Recalculate attempt scores
        attempt = answer.attempt
        
        # Calculate auto score from objective and multichoice questions
        auto_marks = 0
        for ans in attempt.answers.filter(question__question_type__in=['objective', 'multichoice'], is_correct=True):
            auto_marks += ans.question.max_marks
        attempt.auto_score = auto_marks
        
        # Calculate manual score from theory questions
        theory_score = attempt.answers.filter(question__question_type='theory').aggregate(total=models.Sum('manual_score'))['total'] or 0
        attempt.manual_score = theory_score
        
        # Calculate final score
        total_marks = quiz.questions.aggregate(total=models.Sum('max_marks'))['total'] or 1
        attempt.final_score = ((attempt.auto_score + attempt.manual_score) / total_marks) * 100
        
        # Check if all theory questions are graded
        ungraded = attempt.answers.filter(question__question_type='theory', manual_score=0).exists()
        attempt.is_graded = not ungraded
        attempt.save()
        
        messages.success(request, 'Score saved successfully')
        return redirect('core:grade_theory', quiz_id=quiz_id)
    
    # Prepare data for template
    attempts_data = []
    for attempt in attempts:
        theory_answers = []
        for question in theory_questions:
            try:
                answer = QuizAnswer.objects.get(attempt=attempt, question=question)
            except QuizAnswer.DoesNotExist:
                answer = QuizAnswer.objects.create(attempt=attempt, question=question)
            theory_answers.append({'question': question, 'answer': answer})
        attempts_data.append({'attempt': attempt, 'theory_answers': theory_answers})
    
    return render(request, 'teacher/grade_theory.html', {
        'quiz': quiz,
        'attempts_data': attempts_data
    })

@login_required
@feature_required('cbt_quiz')
def delete_quiz(request, quiz_id):
    if request.method == 'DELETE':
        quiz = get_object_or_404(Quiz, id=quiz_id)
        teacher = Teacher.objects.get(user=request.user)
        
        if quiz.teacher != teacher:
            return JsonResponse({'success': False, 'message': 'Unauthorized'})
        
        quiz.delete()
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False})

@login_required
def subscribe_ai(request):
    if not request.user.has_role('subject_teacher'):
        return redirect('core:dashboard')
    
    teacher = Teacher.objects.get(user=request.user)
    
    if request.method == 'POST':
        import secrets
        from datetime import timedelta
        
        # Generate unique reference
        reference = f"AI-{secrets.token_urlsafe(16)}"
        
        # Create subscription record
        subscription = AISubscription.objects.create(
            teacher=teacher,
            reference=reference,
            amount=500.00
        )
        
        # Return Paystack payment data
        return render(request, 'teacher/paystack_payment.html', {
            'reference': reference,
            'amount': 50000,  # 500 Naira in kobo
            'email': teacher.user.email,
            'paystack_public_key': os.getenv('PAYSTACK_PUBLIC_KEY', 'pk_test_c1042d5f25e8d7b4c091d419a1d9262589200499')
        })
    
    return render(request, 'teacher/subscribe_ai.html', {
        'teacher': teacher,
        'has_access': teacher.has_ai_access(),
        'expires': teacher.ai_access_expires
    })

@login_required
def verify_payment(request):
    if not request.user.has_role('subject_teacher'):
        return redirect('core:dashboard')
    
    reference = request.GET.get('reference')
    teacher = Teacher.objects.get(user=request.user)
    
    try:
        import requests
        from datetime import timedelta
        
        # Verify payment with Paystack
        headers = {
            'Authorization': f"Bearer {os.getenv('PAYSTACK_SECRET_KEY', 'sk_test_c50b47becfd4313423586237510e6dfbeb484190')}"
        }
        response = requests.get(f'https://api.paystack.co/transaction/verify/{reference}', headers=headers)
        data = response.json()
        
        if data['status'] and data['data']['status'] == 'success':
            # Update subscription
            subscription = AISubscription.objects.get(reference=reference)
            subscription.status = 'success'
            subscription.start_date = timezone.now()
            subscription.end_date = timezone.now() + timedelta(days=7)
            subscription.save()
            
            # Grant AI access
            teacher.ai_access_expires = subscription.end_date
            teacher.save()
            
            messages.success(request, 'Payment successful! AI Import access granted for 7 days.')
            return redirect('core:import_questions_ai')
        else:
            messages.error(request, 'Payment verification failed.')
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
    
    return redirect('core:subscribe_ai')

@login_required
def import_questions_ai(request):
    if not request.user.has_role('subject_teacher'):
        return redirect('core:dashboard')
    
    teacher = Teacher.objects.get(user=request.user)
    
    # Check AI access
    if not teacher.has_ai_access():
        messages.warning(request, 'AI Import access expired. Please subscribe to continue.')
        return redirect('core:subscribe_ai')
    
    if request.method == 'POST':
        text_content = request.POST.get('text_content')
        subject_id = request.POST.get('subject_id')
        school_class_id = request.POST.get('school_class_id') or None
        
        try:
            from .ai_question_importer import AIQuestionImporter
            importer = AIQuestionImporter()
            
            # Extract questions using AI
            extracted_data = importer.extract_questions_from_text(text_content, subject_id)
            
            # Import to database
            imported_count = importer.import_to_database(
                extracted_data, 
                subject_id, 
                teacher, 
                school_class_id
            )
            
            messages.success(request, f'Successfully imported {imported_count} questions using AI!')
            return redirect('core:question_bank')
        except Exception as e:
            messages.error(request, f'Import failed: {str(e)}')
    
    return render(request, 'teacher/import_questions_ai.html', {
        'subjects': teacher.subjects.all(),
        'classes': teacher.classes.all()
    })

@login_required
def question_bank(request):
    if not request.user.has_role('subject_teacher'):
        return redirect('core:dashboard')
    
    teacher = Teacher.objects.get(user=request.user)
    from .forms import QuestionBankForm
    
    if request.method == 'POST':
        form = QuestionBankForm(request.POST)
        if form.is_valid():
            question = form.save(commit=False)
            question.created_by = teacher
            
            # Handle correct answer based on question type
            question_type = request.POST.get('question_type')
            if question_type == 'objective':
                question.correct_answer = request.POST.get('correct_answer_scq', '')
            elif question_type == 'multichoice':
                correct_multi = request.POST.getlist('correct_multi')
                question.correct_answer = ','.join(sorted(correct_multi))
            
            question.save()
            messages.success(request, 'Question added to bank')
            return redirect('core:question_bank')
    else:
        form = QuestionBankForm()
        form.fields['subject'].queryset = teacher.subjects.all()
        form.fields['school_class'].queryset = teacher.classes.all()
        form.fields['group'].queryset = QuestionGroup.objects.filter(subject__in=teacher.subjects.all())
    
    # Organize questions by groups and standalone
    groups = QuestionGroup.objects.filter(subject__in=teacher.subjects.all()).prefetch_related('questions')
    standalone_questions = QuestionBank.objects.filter(subject__in=teacher.subjects.all(), group__isnull=True).order_by('-created_at')
    
    questions_data = []
    for group in groups:
        questions_data.append({'type': 'group', 'group': group, 'questions': group.questions.all()})
    for question in standalone_questions:
        questions_data.append({'type': 'question', 'question': question})
    
    return render(request, 'teacher/question_bank.html', {
        'questions_data': questions_data,
        'subjects': teacher.subjects.all(),
        'classes': teacher.classes.all(),
        'teacher': teacher,
        'form': form
    })

@login_required
def upload_image(request):
    if request.method == 'POST' and request.FILES.get('upload'):
        import os
        from django.conf import settings
        
        upload = request.FILES['upload']
        upload_dir = os.path.join(settings.MEDIA_ROOT, 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        
        file_path = os.path.join(upload_dir, upload.name)
        with open(file_path, 'wb+') as destination:
            for chunk in upload.chunks():
                destination.write(chunk)
        
        url = f"{settings.MEDIA_URL}uploads/{upload.name}"
        return JsonResponse({'uploaded': 1, 'fileName': upload.name, 'url': url})
    
    return JsonResponse({'uploaded': 0, 'error': {'message': 'Upload failed'}})

@login_required
def create_question_group(request):
    if request.method == 'POST':
        teacher = Teacher.objects.get(user=request.user)
        subject_id = request.POST.get('subject')
        instruction = request.POST.get('instruction')
        
        group = QuestionGroup.objects.create(
            subject_id=subject_id,
            instruction=instruction,
            created_by=teacher
        )
        messages.success(request, 'Question group created successfully')
        return redirect('core:question_bank')
    return redirect('core:question_bank')

@login_required
def add_question_from_bank(request):
    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
            quiz_id = data.get('quiz_id')
            question_id = data.get('question_id')
            
            quiz = Quiz.objects.get(id=quiz_id)
            bank_question = QuestionBank.objects.get(id=question_id)
            
            Question.objects.create(
                quiz=quiz,
                question_type=bank_question.question_type,
                question_text=bank_question.question_text,
                option_a=bank_question.option_a,
                option_b=bank_question.option_b,
                option_c=bank_question.option_c,
                option_d=bank_question.option_d,
                correct_answer=bank_question.correct_answer,
                max_marks=1
            )
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False})

@login_required
def add_group_from_bank(request):
    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
            quiz_id = data.get('quiz_id')
            group_id = data.get('group_id')
            
            quiz = Quiz.objects.get(id=quiz_id)
            bank_group = QuestionGroup.objects.get(id=group_id)
            
            # Create group instance
            group_instance = QuestionGroupInstance.objects.create(
                quiz=quiz,
                instruction=bank_group.instruction,
                order=Question.objects.filter(quiz=quiz).count()
            )
            
            # Add all questions from group
            for bank_question in bank_group.questions.all():
                Question.objects.create(
                    quiz=quiz,
                    group_instance=group_instance,
                    question_type=bank_question.question_type,
                    question_text=bank_question.question_text,
                    option_a=bank_question.option_a,
                    option_b=bank_question.option_b,
                    option_c=bank_question.option_c,
                    option_d=bank_question.option_d,
                    correct_answer=bank_question.correct_answer,
                    max_marks=1
                )
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False})

@login_required
def edit_question(request, question_id):
    if not request.user.has_role('subject_teacher'):
        return redirect('core:dashboard')
    
    question = get_object_or_404(Question, id=question_id)
    from .forms import QuestionForm
    
    if request.method == 'POST':
        form = QuestionForm(request.POST, instance=question)
        if form.is_valid():
            form.save()
            messages.success(request, 'Question updated')
            return redirect('core:add_questions', quiz_id=question.quiz.id)
    else:
        form = QuestionForm(instance=question)
    
    return render(request, 'teacher/edit_question.html', {
        'question': question,
        'form': form
    })

@login_required
def delete_question(request, question_id):
    if request.method == 'DELETE':
        question = get_object_or_404(Question, id=question_id)
        question.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False})

@login_required
@feature_required('cbt_quiz')
def add_questions(request, quiz_id):
    if not request.user.has_role('subject_teacher'):
        return redirect('core:dashboard')
    
    quiz = get_object_or_404(Quiz, id=quiz_id)
    from .forms import QuestionForm
    
    if request.method == 'POST':
        form = QuestionForm(request.POST)
        if form.is_valid():
            question = form.save(commit=False)
            question.quiz = quiz
            question.question_type = request.POST.get('question_type', 'objective')
            question.max_marks = int(request.POST.get('max_marks', 1))
            
            # Handle multichoice correct answers
            if question.question_type == 'multichoice':
                correct_multi = request.POST.getlist('correct_multi')
                question.correct_answer = ','.join(sorted(correct_multi))
            
            question.save()
            messages.success(request, 'Question added')
            return redirect('core:add_questions', quiz_id=quiz.id)
    else:
        form = QuestionForm()
    
    questions = quiz.questions.all()
    return render(request, 'teacher/add_questions.html', {
        'quiz': quiz,
        'questions': questions,
        'form': form
    })

@login_required
@feature_required('reports_broadsheet')
def class_broadsheet(request):
    teacher = Teacher.objects.get(user=request.user)
    try:
        class_teacher = ClassTeacher.objects.get(teacher=teacher)
    except ClassTeacher.DoesNotExist:
        return redirect('core:dashboard')
    
    students = Student.objects.filter(school_class=class_teacher.school_class)
    subjects = Subject.objects.filter(subject_type='academic')
    active_term = Term.objects.filter(is_active=True).first()
    
    # Calculate broadsheet data with positions
    broadsheet_data = []
    subject_scores = {subject.code: [] for subject in subjects}
    
    for student in students:
        student_results = {}
        total_score = 0
        subject_count = 0
        
        for subject in subjects:
            try:
                result = Result.objects.get(
                    student=student, 
                    subject=subject, 
                    term=active_term
                )
                score = float(result.total_score)
                student_results[subject.code] = {
                    'total': score,
                    'grade': result.grade
                }
                total_score += score
                subject_count += 1
                subject_scores[subject.code].append({'student': student, 'score': score})
            except Result.DoesNotExist:
                student_results[subject.code] = {'total': '-', 'grade': '-'}
        
        average = total_score / subject_count if subject_count > 0 else 0
        
        # Get existing comments
        comment = Comment.objects.filter(student=student, term=active_term).first()
        
        broadsheet_data.append({
            'student': student,
            'results': student_results,
            'total_score': total_score,
            'average': round(average, 2),
            'teacher_comment': comment.teacher_comment if comment else '',
            'ht_comment': comment.proprietor_comment if comment else '',
            'ht_comment_mode': 'manual',
            'subject_positions': {}
        })
    
    # Sort by average for class position (handle ties by total_score)
    broadsheet_data.sort(key=lambda x: (x['average'], x['total_score']), reverse=True)
    for idx, data in enumerate(broadsheet_data, 1):
        data['class_position'] = idx
    
    # Calculate subject positions
    for subject_code, scores in subject_scores.items():
        scores.sort(key=lambda x: x['score'], reverse=True)
        for idx, score_data in enumerate(scores, 1):
            for data in broadsheet_data:
                if data['student'] == score_data['student']:
                    data['subject_positions'][subject_code] = idx
                    break
    
    # Calculate best per subject
    best_per_subject = {}
    for subject_code, scores in subject_scores.items():
        if scores:
            best = max(scores, key=lambda x: x['score'])
            best_per_subject[subject_code] = {
                'score': best['score'],
                'student': best['student'].user.get_full_name()
            }
    
    # Calculate subject averages
    subject_averages = {}
    for subject_code, scores in subject_scores.items():
        if scores:
            avg = sum(s['score'] for s in scores) / len(scores)
            subject_averages[subject_code] = avg
        else:
            subject_averages[subject_code] = 0
    
    # Calculate grand totals
    grand_total = sum(data['total_score'] for data in broadsheet_data)
    grand_average = sum(data['average'] for data in broadsheet_data) / len(broadsheet_data) if broadsheet_data else 0
    
    return render(request, 'class_teacher/broadsheet.html', {
        'broadsheet_data': broadsheet_data,
        'subjects': subjects,
        'class_name': class_teacher.school_class.name,
        'term': active_term,
        'best_per_subject': best_per_subject,
        'subject_averages': subject_averages,
        'grand_total': grand_total,
        'grand_average': grand_average,
        'total_students': students.count()
    })


@login_required
@feature_required('reports_broadsheet')
def print_broadsheet(request):
    teacher = Teacher.objects.get(user=request.user)
    try:
        class_teacher = ClassTeacher.objects.get(teacher=teacher)
    except ClassTeacher.DoesNotExist:
        return redirect('core:dashboard')
    
    students = Student.objects.filter(school_class=class_teacher.school_class)
    subjects = Subject.objects.filter(subject_type='academic')
    active_term = Term.objects.filter(is_active=True).first()
    
    broadsheet_data = []
    subject_scores = {subject.code: [] for subject in subjects}
    
    for student in students:
        student_results = {}
        total_score = 0
        subject_count = 0
        
        for subject in subjects:
            try:
                result = Result.objects.get(student=student, subject=subject, term=active_term)
                score = float(result.total_score)
                student_results[subject.code] = {'total': score, 'grade': result.grade}
                total_score += score
                subject_count += 1
                subject_scores[subject.code].append({'student': student, 'score': score})
            except Result.DoesNotExist:
                student_results[subject.code] = {'total': '-', 'grade': '-'}
        
        average = total_score / subject_count if subject_count > 0 else 0
        comment = Comment.objects.filter(student=student, term=active_term).first()
        
        broadsheet_data.append({
            'student': student,
            'results': student_results,
            'total_score': total_score,
            'average': round(average, 2),
            'teacher_comment': comment.teacher_comment if comment else '',
            'ht_comment': comment.proprietor_comment if comment else '',
            'subject_positions': {}
        })
    
    broadsheet_data.sort(key=lambda x: (x['average'], x['total_score']), reverse=True)
    for idx, data in enumerate(broadsheet_data, 1):
        data['class_position'] = idx
    
    for subject_code, scores in subject_scores.items():
        scores.sort(key=lambda x: x['score'], reverse=True)
        for idx, score_data in enumerate(scores, 1):
            for data in broadsheet_data:
                if data['student'] == score_data['student']:
                    data['subject_positions'][subject_code] = idx
                    break
    
    best_per_subject = {}
    for subject_code, scores in subject_scores.items():
        if scores:
            best = max(scores, key=lambda x: x['score'])
            best_per_subject[subject_code] = {'score': best['score'], 'student': best['student'].user.get_full_name()}
    
    subject_averages = {}
    for subject_code, scores in subject_scores.items():
        if scores:
            subject_averages[subject_code] = sum(s['score'] for s in scores) / len(scores)
        else:
            subject_averages[subject_code] = 0
    
    grand_total = sum(data['total_score'] for data in broadsheet_data)
    grand_average = sum(data['average'] for data in broadsheet_data) / len(broadsheet_data) if broadsheet_data else 0
    school_settings = SchoolSettings.get_for_school(class_teacher.school_class.school)
    
    return render(request, 'class_teacher/print_broadsheet.html', {
        'broadsheet_data': broadsheet_data,
        'subjects': subjects,
        'class_name': class_teacher.school_class.name,
        'term': active_term,
        'best_per_subject': best_per_subject,
        'subject_averages': subject_averages,
        'grand_total': grand_total,
        'grand_average': grand_average,
        'total_students': students.count(),
        'school_settings': school_settings
    })


@login_required
def manage_attendance(request):
    """Allow class teachers to record attendance and result comments for their students."""
    teacher = Teacher.objects.get(user=request.user)
    try:
        class_teacher = ClassTeacher.objects.get(teacher=teacher)
    except ClassTeacher.DoesNotExist:
        return redirect('core:dashboard')

    students = Student.objects.filter(school_class=class_teacher.school_class).select_related('user')
    active_term = Term.objects.filter(is_active=True).first()

    if not active_term:
        messages.error(request, 'No active term is set. Please contact the administrator.')
        return redirect('core:dashboard')

    if request.method == 'POST':
        for student in students:
            total_days_str = request.POST.get(f'attendance_{student.id}_total_days', '').strip()
            present_days_str = request.POST.get(f'attendance_{student.id}_days_present', '').strip()
            teacher_comment = request.POST.get(f'comment_{student.id}', '').strip()

            # Save attendance if any value is provided
            if total_days_str or present_days_str:
                try:
                    total_days = int(total_days_str or 0)
                    days_present = int(present_days_str or 0)
                except ValueError:
                    continue

                days_absent = max(total_days - days_present, 0)
                Attendance.objects.update_or_create(
                    student=student,
                    term=active_term,
                    defaults={
                        'total_days': total_days,
                        'days_present': days_present,
                        'days_absent': days_absent,
                    }
                )

            # Save teacher comment (create record even if comment is empty but previously existed)
            if teacher_comment or Comment.objects.filter(student=student, term=active_term).exists():
                Comment.objects.update_or_create(
                    student=student,
                    term=active_term,
                    defaults={
                        'teacher_comment': teacher_comment,
                    }
                )

        messages.success(request, 'Attendance and comments updated successfully.')
        return redirect('core:manage_attendance')

    # Preload existing attendance and comments for display
    attendance_qs = Attendance.objects.filter(student__in=students, term=active_term)
    comment_qs = Comment.objects.filter(student__in=students, term=active_term)

    attendance_map = {att.student.id: att for att in attendance_qs}
    comment_map = {com.student.id: com for com in comment_qs}

    return render(request, 'class_teacher/manage_attendance.html', {
        'teacher': teacher,
        'class_teacher': class_teacher,
        'students': students,
        'term': active_term,
        'attendance_map': attendance_map,
        'comment_map': comment_map,
    })

@login_required
def results_overview(request):
    if not request.user.has_role('subject_teacher'):
        return redirect('core:dashboard')
    
    teacher = Teacher.objects.get(user=request.user)
    return render(request, 'teacher/results_overview.html', {
        'classes': teacher.classes.all(),
        'subjects': teacher.subjects.all(),
    })

@login_required
@feature_required('reports_results')
def component_results(request):
    if not request.user.has_role('subject_teacher'):
        return redirect('core:dashboard')
    
    teacher = Teacher.objects.get(user=request.user)
    terms = Term.objects.all().order_by('-start_date')
    active_term = terms.filter(is_active=True).first()
    return render(request, 'teacher/component_results.html', {
        'classes': teacher.classes.all(),
        'subjects': teacher.subjects.all(),
        'terms': terms,
        'active_term': active_term,
    })

@login_required
def get_components(request):
    class_id = request.GET.get('class_id')
    subject_id = request.GET.get('subject_id')
    
    if class_id and subject_id:
        components = ResultComponent.objects.filter(
            school_class_id=class_id,
            subject_id=subject_id
        ).values('id', 'component_name', 'weight', 'max_score')
        
        return JsonResponse({'components': list(components)})
    
    return JsonResponse({'components': []})

@login_required
def get_student_results(request):
    class_id = request.GET.get('class_id')
    subject_id = request.GET.get('subject_id')
    term_id = request.GET.get('term_id')
    
    if class_id and subject_id and term_id:
        students = Student.objects.filter(school_class_id=class_id)
        student_data = []
        
        for student in students:
            # Get component scores
            component_scores = {}
            components = ResultComponent.objects.filter(
                school_class_id=class_id,
                subject_id=subject_id
            )
            
            for component in components:
                try:
                    comp_result = ComponentResult.objects.get(
                        student=student,
                        component=component,
                        term_id=term_id
                    )
                    component_scores[component.id] = float(comp_result.score)
                except ComponentResult.DoesNotExist:
                    component_scores[component.id] = None
            
            # Get final result
            try:
                result = Result.objects.get(
                    student=student,
                    subject_id=subject_id,
                    term_id=term_id
                )
                total_score = float(result.total_score)
                grade = result.grade
            except Result.DoesNotExist:
                total_score = None
                grade = None
            
            student_data.append({
                'id': student.id,
                'name': student.user.get_full_name(),
                'student_id': student.student_id,
                'component_scores': component_scores,
                'total_score': total_score,
                'grade': grade
            })
        
        return JsonResponse({'students': student_data})
    
    return JsonResponse({'students': []})

@login_required
def update_component_score(request):
    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON data'})
        
        student_id = data.get('student_id')
        component_id = data.get('component_id')
        term_id = data.get('term_id')
        score = data.get('score')
        
        try:
            student = Student.objects.get(id=student_id)
            component = ResultComponent.objects.get(id=component_id)
            term = Term.objects.get(id=term_id)
            
            # Verify teacher can manage this
            teacher = Teacher.objects.get(user=request.user)
            if (component.subject not in teacher.subjects.all() or 
                student.school_class not in teacher.classes.all()):
                return JsonResponse({'success': False, 'message': 'Unauthorized'})
            
            # Update component result
            comp_result, created = ComponentResult.objects.update_or_create(
                student=student,
                component=component,
                term=term,
                defaults={'score': score}
            )
            
            # Recalculate final result
            result, created = Result.objects.get_or_create(
                student=student,
                subject=component.subject,
                term=term
            )
            result.calculate_total()
            
            return JsonResponse({
                'success': True,
                'total_score': float(result.total_score),
                'grade': result.grade
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@login_required
def student_promotion(request):
    teacher = Teacher.objects.get(user=request.user)
    try:
        class_teacher = ClassTeacher.objects.get(teacher=teacher)
    except ClassTeacher.DoesNotExist:
        return redirect('core:dashboard')
    
    students = Student.objects.filter(school_class=class_teacher.school_class)
    
    # Calculate promotion eligibility
    students_data = []
    eligible_count = 0
    not_eligible_count = 0
    promoted_count = 0
    
    active_term = Term.objects.filter(is_active=True).first()
    
    for student in students:
        # Calculate average and failures
        results = Result.objects.filter(student=student, term=active_term)
        
        if results.exists():
            total_score = sum(float(r.total_score) for r in results)
            average = total_score / results.count()
            failures = results.filter(total_score__lt=50).count()
        else:
            average = 0
            failures = 0
        
        # Mock attendance (in real system, get from attendance records)
        attendance = 85  # Default attendance percentage
        
        # Check eligibility
        eligible = (average >= 50 and failures <= 2 and attendance >= 75)
        
        if student.is_promoted:
            promoted_count += 1
        elif eligible:
            eligible_count += 1
        else:
            not_eligible_count += 1
        
        students_data.append({
            'student': student,
            'average': average,
            'failures': failures,
            'attendance': attendance,
            'eligible': eligible
        })
    
    # Get available classes for promotion
    available_classes = SchoolClass.objects.exclude(id=class_teacher.school_class.id)
    
    return render(request, 'class_teacher/student_promotion.html', {
        'class_teacher': class_teacher,
        'students_data': students_data,
        'available_classes': available_classes,
        'eligible_count': eligible_count,
        'not_eligible_count': not_eligible_count,
        'promoted_count': promoted_count,
        'total_students': students.count()
    })

@login_required
def promote_students(request):
    if request.method == 'POST':
        import json
        data = json.loads(request.body)
        
        student_ids = data.get('student_ids', [])
        target_class_id = data.get('target_class_id')
        force_promote = data.get('force_promote', False)
        
        try:
            target_class = SchoolClass.objects.get(id=target_class_id)
            
            for student_id in student_ids:
                student = Student.objects.get(id=student_id)
                student.is_promoted = True
                student.promoted_to = target_class
                student.save()
            
            return JsonResponse({
                'success': True, 
                'message': f'{len(student_ids)} students promoted successfully'
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False})

@login_required
@feature_required('reports_analytics')
def view_analytics(request):
    if not request.user.has_role('subject_teacher'):
        return redirect('core:dashboard')
    
    teacher = Teacher.objects.get(user=request.user)
    class_id = request.GET.get('class_id')
    subject_id = request.GET.get('subject_id')
    
    if class_id and subject_id:
        results = Result.objects.filter(
            student__school_class_id=class_id,
            subject_id=subject_id
        )
        
        total_students = results.values('student').distinct().count()
        avg_score = results.aggregate(Avg('total_score'))['total_score__avg'] or 0
        pass_count = results.filter(total_score__gte=50).count()
        fail_count = results.filter(total_score__lt=50).count()
        
        grade_distribution = []
        for grade in ['A+', 'A', 'B', 'C', 'D', 'F']:
            count = results.filter(grade=grade).count()
            percentage = (count * 100 / total_students) if total_students > 0 else 0
            grade_distribution.append({'grade': grade, 'count': count, 'percentage': percentage})
        
        context = {
            'school_class': SchoolClass.objects.get(id=class_id),
            'subject': Subject.objects.get(id=subject_id),
            'total_students': total_students,
            'avg_score': avg_score,
            'pass_count': pass_count,
            'fail_count': fail_count,
            'grade_distribution': grade_distribution,
            'has_data': True,
        }
    else:
        context = {
            'classes': teacher.classes.all(),
            'subjects': teacher.subjects.all(),
        }
    
    return render(request, 'teacher/analytics.html', context)

@login_required
def export_results(request):
    if not request.user.has_role('subject_teacher'):
        return redirect('core:dashboard')
    
    import csv
    from django.http import HttpResponse
    
    class_id = request.GET.get('class_id')
    subject_id = request.GET.get('subject_id')
    
    if not class_id or not subject_id:
        messages.error(request, 'Please select class and subject')
        return redirect('core:results_overview')
    
    school_class = SchoolClass.objects.get(id=class_id)
    subject = Subject.objects.get(id=subject_id)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{school_class.name}_{subject.code}_results.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Student ID', 'Student Name', 'Total Score', 'Grade', 'Grade Point', 'Remark'])
    
    results = Result.objects.filter(
        student__school_class=school_class,
        subject=subject
    ).select_related('student__user')
    
    for result in results:
        writer.writerow([
            result.student.student_id,
            result.student.user.get_full_name(),
            result.total_score,
            result.grade,
            result.grade_point,
            result.remark
        ])
    
    return response

@login_required
@feature_required('cbt_quiz')
def view_quiz_result(request, quiz_id):
    if not request.user.has_role('student'):
        return redirect('core:dashboard')
    
    quiz = get_object_or_404(Quiz, id=quiz_id)
    student = Student.objects.get(user=request.user)
    attempt = get_object_or_404(QuizAttempt, quiz=quiz, student=student, is_submitted=True)
    
    questions = quiz.questions.all()
    results = []
    
    for question in questions:
        try:
            answer = QuizAnswer.objects.get(attempt=attempt, question=question)
            user_answer = answer.selected_answer if question.question_type in ['objective', 'multichoice'] else answer.theory_answer
            user_answers_list = user_answer.split(',') if user_answer else []
            correct_answers_list = question.correct_answer.split(',') if question.correct_answer else []
            
            results.append({
                'question': question,
                'user_answer': user_answer,
                'user_answers_list': user_answers_list,
                'correct_answers_list': correct_answers_list,
                'is_correct': answer.is_correct,
                'manual_score': answer.manual_score,
                'feedback': answer.teacher_feedback
            })
        except QuizAnswer.DoesNotExist:
            results.append({
                'question': question,
                'user_answer': None,
                'user_answers_list': [],
                'correct_answers_list': question.correct_answer.split(',') if question.correct_answer else [],
                'is_correct': False,
                'manual_score': 0,
                'feedback': ''
            })
    
    return render(request, 'student/view_quiz_result.html', {
        'quiz': quiz,
        'attempt': attempt,
        'results': results
    })

@login_required
def generate_tokens(request):
    if not request.user.has_role('super_admin'):
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        term_id = request.POST.get('term_id')
        max_uses = int(request.POST.get('max_uses', 3))
        individual = request.POST.get('individual')
        
        term = Term.objects.get(id=term_id)
        
        if individual:
            student_id = request.POST.get('student_id')
            student = Student.objects.get(id=student_id)
            action = request.POST.get('action', 'create')
            
            if action == 'regenerate':
                ResultToken.objects.filter(student=student, term=term).delete()
                token = ResultToken.objects.create(student=student, term=term, max_uses=max_uses)
                messages.success(request, f'New token regenerated for {student.user.get_full_name()}')
            else:
                token, created = ResultToken.objects.get_or_create(
                    student=student,
                    term=term,
                    defaults={'max_uses': max_uses}
                )
                if created:
                    messages.success(request, f'Token generated for {student.user.get_full_name()}')
                else:
                    messages.warning(request, f'Token already exists for {student.user.get_full_name()} - use Regenerate to create new token')
        else:
            students = Student.objects.all()
            action = request.POST.get('action', 'create')
            
            if action == 'regenerate':
                ResultToken.objects.filter(term=term).delete()
                for student in students:
                    ResultToken.objects.create(student=student, term=term, max_uses=max_uses)
                messages.success(request, f'All tokens regenerated for {students.count()} students')
            else:
                created_count = 0
                for student in students:
                    _, created = ResultToken.objects.get_or_create(
                        student=student,
                        term=term,
                        defaults={'max_uses': max_uses}
                    )
                    if created:
                        created_count += 1
                messages.success(request, f'Tokens generated: {created_count} new, {students.count() - created_count} already existed')
        
        return redirect('core:generate_tokens')
    
    terms = Term.objects.all()
    students = Student.objects.select_related('user', 'school_class').order_by('student_id')
    tokens = ResultToken.objects.select_related('student__user', 'student__school_class', 'term').order_by('-created_at')
    return render(request, 'admin/generate_tokens.html', {'terms': terms, 'students': students, 'tokens': tokens})

def check_result(request):
    if request.method == 'POST':
        token = request.POST.get('token', '').strip().upper()
        
        try:
            result_token = ResultToken.objects.get(token=token)
            
            if not result_token.can_use():
                messages.error(request, 'Token usage limit exceeded')
                return redirect('core:check_result')
            
            result_token.use_token()
            return redirect('core:view_result_card', token=token)
            
        except ResultToken.DoesNotExist:
            messages.error(request, 'Invalid token')
    
    return render(request, 'check_result.html')

def view_result_card(request, token):
    result_token = get_object_or_404(ResultToken, token=token)
    student = result_token.student
    term = result_token.term
    
    # Get report card settings
    report_settings = ReportCardSettings.objects.filter(is_active=True).first()
    if not report_settings:
        report_settings = ReportCardSettings()  # Use defaults
    
    # Get results for current term
    results = Result.objects.filter(student=student, term=term).select_related('subject')
    
    # Calculate total obtainable marks
    total_obtainable = 0
    for result in results:
        components = ResultComponent.objects.filter(
            subject=result.subject,
            school_class=student.school_class
        )
        subject_total = sum(comp.weight for comp in components)
        total_obtainable += subject_total
    
    # Handle term-specific display
    term_number = None
    if '1st' in term.name or 'First' in term.name:
        term_number = 1
    elif '2nd' in term.name or 'Second' in term.name:
        term_number = 2
    elif '3rd' in term.name or 'Third' in term.name:
        term_number = 3
    
    # For 3rd term, get cumulative results
    cumulative_results = []
    if term_number == 3:
        # Get all terms in the session
        session_terms = Term.all_objects.filter(school=student.school, session=term.session).order_by('start_date')
        
        for result in results:
            subject_cumulative = {
                'subject': result.subject,
                'first_term': None,
                'second_term': None,
                'third_term': None,
                'components': [],
                'cumulative_total': 0,
                'cumulative_average': 0,
                'grade': result.grade,
                'remark': result.remark,
                'terms_count': 0,
            }
            
            # Get scores for all terms
            for session_term in session_terms:
                try:
                    term_result = Result.objects.get(
                        student=student,
                        subject=result.subject,
                        term=session_term
                    )
                    score = float(term_result.total_score)
                    subject_cumulative['cumulative_total'] += score
                    subject_cumulative['terms_count'] += 1
                    
                    # Map to specific term attributes
                    if '1st' in session_term.name or 'First' in session_term.name:
                        subject_cumulative['first_term'] = score
                    elif '2nd' in session_term.name or 'Second' in session_term.name:
                        subject_cumulative['second_term'] = score
                    elif '3rd' in session_term.name or 'Third' in session_term.name:
                        subject_cumulative['third_term'] = score
                        # Get 3rd term component breakdown
                        components = ResultComponent.objects.filter(
                            subject=result.subject,
                            school_class=student.school_class
                        )
                        for component in components:
                            try:
                                comp_result = ComponentResult.objects.get(
                                    student=student,
                                    component=component,
                                    term=session_term
                                )
                                subject_cumulative['components'].append({
                                    'name': component.component_name,
                                    'score': comp_result.score,
                                    'max_score': component.max_score
                                })
                            except ComponentResult.DoesNotExist:
                                subject_cumulative['components'].append({
                                    'name': component.component_name,
                                    'score': 0,
                                    'max_score': component.max_score
                                })
                except Result.DoesNotExist:
                    pass
            
            # Calculate cumulative average from terms that actually have scores.
            # This lets a third-term report still grade correctly when first or
            # second term results were not entered.
            if subject_cumulative['terms_count'] > 0:
                subject_cumulative['cumulative_average'] = (
                    subject_cumulative['cumulative_total'] / subject_cumulative['terms_count']
                )
                cumulative_grade = GradingSystem.all_objects.filter(
                    school=student.school,
                    min_score__lte=subject_cumulative['cumulative_average'],
                    max_score__gte=subject_cumulative['cumulative_average'],
                ).first()
                if cumulative_grade:
                    subject_cumulative['grade'] = cumulative_grade.grade
                    subject_cumulative['remark'] = cumulative_grade.remark
            
            cumulative_results.append(subject_cumulative)
    
    # Get component breakdown for current term
    component_breakdown = []
    for result in results:
        components = ResultComponent.objects.filter(
            subject=result.subject,
            school_class=student.school_class
        )
        
        subject_components = {
            'subject': result.subject,
            'components': [],
            'total_score': result.total_score,
            'grade': result.grade,
            'remark': result.remark
        }
        
        for component in components:
            try:
                comp_result = ComponentResult.objects.get(
                    student=student,
                    component=component,
                    term=term
                )
                subject_components['components'].append({
                    'name': component.component_name,
                    'score': comp_result.score,
                    'max_score': component.max_score,
                    'weight': component.weight
                })
            except ComponentResult.DoesNotExist:
                subject_components['components'].append({
                    'name': component.component_name,
                    'score': 0,
                    'max_score': component.max_score,
                    'weight': component.weight
                })
        
        component_breakdown.append(subject_components)
    
    # Overall totals/averages for this student
    total_score = sum(float(r.total_score) for r in results)
    total_subjects = results.count()
    average = total_score / total_subjects if total_subjects > 0 else 0
    overall_percentage = average
    
    # Derive overall grade/remark from grading system
    overall_grade = None
    overall_remark = ''
    grading = GradingSystem.objects.filter(
        min_score__lte=average,
        max_score__gte=average
    ).first()
    if grading:
        overall_grade = grading.grade
        overall_remark = grading.remark
    
    # Batch/class ranking statistics
    from django.db.models import Avg as AvgFunc
    class_results = Result.objects.filter(
        student__school_class=student.school_class,
        term=term
    ).values('student').annotate(avg=AvgFunc('total_score')).order_by('-avg')
    
    position = 1
    class_highest = 0
    class_lowest = 0
    class_average = 0
    
    if class_results:
        # Determine this student's position
        for idx, cr in enumerate(class_results, 1):
            if cr['student'] == student.id:
                position = idx
                break
        
        avg_values = [float(cr['avg']) for cr in class_results]
        class_highest = max(avg_values)
        class_lowest = min(avg_values)
        class_average = sum(avg_values) / len(avg_values)
    
    attendance = Attendance.objects.filter(student=student, term=term).first()
    comment = Comment.objects.filter(student=student, term=term).first()
    psychomotor = Psychomotor.objects.filter(student=student, term=term).first()
    effective_domain = EffectiveDomain.objects.filter(student=student, term=term).first()
    school_settings = SchoolSettings.get_for_school(student.school)
    total_students = Student.objects.filter(school_class=student.school_class).count()
    
    # Get class teacher
    class_teacher = None
    try:
        class_teacher = ClassTeacher.objects.select_related('teacher__user').get(school_class=student.school_class)
    except ClassTeacher.DoesNotExist:
        pass
    
    # Get head teacher for this class
    head_teacher = None
    try:
        head_teacher = HeadTeacher.objects.select_related('teacher__user').filter(
            teacher__school=student.school,
            classes=student.school_class,
        ).first()
    except HeadTeacher.DoesNotExist:
        pass
    
    # Get next term resumption date
    next_resumption = term.get_next_term_resumption()
    if not next_resumption and hasattr(term, 'resumption_date'):
        next_resumption = term.resumption_date
    
    context = {
        'student': student,
        'term': term,
        'term_number': term_number,
        'results': results,
        'cumulative_results': cumulative_results,
        'component_breakdown': component_breakdown,
        'average': average,
        'total_score': total_score,
        'total_obtainable': total_obtainable,
        'overall_percentage': overall_percentage,
        'overall_grade': overall_grade,
        'overall_remark': overall_remark,
        'position': position,
        'total_students': total_students,
        'class_highest': class_highest,
        'class_lowest': class_lowest,
        'class_average': class_average,
        'attendance': attendance,
        'comment': comment,
        'psychomotor': psychomotor,
        'effective_domain': effective_domain,
        'school_settings': school_settings,
        'class_teacher': class_teacher,
        'head_teacher': head_teacher,
        'next_resumption': next_resumption,
        'report_settings': report_settings,
    }
    
    return render(request, 'result_card.html', context)

@login_required
def revert_promotion(request):
    if request.method == 'POST':
        import json
        data = json.loads(request.body)
        
        student_id = data.get('student_id')
        
        try:
            student = Student.objects.get(id=student_id)
            student.is_promoted = False
            student.promoted_to = None
            student.save()
            
            return JsonResponse({'success': True, 'message': 'Promotion reverted successfully'})
            
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False})

@login_required
def save_broadsheet_comments(request):
    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
            comments = data.get('comments', [])
            active_term = Term.objects.filter(is_active=True).first()
            
            if not active_term:
                return JsonResponse({'success': False, 'message': 'No active term'})
            
            for comment_data in comments:
                student = Student.objects.get(id=comment_data['student_id'])
                Comment.objects.update_or_create(
                    student=student,
                    term=active_term,
                    defaults={
                        'teacher_comment': comment_data['teacher_comment'],
                        'proprietor_comment': comment_data['ht_comment']
                    }
                )
            
            return JsonResponse({'success': True, 'message': 'Comments saved successfully'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': 'Invalid request'})

@login_required
def generate_ai_comment(request):
    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
            student_id = data.get('student_id')
            average = float(data.get('average', 0))
            
            student = Student.objects.get(id=student_id)
            active_term = Term.objects.filter(is_active=True).first()
            
            # Get student results for more context
            results = Result.objects.filter(student=student, term=active_term)
            
            # Count strengths and weaknesses
            strong_subjects = []
            weak_subjects = []
            
            for result in results:
                if float(result.total_score) >= 75:
                    strong_subjects.append(result.subject.name)
                elif float(result.total_score) < 50:
                    weak_subjects.append(result.subject.name)
            
            # Generate contextual comment
            name = student.user.first_name
            comment = f"{name} "
            
            if average >= 80:
                comment += "has demonstrated exceptional academic excellence this term. "
                if strong_subjects:
                    comment += f"Particularly outstanding in {', '.join(strong_subjects[:2])}. "
                comment += "Continue this remarkable performance."
            elif average >= 70:
                comment += "has shown very good academic performance. "
                if strong_subjects:
                    comment += f"Shows strength in {', '.join(strong_subjects[:2])}. "
                if weak_subjects:
                    comment += f"Should focus more on {', '.join(weak_subjects[:2])}. "
                comment += "Keep up the good work."
            elif average >= 60:
                comment += "has made satisfactory progress this term. "
                if weak_subjects:
                    comment += f"Needs improvement in {', '.join(weak_subjects[:2])}. "
                comment += "More consistent effort required."
            elif average >= 50:
                comment += "shows fair performance but needs significant improvement. "
                if weak_subjects:
                    comment += f"Requires extra attention in {', '.join(weak_subjects[:2])}. "
                comment += "Must work harder next term."
            else:
                comment += "requires urgent intervention and support. "
                comment += "Parent-teacher conference recommended. "
                comment += "Extra classes and dedicated study time essential."
            
            return JsonResponse({'success': True, 'comment': comment})
            
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': 'Invalid request'})

@login_required
def admin_view_result(request, student_id, term_id):
    if not request.user.has_any_role(['super_admin', 'class_teacher']):
        return redirect('core:dashboard')
    
    student = get_object_or_404(Student, id=student_id)
    term = get_object_or_404(Term, id=term_id)
    
    # Get report card settings
    report_settings = ReportCardSettings.objects.filter(is_active=True).first()
    if not report_settings:
        report_settings = ReportCardSettings()  # Use defaults
    
    # Get results for current term
    results = Result.objects.filter(student=student, term=term).select_related('subject')
    
    # Calculate total obtainable marks
    total_obtainable = 0
    for result in results:
        components = ResultComponent.objects.filter(
            subject=result.subject,
            school_class=student.school_class
        )
        subject_total = sum(comp.weight for comp in components)
        total_obtainable += subject_total
    
    # Handle term-specific display
    term_number = None
    if '1st' in term.name or 'First' in term.name:
        term_number = 1
    elif '2nd' in term.name or 'Second' in term.name:
        term_number = 2
    elif '3rd' in term.name or 'Third' in term.name:
        term_number = 3
    
    # For 3rd term, get cumulative results
    cumulative_results = []
    if term_number == 3:
        session_terms = Term.all_objects.filter(school=student.school, session=term.session).order_by('start_date')
        
        for result in results:
            subject_cumulative = {
                'subject': result.subject,
                'first_term': None,
                'second_term': None,
                'third_term': None,
                'components': [],
                'cumulative_total': 0,
                'cumulative_average': 0,
                'grade': result.grade,
                'remark': result.remark,
                'terms_count': 0,
            }
            
            for session_term in session_terms:
                try:
                    term_result = Result.objects.get(
                        student=student,
                        subject=result.subject,
                        term=session_term
                    )
                    score = float(term_result.total_score)
                    subject_cumulative['cumulative_total'] += score
                    subject_cumulative['terms_count'] += 1
                    
                    # Map to specific term attributes
                    if '1st' in session_term.name or 'First' in session_term.name:
                        subject_cumulative['first_term'] = score
                    elif '2nd' in session_term.name or 'Second' in session_term.name:
                        subject_cumulative['second_term'] = score
                    elif '3rd' in session_term.name or 'Third' in session_term.name:
                        subject_cumulative['third_term'] = score
                        # Get 3rd term component breakdown
                        components = ResultComponent.objects.filter(
                            subject=result.subject,
                            school_class=student.school_class
                        )
                        for component in components:
                            try:
                                comp_result = ComponentResult.objects.get(
                                    student=student,
                                    component=component,
                                    term=session_term
                                )
                                subject_cumulative['components'].append({
                                    'name': component.component_name,
                                    'score': comp_result.score,
                                    'max_score': component.max_score
                                })
                            except ComponentResult.DoesNotExist:
                                subject_cumulative['components'].append({
                                    'name': component.component_name,
                                    'score': 0,
                                    'max_score': component.max_score
                                })
                except Result.DoesNotExist:
                    pass
            
            if subject_cumulative['terms_count'] > 0:
                subject_cumulative['cumulative_average'] = (
                    subject_cumulative['cumulative_total'] / subject_cumulative['terms_count']
                )
                cumulative_grade = GradingSystem.all_objects.filter(
                    school=student.school,
                    min_score__lte=subject_cumulative['cumulative_average'],
                    max_score__gte=subject_cumulative['cumulative_average'],
                ).first()
                if cumulative_grade:
                    subject_cumulative['grade'] = cumulative_grade.grade
                    subject_cumulative['remark'] = cumulative_grade.remark
            
            cumulative_results.append(subject_cumulative)
    
    # Get component breakdown for current term
    component_breakdown = []
    for result in results:
        components = ResultComponent.objects.filter(
            subject=result.subject,
            school_class=student.school_class
        )
        
        subject_components = {
            'subject': result.subject,
            'components': [],
            'total_score': result.total_score,
            'grade': result.grade,
            'remark': result.remark
        }
        
        for component in components:
            try:
                comp_result = ComponentResult.objects.get(
                    student=student,
                    component=component,
                    term=term
                )
                subject_components['components'].append({
                    'name': component.component_name,
                    'score': comp_result.score,
                    'max_score': component.max_score,
                    'weight': component.weight
                })
            except ComponentResult.DoesNotExist:
                subject_components['components'].append({
                    'name': component.component_name,
                    'score': 0,
                    'max_score': component.max_score,
                    'weight': component.weight
                })
        
        component_breakdown.append(subject_components)
    
    # Calculate statistics
    total_score = sum(float(r.total_score) for r in results)
    total_subjects = results.count()
    average = total_score / total_subjects if total_subjects > 0 else 0
    overall_percentage = average
    
    # Get overall grade/remark
    overall_grade = None
    overall_remark = ''
    grading = GradingSystem.objects.filter(
        min_score__lte=average,
        max_score__gte=average
    ).first()
    if grading:
        overall_grade = grading.grade
        overall_remark = grading.remark
    
    # Class ranking
    from django.db.models import Avg as AvgFunc
    class_results = Result.objects.filter(
        student__school_class=student.school_class,
        term=term
    ).values('student').annotate(avg=AvgFunc('total_score')).order_by('-avg')
    
    position = 1
    class_highest = 0
    class_average = 0
    
    if class_results:
        for idx, cr in enumerate(class_results, 1):
            if cr['student'] == student.id:
                position = idx
                break
        
        avg_values = [float(cr['avg']) for cr in class_results]
        class_highest = max(avg_values)
        class_average = sum(avg_values) / len(avg_values)
    
    # Get additional data
    attendance = Attendance.objects.filter(student=student, term=term).first()
    comment = Comment.objects.filter(student=student, term=term).first()
    psychomotor = Psychomotor.objects.filter(student=student, term=term).first()
    effective_domain = EffectiveDomain.objects.filter(student=student, term=term).first()
    school_settings = SchoolSettings.get_for_school(student.school)
    total_students = Student.objects.filter(school_class=student.school_class).count()
    
    # Get teachers
    class_teacher = None
    try:
        class_teacher = ClassTeacher.objects.select_related('teacher__user').get(school_class=student.school_class)
    except ClassTeacher.DoesNotExist:
        pass
    
    head_teacher = None
    try:
        head_teacher = HeadTeacher.objects.select_related('teacher__user').filter(
            teacher__school=student.school,
            classes=student.school_class,
        ).first()
    except HeadTeacher.DoesNotExist:
        pass
    
    next_resumption = term.get_next_term_resumption()
    if not next_resumption and hasattr(term, 'resumption_date'):
        next_resumption = term.resumption_date
    
    context = {
        'student': student,
        'term': term,
        'term_number': term_number,
        'results': results,
        'cumulative_results': cumulative_results,
        'component_breakdown': component_breakdown,
        'average': average,
        'total_score': total_score,
        'total_obtainable': total_obtainable,
        'overall_percentage': overall_percentage,
        'overall_grade': overall_grade,
        'overall_remark': overall_remark,
        'position': position,
        'total_students': total_students,
        'class_highest': class_highest,
        'class_average': class_average,
        'attendance': attendance,
        'comment': comment,
        'psychomotor': psychomotor,
        'effective_domain': effective_domain,
        'school_settings': school_settings,
        'class_teacher': class_teacher,
        'head_teacher': head_teacher,
        'next_resumption': next_resumption,
        'report_settings': report_settings,
        'is_admin_view': True,
    }
    
    return render(request, 'result_card.html', context)

@login_required
def student_results_lookup(request):
    if not request.user.has_any_role(['super_admin', 'class_teacher']):
        return redirect('core:dashboard')
    
    students = Student.objects.select_related('user', 'school_class').order_by('school_class__name', 'user__first_name')
    terms = Term.objects.all().order_by('-start_date')
    
@login_required
def report_card_settings(request):
    if not request.user.has_role('super_admin'):
        return redirect('core:dashboard')
    
    settings, created = ReportCardSettings.objects.get_or_create(
        is_active=True,
        defaults={
            'show_position': True,
            'show_subject_position': True,
            'show_class_average': True,
            'show_highest_in_class': True,
            'show_attendance': True,
            'show_psychomotor': True,
            'show_effective_domain': True,
            'show_next_resumption': True,
            'show_total_obtainable': True,
            'show_school_opened_days': True,
        }
    )
    
    if request.method == 'POST':
        settings.show_position = request.POST.get('show_position') == 'on'
        settings.show_subject_position = request.POST.get('show_subject_position') == 'on'
        settings.show_class_average = request.POST.get('show_class_average') == 'on'
        settings.show_highest_in_class = request.POST.get('show_highest_in_class') == 'on'
        settings.show_attendance = request.POST.get('show_attendance') == 'on'
        settings.show_psychomotor = request.POST.get('show_psychomotor') == 'on'
        settings.show_effective_domain = request.POST.get('show_effective_domain') == 'on'
        settings.show_next_resumption = request.POST.get('show_next_resumption') == 'on'
        settings.show_total_obtainable = request.POST.get('show_total_obtainable') == 'on'
        settings.show_school_opened_days = request.POST.get('show_school_opened_days') == 'on'
        settings.save()
        
        messages.success(request, 'Report card settings updated successfully!')
        return redirect('core:report_card_settings')
    
    return render(request, 'admin/report_card_settings.html', {'settings': settings})

@login_required
def student_results_lookup(request):
    if not request.user.has_any_role(['super_admin', 'class_teacher']):
        return redirect('core:dashboard')
    
    students = Student.objects.select_related('user', 'school_class').order_by('school_class__name', 'user__first_name')
    terms = Term.objects.all().order_by('-start_date')
    
    return render(request, 'admin/student_results_lookup.html', {
        'students': students,
        'terms': terms
    })

@login_required
@feature_required('cbt_quiz')
def enhanced_quiz(request, quiz_id):
    if not request.user.has_role('student'):
        return redirect('core:dashboard')
    
    quiz = get_object_or_404(Quiz, id=quiz_id)
    student = Student.objects.get(user=request.user)
    
    if not quiz.is_live():
        messages.error(request, 'Quiz is not currently available')
        return redirect('core:dashboard')
    
    attempt, created = QuizAttempt.objects.get_or_create(
        quiz=quiz, student=student,
        defaults={'start_time': timezone.now()}
    )
    
    if attempt.is_submitted:
        return redirect('core:view_quiz_result', quiz_id=quiz_id)
    
    # Organize questions by groups and standalone
    question_groups = QuestionGroupInstance.objects.filter(quiz=quiz).prefetch_related('questions').order_by('order')
    standalone_questions = quiz.questions.filter(group_instance__isnull=True).order_by('order')
    
    # Build questions_data with proper numbering
    questions_data = []
    question_counter = 1
    
    # Add groups
    for group in question_groups:
        group_questions = list(group.questions.all().order_by('order'))
        # Add display_number to each question
        for i, q in enumerate(group_questions):
            q.display_number = question_counter + i
        questions_data.append({
            'type': 'group',
            'instruction': group.instruction,
            'questions': group_questions
        })
        question_counter += len(group_questions)
    
    # Add standalone questions
    for question in standalone_questions:
        questions_data.append({
            'type': 'question',
            'question': question,
            'question_number': question_counter
        })
        question_counter += 1
    
    # Shuffle only if enabled (groups stay together)
    if quiz.shuffle_questions:
        import random
        random.shuffle(questions_data)
        # Renumber after shuffle
        question_counter = 1
        for item in questions_data:
            if item['type'] == 'group':
                for i, q in enumerate(item['questions']):
                    q.display_number = question_counter + i
                question_counter += len(item['questions'])
            else:
                item['question_number'] = question_counter
                question_counter += 1
    
    # Flatten for processing
    all_questions = []
    for item in questions_data:
        if item['type'] == 'group':
            all_questions.extend(item['questions'])
        else:
            all_questions.append(item['question'])
    
    if request.method == 'POST':
        # Process submission
        auto_score = 0
        total_objective_marks = 0
        
        for question in all_questions:
            if question.question_type == 'objective':
                answer = request.POST.get(f'question_{question.id}')
                if answer:
                    quiz_answer, created = QuizAnswer.objects.update_or_create(
                        attempt=attempt, question=question,
                        defaults={'selected_answer': answer}
                    )
                    if quiz_answer.is_correct:
                        auto_score += question.max_marks
                total_objective_marks += question.max_marks
            
            elif question.question_type == 'multichoice':
                answers = request.POST.getlist(f'question_{question.id}')
                selected = ','.join(sorted(answers)) if answers else ''
                quiz_answer, created = QuizAnswer.objects.update_or_create(
                    attempt=attempt, question=question,
                    defaults={'selected_answer': selected}
                )
                if quiz_answer.is_correct:
                    auto_score += question.max_marks
                total_objective_marks += question.max_marks
            
            elif question.question_type == 'theory':
                theory_answer = request.POST.get(f'theory_{question.id}')
                if theory_answer:
                    QuizAnswer.objects.update_or_create(
                        attempt=attempt, question=question,
                        defaults={'theory_answer': theory_answer}
                    )
        
        # Update attempt
        attempt.end_time = timezone.now()
        attempt.is_submitted = True
        attempt.auto_score = auto_score
        
        # Check if all questions are auto-graded (objective/multichoice)
        theory_questions = [q for q in all_questions if q.question_type == 'theory']
        total_marks = sum(q.max_marks for q in all_questions)
        
        if not theory_questions:
            attempt.final_score = (auto_score / total_marks * 100) if total_marks > 0 else 0
            attempt.is_graded = True
        
        attempt.save()
        
        # Log auto-submit reason if present
        auto_submit_reason = request.POST.get('auto_submit_reason')
        if auto_submit_reason:
            attempt.add_integrity_event('auto_submit', auto_submit_reason)
        
        if theory_questions:
            messages.success(request, f'Quiz submitted! Objective score: {auto_score}/{total_objective_marks}. Theory questions pending review.')
        else:
            messages.success(request, f'Quiz submitted! Your score: {auto_score}/{total_objective_marks}')
        
        return redirect('core:dashboard')
    
    return render(request, 'student/enhanced_quiz.html', {
        'quiz': quiz,
        'questions_data': questions_data,
        'attempt': attempt
    })

