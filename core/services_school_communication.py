from dataclasses import dataclass
from decimal import Decimal

from django.template.loader import render_to_string
from django.urls import reverse

from .models import SchoolSettings, StaffPayroll, Student, StudentFee
from .models_biodata import Guardian
from .services_notification import NotificationService


@dataclass(frozen=True)
class EmailRecipient:
    email: str
    name: str


class SchoolCommunicationService:
    def __init__(self, school):
        self.school = school
        self.notification_service = NotificationService()
        settings = SchoolSettings.get_for_school(school)
        self.school_name = settings.school_name if settings else school.name

    def _deduplicate(self, recipients):
        unique = {}
        for recipient in recipients:
            email = (recipient.email or '').strip().lower()
            if email:
                unique[email] = EmailRecipient(email=email, name=recipient.name or email)
        return list(unique.values())

    def _student_recipients(self, student):
        recipients = [
            EmailRecipient(student.user.email, student.user.get_full_name() or student.user.username),
        ]
        for guardian in Guardian.objects.filter(student=student).select_related('user'):
            name = guardian.get_full_name()
            recipients.append(EmailRecipient(guardian.email, name))
            if guardian.user:
                recipients.append(
                    EmailRecipient(
                        guardian.user.email,
                        guardian.user.get_full_name() or guardian.user.username,
                    )
                )
        return self._deduplicate(recipients)

    def _teacher_recipients(self):
        from .models import Teacher

        return self._deduplicate(
            EmailRecipient(teacher.user.email, teacher.user.get_full_name() or teacher.user.username)
            for teacher in Teacher.all_objects.filter(school=self.school).select_related('user')
        )

    def _parent_recipients(self):
        recipients = []
        for guardian in Guardian.objects.filter(student__school=self.school).select_related('user'):
            recipients.append(EmailRecipient(guardian.email, guardian.get_full_name()))
            if guardian.user:
                recipients.append(
                    EmailRecipient(
                        guardian.user.email,
                        guardian.user.get_full_name() or guardian.user.username,
                    )
                )
        return self._deduplicate(recipients)

    def _student_portal_recipients(self):
        return self._deduplicate(
            EmailRecipient(student.user.email, student.user.get_full_name() or student.user.username)
            for student in Student.all_objects.filter(school=self.school).select_related('user')
        )

    def _send(self, recipients, subject, title, message, rows=None, portal_path=None):
        sent = failed = skipped = 0
        recipients = self._deduplicate(recipients)
        if not recipients:
            return {'sent': 0, 'failed': 0, 'skipped': 1}

        html_content = render_to_string('notifications/email/school_communication.html', {
            'school_name': self.school_name,
            'title': title,
            'message': message,
            'rows': rows or [],
            'portal_path': portal_path,
        })
        for recipient in recipients:
            if self.notification_service.send_custom_email(
                recipient_email=recipient.email,
                recipient_name=recipient.name,
                subject=subject,
                html_content=html_content,
            ):
                sent += 1
            else:
                failed += 1
        return {'sent': sent, 'failed': failed, 'skipped': skipped}

    def send_result(self, student, term):
        results = student.result_set.filter(term=term).select_related('subject').order_by('subject__name')
        if not results.exists():
            return {'sent': 0, 'failed': 0, 'skipped': 1}

        term.result_published = True
        term.save(update_fields=['result_published'])
        rows = [
            (result.subject.name, f'{result.total_score} ({result.grade or "-"})')
            for result in results
        ]
        return self._send(
            self._student_recipients(student),
            f'{term.name} {term.session} result for {student.user.get_full_name()}',
            'Result Published',
            f'The result for {student.user.get_full_name()} is now available on the student and parent portals.',
            rows=rows,
            portal_path=reverse('core:dashboard'),
        )

    def send_fee_statement(self, student):
        fees = StudentFee.objects.filter(student=student).select_related('fee_structure__term').order_by(
            '-fee_structure__term__start_date'
        )
        rows = [
            (
                f'{fee.fee_structure.name} ({fee.fee_structure.term.name} {fee.fee_structure.term.session})',
                f'Total: {fee.total_amount} | Paid: {fee.paid_amount} | Discount: {fee.discount_amount} | Outstanding: {fee.balance_amount}',
            )
            for fee in fees
        ]
        total_outstanding = sum((max(fee.balance_amount, Decimal('0')) for fee in fees), Decimal('0'))
        return self._send(
            self._student_recipients(student),
            f'Fee statement for {student.user.get_full_name()}',
            'School Fee Statement',
            f'The current outstanding school fee balance for {student.user.get_full_name()} is {total_outstanding}.',
            rows=rows,
            portal_path=reverse('core:dashboard'),
        )

    def send_payslip(self, payroll):
        from .models_loans import TeacherLoan

        loan_deductions = payroll.custom_deductions.filter(deduction_type='loan')
        other_custom_deductions = payroll.custom_deductions.exclude(deduction_type='loan')
        projected_loans = TeacherLoan.objects.none()
        if not loan_deductions.exists() and not payroll.is_paid:
            projected_loans = TeacherLoan.objects.filter(teacher=payroll.teacher, status='active', balance__gt=0)
        html_content = render_to_string('financial/payslip_email.html', {
            'payroll': payroll,
            'loan_deductions': loan_deductions,
            'projected_loans': projected_loans,
            'other_custom_deductions': other_custom_deductions,
            'total_loan_deduction': sum(deduction.amount for deduction in loan_deductions),
            'total_deductions': payroll.total_deductions,
            'correct_net_pay': payroll.gross_salary - payroll.total_deductions,
        })
        teacher = payroll.teacher.user
        success = self.notification_service.send_custom_email(
            recipient_email=teacher.email,
            recipient_name=teacher.get_full_name() or teacher.username,
            subject=f'Payslip for {payroll.month.strftime("%B %Y")}',
            html_content=html_content,
        ) if teacher.email else False
        return {'sent': int(success), 'failed': int(bool(teacher.email) and not success), 'skipped': int(not teacher.email)}

    def send_announcement(self, audience, subject, message):
        recipients = []
        if audience in ['parents', 'everyone']:
            recipients.extend(self._parent_recipients())
        if audience in ['students', 'everyone']:
            recipients.extend(self._student_portal_recipients())
        if audience in ['teachers', 'everyone']:
            recipients.extend(self._teacher_recipients())
        return self._send(recipients, subject, 'School Information', message)
