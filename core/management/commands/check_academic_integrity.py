"""
Management command to check academic data integrity and referential consistency
"""

from django.core.management.base import BaseCommand
from django.core.exceptions import ValidationError
from core.validators_academic import (
    AcademicDataValidator, 
    DataConsistencyChecker, 
    ReferentialIntegrityManager
)


class Command(BaseCommand):
    help = 'Check academic management data integrity and referential consistency'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Attempt to fix consistency issues where possible',
        )
        parser.add_argument(
            '--model',
            type=str,
            help='Check specific model only (e.g., Curriculum, LessonPlan)',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('Starting Academic Management Data Integrity Check...')
        )
        
        if options['model']:
            self.check_specific_model(options['model'], options['verbose'])
        else:
            self.check_all_models(options['fix'], options['verbose'])

    def check_specific_model(self, model_name, verbose):
        """Check integrity for a specific model"""
        from core.models import (
            Curriculum, LearningObjective, LessonPlan, CurriculumCoverage,
            AcademicEvent, ExamSchedule, Timetable, Assignment, AssignmentSubmission
        )
        
        model_map = {
            'Curriculum': (Curriculum, AcademicDataValidator.validate_curriculum_relationships),
            'LearningObjective': (LearningObjective, AcademicDataValidator.validate_learning_objective_relationships),
            'LessonPlan': (LessonPlan, AcademicDataValidator.validate_lesson_plan_relationships),
            'CurriculumCoverage': (CurriculumCoverage, AcademicDataValidator.validate_curriculum_coverage_relationships),
            'AcademicEvent': (AcademicEvent, AcademicDataValidator.validate_academic_event_relationships),
            'ExamSchedule': (ExamSchedule, AcademicDataValidator.validate_exam_schedule_relationships),
            'Timetable': (Timetable, AcademicDataValidator.validate_timetable_relationships),
            'Assignment': (Assignment, AcademicDataValidator.validate_assignment_relationships),
            'AssignmentSubmission': (AssignmentSubmission, AcademicDataValidator.validate_assignment_submission_relationships),
        }
        
        if model_name not in model_map:
            self.stdout.write(
                self.style.ERROR(f'Unknown model: {model_name}')
            )
            self.stdout.write(
                f'Available models: {", ".join(model_map.keys())}'
            )
            return
        
        model_class, validator_func = model_map[model_name]
        
        self.stdout.write(f'Checking {model_name} integrity...')
        
        total_records = 0
        invalid_records = 0
        
        for instance in model_class.objects.all():
            total_records += 1
            errors = validator_func(instance)
            
            if errors:
                invalid_records += 1
                self.stdout.write(
                    self.style.ERROR(f'  ID {instance.pk}: {"; ".join(errors)}')
                )
            elif verbose:
                self.stdout.write(
                    self.style.SUCCESS(f'  ID {instance.pk}: OK')
                )
        
        self.stdout.write(
            f'{model_name}: {total_records} total, {invalid_records} invalid'
        )

    def check_all_models(self, fix_issues, verbose):
        """Check integrity for all academic models"""
        
        # Run foreign key validation
        self.stdout.write('\n1. Checking Foreign Key Constraints...')
        validation_results = ReferentialIntegrityManager.validate_foreign_key_constraints()
        
        total_invalid = 0
        for model_name, results in validation_results.items():
            invalid_count = results['invalid_records']
            total_invalid += invalid_count
            
            if invalid_count > 0:
                self.stdout.write(
                    self.style.ERROR(
                        f'  {model_name}: {invalid_count}/{results["total_records"]} invalid'
                    )
                )
                if verbose:
                    for error in results['errors'][:5]:  # Show first 5 errors
                        self.stdout.write(f'    - {error}')
                    if len(results['errors']) > 5:
                        self.stdout.write(f'    ... and {len(results["errors"]) - 5} more')
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  {model_name}: {results["total_records"]} records OK'
                    )
                )
        
        # Run data consistency checks
        self.stdout.write('\n2. Checking Data Consistency...')
        consistency_results = DataConsistencyChecker.run_full_consistency_check()
        
        if consistency_results['total_issues'] > 0:
            self.stdout.write(
                self.style.ERROR(
                    f'  Found {consistency_results["total_issues"]} consistency issues:'
                )
            )
            for issue in consistency_results['issues']:
                self.stdout.write(f'    - {issue}')
        else:
            self.stdout.write(
                self.style.SUCCESS('  All data consistency checks passed')
            )
        
        # Summary
        self.stdout.write('\n' + '='*50)
        self.stdout.write('INTEGRITY CHECK SUMMARY')
        self.stdout.write('='*50)
        
        if total_invalid == 0 and consistency_results['total_issues'] == 0:
            self.stdout.write(
                self.style.SUCCESS('✓ All integrity checks passed!')
            )
        else:
            self.stdout.write(
                self.style.ERROR(
                    f'✗ Found {total_invalid} foreign key violations and '
                    f'{consistency_results["total_issues"]} consistency issues'
                )
            )
            
            if fix_issues:
                self.stdout.write('\nAttempting to fix issues...')
                self.attempt_fixes(validation_results, consistency_results)
            else:
                self.stdout.write('\nRun with --fix to attempt automatic fixes')

    def attempt_fixes(self, validation_results, consistency_results):
        """Attempt to fix common integrity issues"""
        
        self.stdout.write('Automatic fixing is not yet implemented.')
        self.stdout.write('Please review the issues manually and fix them in the Django admin or shell.')
        
        # Future implementation could include:
        # - Removing orphaned records
        # - Updating inconsistent coverage calculations
        # - Fixing academic year formats
        # - etc.