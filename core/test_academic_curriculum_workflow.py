from datetime import date, timedelta

from django.test import Client, TestCase
from django.urls import reverse

from .forms_academic import LessonPlanForm
from .models import (
    Curriculum,
    LearningObjective,
    LessonNote,
    LessonPlan,
    SchoolClass,
    SchoolDomain,
    SchoolMembership,
    SchoolTenant,
    Student,
    Subject,
    Teacher,
    User,
)
from .permissions import AcademicPermissionManager


class AcademicCurriculumWorkflowTests(TestCase):
    host = 'academic-workflow.testserver'

    def setUp(self):
        self.school = SchoolTenant.objects.create(
            name='Academic Workflow School',
            slug='academic-workflow-school',
            plan='premium',
        )
        SchoolDomain.objects.create(school=self.school, domain=self.host)
        self.teacher_user = User.objects.create_user(
            username='workflow_teacher',
            password='password',
            role='subject_teacher',
        )
        SchoolMembership.objects.create(
            school=self.school,
            user=self.teacher_user,
            primary_role='subject_teacher',
        )
        self.subject = Subject.all_objects.create(
            school=self.school,
            name='Basic Science',
            code='BSC',
        )
        self.school_class = SchoolClass.all_objects.create(
            school=self.school,
            name='Basic 4',
            stream='Silver',
        )
        self.teacher = Teacher.all_objects.create(
            school=self.school,
            user=self.teacher_user,
            employee_id='T-WORKFLOW',
        )
        self.teacher.subjects.add(self.subject)
        self.teacher.classes.add(self.school_class)
        self.curriculum = Curriculum.all_objects.create(
            school=self.school,
            title='Basic 4 Science Curriculum',
            description='Natural cycles and weather patterns.',
            academic_year='2026-2027',
            created_by=self.teacher_user,
            is_published=True,
        )
        self.curriculum.subjects.add(self.subject)
        self.objective = LearningObjective.objects.create(
            curriculum=self.curriculum,
            title='Compare day and night',
            description='Identify two differences between day and night.',
            subject=self.subject,
            grade_level='Basic 4',
            order=1,
        )
        self.lesson_plan = LessonPlan.objects.create(
            title='Changes in Nature: Day and Night',
            curriculum=self.curriculum,
            subject=self.subject,
            school_class=self.school_class,
            teacher=self.teacher,
            week_number=4,
            average_age=9,
            previous_knowledge='Learners can describe morning and night.',
            content='<p>Compare daytime and nighttime activities.</p>',
            reference_book='Basic Science Book 4, pages 12-15.',
            resources='Day and night picture cards.',
            estimated_duration=timedelta(minutes=45),
        )
        self.lesson_plan.learning_objectives.add(self.objective)
        self.client = Client(HTTP_HOST=self.host)
        self.client.force_login(self.teacher_user)

    def _plan_data(self, **overrides):
        data = {
            'title': 'Water Cycle',
            'curriculum': self.curriculum.pk,
            'subject': self.subject.pk,
            'school_class': self.school_class.pk,
            'week_number': 5,
            'average_age': 9,
            'previous_knowledge': 'Learners have observed rain.',
            'learning_objectives': [self.objective.pk],
            'new_learning_objectives': '',
            'content': '<p>Observe and label the water cycle.</p>',
            'reference_book': 'Basic Science Book 4, pages 20-22.',
            'resources': 'Water cycle chart.',
            'estimated_duration': 40,
        }
        data.update(overrides)
        return data

    def test_form_stores_duration_as_minutes_and_teaching_context(self):
        form = LessonPlanForm(data=self._plan_data(), user=self.teacher_user)

        self.assertTrue(form.is_valid(), form.errors.as_json())
        lesson_plan = form.save(commit=False)
        lesson_plan.teacher = self.teacher
        lesson_plan.save()
        form.save_m2m()

        self.assertEqual(lesson_plan.estimated_duration, timedelta(minutes=40))
        self.assertEqual(lesson_plan.week_number, 5)
        self.assertEqual(lesson_plan.average_age, 9)
        self.assertEqual(lesson_plan.previous_knowledge, 'Learners have observed rain.')

    def test_standalone_plan_can_create_and_retrieve_typed_objective(self):
        form = LessonPlanForm(
            data=self._plan_data(
                curriculum='',
                learning_objectives=[],
                new_learning_objectives='Identify rainfall using a simple diagram.',
            ),
            user=self.teacher_user,
        )

        self.assertTrue(form.is_valid(), form.errors.as_json())
        lesson_plan = form.save(commit=False)
        lesson_plan.teacher = self.teacher
        lesson_plan.save()
        form.save_m2m()

        objective = lesson_plan.learning_objectives.get()
        self.assertIsNone(objective.curriculum)
        self.assertEqual(objective.subject, self.subject)
        self.assertEqual(objective.title, 'Identify rainfall using a simple diagram.')

        edit_form = LessonPlanForm(instance=lesson_plan, user=self.teacher_user)
        self.assertIn(objective, edit_form.fields['learning_objectives'].queryset)

    def test_lesson_note_inherits_curriculum_when_omitted(self):
        response = self.client.post(
            reverse('academic:lesson_note_create'),
            {
                'lesson_plan': self.lesson_plan.pk,
                'curriculum': '',
                'date_taught': '2026-09-21',
                'content_covered': '<p>Compared day and night.</p>',
                'student_engagement': 'high',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            LessonNote.objects.get(lesson_plan=self.lesson_plan).curriculum,
            self.curriculum,
        )

    def test_context_endpoint_returns_plan_metadata(self):
        response = self.client.get(
            reverse('academic:lesson_plan_context', args=[self.lesson_plan.pk])
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['topic'], self.lesson_plan.title)
        self.assertEqual(payload['week_number'], 4)
        self.assertEqual(payload['estimated_duration_minutes'], 45)
        self.assertEqual(
            payload['behavioural_objectives'][0]['title'],
            self.objective.title,
        )

    def test_unassigned_teacher_cannot_read_plan_context(self):
        other_user = User.objects.create_user(
            username='unassigned_teacher',
            password='password',
            role='subject_teacher',
        )
        SchoolMembership.objects.create(
            school=self.school,
            user=other_user,
            primary_role='subject_teacher',
        )
        Teacher.all_objects.create(
            school=self.school,
            user=other_user,
            employee_id='T-UNASSIGNED',
        )
        self.client.force_login(other_user)

        response = self.client.get(
            reverse('academic:lesson_plan_context', args=[self.lesson_plan.pk])
        )

        self.assertEqual(response.status_code, 403)

    def test_class_teacher_can_edit_own_plan(self):
        self.teacher_user.role = 'class_teacher'
        self.teacher_user.save(update_fields=['role'])
        membership = self.teacher_user.school_memberships.get(school=self.school)
        membership.primary_role = 'class_teacher'
        membership.save(update_fields=['primary_role'])

        self.assertTrue(
            AcademicPermissionManager.can_edit_lesson_plan(
                self.teacher_user,
                self.lesson_plan,
            )
        )

    def test_removed_objective_is_hidden_and_restorable(self):
        self.objective.delete()

        self.assertFalse(LearningObjective.objects.filter(pk=self.objective.pk).exists())
        removed = LearningObjective.all_objects.get(pk=self.objective.pk)
        self.assertIsNotNone(removed.pending_deletion_at)

        removed.restore()
        self.assertTrue(LearningObjective.objects.filter(pk=self.objective.pk).exists())

    def test_student_can_read_notes_for_their_class(self):
        note = LessonNote.objects.create(
            lesson_plan=self.lesson_plan,
            curriculum=self.curriculum,
            teacher=self.teacher,
            date_taught=date(2026, 9, 21),
            content_covered='<p>Halves and quarters.</p>',
        )
        student_user = User.objects.create_user(
            username='workflow_student',
            password='password',
            role='student',
        )
        SchoolMembership.objects.create(
            school=self.school,
            user=student_user,
            primary_role='student',
        )
        Student.all_objects.create(
            school=self.school,
            user=student_user,
            student_id='ST-WORKFLOW',
            school_class=self.school_class,
            date_of_birth=date(2016, 1, 1),
        )
        self.client.force_login(student_user)

        response = self.client.get(reverse('academic:student_lesson_notes'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, note.lesson_plan.title)
        self.assertContains(response, 'Halves and quarters.')
