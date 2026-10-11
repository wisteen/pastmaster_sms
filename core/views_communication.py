from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .access_control import user_has_portal_access
from .forms_communication import SchoolMessageComposeForm
from .models import SchoolClass, SchoolMessage
from .services_portal_delivery import TenantPortalDeliveryService


def _active_school_or_redirect(request):
    school = getattr(request, 'school', None)
    if not school:
        messages.error(request, 'Select a school first.')
    return school


def _can_use_school_messages(user, school):
    return user_has_portal_access(user, school)


def _email_message_recipients(request, school, message, recipients):
    summary = TenantPortalDeliveryService(
        school,
        sender=request.user,
        request=request,
    ).send_school_message_notification(message, recipients)
    if summary.failed:
        messages.warning(
            request,
            'The portal message was sent, but one or more email notifications could not be delivered.',
        )
    elif summary.skipped:
        messages.warning(
            request,
            'The portal message was sent, but one or more recipients do not have an email address.',
        )
    return summary


@login_required
def message_center(request):
    school = _active_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')
    if not _can_use_school_messages(request.user, school):
        messages.error(request, 'You do not have access to this school communication center.')
        return redirect('core:dashboard')

    form = SchoolMessageComposeForm(school=school, sender=request.user)
    if request.method == 'POST':
        form = SchoolMessageComposeForm(request.POST, school=school, sender=request.user)
        if form.is_valid():
            recipients = list(form.resolved_recipients())
            if not recipients:
                form.add_error('recipient_users', 'No active users matched this audience.')
            else:
                message = form.save(commit=False)
                message.school = school
                message.sender = request.user
                message.save()
                message.recipients.set(recipients)
                _email_message_recipients(request, school, message, recipients)
                messages.success(request, f'Message sent to {len(recipients)} user(s).')
                return redirect('core:message_center')

    inbox = SchoolMessage.all_objects.filter(
        school=school,
        recipients=request.user,
    ).select_related('sender').order_by('-created_at')
    sent = SchoolMessage.all_objects.filter(
        school=school,
        sender=request.user,
    ).prefetch_related('recipients').order_by('-created_at')

    search = request.GET.get('search', '').strip()
    if search:
        inbox = inbox.filter(
            Q(subject__icontains=search) |
            Q(body__icontains=search) |
            Q(sender__first_name__icontains=search) |
            Q(sender__last_name__icontains=search) |
            Q(sender__username__icontains=search)
        )
        sent = sent.filter(
            Q(subject__icontains=search) | Q(body__icontains=search) |
            Q(recipients__first_name__icontains=search) |
            Q(recipients__last_name__icontains=search) |
            Q(recipients__username__icontains=search)
        )

    class_id = request.GET.get('class_id', '').strip()
    if class_id:
        inbox = inbox.filter(
            Q(sender__student__school_class_id=class_id) |
            Q(recipients__student__school_class_id=class_id)
        )
        sent = sent.filter(recipients__student__school_class_id=class_id)

    inbox = inbox.distinct()
    sent = sent.distinct()[:15]

    paginator = Paginator(inbox, 15)
    page_obj = paginator.get_page(request.GET.get('page'))
    unread_count = SchoolMessage.all_objects.filter(
        school=school,
        recipients=request.user,
    ).exclude(read_by=request.user).count()

    return render(request, 'communication/message_center.html', {
        'school': school,
        'form': form,
        'page_obj': page_obj,
        'sent_messages': sent,
        'unread_count': unread_count,
        'search': search,
        'class_id': class_id,
        'classes': SchoolClass.all_objects.filter(school=school).order_by('name', 'stream'),
    })


@login_required
def message_detail(request, message_id):
    school = _active_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')
    if not _can_use_school_messages(request.user, school):
        messages.error(request, 'You do not have access to this school communication center.')
        return redirect('core:dashboard')

    message = get_object_or_404(
        SchoolMessage.all_objects.filter(school=school).select_related('sender', 'parent'),
        Q(id=message_id) & (Q(recipients=request.user) | Q(sender=request.user)),
    )
    if message.sender_id != request.user.id:
        message.read_by.add(request.user)

    if request.method == 'POST':
        body = (request.POST.get('body') or '').strip()
        if not body:
            messages.error(request, 'Enter a reply before sending.')
        else:
            recipients = [message.sender] if message.sender_id != request.user.id else list(message.recipients.exclude(pk=request.user.pk))
            if not recipients:
                messages.error(request, 'There is no recipient available for this reply.')
            else:
                reply = SchoolMessage.all_objects.create(
                    school=school,
                    sender=request.user,
                    parent=message,
                    audience='selected',
                    subject=f'Re: {message.subject}'[:200],
                    body=body,
                )
                reply.recipients.set(recipients)
                _email_message_recipients(request, school, reply, recipients)
                messages.success(request, 'Reply sent.')
                return redirect('core:message_detail', message_id=reply.id)

    replies = SchoolMessage.all_objects.filter(
        school=school,
        parent=message,
    ).filter(
        Q(recipients=request.user) | Q(sender=request.user)
    ).select_related('sender').order_by('created_at')

    return render(request, 'communication/message_detail.html', {
        'school': school,
        'message': message,
        'replies': replies,
    })
