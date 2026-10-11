from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import QuestionBank


# SS1 objective questions whose keys were missing.
SS1_ANSWERS = {
    1815: "C",
    6057: "B",
    6058: "C",
    6059: "C",
    6060: "B",
    6061: "C",
    6062: "B",
    6063: "C",
    6064: "B",
    6065: "B",
    6066: "C",
    6067: "B",
    6068: "B",
    6069: "C",
    6070: "C",
    6071: "C",
    6072: "C",
    6073: "B",
    6074: "A",
    6075: "B",
    6076: "C",
    6077: "B",
    6078: "C",
    6079: "B",
    6080: "C",
    6081: "C",
    6082: "B",
    6083: "B",
    6084: "B",
    6085: "B",
    6086: "B",
    6087: "B",
    6088: "B",
    6089: "B",
    6090: "C",
    6091: "B",
    6092: "C",
    6093: "B",
    6094: "C",
    6095: "B",
    6096: "B",
    6097: "B",
    6098: "B",
    6099: "B",
    6100: "A",
    6101: "A",
    6102: "B",
    6103: "B",
    6104: "A",
    6105: "A",
}


# The first SS2 block is the canonical copy. The second block (IDs + 42)
# repeats the same questions but was imported with every answer set to A.
SS2_CANONICAL_ANSWERS = {
    6141: "C",
    6142: "C",
    6143: "C",
    6144: "B",
    6145: "C",
    6146: "C",
    6147: "B",
    6148: "B",
    6149: "B",
    6150: "B",
    6151: "B",
    6152: "B",
    6153: "C",
    6154: "B",
    6155: "B",
    6156: "B",
    6157: "B",
    6158: "B",
    6159: "B",
    6160: "B",
    6161: "B",
    6162: "B",
    6163: "B",
    6164: "A",
    6165: "A",
    6166: "B",
    6167: "B",
    6168: "B",
    6169: "B",
    6170: "B",
    6171: "B",
    6172: "B",
    6173: "C",
    6174: "A",
    6175: "C",
    6176: "B",
    6177: "D",
    6178: "B",
    6179: "B",
    6180: "B",
    6181: "B",
    6182: "C",
}


ANSWERS = {
    **SS1_ANSWERS,
    **SS2_CANONICAL_ANSWERS,
    **{question_id + 42: answer for question_id, answer in SS2_CANONICAL_ANSWERS.items()},
}


SS1_MEDIUM = {
    6058,
    6070,
    6071,
    6072,
    6075,
    6077,
    6081,
    6086,
    6090,
    6091,
    6104,
}
SS1_THEORY_HARD = {6106, 6108, 6110}
SS1_THEORY_MEDIUM = {6107, 6109}

SS2_MEDIUM_CANONICAL = {
    6142,
    6143,
    6144,
    6147,
    6150,
    6151,
    6153,
    6154,
    6157,
    6159,
    6164,
    6165,
    6166,
    6167,
    6168,
    6174,
    6175,
    6177,
    6178,
    6180,
    6181,
}
SS2_MEDIUM = SS2_MEDIUM_CANONICAL | {
    question_id + 42 for question_id in SS2_MEDIUM_CANONICAL
}


CONTENT_FIXES = {
    # The intended scientific term was absent from the imported options.
    6099: {"option_b": "electron"},
}


class Command(BaseCommand):
    help = (
        "Curate imported Biology questions: repair objective answer keys, "
        "fix a scientific typo, and calibrate difficulty."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Persist changes. Without this flag the command performs a dry-run.",
        )

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        biology = QuestionBank.objects.filter(
            subject__school_id=2,
            subject__name="Biology",
        ).order_by("id")

        questions = {question.id: question for question in biology}
        expected_ids = set(ANSWERS) | SS1_THEORY_HARD | SS1_THEORY_MEDIUM | {1816}
        missing_ids = sorted(expected_ids - set(questions))
        if missing_ids:
            raise CommandError(
                "Expected Biology question IDs are missing: "
                + ", ".join(map(str, missing_ids))
            )

        if biology.count() != 140:
            raise CommandError(
                f"Expected 140 Biology questions for school 2; found {biology.count()}."
            )

        answer_changes = 0
        difficulty_changes = 0
        content_changes = 0
        changed_questions = []

        with transaction.atomic():
            for question in questions.values():
                changed_fields = []

                expected_answer = ANSWERS.get(question.id)
                if expected_answer and question.correct_answer != expected_answer:
                    question.correct_answer = expected_answer
                    changed_fields.append("correct_answer")
                    answer_changes += 1

                if question.id in SS1_THEORY_HARD:
                    expected_difficulty = "hard"
                elif (
                    question.id in SS1_MEDIUM
                    or question.id in SS1_THEORY_MEDIUM
                    or question.id in SS2_MEDIUM
                ):
                    expected_difficulty = "medium"
                else:
                    expected_difficulty = "easy"

                if question.difficulty != expected_difficulty:
                    question.difficulty = expected_difficulty
                    changed_fields.append("difficulty")
                    difficulty_changes += 1

                for field, value in CONTENT_FIXES.get(question.id, {}).items():
                    if getattr(question, field) != value:
                        setattr(question, field, value)
                        changed_fields.append(field)
                        content_changes += 1

                if changed_fields:
                    changed_questions.append((question, changed_fields))

            self._validate(questions)

            if apply_changes:
                for question, changed_fields in changed_questions:
                    question.save(update_fields=changed_fields)
            else:
                transaction.set_rollback(True)

        mode = "APPLIED" if apply_changes else "DRY RUN"
        self.stdout.write(self.style.SUCCESS(f"Biology curation: {mode}"))
        self.stdout.write(f"Questions inspected: {len(questions)}")
        self.stdout.write(f"Answer keys changed: {answer_changes}")
        self.stdout.write(f"Difficulty values changed: {difficulty_changes}")
        self.stdout.write(f"Content fields changed: {content_changes}")
        self.stdout.write(f"Question records changed: {len(changed_questions)}")

    def _validate(self, questions):
        objective_count = 0
        theory_count = 0

        for question in questions.values():
            if question.question_type == "objective":
                objective_count += 1
                if question.correct_answer not in {"A", "B", "C", "D"}:
                    raise CommandError(
                        f"Objective question {question.id} has invalid answer key "
                        f"{question.correct_answer!r}."
                    )
                selected_option = getattr(
                    question, f"option_{question.correct_answer.lower()}"
                )
                if not selected_option.strip():
                    raise CommandError(
                        f"Objective question {question.id} points to an empty option."
                    )
            elif question.question_type == "theory":
                theory_count += 1
                if question.correct_answer:
                    raise CommandError(
                        f"Theory question {question.id} unexpectedly has an A-D key."
                    )
            else:
                raise CommandError(
                    f"Question {question.id} has unsupported type {question.question_type!r}."
                )

        if objective_count != 135 or theory_count != 5:
            raise CommandError(
                "Expected 135 objective and 5 theory Biology questions; found "
                f"{objective_count} objective and {theory_count} theory."
            )
