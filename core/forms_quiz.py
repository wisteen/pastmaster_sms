from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.html import strip_tags
from html import unescape

from .models import Quiz, Question, QuestionBank


def content_present(value):
    return bool(unescape(strip_tags(value or '')).replace('\xa0', '').strip() or '<img' in (value or '').lower())


def question_errors(question):
    errors = []
    if not content_present(question.question_text):
        errors.append('Enter the question text.')
    if question.max_marks is None or question.max_marks < 1:
        errors.append('Marks must be at least 1.')
    if question.question_type not in dict(Question.QUESTION_TYPES):
        errors.append('Select a valid question type.')
    if question.question_type in ('objective', 'multichoice'):
        options = {letter for letter in 'ABCD' if content_present(getattr(question, f'option_{letter.lower()}'))}
        selected = set(filter(None, question.correct_answer.split(',')))
        if len(options) < 2:
            errors.append('Provide at least two answer options.')
        if not selected or not selected.issubset(options):
            errors.append('Select correct answers that have option text.')
        if question.question_type == 'objective' and len(selected) != 1:
            errors.append('Single-choice questions need exactly one correct answer.')
    return errors


class QuizForm(forms.ModelForm):
    class Meta:
        model = Quiz
        fields = ['title', 'subject', 'school_class', 'start_time', 'end_time', 'duration_minutes', 'instructions', 'status', 'shuffle_questions', 'shuffle_options', 'full_screen_mode', 'detect_tab_switching', 'max_tab_switches']
        widgets = {
            'start_time': forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local'}),
            'end_time': forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local'}),
            'instructions': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, classes, subjects, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['school_class'].queryset = classes
        self.fields['subject'].queryset = subjects
        self.fields['duration_minutes'].min_value = 1
        self.fields['max_tab_switches'].min_value = 1
        self.fields['max_tab_switches'].max_value = 10
        self.fields['status'].help_text = 'Draft is private. Scheduled and Live open only within the dates above.'
        self.fields['start_time'].help_text = f'Times use {timezone.get_current_timezone_name()}.'
        if not self.instance.pk:
            self.fields['status'].initial = 'draft'
            self.fields['status'].disabled = True
        elif self.instance.quizattempt_set.exists():
            for name, field in self.fields.items():
                if name != 'status':
                    field.disabled = True
            self.fields['status'].help_text = 'Attempts have started. Settings and questions are locked to preserve results; you can close the quiz.'

    def clean(self):
        data = super().clean()
        start, end = data.get('start_time'), data.get('end_time')
        if start and end and end <= start:
            self.add_error('end_time', 'End time must be after start time.')
        if (data.get('duration_minutes') or 0) < 1:
            self.add_error('duration_minutes', 'Duration must be at least one minute.')
        if not 1 <= (data.get('max_tab_switches') or 0) <= 10:
            self.add_error('max_tab_switches', 'Choose between 1 and 10 tab switches.')
        if self.instance.pk and self.instance.quizattempt_set.exists() and data.get('status') == 'draft':
            self.add_error('status', 'A quiz with attempts cannot return to draft. Choose Ended to close it.')
        if data.get('status') in ('scheduled', 'live'):
            if end and end <= timezone.now():
                self.add_error('end_time', 'Set an end time in the future before publishing.')
            questions = list(self.instance.questions.all()) if self.instance.pk else []
            if not questions:
                self.add_error('status', 'Add at least one question before publishing.')
            for number, question in enumerate(questions, 1):
                if errors := question_errors(question):
                    self.add_error('status', f'Question {number}: {" ".join(errors)}')
        return data


class QuestionForm(forms.ModelForm):
    correct_answer = forms.ChoiceField(choices=[('', 'Choose an answer')] + [(x, x) for x in 'ABCD'], required=False)
    correct_multi = forms.MultipleChoiceField(choices=[(x, x) for x in 'ABCD'], widget=forms.CheckboxSelectMultiple, required=False)

    class Meta:
        model = Question
        fields = ['question_type', 'question_text', 'option_a', 'option_b', 'option_c', 'option_d', 'correct_answer', 'max_marks']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.question_type == 'multichoice':
            self.initial['correct_multi'] = self.instance.correct_answer.split(',')
            self.initial['correct_answer'] = ''
        self.fields['max_marks'].min_value = 1

    def clean(self):
        data = super().clean()
        kind = data.get('question_type')
        if kind == 'multichoice':
            data['correct_answer'] = ','.join(sorted(data.get('correct_multi', [])))
        elif kind == 'theory':
            data['correct_answer'] = ''
        candidate = Question(**{key: data[key] for key in self.Meta.fields if key in data})
        errors = question_errors(candidate)
        if errors:
            raise ValidationError(errors)
        return data


class TheoryGradeForm(forms.Form):
    score = forms.DecimalField(min_value=0, max_digits=5, decimal_places=2)
    feedback = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}))

    def __init__(self, *args, max_marks, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_marks = max_marks

    def clean_score(self):
        score = self.cleaned_data['score']
        if score > self.max_marks:
            raise ValidationError(f'Score cannot exceed {self.max_marks}.')
        return score


from .forms import QuestionBankForm as BaseQuestionBankForm


class QuestionBankForm(BaseQuestionBankForm):
    def __init__(self, *args, classes, subjects, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import QuestionGroup
        self.fields['subject'].queryset = subjects
        self.fields['school_class'].queryset = classes
        self.fields['group'].queryset = QuestionGroup.objects.filter(subject__in=subjects)

    def clean(self):
        data = super().clean()
        kind = data.get('question_type')
        if kind == 'objective':
            data['correct_answer'] = self.data.get('correct_answer_scq', '')
        elif kind == 'multichoice':
            data['correct_answer'] = ','.join(sorted(set(self.data.getlist('correct_multi'))))
        else:
            data['correct_answer'] = ''
        candidate = Question(max_marks=1, **{name: data.get(name, '') for name in ('question_type', 'question_text', 'option_a', 'option_b', 'option_c', 'option_d', 'correct_answer')})
        for error in question_errors(candidate):
            self.add_error(None, error)
        if data.get('group') and data['group'].subject_id != getattr(data.get('subject'), 'pk', None):
            self.add_error('group', 'Choose a group for the selected subject.')
        return data
