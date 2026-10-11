from dataclasses import dataclass, field
import base64
import json
import mimetypes
import re
from urllib import error as url_error
from urllib import request as url_request

from django.conf import settings as django_settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape

from .access_control import user_has_portal_access
from .models import NotificationLog, SchoolMessage, SchoolSettings
from .models_biodata import Guardian


DEFAULT_TERMII_BASE_URL = 'https://api.ng.termii.com'
DELIVERY_CHANNELS = {'email', 'sms', 'whatsapp', 'in_app'}


@dataclass(frozen=True)
class DeliveryContact:
    name: str
    email: str = ''
    phone: str = ''
    user: object = None


@dataclass
class DeliverySummary:
    sent: int = 0
    failed: int = 0
    skipped: int = 0
    errors: list = field(default_factory=list)

    def add(self, sent=0, failed=0, skipped=0, error=''):
        self.sent += sent
        self.failed += failed
        self.skipped += skipped
        if error:
            self.errors.append(error)

    def merge(self, other):
        self.sent += other.sent
        self.failed += other.failed
        self.skipped += other.skipped
        self.errors.extend(other.errors)

    def as_message(self):
        parts = [f'{self.sent} sent', f'{self.failed} failed', f'{self.skipped} skipped']
        if self.errors:
            parts.append('; '.join(self.errors[:3]))
        return ', '.join(parts)


def delivery_channels_from_post(post, default=None):
    default = list(default or ['email'])
    selected = [
        channel for channel in post.getlist('channels')
        if channel in DELIVERY_CHANNELS
    ]
    return selected or default


class TenantPortalDeliveryService:
    def __init__(self, school, sender=None, request=None):
        self.school = school
        self.sender = sender
        self.request = request
        self.school_settings = SchoolSettings.get_for_school(school)
        self.school_name = (
            getattr(self.school_settings, 'school_name', '')
            or getattr(school, 'name', '')
            or 'School Portal'
        )

    def send_login_details(self, user, temporary_password, channels):
        login_url = self._absolute_url(reverse('core:login'))
        subject = f'{self.school_name} portal login details'
        body = (
            f'Hello {self._display_name(user)},\n\n'
            f'Your {self.school_name} portal login details are below.\n\n'
            f'Username: {user.username}\n'
            f'Password: {temporary_password}\n'
            f'Portal: {login_url}\n\n'
            'Keep these details private and change the password after signing in.'
        )
        return self._send_to_contacts(
            self._login_contacts(user),
            subject,
            body,
            channels,
            notification_type='portal_login',
        )

    def send_onboarding_invitation(self, onboarding_record, invitation_url, channels):
        person_label = 'teacher' if onboarding_record.person_type == 'teacher' else 'student'
        recipient_name = onboarding_record.recipient_name or onboarding_record.display_name
        subject = f'Complete {onboarding_record.display_name}\'s {self.school_name} onboarding'
        body = (
            f'Hello {recipient_name},\n\n'
            f'{self.school_name} has created a basic {person_label} profile for '
            f'{onboarding_record.display_name}.\n\n'
            'Use the secure link below to complete the remaining information and submit it for review.\n\n'
            f'Complete onboarding: {invitation_url}\n\n'
            'This private link expires in 7 days. Do not forward it to anyone else.'
        )
        contact = DeliveryContact(
            name=recipient_name,
            email=onboarding_record.recipient_email,
            phone=onboarding_record.recipient_phone,
        )
        return self._send_to_contacts(
            [contact],
            subject,
            body,
            channels,
            notification_type='onboarding_invitation',
        )

    def send_school_message_notification(self, message, recipients=None):
        recipients = recipients if recipients is not None else message.recipients.all()
        recipient_users = {
            user.pk: user
            for user in recipients
            if user.pk and user.pk != message.sender_id
        }
        contacts = [
            DeliveryContact(
                name=self._display_name(user),
                email=user.email,
                phone=getattr(user, 'phone', ''),
                user=user,
            )
            for user in recipient_users.values()
        ]

        sender_name = self._display_name(message.sender)
        is_reply = bool(message.parent_id)
        message_kind = 'reply' if is_reply else 'message'
        message_url = self._absolute_url(reverse('core:message_detail', args=[message.pk]))
        subject = f'New {message_kind} from {sender_name}: {message.subject}'[:200]
        body = (
            'Hello,\n\n'
            f'{sender_name} sent you a new {message_kind} in the {self.school_name} communication portal.\n\n'
            f'Subject: {message.subject}\n'
            f'Open message: {message_url}\n\n'
            'Sign in to read and reply securely. Please do not reply directly to this notification email.'
        )
        return self._send_to_contacts(
            contacts,
            subject,
            body,
            ['email'],
            notification_type='school_message',
        )

    def send_result_token_details(self, result_token, channels):
        student = result_token.student
        portal_url = self._absolute_url(reverse('core:check_result'))
        subject = f'{self.school_name} result token for {self._display_name(student.user)}'
        body = (
            f'Hello,\n\n'
            f'The result token for {self._display_name(student.user)} is below.\n\n'
            f'Student: {self._display_name(student.user)}\n'
            f'Student ID: {student.student_id}\n'
            f'Class: {student.school_class}\n'
            f'Term: {result_token.term.session} - {result_token.term.name}\n'
            f'Result Token: {result_token.token}\n'
            f'Result Portal: {portal_url}\n\n'
            'Open the result portal and enter the token to view the published result.'
        )
        return self._send_to_contacts(
            self._student_contacts(student),
            subject,
            body,
            channels,
            notification_type='result_token',
        )

    def send_password_reset_code(self, user, code, expires_at):
        contact = DeliveryContact(
            name=self._display_name(user),
            email=user.email,
            phone=getattr(user, 'phone', ''),
            user=user,
        )
        if not contact.email:
            return DeliverySummary(skipped=1, errors=['No email address found for this account.'])

        if not self._email_delivery_ready():
            return DeliverySummary(failed=1, errors=['No school SMTP or platform email service is configured.'])

        reset_url = self._absolute_url(reverse('core:password_reset'))
        expiry_label = timezone.localtime(expires_at).strftime('%I:%M %p')
        subject = f'{self.school_name} password reset code'
        body = (
            f'Hello {contact.name},\n\n'
            f'Use this code to reset your {self.school_name} portal password:\n\n'
            f'{code}\n\n'
            f'This code expires at {expiry_label}.\n'
            f'Reset page: {reset_url}\n\n'
            'If you did not request this reset, you can ignore this email.'
        )

        summary = DeliverySummary()
        error = self._deliver_email_with_fallback(
            contact,
            subject,
            body,
            'password_reset',
            self._password_reset_html(contact.name, code, expiry_label, reset_url),
        )
        if not error:
            summary.add(sent=1)
        else:
            summary.add(failed=1, error=f'Email to {contact.email}: {error}')
        return summary

    def _send_to_contacts(self, contacts, subject, body, channels, notification_type):
        summary = DeliverySummary()
        channels = [channel for channel in channels if channel in DELIVERY_CHANNELS]
        if not channels:
            channels = ['email']

        if 'email' in channels:
            summary.merge(self._send_email_contacts(contacts, subject, body, notification_type))
        if 'sms' in channels:
            summary.merge(self._send_termii_contacts(contacts, subject, body, notification_type, 'sms'))
        if 'whatsapp' in channels:
            summary.merge(self._send_termii_contacts(contacts, subject, body, notification_type, 'whatsapp'))
        if 'in_app' in channels:
            summary.merge(self._send_in_app_contacts(contacts, subject, body, notification_type))

        return summary

    def _send_email_contacts(self, contacts, subject, body, notification_type):
        summary = DeliverySummary()
        if not self._email_delivery_ready():
            summary.add(failed=1, error='No school SMTP or platform email service is configured.')
            return summary

        recipients = {}
        for contact in contacts:
            email = (contact.email or '').strip().lower()
            if email:
                recipients[email] = contact
            else:
                summary.add(skipped=1)

        if not recipients:
            if not summary.skipped:
                summary.add(skipped=1)
            summary.errors.append('No email recipient found.')
            return summary

        for email, contact in recipients.items():
            error = self._deliver_email_with_fallback(
                contact,
                subject,
                body,
                notification_type,
                self._html_body(body),
            )
            if not error:
                summary.add(sent=1)
            else:
                summary.add(failed=1, error=f'Email to {email}: {error}')
        return summary

    def _deliver_email_with_fallback(self, contact, subject, body, notification_type, html_body):
        errors = []
        routes = self._email_routes()
        for route_index, (route_name, connection, from_email) in enumerate(routes):
            try:
                message = EmailMultiAlternatives(
                    subject=subject,
                    body=body,
                    from_email=from_email,
                    to=[contact.email],
                    connection=connection,
                )
                message.attach_alternative(html_body, 'text/html')
                message.send()
                self._log(
                    notification_type,
                    'email',
                    contact.email,
                    contact.name,
                    subject,
                    'sent',
                    context={
                        'email_route': route_name,
                        'used_default_fallback': route_name == 'default' and route_index > 0,
                    },
                )
                return ''
            except Exception as exc:
                route_error = str(exc)
                errors.append(f'{route_name}: {route_error}')
                self._log(
                    notification_type,
                    'email',
                    contact.email,
                    contact.name,
                    subject,
                    'failed',
                    route_error,
                    context={
                        'email_route': route_name,
                        'fallback_available': route_index < len(routes) - 1,
                    },
                )
        return '; '.join(errors) or 'No email route is configured.'

    def _send_in_app_contacts(self, contacts, subject, body, notification_type):
        users = {}
        for contact in contacts:
            user = getattr(contact, 'user', None)
            if user and user.pk and user_has_portal_access(user, self.school):
                users[user.pk] = user

        if not users:
            return DeliverySummary(skipped=1, errors=['No in-app recipient found.'])

        message = SchoolMessage.all_objects.create(
            school=self.school,
            sender=self.sender,
            audience='selected',
            subject=subject[:200],
            body=body,
        )
        message.recipients.set(users.values())
        self._log(notification_type, 'in_app', 'in-app@local.invalid', f'{len(users)} portal user(s)', subject, 'sent')
        return DeliverySummary(sent=len(users))

    def _send_termii_contacts(self, contacts, subject, body, notification_type, requested_channel):
        summary = DeliverySummary()
        api_key = (getattr(self.school_settings, 'termii_api_key', '') or '').strip()
        sender_id = (getattr(self.school_settings, 'termii_sender_id', '') or '').strip()
        if not api_key or not sender_id:
            summary.add(failed=1, error='Termii API key and sender ID are required for SMS/WhatsApp.')
            return summary

        recipients = {}
        for contact in contacts:
            phone = self._normalize_phone(contact.phone)
            if phone:
                recipients[phone] = contact

        if not recipients:
            summary.add(skipped=1, error='No phone recipient found.')
            return summary

        channel = 'whatsapp' if requested_channel == 'whatsapp' else (
            getattr(self.school_settings, 'termii_channel', '') or 'dnd'
        )
        text = body[:1500]
        for phone, contact in recipients.items():
            payload = {
                'api_key': api_key,
                'to': phone,
                'from': sender_id,
                'sms': text,
                'type': 'plain',
                'channel': channel,
            }
            try:
                response = self._post_termii(payload)
                if self._termii_response_is_success(response):
                    self._log(
                        notification_type,
                        requested_channel,
                        f'{requested_channel}@local.invalid',
                        contact.name or phone,
                        subject,
                        'sent',
                        context={'phone': phone, 'termii_response': response, 'channel': channel},
                    )
                    summary.add(sent=1)
                else:
                    error = response.get('message') or response.get('error') or 'Termii rejected the message.'
                    self._log(
                        notification_type,
                        requested_channel,
                        f'{requested_channel}@local.invalid',
                        contact.name or phone,
                        subject,
                        'failed',
                        error,
                        context={'phone': phone, 'termii_response': response, 'channel': channel},
                    )
                    summary.add(failed=1, error=f'{requested_channel.upper()} to {phone}: {error}')
            except Exception as exc:
                error = str(exc)
                self._log(
                    notification_type,
                    requested_channel,
                    f'{requested_channel}@local.invalid',
                    contact.name or phone,
                    subject,
                    'failed',
                    error,
                    context={'phone': phone, 'channel': channel},
                )
                summary.add(failed=1, error=f'{requested_channel.upper()} to {phone}: {error}')
        return summary

    def _post_termii(self, payload):
        endpoint = self._termii_base_url().rstrip('/') + '/api/sms/send'
        request = url_request.Request(
            endpoint,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        try:
            with url_request.urlopen(request, timeout=15) as response:
                raw_body = response.read().decode('utf-8')
                if not raw_body:
                    return {'status_code': response.status}
                data = json.loads(raw_body)
                data.setdefault('status_code', response.status)
                return data
        except url_error.HTTPError as exc:
            raw_body = exc.read().decode('utf-8')
            try:
                data = json.loads(raw_body)
            except json.JSONDecodeError:
                data = {'message': raw_body or str(exc)}
            data.setdefault('status_code', exc.code)
            return data

    def _termii_response_is_success(self, response):
        status_code = int(response.get('status_code') or 0)
        return (
            200 <= status_code < 300
            and (
                response.get('code') == 'ok'
                or bool(response.get('message_id'))
                or bool(response.get('message_id_str'))
                or response.get('smsStatus') in ['Message Sent', 'sent']
            )
        )

    def _email_connection(self):
        host = (getattr(self.school_settings, 'email_host', '') or '').strip()
        if not host:
            return None
        return get_connection(
            host=host,
            port=getattr(self.school_settings, 'email_port', 587) or 587,
            username=(getattr(self.school_settings, 'email_host_user', '') or '').strip() or None,
            password=(getattr(self.school_settings, 'email_host_password', '') or '').strip() or None,
            use_tls=bool(getattr(self.school_settings, 'email_use_tls', True)),
            fail_silently=False,
        )

    def _email_routes(self):
        routes = []
        if (getattr(self.school_settings, 'email_host', '') or '').strip():
            routes.append(('school', self._email_connection(), self._school_from_email()))
        if self._default_email_delivery_ready():
            routes.append((
                'default',
                None,
                getattr(django_settings, 'DEFAULT_FROM_EMAIL', 'noreply@school.edu'),
            ))
        return routes

    def _default_email_delivery_ready(self):
        backend = getattr(django_settings, 'EMAIL_BACKEND', '')
        if backend and backend != 'django.core.mail.backends.smtp.EmailBackend':
            return True
        return bool((getattr(django_settings, 'EMAIL_HOST', '') or '').strip())

    def _email_delivery_ready(self):
        return bool(self._email_routes())

    def _school_from_email(self):
        return (
            (getattr(self.school_settings, 'email_from_address', '') or '').strip()
            or getattr(django_settings, 'DEFAULT_FROM_EMAIL', 'noreply@school.edu')
        )

    def _from_email(self):
        return self._school_from_email()

    def _termii_base_url(self):
        return (
            (getattr(self.school_settings, 'termii_base_url', '') or '').strip()
            or DEFAULT_TERMII_BASE_URL
        )

    def _absolute_url(self, path):
        if self.request:
            return self.request.build_absolute_uri(path)
        return path

    def _display_name(self, user):
        return user.get_full_name() or user.username

    def _login_contacts(self, user):
        contacts = [
            DeliveryContact(
                name=self._display_name(user),
                email=user.email,
                phone=getattr(user, 'phone', ''),
                user=user,
            )
        ]
        try:
            student = user.student
        except Exception:
            student = None
        if student:
            contacts.extend(self._guardian_contacts(student))
        return contacts

    def _student_contacts(self, student):
        contacts = [
            DeliveryContact(
                name=self._display_name(student.user),
                email=student.user.email,
                phone=getattr(student.user, 'phone', ''),
                user=student.user,
            )
        ]
        contacts.extend(self._guardian_contacts(student))
        return contacts

    def _guardian_contacts(self, student):
        contacts = []
        guardians = Guardian.objects.filter(student=student).select_related('user')
        for guardian in guardians:
            contacts.append(
                DeliveryContact(
                    name=guardian.get_full_name(),
                    email=guardian.email,
                    phone=guardian.phone_number,
                    user=guardian.user,
                )
            )
            if guardian.user:
                contacts.append(
                    DeliveryContact(
                        name=self._display_name(guardian.user),
                        email=guardian.user.email,
                        phone=getattr(guardian.user, 'phone', ''),
                        user=guardian.user,
                    )
                )
        return contacts

    def _normalize_phone(self, phone):
        digits = re.sub(r'\D+', '', phone or '')
        if not digits:
            return ''
        if digits.startswith('0'):
            return '234' + digits[1:]
        return digits

    def _html_body(self, body):
        escaped = escape(body).replace('\n', '<br>')
        return f'<div style="font-family:Arial,sans-serif;font-size:14px;line-height:1.5">{escaped}</div>'

    def _password_reset_html(self, recipient_name, code, expiry_label, reset_url):
        logo_uri = self._logo_data_uri()
        if logo_uri:
            logo_html = (
                f'<img src="{logo_uri}" alt="{escape(self.school_name)}" '
                'style="display:block;width:72px;height:72px;object-fit:contain;border-radius:12px;margin:0 auto 14px;">'
            )
        else:
            logo_html = (
                '<div style="width:72px;height:72px;border-radius:12px;margin:0 auto 14px;'
                'background:#eef2ff;color:#1d4ed8;display:flex;align-items:center;justify-content:center;'
                'font-weight:800;text-align:center;font-size:13px;padding:6px;">'
                f'{escape(self.school_name[:18])}'
                '</div>'
            )
        return f'''
        <div style="margin:0;padding:24px;background:#f8fafc;font-family:Arial,sans-serif;color:#0f172a;">
          <div style="max-width:520px;margin:0 auto;background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;padding:28px;">
            {logo_html}
            <h1 style="margin:0;text-align:center;font-size:22px;line-height:1.3;color:#0f172a;">{escape(self.school_name)}</h1>
            <p style="margin:18px 0 0;font-size:15px;line-height:1.6;">Hello {escape(recipient_name)},</p>
            <p style="margin:12px 0 0;font-size:15px;line-height:1.6;">Use this code to reset your portal password.</p>
            <div style="margin:22px 0;padding:18px;border-radius:10px;background:#eef2ff;text-align:center;">
              <div style="font-size:34px;font-weight:800;letter-spacing:8px;color:#1d4ed8;">{escape(code)}</div>
            </div>
            <p style="margin:0;font-size:14px;line-height:1.6;color:#475569;">This code expires at {escape(expiry_label)}.</p>
            <p style="margin:18px 0 0;">
              <a href="{escape(reset_url)}" style="display:inline-block;background:#2563eb;color:#ffffff;text-decoration:none;padding:12px 18px;border-radius:8px;font-weight:700;">Open reset page</a>
            </p>
            <p style="margin:22px 0 0;font-size:13px;line-height:1.6;color:#64748b;">If you did not request this reset, ignore this email.</p>
          </div>
          <p style="margin:16px 0 0;text-align:center;font-size:12px;color:#64748b;">Powered by Virtuakids</p>
        </div>
        '''

    def _logo_data_uri(self):
        logo = getattr(self.school_settings, 'school_logo', None)
        if not logo:
            return ''
        try:
            with logo.open('rb') as image_file:
                encoded_logo = base64.b64encode(image_file.read()).decode('ascii')
        except Exception:
            return ''

        content_type = mimetypes.guess_type(getattr(logo, 'name', '') or '')[0] or 'image/png'
        return f'data:{content_type};base64,{encoded_logo}'

    def _log(self, notification_type, channel, recipient_email, recipient_name, subject, status, error='', context=None):
        context_data = {
            'school_id': getattr(self.school, 'id', None),
            'channel': channel,
            'tenant_delivery': True,
        }
        if context:
            context_data.update(context)
        NotificationLog.all_objects.create(
            school=self.school,
            notification_type=notification_type,
            recipient_email=recipient_email,
            recipient_name=recipient_name or recipient_email,
            subject=subject[:200],
            status=status,
            sent_at=timezone.now() if status == 'sent' else None,
            error_message=error,
            context_data=context_data,
        )
