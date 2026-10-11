from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import get_random_string

from .forms_onboarding import (
    BasicOnboardingForm,
    BulkOnboardingUploadForm,
    ReviewOnboardingForm,
    parent_self_service_forms,
    teacher_self_service_forms,
)
from .models import SchoolMembership
from .models_onboarding import OnboardingRecord
from .services_onboarding import (
    columns_for,
    create_basic_person,
    ensure_onboarding_records,
    import_rows,
    parse_spreadsheet,
    rows_from_post,
    template_response,
    validate_rows,
)
from .services_portal_delivery import TenantPortalDeliveryService
from .views_school_admin import _active_school_or_redirect, _require_school_admin


@login_required
def school_admin_onboarding(request):
    if not _require_school_admin(request):
        return redirect('core:dashboard')
    school = _active_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')

    ensure_onboarding_records(school, created_by=request.user)
    basic_form = BasicOnboardingForm(school=school, prefix='basic')
    upload_form = BulkOnboardingUploadForm(prefix='upload')
    preview_rows = []
    preview_person_type = ''
    preview_columns = []

    if request.method == 'POST':
        action = request.POST.get('action', '')
        if action == 'create_basic':
            basic_form = BasicOnboardingForm(request.POST, school=school, prefix='basic')
            if basic_form.is_valid():
                record = _create_basic_from_form(school, basic_form, request.user)
                if basic_form.cleaned_data.get('send_invitation'):
                    summary = _send_invitation(request, record, _default_channels(record))
                    _add_delivery_message(request, f'Invitation for {record.display_name}', summary)
                else:
                    messages.success(request, f'Basic profile created for {record.display_name}.')
                return redirect('core:school_admin_onboarding')

        elif action == 'preview_upload':
            upload_form = BulkOnboardingUploadForm(request.POST, request.FILES, prefix='upload')
            if upload_form.is_valid():
                preview_person_type = upload_form.cleaned_data['person_type']
                try:
                    rows = parse_spreadsheet(upload_form.cleaned_data['spreadsheet'], preview_person_type)
                    preview_rows = validate_rows(school, preview_person_type, rows)
                    preview_columns = columns_for(preview_person_type)
                except (ValueError, UnicodeDecodeError) as exc:
                    upload_form.add_error('spreadsheet', str(exc))

        elif action in {'validate_rows', 'import_rows'}:
            preview_person_type = request.POST.get('person_type', OnboardingRecord.PERSON_STUDENT)
            if preview_person_type not in dict(OnboardingRecord.PERSON_TYPE_CHOICES):
                preview_person_type = OnboardingRecord.PERSON_STUDENT
            preview_columns = columns_for(preview_person_type)
            preview_rows = validate_rows(
                school,
                preview_person_type,
                rows_from_post(request.POST, preview_person_type),
            )
            if action == 'validate_rows' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'valid': bool(preview_rows) and all(row['valid'] for row in preview_rows),
                    'valid_count': sum(row['valid'] for row in preview_rows),
                    'invalid_count': sum(not row['valid'] for row in preview_rows),
                    'rows': [
                        {
                            'index': index,
                            'number': row['number'],
                            'valid': row['valid'],
                            'errors': row['errors'],
                        }
                        for index, row in enumerate(preview_rows)
                    ],
                })
            if action == 'import_rows' and preview_rows and all(row['valid'] for row in preview_rows):
                records = import_rows(school, preview_person_type, preview_rows, created_by=request.user)
                sent = failed = skipped = 0
                if request.POST.get('send_invitations'):
                    channels = request.POST.getlist('channels') or ['email']
                    for record in records:
                        summary = _send_invitation(request, record, channels)
                        sent += summary.sent
                        failed += summary.failed
                        skipped += summary.skipped
                messages.success(request, f'{len(records)} {preview_person_type} record(s) imported successfully.')
                if request.POST.get('send_invitations'):
                    delivery_message = f'Invitation delivery: {sent} sent, {failed} failed, {skipped} skipped.'
                    if failed:
                        messages.warning(request, delivery_message)
                    else:
                        messages.success(request, delivery_message)
                return redirect('core:school_admin_onboarding')
            if action == 'import_rows' and preview_rows:
                messages.error(request, 'Correct the highlighted spreadsheet cells before importing.')

        elif action == 'send_invitation':
            record = _school_record(school, request.POST.get('record_id'))
            summary = _send_invitation(request, record, request.POST.getlist('channels'))
            _add_delivery_message(request, f'Invitation for {record.display_name}', summary)
            return redirect('core:school_admin_onboarding')

        elif action == 'send_login':
            record = _school_record(school, request.POST.get('record_id'))
            summary = _send_login(request, record, request.POST.getlist('channels'))
            _add_delivery_message(request, f'Login details for {record.display_name}', summary)
            return redirect('core:school_admin_onboarding')

    records = OnboardingRecord.all_objects.filter(school=school).select_related(
        'user', 'student__school_class', 'teacher'
    ).prefetch_related('user__school_memberships')
    person_filter = request.GET.get('person_type', '').strip()
    status_filter = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    if person_filter in dict(OnboardingRecord.PERSON_TYPE_CHOICES):
        records = records.filter(person_type=person_filter)
    if status_filter in dict(OnboardingRecord.STATUS_CHOICES):
        records = records.filter(status=status_filter)
    if search:
        records = records.filter(
            Q(user__first_name__icontains=search)
            | Q(user__last_name__icontains=search)
            | Q(user__username__icontains=search)
            | Q(recipient_email__icontains=search)
            | Q(recipient_phone__icontains=search)
        )
    records = list(records)
    all_records = list(OnboardingRecord.all_objects.filter(school=school).select_related(
        'user', 'student', 'teacher'
    ).prefetch_related('user__school_memberships'))
    summary = {
        'basic': len(all_records),
        'details_pending': sum(not record.details_complete for record in all_records),
        'login_not_sent': sum(not record.login_complete for record in all_records),
        'ready': sum(record.status == OnboardingRecord.STATUS_READY for record in all_records),
        'active': sum(record.status == OnboardingRecord.STATUS_ACTIVE for record in all_records),
    }
    return render(request, 'school_admin/onboarding.html', {
        'school': school,
        'records': records,
        'summary': summary,
        'basic_form': basic_form,
        'upload_form': upload_form,
        'preview_rows': preview_rows,
        'preview_person_type': preview_person_type,
        'preview_columns': preview_columns,
        'preview_has_errors': any(not row['valid'] for row in preview_rows),
        'person_filter': person_filter,
        'status_filter': status_filter,
        'search': search,
        'status_choices': OnboardingRecord.STATUS_CHOICES,
        'person_type_choices': OnboardingRecord.PERSON_TYPE_CHOICES,
    })


@login_required
def download_onboarding_template(request, person_type, file_format):
    if not _require_school_admin(request):
        return redirect('core:dashboard')
    if not _active_school_or_redirect(request):
        return redirect('core:dashboard')
    if person_type not in dict(OnboardingRecord.PERSON_TYPE_CHOICES) or file_format not in {'csv', 'xlsx'}:
        raise Http404('Template not found.')
    return template_response(person_type, file_format)


@login_required
def review_onboarding(request, record_id):
    if not _require_school_admin(request):
        return redirect('core:dashboard')
    school = _active_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')
    record = _school_record(school, record_id)
    review_form = ReviewOnboardingForm()

    if request.method == 'POST':
        review_form = ReviewOnboardingForm(request.POST)
        if review_form.is_valid():
            action = review_form.cleaned_data['action']
            if record.status != OnboardingRecord.STATUS_PENDING_REVIEW:
                messages.error(request, 'This submission is no longer awaiting review.')
                return redirect('core:review_onboarding', record_id=record.id)
            if action == ReviewOnboardingForm.ACTION_APPROVE:
                if not record.details_complete:
                    messages.error(request, 'Required onboarding details are still missing.')
                else:
                    record.status = OnboardingRecord.STATUS_READY
                    record.review_note = (review_form.cleaned_data.get('review_note') or '').strip()
                    record.reviewed_by = request.user
                    record.reviewed_at = timezone.now()
                    record.token_digest = None
                    record.expires_at = None
                    record.save(update_fields=[
                        'status', 'review_note', 'reviewed_by', 'reviewed_at',
                        'token_digest', 'expires_at', 'updated_at',
                    ])
                    messages.success(request, f'{record.display_name} is approved and ready for login delivery.')
                    return redirect('core:school_admin_onboarding')
            else:
                record.review_note = review_form.cleaned_data['review_note'].strip()
                record.reviewed_by = request.user
                record.reviewed_at = timezone.now()
                record.save(update_fields=['review_note', 'reviewed_by', 'reviewed_at', 'updated_at'])
                raw_token = record.issue_invitation(status=OnboardingRecord.STATUS_CHANGES_REQUESTED)
                summary = _deliver_invitation(request, record, raw_token, review_form.cleaned_data.get('channels'))
                _add_delivery_message(request, f'Correction request for {record.display_name}', summary)
                return redirect('core:review_onboarding', record_id=record.id)

    return render(request, 'school_admin/onboarding_review.html', {
        'school': school,
        'record': record,
        'review_form': review_form,
        'student_bio': getattr(record.student, 'bio_data', None) if record.student_id else None,
        'guardian': record.student.guardians.first() if record.student_id else None,
        'staff_bio': getattr(record.teacher, 'bio_data', None) if record.teacher_id else None,
        'qualification': record.teacher.bio_data.qualifications.first()
        if record.teacher_id and hasattr(record.teacher, 'bio_data') else None,
        'bank_account': getattr(record.teacher.bio_data, 'bank_account', None)
        if record.teacher_id and hasattr(record.teacher, 'bio_data') else None,
    })


def onboarding_invitation(request, token):
    record = OnboardingRecord.find_by_token(token)
    if not record:
        return render(request, 'onboarding/invitation_complete.html', {
            'invalid': True,
            'page_title': 'Invitation unavailable',
        }, status=404)
    if record.is_expired:
        return render(request, 'onboarding/invitation_complete.html', {
            'expired': True,
            'record': record,
            'page_title': 'Invitation expired',
        }, status=410)
    if record.status in {
        OnboardingRecord.STATUS_PENDING_REVIEW,
        OnboardingRecord.STATUS_READY,
        OnboardingRecord.STATUS_ACTIVE,
    }:
        return render(request, 'onboarding/invitation_complete.html', {
            'record': record,
            'submitted': record.status == OnboardingRecord.STATUS_PENDING_REVIEW,
            'approved': record.status in {OnboardingRecord.STATUS_READY, OnboardingRecord.STATUS_ACTIVE},
            'page_title': 'Onboarding submitted',
        })
    if not record.can_open_invitation:
        return render(request, 'onboarding/invitation_complete.html', {
            'invalid': True,
            'record': record,
            'page_title': 'Invitation unavailable',
        }, status=410)

    if request.method == 'GET' and not record.opened_at:
        record.opened_at = timezone.now()
        if record.status == OnboardingRecord.STATUS_INVITED:
            record.status = OnboardingRecord.STATUS_IN_PROGRESS
        record.save(update_fields=['opened_at', 'status', 'updated_at'])

    if record.person_type == OnboardingRecord.PERSON_TEACHER:
        forms_bundle = teacher_self_service_forms(
            request.POST or None,
            request.FILES or None,
            teacher=record.teacher,
        )
        form_sections = _teacher_sections(forms_bundle)
    else:
        forms_bundle = parent_self_service_forms(
            request.POST or None,
            request.FILES or None,
            student=record.student,
            record=record,
        )
        form_sections = _parent_sections(forms_bundle)

    forms_are_valid = all([form.is_valid() for form in forms_bundle.values()]) if request.method == 'POST' else False
    if request.method == 'POST' and forms_are_valid:
        with transaction.atomic():
            if record.person_type == OnboardingRecord.PERSON_TEACHER:
                _save_teacher_submission(record, forms_bundle)
            else:
                _save_parent_submission(record, forms_bundle)
            record.status = OnboardingRecord.STATUS_PENDING_REVIEW
            record.submitted_at = timezone.now()
            record.review_note = ''
            record.save(update_fields=['status', 'submitted_at', 'review_note', 'updated_at'])
        return redirect('core:onboarding_invitation', token=token)

    return render(request, 'onboarding/invitation_form.html', {
        'record': record,
        'forms_bundle': forms_bundle,
        'form_sections': form_sections,
        'school_settings': getattr(record.school, 'settings', None),
    })


def _create_basic_from_form(school, form, user):
    values = dict(form.cleaned_data)
    school_class = values.get('school_class')
    if school_class:
        values['class_name'] = school_class.name
        values['class_stream'] = school_class.stream
    return create_basic_person(
        school,
        values['person_type'],
        values,
        created_by=user,
        source=OnboardingRecord.SOURCE_MANUAL,
    )


def _school_record(school, record_id):
    return get_object_or_404(
        OnboardingRecord.all_objects.select_related('school', 'user', 'student__school_class', 'teacher'),
        id=record_id,
        school=school,
    )


def _default_channels(record):
    if record.recipient_email:
        return ['email']
    if record.recipient_phone:
        return ['sms']
    return ['email']


def _send_invitation(request, record, channels):
    previous_status = record.status
    raw_token = record.issue_invitation()
    summary = _deliver_invitation(request, record, raw_token, channels)
    if not summary.sent:
        record.status = previous_status
        record.token_digest = None
        record.expires_at = None
        record.save(update_fields=['status', 'token_digest', 'expires_at', 'updated_at'])
    return summary


def _deliver_invitation(request, record, raw_token, channels):
    invitation_url = request.build_absolute_uri(
        reverse('core:onboarding_invitation', kwargs={'token': raw_token})
    )
    return TenantPortalDeliveryService(
        record.school,
        sender=request.user if request.user.is_authenticated else None,
        request=request,
    ).send_onboarding_invitation(record, invitation_url, channels or _default_channels(record))


def _send_login(request, record, channels):
    if record.status != OnboardingRecord.STATUS_READY or not record.details_complete:
        from .services_portal_delivery import DeliverySummary
        return DeliverySummary(failed=1, errors=['Approve the completed onboarding details before sending a login.'])
    temporary_password = get_random_string(
        10,
        allowed_chars='ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789',
    )
    record.user.set_password(temporary_password)
    record.user.is_active = True
    record.user.save(update_fields=['password', 'is_active'])
    summary = TenantPortalDeliveryService(
        record.school,
        sender=request.user,
        request=request,
    ).send_login_details(record.user, temporary_password, channels or _default_channels(record))
    if summary.sent:
        membership = SchoolMembership.objects.filter(school=record.school, user=record.user).first()
        if membership:
            membership.is_active = True
            membership.portal_access_enabled = True
            membership.save(update_fields=['is_active', 'portal_access_enabled', 'updated_at'])
        record.status = OnboardingRecord.STATUS_ACTIVE
        record.login_sent_at = timezone.now()
        record.activated_at = timezone.now()
        record.save(update_fields=['status', 'login_sent_at', 'activated_at', 'updated_at'])
    else:
        record.user.set_unusable_password()
        record.user.save(update_fields=['password'])
    return summary


def _add_delivery_message(request, subject, summary):
    text = f'{subject}: {summary.as_message()}.'
    if summary.failed:
        messages.warning(request, text)
    elif summary.sent:
        messages.success(request, text)
    else:
        messages.warning(request, text)


def _save_teacher_submission(record, forms_bundle):
    bio_data = forms_bundle['bio'].save(commit=False)
    bio_data.teacher = record.teacher
    bio_data.save()
    qualification = forms_bundle['qualification'].save(commit=False)
    qualification.staff_bio_data = bio_data
    qualification.save()
    bank_account = forms_bundle['bank'].save(commit=False)
    bank_account.staff_bio_data = bio_data
    bank_account.save()
    signature = forms_bundle['signature'].cleaned_data.get('signature')
    if signature:
        record.teacher.signature = signature
        record.teacher.save(update_fields=['signature'])
    record.recipient_name = record.user.get_full_name()
    record.recipient_email = bio_data.email
    record.recipient_phone = bio_data.phone_number
    record.save(update_fields=['recipient_name', 'recipient_email', 'recipient_phone', 'updated_at'])


def _save_parent_submission(record, forms_bundle):
    bio_data = forms_bundle['bio'].save(commit=False)
    bio_data.student = record.student
    bio_data.save()
    guardian = forms_bundle['guardian'].save(commit=False)
    guardian.student = record.student
    guardian.user = None
    guardian.save()
    record.student.date_of_birth = bio_data.date_of_birth
    record.student.address = bio_data.home_address
    record.student.save(update_fields=['date_of_birth', 'address'])
    record.recipient_name = guardian.get_full_name()
    record.recipient_email = guardian.email
    record.recipient_phone = guardian.phone_number
    record.save(update_fields=['recipient_name', 'recipient_email', 'recipient_phone', 'updated_at'])


def _teacher_sections(forms_bundle):
    bio = forms_bundle['bio']
    return [
        ('Personal and contact details', [bio[name] for name in [
            'date_of_birth', 'place_of_birth', 'nationality', 'state_of_origin', 'lga',
            'religion', 'marital_status', 'home_address', 'phone_number', 'email', 'passport_photo',
        ]]),
        ('Health and identification', [bio[name] for name in [
            'blood_group', 'genotype', 'allergies', 'medical_conditions', 'nin', 'bvn',
            'passport_number', 'drivers_license',
        ]]),
        ('Emergency contact', [bio[name] for name in [
            'emergency_contact_name', 'emergency_contact_relationship',
            'emergency_contact_phone', 'emergency_contact_address',
        ]]),
        ('Employment', [bio[name] for name in [
            'date_of_employment', 'employment_type', 'department', 'position',
            'previous_employer', 'previous_position', 'years_of_experience',
        ]]),
        ('Highest qualification', list(forms_bundle['qualification'])),
        ('Bank account', list(forms_bundle['bank'])),
        ('Signature', list(forms_bundle['signature'])),
    ]


def _parent_sections(forms_bundle):
    bio = forms_bundle['bio']
    return [
        ('Student details', [bio[name] for name in [
            'date_of_birth', 'place_of_birth', 'nationality', 'state_of_origin', 'lga',
            'religion', 'home_address', 'phone_number', 'email', 'passport_photo',
        ]]),
        ('Previous school', [bio[name] for name in [
            'previous_school_name', 'previous_school_address', 'previous_class',
            'reason_for_leaving', 'transfer_certificate',
        ]]),
        ('Health and emergency information', [bio[name] for name in [
            'blood_group', 'genotype', 'allergies', 'medical_conditions', 'medications',
            'doctor_name', 'doctor_phone', 'hospital_name', 'hospital_address',
        ]]),
        ('Documents and interests', [bio[name] for name in [
            'birth_certificate_number', 'nin', 'hobbies', 'special_talents',
        ]]),
        ('Parent or guardian', list(forms_bundle['guardian'])),
    ]
