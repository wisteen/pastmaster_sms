import json
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .decorators_features import feature_required
from .forms_quiz import QuizForm, QuestionForm, TheoryGradeForm, question_errors
from .models import Quiz, QuizAttempt, QuizAnswer, Question, QuestionBank, QuestionGroup, QuestionGroupInstance, Student, Teacher
from .services_quiz import deadline_for, expire_attempt, finish_attempt, question_cards, recalculate, save_answers


def teacher_for(request):
    if not request.user.has_any_role(['subject_teacher', 'class_teacher']):
        return None
    return Teacher.objects.filter(user=request.user, status='active').first()


def student_for(request):
    if not request.user.has_role('student'):
        return None
    return Student.objects.filter(user=request.user, status='active').first()


def teacher_scope(teacher):
    from .views import _teacher_quiz_scope
    return _teacher_quiz_scope(teacher)


def quiz_is_locked(quiz):
    return quiz.quizattempt_set.exists()


@login_required
@feature_required('cbt_quiz')
def quiz_form(request, quiz_id=None):
    teacher = teacher_for(request)
    if not teacher:
        return HttpResponseForbidden('Only assigned teachers can manage quizzes.')
    classes, subjects = teacher_scope(teacher)
    with transaction.atomic():
        quiz = get_object_or_404(Quiz.objects.select_for_update(), pk=quiz_id, teacher=teacher) if quiz_id else Quiz(teacher=teacher)
        data = request.POST.copy() if request.method == 'POST' else None
        if data is not None and 'class' in data and 'school_class' not in data:
            data['school_class'] = data['class']
        form = QuizForm(data, instance=quiz, classes=classes, subjects=subjects)
        if request.method == 'POST' and form.is_valid():
            form.save()
            messages.success(request, 'Quiz settings saved.' if quiz_id else 'Draft created. Add questions, then publish your quiz.')
            return redirect('core:quiz_management' if quiz_id else 'core:add_questions', **({} if quiz_id else {'quiz_id': quiz.pk}))
    return render(request, 'teacher/quiz_form.html', {'form': form, 'quiz': quiz, 'editing': bool(quiz_id), 'locked': bool(quiz_id and quiz_is_locked(quiz))})


create_quiz = quiz_form
edit_quiz = quiz_form


@login_required
@feature_required('cbt_quiz')
def quiz_management(request):
    teacher = teacher_for(request)
    if not teacher:
        return HttpResponseForbidden('Only assigned teachers can manage quizzes.')
    quizzes = Quiz.objects.filter(teacher=teacher).select_related('subject', 'school_class').prefetch_related('questions', 'quizattempt_set').order_by('-created_at')
    return render(request, 'teacher/quiz_management.html', {'quizzes': quizzes})


@login_required
@feature_required('cbt_quiz')
def add_questions(request, quiz_id):
    teacher = teacher_for(request)
    if not teacher:
        return HttpResponseForbidden('Only assigned teachers can manage questions.')
    with transaction.atomic():
        quiz = get_object_or_404(Quiz.objects.select_for_update(), pk=quiz_id, teacher=teacher)
        locked = quiz_is_locked(quiz)
        form = QuestionForm(request.POST if request.method == 'POST' else None)
        if request.method == 'POST':
            if locked:
                form.add_error(None, 'Attempts have started. Questions are locked to preserve students’ work.')
            elif form.is_valid():
                question = form.save(commit=False)
                question.quiz = quiz
                question.order = quiz.questions.count()
                question.save()
                messages.success(request, 'Question added.')
                return redirect('core:add_questions', quiz_id=quiz.pk)
    return render(request, 'teacher/questions.html', {'quiz': quiz, 'form': form, 'questions': quiz.questions.all(), 'locked': locked})


@login_required
@feature_required('cbt_quiz')
def edit_question(request, question_id):
    teacher = teacher_for(request)
    if not teacher:
        return HttpResponseForbidden('Only assigned teachers can edit questions.')
    question = get_object_or_404(Question, pk=question_id, quiz__teacher=teacher)
    with transaction.atomic():
        quiz = Quiz.objects.select_for_update().get(pk=question.quiz_id)
        if quiz_is_locked(quiz):
            messages.error(request, 'Attempts have started. Questions are locked.')
            return redirect('core:add_questions', quiz_id=quiz.pk)
        form = QuestionForm(request.POST if request.method == 'POST' else None, instance=question)
        if request.method == 'POST' and form.is_valid():
            form.save()
            messages.success(request, 'Question updated.')
            return redirect('core:add_questions', quiz_id=quiz.pk)
    return render(request, 'teacher/questions.html', {'quiz': quiz, 'form': form, 'editing': True, 'questions': quiz.questions.all()})


@login_required
@feature_required('cbt_quiz')
def delete_question(request, question_id):
    if request.method != 'DELETE':
        return JsonResponse({'success': False}, status=405)
    teacher = teacher_for(request)
    if not teacher:
        return JsonResponse({'success': False, 'message': 'Only teachers can delete questions.'}, status=403)
    question = get_object_or_404(Question, pk=question_id, quiz__teacher=teacher)
    with transaction.atomic():
        quiz = Quiz.objects.select_for_update().get(pk=question.quiz_id)
        if quiz_is_locked(quiz):
            return JsonResponse({'success': False, 'message': 'Attempts have started. Questions are locked.'}, status=409)
        question.delete()
        if not quiz.questions.exists():
            quiz.status = 'draft'
            quiz.save(update_fields=['status'])
    return JsonResponse({'success': True})


@login_required
@feature_required('cbt_quiz')
def delete_quiz(request, quiz_id):
    if request.method != 'DELETE':
        return JsonResponse({'success': False}, status=405)
    teacher = teacher_for(request)
    if not teacher:
        return JsonResponse({'success': False}, status=403)
    with transaction.atomic():
        quiz = get_object_or_404(Quiz.objects.select_for_update(), pk=quiz_id, teacher=teacher)
        if quiz_is_locked(quiz):
            return JsonResponse({'success': False, 'message': 'This quiz has attempts. Set its status to Ended to preserve results.'}, status=409)
        quiz.delete()
    return JsonResponse({'success': True})


@login_required
@feature_required('cbt_quiz')
def student_cbt_dashboard(request):
    student = student_for(request)
    if not student:
        return redirect('core:dashboard')
    quizzes = Quiz.objects.filter(school_class=student.school_class).exclude(status='draft').select_related('subject').order_by('-start_time')
    attempts = {a.quiz_id: expire_attempt(a) for a in QuizAttempt.objects.filter(student=student, quiz__in=quizzes).select_related('quiz')}
    cards = []
    for quiz in quizzes:
        availability = 'live' if quiz.is_live() else 'upcoming' if quiz.status in ('live', 'scheduled') and quiz.start_time > timezone.now() else 'ended'
        cards.append({'quiz': quiz, 'attempt': attempts.get(quiz.pk), 'availability': availability})
    return render(request, 'student/cbt_dashboard.html', {'student': student, 'quiz_cards': cards})


@login_required
@feature_required('cbt_quiz')
def enhanced_quiz(request, quiz_id):
    student = student_for(request)
    if not student:
        return redirect('core:dashboard')
    with transaction.atomic():
        quiz = get_object_or_404(Quiz.objects.select_for_update(), pk=quiz_id, school_class=student.school_class)
        attempt = QuizAttempt.objects.select_for_update().filter(quiz=quiz, student=student).first()
        if attempt and attempt.is_submitted:
            if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'submitted': True, 'result_url': reverse('core:view_quiz_result', args=[quiz.pk])})
            return redirect('core:view_quiz_result', quiz_id=quiz.pk)
        if request.method == 'POST' and request.POST.get('action') == 'start' and not attempt:
            if not quiz.is_live() or not quiz.questions.exists():
                messages.error(request, 'This quiz is not available to start.')
                return redirect('core:student_cbt_dashboard')
            attempt = QuizAttempt.objects.create(quiz=quiz, student=student)
            return redirect('core:enhanced_quiz', quiz_id=quiz.pk)
        if request.method == 'POST' and request.POST.get('action') == 'start' and attempt:
            return redirect('core:enhanced_quiz', quiz_id=quiz.pk)
        if request.method == 'POST' and attempt and request.POST.get('action') != 'start':
            # A short transport allowance lets the automatic final request arrive.
            within_deadline = timezone.now() <= deadline_for(attempt) + timedelta(seconds=15)
            if within_deadline and quiz.status in ('live', 'scheduled'):
                save_answers(attempt, request.POST)
            finish_attempt(attempt, '' if within_deadline else 'Deadline reached; last saved answers submitted')
            result_url = reverse('core:view_quiz_result', args=[quiz.pk])
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'submitted': True, 'result_url': result_url})
            return redirect(result_url)
        if attempt and (timezone.now() >= deadline_for(attempt) or quiz.status == 'ended'):
            finish_attempt(attempt, 'Deadline reached; last saved answers submitted')
            return redirect('core:view_quiz_result', quiz_id=quiz.pk)
        if not quiz.is_live():
            messages.info(request, 'This quiz is not open. Check its start and end times.')
            return redirect('core:student_cbt_dashboard')
    if not attempt:
        return render(request, 'student/quiz_start.html', {'quiz': quiz, 'question_count': quiz.questions.count()})
    return render(request, 'student/enhanced_quiz.html', {
        'quiz': quiz, 'attempt': attempt, 'cards': question_cards(quiz, attempt),
        'quiz_config': {
            'deadline': deadline_for(attempt).isoformat(), 'serverNow': timezone.now().isoformat(),
            'saveUrl': reverse('core:save_quiz_answers', args=[quiz.pk]),
            'integrityUrl': reverse('core:quiz_integrity', args=[quiz.pk]),
            'resultUrl': reverse('core:view_quiz_result', args=[quiz.pk]),
            'tabSwitches': attempt.tab_switches, 'maxTabSwitches': quiz.max_tab_switches,
            'detectTabs': quiz.detect_tab_switching, 'fullscreen': quiz.full_screen_mode,
            'storageKey': f'quiz-draft-{student.pk}-{attempt.pk}',
        },
    })


take_quiz = enhanced_quiz


@login_required
@require_POST
@feature_required('cbt_quiz')
def save_quiz_answers(request, quiz_id):
    student = student_for(request)
    if not student:
        return JsonResponse({'error': 'Student access required.'}, status=403)
    with transaction.atomic():
        attempt = get_object_or_404(QuizAttempt.objects.select_for_update().select_related('quiz'), quiz_id=quiz_id, student=student, quiz__school_class=student.school_class)
        if not attempt.is_submitted and (timezone.now() >= deadline_for(attempt) or attempt.quiz.status == 'ended'):
            finish_attempt(attempt, 'Deadline reached; last saved answers submitted')
        if attempt.is_submitted:
            return JsonResponse({'submitted': True, 'result_url': reverse('core:view_quiz_result', args=[quiz_id])})
        save_answers(attempt, request.POST)
    return JsonResponse({'saved': True, 'saved_at': timezone.now().isoformat()})


@login_required
@require_POST
@feature_required('cbt_quiz')
def quiz_integrity(request, quiz_id):
    student = student_for(request)
    if not student:
        return JsonResponse({'error': 'Student access required.'}, status=403)
    with transaction.atomic():
        attempt = get_object_or_404(QuizAttempt.objects.select_for_update().select_related('quiz'), student=student, quiz_id=quiz_id, quiz__school_class=student.school_class)
        event = request.POST.get('event_type')
        if event not in ('tab_switch', 'fullscreen_exit'):
            return JsonResponse({'error': 'Invalid event.'}, status=400)
        if not attempt.is_submitted:
            enabled = attempt.quiz.detect_tab_switching if event == 'tab_switch' else attempt.quiz.full_screen_mode
            if enabled:
                attempt.add_integrity_event(event)
            if timezone.now() >= deadline_for(attempt) or attempt.quiz.status == 'ended' or (attempt.quiz.detect_tab_switching and attempt.tab_switches >= attempt.quiz.max_tab_switches):
                finish_attempt(attempt, 'Time, quiz closure, or tab-switch limit reached')
    return JsonResponse({'tab_switches': attempt.tab_switches, 'submitted': attempt.is_submitted, 'result_url': reverse('core:view_quiz_result', args=[quiz_id])})


@login_required
@feature_required('cbt_quiz')
def view_quiz_result(request, quiz_id):
    student = student_for(request)
    if not student:
        return redirect('core:dashboard')
    attempt = get_object_or_404(QuizAttempt.objects.select_related('quiz'), quiz_id=quiz_id, student=student, is_submitted=True)
    results = []
    for answer in attempt.answers.select_related('question').order_by('question__order', 'question_id'):
        question = answer.question
        user_answer = answer.theory_answer if question.question_type == 'theory' else answer.selected_answer
        results.append({'question': question, 'user_answer': user_answer, 'user_answers_list': answer.selected_answer.split(','), 'correct_answers_list': question.correct_answer.split(','), 'is_correct': answer.is_correct, 'manual_score': answer.manual_score, 'graded': answer.graded_at is not None, 'feedback': answer.teacher_feedback})
    return render(request, 'student/view_quiz_result.html', {'quiz': attempt.quiz, 'attempt': attempt, 'results': results, 'show_answers': timezone.now() >= attempt.quiz.end_time or attempt.quiz.status == 'ended'})


@login_required
@feature_required('cbt_quiz')
def quiz_results(request, quiz_id):
    teacher = teacher_for(request)
    if not teacher:
        return HttpResponseForbidden('Only teachers can view quiz results.')
    quiz = get_object_or_404(Quiz, pk=quiz_id, teacher=teacher)
    for attempt in quiz.quizattempt_set.filter(is_submitted=False).select_related('quiz'):
        expire_attempt(attempt)
    return render(request, 'teacher/quiz_results.html', {'quiz': quiz, 'attempts': quiz.quizattempt_set.select_related('student__user').order_by('student__user__first_name')})


@login_required
@feature_required('cbt_quiz')
def grade_theory(request, quiz_id):
    teacher = teacher_for(request)
    if not teacher:
        return HttpResponseForbidden('Only teachers can grade quizzes.')
    quiz = get_object_or_404(Quiz, pk=quiz_id, teacher=teacher)
    form = None
    answer_id = None
    if request.method == 'POST':
        if not request.POST.get('answer_id', '').isdigit():
            return JsonResponse({'error': 'Select a valid answer to grade.'}, status=400)
        answer = get_object_or_404(QuizAnswer, pk=request.POST.get('answer_id'), attempt__quiz=quiz, attempt__is_submitted=True, question__question_type='theory')
        answer_id = answer.pk
        form = TheoryGradeForm(request.POST, max_marks=answer.question.max_marks)
        if form.is_valid():
            with transaction.atomic():
                attempt = QuizAttempt.objects.select_for_update().get(pk=answer.attempt_id)
                answer.manual_score = form.cleaned_data['score']
                answer.teacher_feedback = form.cleaned_data['feedback']
                answer.graded_at = timezone.now()
                answer.save()
                recalculate(attempt)
            messages.success(request, 'Grade saved, including any zero mark.')
            return redirect('core:grade_theory', quiz_id=quiz.pk)
    attempts = quiz.quizattempt_set.filter(is_submitted=True).prefetch_related('answers__question').select_related('student__user')
    rows = [{'attempt': a, 'theory_answers': [{'question': ans.question, 'answer': ans, 'form': form if ans.pk == answer_id else TheoryGradeForm(max_marks=ans.question.max_marks, initial={'score': ans.manual_score if ans.graded_at else None, 'feedback': ans.teacher_feedback})} for ans in a.answers.all() if ans.question.question_type == 'theory']} for a in attempts]
    return render(request, 'teacher/grade_theory.html', {'quiz': quiz, 'attempts_data': rows, 'form': form})


@login_required
@feature_required('cbt_quiz')
def quiz_preview(request, quiz_id):
    teacher = teacher_for(request)
    if not teacher:
        return HttpResponseForbidden('Only teachers can preview quizzes.')
    quiz = get_object_or_404(Quiz, pk=quiz_id, teacher=teacher)
    return render(request, 'student/quiz_preview.html', {'quiz': quiz, 'cards': question_cards(quiz)})


def import_bank(request, grouped=False):
    teacher = teacher_for(request)
    if not teacher:
        return JsonResponse({'success': False, 'error': 'Only assigned teachers can add questions.'}, status=403)
    try:
        data = json.loads(request.body)
        quiz_id = int(data['quiz_id'])
        source_id = int(data['group_id' if grouped else 'question_id'])
    except (ValueError, KeyError, TypeError):
        return JsonResponse({'success': False, 'error': 'Select a valid quiz and question.'}, status=400)
    with transaction.atomic():
        quiz = get_object_or_404(Quiz.objects.select_for_update(), pk=quiz_id, teacher=teacher)
        if quiz_is_locked(quiz):
            return JsonResponse({'success': False, 'error': 'Attempts have started. Questions are locked.'}, status=409)
        source = get_object_or_404(QuestionGroup if grouped else QuestionBank, pk=source_id, subject=quiz.subject)
        bank_questions = list(source.questions.all()) if grouped else [source]
        candidates = []
        for bank in bank_questions:
            q = Question(quiz=quiz, max_marks=1, **{field: getattr(bank, field) for field in ['question_type', 'question_text', 'option_a', 'option_b', 'option_c', 'option_d', 'correct_answer']})
            if errors := question_errors(q):
                return JsonResponse({'success': False, 'error': ' '.join(errors)}, status=400)
            candidates.append(q)
        if not candidates:
            return JsonResponse({'success': False, 'error': 'This group has no questions.'}, status=400)
        group = QuestionGroupInstance.objects.create(quiz=quiz, instruction=source.instruction, order=quiz.questions.count()) if grouped else None
        order = quiz.questions.count()
        for index, candidate in enumerate(candidates):
            candidate.order = order + index
            candidate.group_instance = group
            candidate.save()
    return JsonResponse({'success': True})


@login_required
@require_POST
@feature_required('cbt_quiz')
def add_question_from_bank(request):
    return import_bank(request)


@login_required
@require_POST
@feature_required('cbt_quiz')
def add_group_from_bank(request):
    return import_bank(request, grouped=True)
