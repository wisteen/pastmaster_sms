from decimal import Decimal

from django.db import transaction

from .models import ScholarshipFeeApplication, StudentFee


ZERO = Decimal('0.00')


def _eligible_student_fees(recipient):
    return StudentFee.objects.filter(
        student=recipient.student,
        fee_structure__term__session=recipient.scholarship.academic_year,
        fee_structure__term__end_date__gte=recipient.start_date,
        fee_structure__term__start_date__lte=recipient.end_date,
    ).select_related('fee_structure__term').order_by('fee_structure__term__start_date', 'id')


@transaction.atomic
def clear_scholarship_fee_applications(recipient):
    applications = list(
        recipient.fee_applications.select_for_update().select_related('student_fee')
    )
    for application in applications:
        student_fee = application.student_fee
        student_fee.discount_amount = max(ZERO, student_fee.discount_amount - application.amount)
        student_fee.save(update_fields=['discount_amount'])
        student_fee.update_status()
    recipient.fee_applications.all().delete()


@transaction.atomic
def sync_scholarship_fee_applications(recipient):
    clear_scholarship_fee_applications(recipient)
    if recipient.status != 'active':
        return []

    remaining_award = recipient.awarded_amount
    created = []
    for student_fee in _eligible_student_fees(recipient).select_for_update():
        available_balance = max(ZERO, student_fee.balance_amount)
        if available_balance <= ZERO:
            continue

        if recipient.scholarship.percentage:
            amount = min(
                available_balance,
                (student_fee.total_amount * recipient.scholarship.percentage) / Decimal('100'),
            )
        else:
            if remaining_award <= ZERO:
                break
            amount = min(available_balance, remaining_award)

        if amount <= ZERO:
            continue

        application = ScholarshipFeeApplication.objects.create(
            recipient=recipient,
            student_fee=student_fee,
            amount=amount,
        )
        student_fee.discount_amount += amount
        student_fee.save(update_fields=['discount_amount'])
        student_fee.update_status()
        created.append(application)

        if not recipient.scholarship.percentage:
            remaining_award -= amount

    return created


def sync_active_scholarships_for_student(student):
    for recipient in student.scholarshiprecipient_set.filter(status='active').select_related('scholarship'):
        sync_scholarship_fee_applications(recipient)
