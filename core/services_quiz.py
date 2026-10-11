from datetime import timedelta
from decimal import Decimal
import random

from django.db import transaction
from django.utils import timezone

from .models import QuizAnswer, QuizAttempt


def deadline_for(attempt):
    return min(attempt.start_time + timedelta(minutes=attempt.quiz.duration_minutes), attempt.quiz.end_time)


def save_answers(attempt, data):
    """Called while holding the attempt lock; empty responses clear previous drafts."""
    for question in attempt.quiz.questions.all():
        selected, theory = '', ''
        if question.question_type == 'theory':
            theory = data.get(f'theory_{question.pk}', '')
        else:
            choices = sorted(set(data.getlist(f'question_{question.pk}')) & set('ABCD'))
            if question.question_type == 'objective':
                choices = choices[:1]
            selected = ','.join(choices)
        QuizAnswer.objects.update_or_create(
            attempt=attempt, question=question,
            defaults={'selected_answer': selected, 'theory_answer': theory},
        )


def recalculate(attempt):
    answers = list(attempt.answers.select_related('question'))
    questions = list(attempt.quiz.questions.all())
    attempt.auto_score = sum(a.question.max_marks for a in answers if a.question.question_type != 'theory' and a.is_correct)
    attempt.manual_score = sum((a.manual_score for a in answers if a.question.question_type == 'theory' and a.graded_at), Decimal('0'))
    total = sum(q.max_marks for q in questions)
    attempt.final_score = (Decimal(attempt.auto_score) + attempt.manual_score) * 100 / total if total else 0
    theory_ids = {q.pk for q in questions if q.question_type == 'theory'}
    graded_ids = {a.question_id for a in answers if a.graded_at}
    attempt.is_graded = theory_ids.issubset(graded_ids)
    attempt.save()


def finish_attempt(attempt, reason=''):
    if attempt.is_submitted:
        return
    for question in attempt.quiz.questions.all():
        QuizAnswer.objects.get_or_create(attempt=attempt, question=question)
    attempt.is_submitted = True
    attempt.end_time = min(timezone.now(), deadline_for(attempt))
    recalculate(attempt)
    if reason:
        attempt.add_integrity_event('auto_submit', reason)


def expire_attempt(attempt):
    with transaction.atomic():
        locked = QuizAttempt.objects.select_for_update().select_related('quiz').get(pk=attempt.pk)
        if not locked.is_submitted and (timezone.now() >= deadline_for(locked) or locked.quiz.status == 'ended'):
            finish_attempt(locked, 'Quiz deadline reached or quiz closed')
        return locked


def question_cards(quiz, attempt=None):
    """Seeded shuffling keeps groups and displayed order stable across refreshes."""
    questions = list(quiz.questions.select_related('group_instance').order_by('order', 'id'))
    groups, blocks = {}, []
    for q in questions:
        if q.group_instance_id:
            if q.group_instance_id not in groups:
                groups[q.group_instance_id] = []
                blocks.append(groups[q.group_instance_id])
            groups[q.group_instance_id].append(q)
        else:
            blocks.append([q])
    rng = random.Random(f'quiz-{quiz.pk}-attempt-{attempt.pk if attempt else "preview"}')
    if quiz.shuffle_questions:
        rng.shuffle(blocks)
    answers = {a.question_id: a for a in attempt.answers.all()} if attempt else {}
    cards = []
    for block in blocks:
        for index, question in enumerate(block):
            answer = answers.get(question.pk)
            selected = answer.selected_answer.split(',') if answer else []
            options = [(x, getattr(question, f'option_{x.lower()}')) for x in 'ABCD' if getattr(question, f'option_{x.lower()}')]
            if quiz.shuffle_options:
                rng.shuffle(options)
            cards.append({
                'question': question, 'number': len(cards) + 1,
                'instruction': question.group_instance.instruction if index == 0 and question.group_instance_id else '',
                'options': [{'value': x, 'text': text, 'selected': x in selected} for x, text in options],
                'theory_answer': answer.theory_answer if answer else '',
            })
    return cards
