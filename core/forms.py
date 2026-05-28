from django import forms
from .models import Question, QuestionBank, SchoolClass, QuestionGroup

class QuestionForm(forms.ModelForm):
    correct_answer = forms.ChoiceField(
        choices=[('', 'Select Correct Answer'), ('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D')],
        required=False,
        widget=forms.Select(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md'})
    )
    
    class Meta:
        model = Question
        fields = ['question_text', 'option_a', 'option_b', 'option_c', 'option_d', 'correct_answer']

class QuestionGroupForm(forms.ModelForm):
    class Meta:
        model = QuestionGroup
        fields = ['subject', 'instruction']
        widgets = {
            'subject': forms.Select(attrs={'class': 'w-full px-3 py-2 border rounded'}),
        }

class QuestionBankForm(forms.ModelForm):
    class Meta:
        model = QuestionBank
        fields = ['subject', 'school_class', 'question_type', 'topic', 'group', 'question_text', 'option_a', 'option_b', 'option_c', 'option_d', 'correct_answer', 'difficulty']
        widgets = {
            'subject': forms.Select(attrs={'class': 'w-full px-3 py-2 border rounded'}),
            'school_class': forms.Select(attrs={'class': 'w-full px-3 py-2 border rounded'}),
            'question_type': forms.Select(attrs={'class': 'w-full px-3 py-2 border rounded', 'onchange': 'toggleOptions()'}),
            'topic': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border rounded', 'placeholder': 'Optional'}),
            'group': forms.Select(attrs={'class': 'w-full px-3 py-2 border rounded'}),
            'correct_answer': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border rounded', 'placeholder': 'e.g., A or A,B,C'}),
            'difficulty': forms.Select(attrs={'class': 'w-full px-3 py-2 border rounded'}),
        }
