from datetime import date, timedelta
from decimal import Decimal
from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (
    Assignment, AssignmentSubmission, ClassTeacher, Question, Quiz, QuizAnswer,
    QuizAttempt, SchoolClass, SchoolDomain, SchoolMembership, SchoolTenant,
    Student, Subject, Teacher, User,
)
from .models_license import SystemLicense
from .models_features import FeatureFlag, TenantFeatureOverride


class AssessmentWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.school = SchoolTenant.objects.create(name='Assessment School', slug='assessment-school', plan='premium')
        SchoolDomain.objects.create(school=cls.school, domain='assessment.testserver')
        SystemLicense.all_objects.create(school=cls.school, school_name=cls.school.name, license_key='assessment-workflow-license', expiry_date=timezone.localdate() + timedelta(days=365))
        cls.teacher_user = User.objects.create_user(username='assessment_teacher', role='class_teacher')
        cls.student_user = User.objects.create_user(username='assessment_student', role='student')
        for user in (cls.teacher_user, cls.student_user):
            SchoolMembership.objects.create(school=cls.school, user=user, primary_role=user.role)
        cls.school_class = SchoolClass.all_objects.create(school=cls.school, name='Basic 4')
        cls.subject = Subject.all_objects.create(school=cls.school, name='Science', code='SCI')
        cls.teacher = Teacher.all_objects.create(school=cls.school, user=cls.teacher_user, employee_id='T-ASSESS')
        cls.teacher.subjects.add(cls.subject)
        ClassTeacher.objects.create(teacher=cls.teacher, school_class=cls.school_class)
        cls.student = Student.all_objects.create(school=cls.school, user=cls.student_user, school_class=cls.school_class, date_of_birth=date(2015, 1, 1), student_id='S-ASSESS')
        cls.assignment = Assignment.objects.create(title='Science homework', description='Describe evaporation.', teacher=cls.teacher, subject=cls.subject, due_date=timezone.now() + timedelta(days=2), max_score=10)
        cls.assignment.school_classes.add(cls.school_class)
        cls.quiz = Quiz.objects.create(title='Science quiz', teacher=cls.teacher, subject=cls.subject, school_class=cls.school_class, start_time=timezone.now() - timedelta(minutes=5), end_time=timezone.now() + timedelta(hours=1), duration_minutes=30, status='live')
        cls.question = Question.objects.create(quiz=cls.quiz, question_text='Which is a gas?', option_a='Steam', option_b='Ice', correct_answer='A', max_marks=2)

    def setUp(self):
        self.client = Client(HTTP_HOST='assessment.testserver')
        self.client.force_login(self.student_user)
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        settings = override_settings(MEDIA_ROOT=self.media.name)
        settings.enable()
        self.addCleanup(settings.disable)

    def url(self, name, pk=None):
        return reverse(name, args=[pk] if pk is not None else [])

    def start(self):
        response = self.client.post(self.url('core:enhanced_quiz', self.quiz.pk), {'action': 'start'})
        self.assertEqual(response.status_code, 302)
        return QuizAttempt.objects.get(quiz=self.quiz, student=self.student)

    def submit_quiz(self, data=None):
        return self.client.post(self.url('core:enhanced_quiz', self.quiz.pk), data or {'action': 'submit'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    def submission(self, **extra):
        return AssignmentSubmission.objects.create(assignment=self.assignment, student=self.student, submission_text='My response', **extra)

    def test_class_teacher_can_create_edit_view_and_grade_assignment(self):
        self.client.force_login(self.teacher_user)
        data = {'title': 'New assignment', 'description': 'Describe rain.', 'subject': self.subject.pk, 'school_classes': [self.school_class.pk], 'due_date': timezone.localtime(self.assignment.due_date).strftime('%Y-%m-%dT%H:%M'), 'max_score': '10', 'late_penalty_percentage': '0'}
        response = self.client.post(self.url('academic:assignment_create'), data)
        self.assertEqual(response.status_code, 302, getattr(response, 'context', None))
        assignment = Assignment.objects.get(title='New assignment')
        self.assertEqual(self.client.get(response.url).status_code, 200)
        response = self.client.get(self.url('academic:assignment_edit', assignment.pk))
        self.assertContains(response, timezone.localtime(assignment.due_date).strftime('%Y-%m-%dT%H:%M'))
        data['title'] = 'Updated assignment'
        self.assertEqual(self.client.post(self.url('academic:assignment_edit', assignment.pk), data).status_code, 302)
        submission = self.submission()
        response = self.client.post(self.url('academic:grade_submission', submission.pk), {'score': '0', 'feedback': 'Please revise.'})
        self.assertEqual(response.status_code, 302)
        submission.refresh_from_db()
        self.assertEqual(submission.score, 0)
        self.assertTrue(submission.is_graded)

    def test_assignment_list_includes_submission_and_zero_grade_is_locked(self):
        submission = self.submission(score=0)
        response = self.client.get(self.url('academic:assignment_list'))
        self.assertEqual(response.context['assignment_info'][0]['submission'], submission)
        self.assertNotContains(response, 'Edit Submission')
        response = self.client.get(self.url('academic:assignment_detail', self.assignment.pk))
        self.assertContains(response, 'Score: 0.00')
        self.assertContains(response, 'My response')
        self.assertNotContains(response, 'Update Submission')
        self.client.post(self.url('academic:submit_assignment', self.assignment.pk), {'submission_text': 'Changed'})
        submission.refresh_from_db()
        self.assertEqual(submission.submission_text, 'My response')

    def test_assignment_rejects_empty_rich_text_and_invalid_upload(self):
        url = self.url('academic:submit_assignment', self.assignment.pk)
        response = self.client.post(url, {'submission_text': '<p>&nbsp;</p>'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(AssignmentSubmission.objects.exists())
        response = self.client.post(url, {'file': SimpleUploadedFile('unsafe.exe', b'bad')})
        self.assertContains(response, 'not allowed')
        self.assertFalse(AssignmentSubmission.objects.exists())

    def test_file_only_submission_can_be_updated_without_reupload(self):
        url = self.url('academic:submit_assignment', self.assignment.pk)
        response = self.client.post(url, {'file': SimpleUploadedFile('answer.txt', b'Evaporation')})
        self.assertEqual(response.status_code, 302)
        submission = AssignmentSubmission.objects.get()
        self.assertEqual(submission.files.count(), 1)
        self.assertEqual(self.client.post(url, {'submission_text': ''}).status_code, 302)
        self.assertEqual(AssignmentSubmission.objects.count(), 1)
        self.assertEqual(submission.files.count(), 1)
        self.assertContains(self.client.get(self.url('academic:assignment_detail', self.assignment.pk)), 'answer.txt')

    def test_assignment_late_revision_is_marked_late_and_penalty_is_not_compounded(self):
        submission = self.submission()
        self.assignment.due_date = timezone.now() - timedelta(minutes=1)
        self.assignment.allow_late_submission = True
        self.assignment.late_penalty_percentage = Decimal('10')
        self.assignment.save()
        self.client.post(self.url('academic:submit_assignment', self.assignment.pk), {'submission_text': 'Revision'})
        submission.refresh_from_db()
        self.assertTrue(submission.is_late)
        self.client.force_login(self.teacher_user)
        url = self.url('academic:grade_submission', submission.pk)
        for _ in range(2):
            self.assertEqual(self.client.post(url, {'score': '8'}).status_code, 302)
            submission.refresh_from_db()
            self.assertEqual(submission.raw_score, Decimal('8'))
            self.assertEqual(submission.score, Decimal('7.20'))
        self.assertContains(self.client.get(url), 'value="8.00"')

    def test_invalid_assignment_grades_preserve_previous_grade_and_feedback(self):
        submission = self.submission(score=3, feedback='Original')
        self.client.force_login(self.teacher_user)
        for score in ('-1', '11', 'NaN', 'bad', '', '2.123'):
            with self.subTest(score=score):
                response = self.client.post(self.url('academic:grade_submission', submission.pk), {'score': score, 'feedback': 'Changed'})
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context['form'].errors)
                submission.refresh_from_db()
                self.assertEqual(submission.score, 3)
                self.assertEqual(submission.feedback, 'Original')

    def test_feedback_only_grade_locks_submission(self):
        self.assignment.max_score = None
        self.assignment.save()
        submission = self.submission()
        self.client.force_login(self.teacher_user)
        self.client.post(self.url('academic:grade_submission', submission.pk), {'feedback': 'Reviewed'})
        submission.refresh_from_db()
        self.assertIsNone(submission.score)
        self.assertTrue(submission.is_graded)
        self.client.force_login(self.student_user)
        response = self.client.get(self.url('academic:assignment_detail', self.assignment.pk))
        self.assertContains(response, 'Reviewed')
        self.assertNotContains(response, 'Update Submission')

    def test_closed_assignment_cannot_be_submitted(self):
        self.assignment.due_date = timezone.now() - timedelta(minutes=1)
        self.assignment.save()
        response = self.client.post(self.url('academic:submit_assignment', self.assignment.pk), {'submission_text': 'Too late'})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(AssignmentSubmission.objects.exists())

    def test_get_quiz_does_not_start_timer_and_repeated_start_is_safe(self):
        self.assertEqual(self.client.get(self.url('core:enhanced_quiz', self.quiz.pk)).status_code, 200)
        self.assertFalse(QuizAttempt.objects.exists())
        attempt = self.start()
        self.assertContains(self.client.get(self.url('core:student_cbt_dashboard')), 'Resume quiz')
        self.start()
        self.assertEqual(QuizAttempt.objects.count(), 1)
        self.assertContains(self.client.get(self.url('core:enhanced_quiz', self.quiz.pk)), 'quiz-config')
        attempt.refresh_from_db()
        self.assertFalse(attempt.is_submitted)

    def test_autosaved_answer_changes_update_correctness_and_can_be_cleared(self):
        attempt = self.start()
        url = self.url('core:save_quiz_answers', self.quiz.pk)
        for selected, correct in [('B', False), ('A', True), ('', False), ('A', True)]:
            response = self.client.post(url, {f'question_{self.question.pk}': selected})
            self.assertEqual(response.status_code, 200)
            answer = QuizAnswer.objects.get(attempt=attempt, question=self.question)
            self.assertEqual(answer.is_correct, correct)
        self.assertEqual(attempt.answers.count(), 1)
        response = self.submit_quiz({f'question_{self.question.pk}': 'A'})
        self.assertTrue(response.json()['submitted'])
        attempt.refresh_from_db()
        self.assertEqual(attempt.final_score, 100)
        self.assertTrue(attempt.is_graded)

    def test_submission_retry_returns_confirmation_without_replacing_answers(self):
        attempt = self.start()
        self.submit_quiz({f'question_{self.question.pk}': 'A'})
        response = self.submit_quiz({f'question_{self.question.pk}': 'B'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['submitted'])
        self.assertEqual(attempt.answers.get().selected_answer, 'A')

    def test_quiz_review_hides_answers_until_closed(self):
        self.start()
        self.submit_quiz({f'question_{self.question.pk}': 'B'})
        url = self.url('core:view_quiz_result', self.quiz.pk)
        self.assertNotContains(self.client.get(url), 'Steam')
        self.quiz.status = 'ended'
        self.quiz.save()
        self.assertContains(self.client.get(url), 'Steam')

    def test_expired_quiz_uses_saved_answers_and_cannot_be_restarted(self):
        attempt = self.start()
        self.client.post(self.url('core:save_quiz_answers', self.quiz.pk), {f'question_{self.question.pk}': 'A'})
        QuizAttempt.objects.filter(pk=attempt.pk).update(start_time=timezone.now() - timedelta(hours=1))
        self.submit_quiz({f'question_{self.question.pk}': 'B'})
        attempt.refresh_from_db()
        self.assertTrue(attempt.is_submitted)
        self.assertEqual(attempt.final_score, 100)
        self.start()
        self.assertEqual(QuizAttempt.objects.count(), 1)

    def test_theory_zero_grade_completes_grading_and_invalid_grade_has_errors(self):
        theory = Question.objects.create(quiz=self.quiz, question_type='theory', question_text='Explain.', max_marks=3)
        attempt = self.start()
        self.submit_quiz({f'question_{self.question.pk}': 'A', f'theory_{theory.pk}': 'My explanation'})
        attempt.refresh_from_db()
        self.assertFalse(attempt.is_graded)
        answer = attempt.answers.get(question=theory)
        self.client.force_login(self.teacher_user)
        url = self.url('core:grade_theory', self.quiz.pk)
        response = self.client.post(url, {'answer_id': answer.pk, 'score': '4', 'feedback': 'Keep this feedback'})
        self.assertContains(response, 'Score cannot exceed')
        self.assertContains(response, 'Keep this feedback')
        self.assertEqual(self.client.post(url, {'answer_id': answer.pk, 'score': '0'}).status_code, 302)
        attempt.refresh_from_db()
        answer.refresh_from_db()
        self.assertTrue(attempt.is_graded)
        self.assertIsNotNone(answer.graded_at)
        self.assertEqual(attempt.final_score, 40)

    def test_started_quiz_questions_and_deletion_are_locked(self):
        self.start()
        self.client.force_login(self.teacher_user)
        self.assertEqual(self.client.delete(self.url('core:delete_quiz', self.quiz.pk)).status_code, 409)
        self.assertEqual(self.client.delete(self.url('core:delete_question', self.question.pk)).status_code, 409)
        response = self.client.post(self.url('core:add_questions', self.quiz.pk), {})
        self.assertContains(response, 'Questions are locked')
        self.assertEqual(self.quiz.questions.count(), 1)

    def test_quiz_create_questions_publish_and_preview(self):
        self.client.force_login(self.teacher_user)
        data = {'title': 'New quiz', 'subject': self.subject.pk, 'school_class': self.school_class.pk, 'start_time': timezone.localtime(self.quiz.start_time).strftime('%Y-%m-%dT%H:%M'), 'end_time': timezone.localtime(self.quiz.end_time).strftime('%Y-%m-%dT%H:%M'), 'duration_minutes': '20', 'max_tab_switches': '3', 'status': 'live'}
        self.assertEqual(self.client.post(self.url('core:create_quiz'), data).status_code, 302)
        quiz = Quiz.objects.get(title='New quiz')
        self.assertEqual(quiz.status, 'draft')
        response = self.client.post(self.url('core:edit_quiz', quiz.pk), data)
        self.assertContains(response, 'Add at least one question')
        question_data = {'question_type': 'multichoice', 'question_text': 'Pick both', 'option_a': 'One', 'option_b': 'Two', 'correct_multi': ['A', 'B'], 'max_marks': '2'}
        self.assertEqual(self.client.post(self.url('core:add_questions', quiz.pk), question_data).status_code, 302)
        self.assertEqual(quiz.questions.get().correct_answer, 'A,B')
        self.assertEqual(self.client.post(self.url('core:edit_quiz', quiz.pk), data).status_code, 302)
        quiz.refresh_from_db()
        self.assertTrue(quiz.is_live())
        self.assertEqual(self.client.get(self.url('core:quiz_preview', quiz.pk)).status_code, 200)
        self.assertFalse(quiz.quizattempt_set.exists())

    def test_student_cannot_manage_quiz_or_access_other_class(self):
        self.assertEqual(self.client.get(self.url('core:edit_quiz', self.quiz.pk)).status_code, 403)
        other_class = SchoolClass.all_objects.create(school=self.school, name='Basic 5')
        self.quiz.school_class = other_class
        self.quiz.save()
        self.assertEqual(self.client.post(self.url('core:enhanced_quiz', self.quiz.pk), {'action': 'start'}).status_code, 404)
        self.assertFalse(QuizAttempt.objects.exists())

    def test_other_school_cannot_read_assessments(self):
        other = SchoolTenant.objects.create(name='Other School', slug='other-assessment', plan='premium')
        SchoolDomain.objects.create(school=other, domain='other-assessment.testserver')
        SystemLicense.all_objects.create(school=other, school_name=other.name, license_key='other-assessment-license', expiry_date=timezone.localdate() + timedelta(days=365))
        SchoolMembership.objects.create(school=other, user=self.teacher_user, primary_role='class_teacher')
        client = Client(HTTP_HOST='other-assessment.testserver')
        client.force_login(self.teacher_user)
        self.assertEqual(client.get(self.url('academic:assignment_detail', self.assignment.pk)).status_code, 404)
        self.assertEqual(client.get(self.url('core:quiz_results', self.quiz.pk)).status_code, 403)

    def test_registered_assignment_feature_is_available_and_respects_school_override(self):
        feature = FeatureFlag.objects.create(name='academic_assignments', display_name='Assignments', category='academic')
        self.assertEqual(self.client.get(self.url('academic:assignment_list')).status_code, 200)
        TenantFeatureOverride.objects.create(school=self.school, feature=feature, is_enabled=False)
        self.assertEqual(self.client.get(self.url('academic:assignment_detail', self.assignment.pk)).status_code, 403)
        self.assertEqual(self.client.post(self.url('academic:submit_assignment', self.assignment.pk), {'submission_text': 'Answer'}).status_code, 403)
        self.assertFalse(AssignmentSubmission.objects.exists())

    def test_class_teacher_can_use_question_bank_and_import_group(self):
        from .models import QuestionBank, QuestionGroup
        self.client.force_login(self.teacher_user)
        group = QuestionGroup.objects.create(subject=self.subject, created_by=self.teacher, instruction='Read the passage.')
        url = self.url('core:question_bank') + f'?quiz_id={self.quiz.pk}'
        self.assertContains(self.client.get(url), 'Back to Science quiz')
        data = {'subject': self.subject.pk, 'group': group.pk, 'question_type': 'objective', 'question_text': 'Bank question', 'option_a': 'Yes', 'option_b': 'No', 'correct_answer_scq': 'A', 'difficulty': 'easy'}
        self.assertEqual(self.client.post(url, data).status_code, 302)
        bank = QuestionBank.objects.get()
        self.assertEqual(bank.correct_answer, 'A')
        response = self.client.post(self.url('core:add_group_from_bank'), {'quiz_id': self.quiz.pk, 'group_id': group.pk}, content_type='application/json')
        self.assertTrue(response.json()['success'])
        imported = self.quiz.questions.get(question_text='Bank question')
        self.assertEqual(imported.group_instance.instruction, 'Read the passage.')
        data['correct_answer_scq'] = 'D'
        response = self.client.post(url, data)
        self.assertContains(response, 'Select correct answers that have option text.')
        self.assertEqual(QuestionBank.objects.count(), 1)

    def test_unassigned_subject_cannot_be_forged_in_question_bank(self):
        from .models import QuestionBank
        other_subject = Subject.all_objects.create(school=self.school, name='Other', code='OTH')
        self.client.force_login(self.teacher_user)
        response = self.client.post(self.url('core:question_bank'), {'subject': other_subject.pk, 'question_type': 'theory', 'question_text': 'Question', 'difficulty': 'easy'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)
        self.assertFalse(QuestionBank.objects.exists())

    def test_question_validation_rejects_missing_marks_and_blank_options(self):
        self.client.force_login(self.teacher_user)
        for marks in ('', '0', '-2', 'bad'):
            response = self.client.post(self.url('core:add_questions', self.quiz.pk), {'question_type': 'objective', 'question_text': 'Question', 'option_a': '<p>&nbsp;</p>', 'option_b': 'B', 'correct_answer': 'A', 'max_marks': marks})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['form'].errors)
        self.assertEqual(self.quiz.questions.count(), 1)

    def test_tab_limit_submits_saved_work(self):
        attempt = self.start()
        self.client.post(self.url('core:save_quiz_answers', self.quiz.pk), {f'question_{self.question.pk}': 'A'})
        url = self.url('core:quiz_integrity', self.quiz.pk)
        for number in range(1, 4):
            response = self.client.post(url, {'event_type': 'tab_switch'})
            self.assertEqual(response.json()['tab_switches'], number)
            self.assertEqual(response.json()['submitted'], number == 3)
        attempt.refresh_from_db()
        self.assertEqual(attempt.final_score, 100)

    def test_second_teacher_cannot_grade_or_edit_another_teachers_work(self):
        other_user = User.objects.create_user(username='other_teacher', role='subject_teacher')
        SchoolMembership.objects.create(school=self.school, user=other_user, primary_role='subject_teacher')
        Teacher.all_objects.create(school=self.school, user=other_user, employee_id='T-OTHER')
        submission = self.submission()
        self.client.force_login(other_user)
        response = self.client.post(self.url('academic:grade_submission', submission.pk), {'score': '10'})
        self.assertEqual(response.status_code, 302)
        submission.refresh_from_db()
        self.assertIsNone(submission.score)
        self.assertEqual(self.client.get(self.url('core:edit_quiz', self.quiz.pk)).status_code, 404)

    def test_assignment_marking_settings_stay_fixed_after_submission(self):
        self.submission()
        self.client.force_login(self.teacher_user)
        response = self.client.post(self.url('academic:assignment_edit', self.assignment.pk), {'title': self.assignment.title, 'description': self.assignment.description, 'due_date': timezone.localtime(self.assignment.due_date).strftime('%Y-%m-%dT%H:%M'), 'max_score': '100', 'late_penalty_percentage': '90'})
        self.assertEqual(response.status_code, 302)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.max_score, 10)
        self.assertEqual(self.assignment.late_penalty_percentage, 0)
