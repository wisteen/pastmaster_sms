from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db.models import Q
from django.core.exceptions import ObjectDoesNotExist
from datetime import datetime, timedelta
import barcode
from barcode.writer import ImageWriter
import qrcode
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import base64
import json
import os
import re

from .models import Student, Teacher, User, SchoolSettings, StudentFee
from .models_attendance import IDCard, AttendanceSession, AttendanceRecord, Visitor
from .decorators import role_required
from .decorators_features import feature_required
from .services_attendance_clock import AttendanceClockError, clock_attendance
from .services_id_cards import resolve_id_card, tenant_card_code
from .staffing import active_staff, active_students

STAFF_CARD_ROLES = [
    'super_admin', 'administrator', 'subject_teacher', 'class_teacher', 'security',
    'cleaner', 'clerk', 'driver', 'nurse', 'maintenance', 'staff', 'librarian',
    'accountant', 'bursar',
]


def _can_manage_or_own_staff_card(request, id_card):
    if request.user.has_any_role(['super_admin', 'administrator']):
        return True
    return bool(id_card.teacher_id and id_card.teacher.user_id == request.user.id)


def _request_school(request):
    return getattr(request, 'school', None)


def _tenant_code(school):
    return tenant_card_code(school)


def _holder_identity(card_type, holder, school=None):
    if card_type == 'student':
        prefix = 'STU'
        barcode_prefix = 'STUDENT'
        holder_code = holder.student_id
    else:
        prefix = 'STF'
        barcode_prefix = 'STAFF'
        holder_code = holder.employee_id

    tenant_code = _tenant_code(school or getattr(holder, 'school', None))
    if tenant_code:
        return f"{tenant_code}-{prefix}-{holder_code}", f"{tenant_code}:{barcode_prefix}:{holder_code}"
    return f"{prefix}-{holder_code}", f"{barcode_prefix}-{holder_code}"


def _holder_queryset(request, card_type):
    school = _request_school(request)
    if card_type == 'student':
        return active_students(school).select_related('user', 'school_class', 'school')
    elif card_type in {'teacher', 'staff'}:
        return active_staff(school).select_related('user', 'school')
    else:
        return None
    return queryset


def _id_card_queryset(request):
    queryset = IDCard.all_objects.select_related(
        'student__user',
        'student__school',
        'teacher__user',
        'teacher__school',
    )
    school = _request_school(request)
    if school:
        queryset = queryset.filter(
            Q(student__school=school) | Q(teacher__school=school)
        ).distinct()
    student_ids = active_students(school).values_list('pk', flat=True)
    staff_ids = active_staff(school).values_list('pk', flat=True)
    return queryset.filter(is_active=True).filter(
        Q(card_type='student', student_id__in=student_ids) |
        Q(card_type__in=['teacher', 'staff'], teacher_id__in=staff_ids)
    )


def _attendance_session_queryset(request):
    school = _request_school(request)
    queryset = AttendanceSession.all_objects if school else AttendanceSession.objects
    if school:
        return queryset.filter(school=school)
    return queryset.all()


def _get_or_create_attendance_session(request, date, session_type):
    school = _request_school(request)
    lookup = {'date': date, 'session_type': session_type}
    if school:
        lookup['school'] = school
    return AttendanceSession.all_objects.get_or_create(
        **lookup,
        defaults={'created_by': request.user}
    )


def _school_settings(request):
    return SchoolSettings.get_for_school(_request_school(request))


def _safe_hex_color(value, fallback):
    value = (value or '').strip()
    if re.fullmatch(r'#[0-9a-fA-F]{6}', value):
        return value
    return fallback


def _card_theme(school_settings):
    return {
        'primary': _safe_hex_color(getattr(school_settings, 'primary_color', ''), '#1d4ed8'),
        'secondary': _safe_hex_color(getattr(school_settings, 'secondary_color', ''), '#0f172a'),
        'accent': _safe_hex_color(getattr(school_settings, 'accent_color', ''), '#f97316'),
    }


def _sync_id_card_identity(id_card, card_number, barcode_data):
    updates = {}
    if id_card.card_number != card_number:
        collision = IDCard.all_objects.exclude(pk=id_card.pk).filter(card_number=card_number).exists()
        if not collision:
            updates['card_number'] = card_number
    if id_card.barcode_data != barcode_data:
        collision = IDCard.all_objects.exclude(pk=id_card.pk).filter(barcode_data=barcode_data).exists()
        if not collision:
            updates['barcode_data'] = barcode_data

    if updates:
        for field, value in updates.items():
            setattr(id_card, field, value)
        id_card.save(update_fields=list(updates))


def _get_or_create_id_card(card_type, holder, request):
    normalized_type = 'student' if card_type == 'student' else 'staff'
    card_number, barcode_data = _holder_identity(normalized_type, holder, _request_school(request))
    lookup = {'student': holder} if normalized_type == 'student' else {'teacher': holder}
    id_card, created = IDCard.all_objects.get_or_create(
        **lookup,
        defaults={
            'card_number': card_number,
            'barcode_data': barcode_data,
            'card_type': normalized_type,
            'expiry_date': timezone.now().date() + timedelta(days=36500)
        }
    )
    if not created:
        _sync_id_card_identity(id_card, card_number, barcode_data)
        if id_card.card_type != normalized_type:
            id_card.card_type = normalized_type
            id_card.save(update_fields=['card_type'])
    return id_card


def _barcode_base64(barcode_data):
    barcode_class = barcode.get_barcode_class('code128')
    barcode_instance = barcode_class(barcode_data, writer=ImageWriter())
    barcode_buffer = BytesIO()
    barcode_instance.write(barcode_buffer)
    return base64.b64encode(barcode_buffer.getvalue()).decode()


def _qrcode_base64(barcode_data):
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(barcode_data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    qr_buffer = BytesIO()
    qr_img.save(qr_buffer, format='PNG')
    qr_buffer.seek(0)
    return base64.b64encode(qr_buffer.getvalue()).decode()


def _card_item(id_card):
    return {
        'id_card': id_card,
        'holder': id_card.get_holder(),
        'barcode_base64': _barcode_base64(id_card.barcode_data),
        'qrcode_base64': _qrcode_base64(id_card.barcode_data),
    }


@login_required
@role_required(STAFF_CARD_ROLES)
@feature_required('attendance_id_cards')
def generate_id_card(request, card_type, holder_id):
    """Generate ID card for student or teacher"""
    holders = _holder_queryset(request, card_type)
    if holders is None:
        return JsonResponse({'success': False, 'error': 'Invalid card type'}, status=400)

    holder = get_object_or_404(holders, id=holder_id)
    is_manager = request.user.has_any_role(['super_admin', 'administrator'])
    if card_type == 'student' and not is_manager:
        return HttpResponse('You do not have permission to generate learner ID cards.', status=403)
    if card_type != 'student' and not is_manager and holder.user_id != request.user.id:
        return HttpResponse('You may only view your own staff ID card.', status=403)
    id_card = _get_or_create_id_card(card_type, holder, request)
    school = _school_settings(request)
    item = _card_item(id_card)
    
    context = {
        'id_card': id_card,
        'holder': holder,
        'school': school,
        'card_theme': _card_theme(school),
        'barcode_base64': item['barcode_base64'],
        'qrcode_base64': item['qrcode_base64'],
        'photo_url': id_card.get_photo(),
    }
    
    return render(request, 'attendance/id_card.html', context)

@login_required
@role_required(['super_admin', 'administrator'])
@feature_required('attendance_id_cards')
def bulk_generate_id_cards(request):
    """Bulk generate ID cards for students or teachers"""
    
    if request.method == 'POST':
        card_type = request.POST.get('card_type')
        selected_ids = request.POST.getlist('selected_ids')
        holders = _holder_queryset(request, card_type)

        if holders is None:
            return JsonResponse({'success': False, 'error': 'Invalid card type'}, status=400)
        
        generated_ids = []
        
        for holder_id in selected_ids:
            holder = holders.filter(id=holder_id).first()
            
            if holder:
                id_card = _get_or_create_id_card(card_type, holder, request)
                generated_ids.append(id_card.id)
        
        pdf_url = ''
        if generated_ids:
            pdf_url = f"{reverse('attendance:download_id_cards_pdf')}?ids={','.join(str(card_id) for card_id in generated_ids)}"
        return JsonResponse({
            'success': True,
            'count': len(generated_ids),
            'card_ids': generated_ids,
            'pdf_url': pdf_url,
            'print_url': pdf_url,
        })
    
    students = _holder_queryset(request, 'student')
    teachers = _holder_queryset(request, 'teacher')
    
    context = {
        'students': students,
        'teachers': teachers,
    }
    
    return render(request, 'attendance/bulk_generate_cards.html', context)

@login_required
@role_required(['super_admin', 'class_teacher', 'subject_teacher', 'accountant', 'security'])
@feature_required('attendance_marking')
def mark_attendance_view(request):
    """View for marking attendance with camera - Security role access"""
    
    # Get or create today's session
    today = timezone.now().date()
    current_hour = timezone.now().hour
    session_type = 'morning' if current_hour < 12 else 'afternoon'
    
    session, created = _get_or_create_attendance_session(request, today, session_type)
    
    # Show the whole gate-attendance day, not only one time bucket.
    today_records = AttendanceRecord.objects.filter(
        session__date=today
    ).filter(
        Q(student_id__in=active_students(_request_school(request)).values_list('pk', flat=True)) |
        Q(teacher_id__in=active_staff(_request_school(request)).values_list('pk', flat=True))
    ).select_related('student__user', 'teacher__user', 'id_card').order_by('-check_in_time')[:10]
    
    context = {
        'session': session,
        'recent_records': today_records,
        'total_marked': AttendanceRecord.objects.filter(
            session__date=today,
        ).filter(
            Q(student_id__in=active_students(_request_school(request)).values_list('pk', flat=True)) |
            Q(teacher_id__in=active_staff(_request_school(request)).values_list('pk', flat=True))
        ).values('id_card_id').distinct().count(),
    }
    
    return render(request, 'attendance/mark_attendance.html', context)

@login_required
def scan_barcode(request):
    """API endpoint to process scanned barcode"""

    if request.method == 'POST':
        try:
            data = json.loads(request.body or b'{}')
        except (TypeError, ValueError, json.JSONDecodeError):
            return JsonResponse({'success': False, 'error': 'Invalid scan data'}, status=400)

        barcode_data = str(data.get('barcode') or '').strip()
        if not barcode_data:
            return JsonResponse({'success': False, 'error': 'No ID card code was received'}, status=400)

        try:
            # Accept the encoded QR/barcode value and the number printed on the card.
            id_card = resolve_id_card(
                barcode_data,
                school=_request_school(request),
                allow_student_number=True,
                allow_teacher_number=True,
            )
            if id_card is None:
                inactive_card = resolve_id_card(
                    barcode_data,
                    school=_request_school(request),
                    allow_student_number=True,
                    allow_teacher_number=True,
                    active_only=False,
                )
                error = 'This ID card is inactive' if inactive_card else 'Invalid ID card for this school'
                return JsonResponse({'success': False, 'error': error}, status=404)
            
            now = timezone.now()
            today = timezone.localdate(now)
            current_hour = timezone.localtime(now).hour
            session_type = 'morning' if current_hour < 12 else 'afternoon'

            existing = AttendanceRecord.objects.filter(
                id_card=id_card
            ).filter(session__date=today).select_related('session').order_by('-check_in_time').first()

            if existing:
                session = existing.session
            else:
                session, _ = _get_or_create_attendance_session(request, today, session_type)

            result = clock_attendance(
                session=session,
                id_card=id_card,
                actor=request.user,
                requested_action='auto',
                event_time=now,
                source='web',
            )
            record = result.record
            
            # Get holder info
            holder = id_card.get_holder()
            holder_name = holder.user.get_full_name()
            holder_id = id_card.get_holder_id()
            photo_url = id_card.get_photo()
            
            # Check for outstanding fees (students only)
            has_fees = False
            fee_balance = 0
            
            if id_card.student:
                has_fees = record.has_outstanding_fees()
                fee_balance = record.get_fee_balance()
            
            return JsonResponse({
                'success': True,
                'data': {
                    'name': holder_name,
                    'id': holder_id,
                    'type': id_card.get_holder_role(),
                    'photo': photo_url,
                    'has_outstanding_fees': has_fees,
                    'fee_balance': float(fee_balance),
                    'check_in_time': record.check_in_time.strftime('%H:%M:%S'),
                    'check_out_time': record.check_out_time.strftime('%H:%M:%S') if record.check_out_time else None,
                    'event_time': timezone.localtime(result.event_time).strftime('%H:%M:%S'),
                    'action': 'checkout' if result.action == 'out' else 'checkin',
                    'is_first_checkin': result.action == 'in' and record.movements.count() == 1,
                    'premises_status': 'off_premises' if result.action == 'out' else 'on_premises',
                }
            })

        except AttendanceClockError as exc:
            return JsonResponse({
                'success': False,
                'error': str(exc),
                'code': exc.code,
                'retry_after_seconds': exc.retry_after_seconds,
            }, status=409)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})

def _daily_attendance_days(records):
    """Collapse gate session rows into one daily row per ID-card holder."""
    days = []
    day_map = {}
    for record in records:
        holder = record.student or record.teacher
        if not holder:
            continue
        day = record.session.date
        bucket = day_map.get(day)
        if bucket is None:
            bucket = {'date': day, 'entries': [], 'entry_map': {}}
            day_map[day] = bucket
            days.append(bucket)

        holder_key = ('student', holder.pk) if record.student else ('staff', holder.pk)
        entry = bucket['entry_map'].get(holder_key)
        if entry is None:
            entry = {
                'name': holder.user.get_full_name() or holder.user.username,
                'holder_id': record.id_card.get_holder_id(),
                'card_type': 'student' if record.student else 'staff',
                'role': record.id_card.get_holder_role(),
                'clock_in_time': record.check_in_time,
                'clock_out_time': record.check_out_time,
                'status': record.status,
                'is_student': record.student is not None,
                'has_outstanding_fees': False,
                'fee_balance': 0,
                'last_movement_action': None,
                'last_movement_time': None,
                'movement_count': 0,
                'movement_events': [],
            }
            if record.student:
                entry['has_outstanding_fees'] = record.has_outstanding_fees()
                entry['fee_balance'] = record.get_fee_balance()
            bucket['entry_map'][holder_key] = entry
            bucket['entries'].append(entry)
        else:
            if record.check_in_time and record.check_in_time < entry['clock_in_time']:
                entry['clock_in_time'] = record.check_in_time
            if record.check_out_time and (
                entry['clock_out_time'] is None or record.check_out_time > entry['clock_out_time']
            ):
                entry['clock_out_time'] = record.check_out_time
            if record.status == 'late':
                entry['status'] = 'late'

        movements = list(record.movements.all())
        if movements:
            entry['movement_count'] += len(movements)
            entry['movement_events'].extend(movements)
            latest = max(movements, key=lambda movement: (movement.event_time, movement.pk))
            if entry['last_movement_time'] is None or latest.event_time > entry['last_movement_time']:
                entry['last_movement_action'] = latest.action
                entry['last_movement_time'] = latest.event_time
        else:
            inferred_action = 'out' if record.check_out_time else 'in'
            inferred_time = record.check_out_time or record.check_in_time
            entry['movement_count'] += 2 if record.check_out_time else 1
            entry['movement_events'].append({'action': 'in', 'event_time': record.check_in_time})
            if record.check_out_time:
                entry['movement_events'].append({'action': 'out', 'event_time': record.check_out_time})
            if entry['last_movement_time'] is None or inferred_time > entry['last_movement_time']:
                entry['last_movement_action'] = inferred_action
                entry['last_movement_time'] = inferred_time

    days.sort(key=lambda item: item['date'], reverse=True)
    for bucket in days:
        bucket['total_present'] = len(bucket['entries'])
        for entry in bucket['entries']:
            entry['is_on_premises'] = entry['last_movement_action'] != 'out'
            if entry['is_on_premises']:
                entry['clock_out_time'] = None
            entry['movement_events'].sort(
                key=lambda movement: movement.event_time if hasattr(movement, 'event_time') else movement['event_time']
            )
        bucket['entries'].sort(key=lambda entry: (not entry['is_student'], entry['name'].lower()))
    return days


@login_required
@role_required(['super_admin', 'class_teacher', 'subject_teacher', 'accountant', 'security'])
@feature_required('attendance_reports')
def attendance_report(request):
    """Daily gate report: first arrival, final departure and movement state."""
    
    date_from = request.GET.get('date_from', timezone.now().date() - timedelta(days=7))
    date_to = request.GET.get('date_to', timezone.now().date())
    
    records = AttendanceRecord.objects.filter(
        session__date__range=[date_from, date_to],
    ).filter(
        Q(student_id__in=active_students(_request_school(request)).values_list('pk', flat=True)) |
        Q(teacher_id__in=active_staff(_request_school(request)).values_list('pk', flat=True))
    ).select_related(
        'session', 'id_card', 'student__user', 'teacher__user',
    ).prefetch_related('movements').order_by('-session__date', '-check_in_time')

    days = _daily_attendance_days(records)
    
    context = {
        'days': days,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'attendance/report.html', context)

@login_required
@role_required(['super_admin', 'class_teacher', 'subject_teacher', 'accountant', 'security'])
def student_attendance_detail(request, student_id):
    """View individual student attendance details"""
    
    student = get_object_or_404(_holder_queryset(request, 'student'), id=student_id)
    
    records = AttendanceRecord.objects.filter(
        student=student
    ).select_related('session').order_by('-session__date')
    
    # Calculate statistics
    total_days = records.count()
    present_days = records.filter(status='present').count()
    late_days = records.filter(status='late').count()
    absent_days = records.filter(status='absent').count()
    
    attendance_percentage = (present_days / total_days * 100) if total_days > 0 else 0
    
    context = {
        'student': student,
        'records': records,
        'total_days': total_days,
        'present_days': present_days,
        'late_days': late_days,
        'absent_days': absent_days,
        'attendance_percentage': round(attendance_percentage, 2),
    }
    
    return render(request, 'attendance/student_detail.html', context)

@login_required
@role_required(['super_admin', 'administrator'])
@feature_required('attendance_id_cards')
def id_card_list(request):
    """List all ID cards"""
    
    card_type = request.GET.get('type', 'all')
    
    if card_type == 'student':
        cards = _id_card_queryset(request).filter(card_type='student')
    elif card_type in {'teacher', 'staff'}:
        cards = _id_card_queryset(request).filter(card_type__in=['teacher', 'staff'])
    else:
        cards = _id_card_queryset(request)
    
    context = {
        'cards': cards,
        'card_type': card_type,
    }
    
    return render(request, 'attendance/id_card_list.html', context)


def _selected_card_ids_from_request(request):
    raw_ids = []
    for value in request.GET.getlist('card_ids') + request.POST.getlist('card_ids'):
        raw_ids.extend(str(value).split(','))
    for value in request.GET.getlist('ids') + request.POST.getlist('ids'):
        raw_ids.extend(str(value).split(','))

    card_ids = []
    seen = set()
    for raw_id in raw_ids:
        raw_id = str(raw_id).strip()
        if raw_id.isdigit():
            card_id = int(raw_id)
            if card_id not in seen:
                seen.add(card_id)
                card_ids.append(card_id)
    return card_ids


def _selected_id_cards(request, only_active=True):
    cards = _id_card_queryset(request)
    if only_active:
        cards = cards.filter(is_active=True)

    card_ids = _selected_card_ids_from_request(request)
    if card_ids:
        cards = cards.filter(id__in=card_ids)

    return cards.order_by('card_type', 'student__student_id', 'teacher__employee_id', 'id'), card_ids


@login_required
@role_required(['super_admin', 'administrator'])
@feature_required('attendance_id_cards')
def print_id_cards(request):
    """Print selected or all ID cards for the active tenant."""
    cards, card_ids = _selected_id_cards(request)

    school = _school_settings(request)
    download_url = reverse('attendance:download_id_cards_pdf')
    if card_ids:
        download_url = f"{download_url}?ids={','.join(str(card_id) for card_id in card_ids)}"
    context = {
        'school': school,
        'card_theme': _card_theme(school),
        'card_items': [_card_item(card) for card in cards],
        'selected_count': len(card_ids),
        'download_url': download_url,
    }
    return render(request, 'attendance/print_id_cards.html', context)


def _field_image_reader(file_field, ImageReader):
    if not file_field:
        return None
    try:
        path = getattr(file_field, 'path', '')
        if path and os.path.exists(path):
            return ImageReader(path)
    except Exception:
        pass
    try:
        file_field.open('rb')
        image_data = BytesIO(file_field.read())
        file_field.close()
        image_data.seek(0)
        return ImageReader(image_data)
    except Exception:
        return None


def _draw_fit_text(pdf, text, x, y, max_width, font_name='Helvetica-Bold', font_size=10, min_size=5, color=None):
    from reportlab.pdfbase.pdfmetrics import stringWidth

    text = str(text or '')
    size = font_size
    while size > min_size and stringWidth(text, font_name, size) > max_width:
        size -= .5
    if color:
        pdf.setFillColor(color)
    pdf.setFont(font_name, size)
    pdf.drawString(x, y, text)


def _draw_wrapped_text(pdf, text, x, y, max_width, font_name='Helvetica', font_size=7, line_height=9, max_lines=3, color=None):
    from reportlab.pdfbase.pdfmetrics import stringWidth

    words = str(text or '').split()
    lines = []
    current = ''
    for word in words:
        candidate = f'{current} {word}'.strip()
        if stringWidth(candidate, font_name, font_size) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
        if len(lines) >= max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)

    if color:
        pdf.setFillColor(color)
    pdf.setFont(font_name, font_size)
    for index, line in enumerate(lines):
        pdf.drawString(x, y - (index * line_height), line)


def _draw_pdf_logo(pdf, school, ImageReader, x, y, size, fallback_color, text_color):
    from reportlab.lib import colors

    pdf.setFillColor(colors.white)
    pdf.roundRect(x, y, size, size, 5, fill=1, stroke=0)
    logo = _field_image_reader(getattr(school, 'school_logo', None), ImageReader)
    if logo:
        pdf.drawImage(logo, x + 4, y + 4, size - 8, size - 8, preserveAspectRatio=True, mask='auto')
        return
    pdf.setFillColor(fallback_color)
    pdf.roundRect(x + 4, y + 4, size - 8, size - 8, 4, fill=1, stroke=0)
    pdf.setFillColor(text_color)
    pdf.setFont('Helvetica-Bold', 5)
    pdf.drawCentredString(x + size / 2, y + size / 2 - 2, 'SCHOOL')


def _draw_pdf_photo(pdf, id_card, holder, ImageReader, x, y, size, accent_color):
    from reportlab.lib import colors

    pdf.setFillColor(colors.white)
    pdf.roundRect(x, y, size, size, 7, fill=1, stroke=0)
    pdf.setStrokeColor(accent_color)
    pdf.setLineWidth(2)
    pdf.roundRect(x, y, size, size, 7, fill=0, stroke=1)
    photo = None
    if id_card.card_type == 'student':
        photo = _field_image_reader(getattr(holder, 'passport_photo', None), ImageReader)
    if photo:
        pdf.drawImage(photo, x + 3, y + 3, size - 6, size - 6, preserveAspectRatio=True, mask='auto')
        return
    pdf.setFillColor(colors.HexColor('#dbeafe'))
    pdf.roundRect(x + 3, y + 3, size - 6, size - 6, 6, fill=1, stroke=0)
    pdf.setFillColor(colors.HexColor('#64748b'))
    pdf.setFont('Helvetica-Bold', 16)
    pdf.drawCentredString(x + size / 2, y + size / 2 - 5, 'ID')


def _barcode_buffer(barcode_data):
    barcode_class = barcode.get_barcode_class('code128')
    barcode_instance = barcode_class(barcode_data, writer=ImageWriter())
    buffer = BytesIO()
    barcode_instance.write(buffer)
    buffer.seek(0)
    return buffer


def _qr_buffer(barcode_data):
    qr = qrcode.QRCode(version=1, box_size=8, border=1)
    qr.add_data(barcode_data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    qr_img.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer


def _draw_pdf_page_background(pdf, page_width, page_height):
    from reportlab.lib import colors

    pdf.setFillColor(colors.HexColor('#f6f1e7'))
    pdf.rect(0, 0, page_width, page_height, fill=1, stroke=0)


def _draw_id_card_pdf(pdf, id_card, school, theme, ImageReader, x, y, card_width, card_height, side='front'):
    from reportlab.lib import colors

    primary = colors.HexColor(theme['primary'])
    secondary = colors.HexColor(theme['secondary'])
    accent = colors.HexColor(theme['accent'])
    holder = id_card.get_holder()
    school_name = getattr(school, 'school_name', '') or 'School Portal'
    school_address = getattr(school, 'school_address', '') or 'Official Identification Card'

    if side == 'front':
        pdf.setFillColor(primary)
        pdf.roundRect(x, y, card_width, card_height, 9, fill=1, stroke=0)
        pdf.setFillColor(secondary)
        pdf.rect(x + card_width * .56, y, card_width * .44, card_height, fill=1, stroke=0)
        pdf.setFillColor(accent)
        pdf.circle(x + card_width * .93, y + card_height * .9, card_width * .18, fill=1, stroke=0)

        _draw_pdf_logo(pdf, school, ImageReader, x + 10, y + card_height - 38, 28, colors.white, primary)
        _draw_fit_text(pdf, school_name.upper(), x + 44, y + card_height - 20, card_width - 60, font_size=8, min_size=4.5, color=colors.white)
        _draw_wrapped_text(pdf, school_address, x + 44, y + card_height - 30, card_width - 60, font_size=5.2, line_height=6, max_lines=2, color=colors.white)

        _draw_pdf_photo(pdf, id_card, holder, ImageReader, x + 14, y + 38, 72, accent)
        _draw_fit_text(
            pdf,
            holder.user.get_full_name().upper() or holder.user.username.upper(),
            x + 95,
            y + 93,
            card_width - 110,
            font_size=10,
            min_size=5,
            color=colors.white,
        )
        pdf.setFillColor(accent)
        pdf.roundRect(x + 95, y + 78, 58, 12, 6, fill=1, stroke=0)
        pdf.setFillColor(colors.white)
        pdf.setFont('Helvetica-Bold', 6)
        pdf.drawCentredString(x + 124, y + 82, id_card.get_holder_role().upper())

        detail_x = x + 95
        detail_y = y + 58
        detail_width = card_width - 110
        details = [
            ('ID No.', id_card.get_holder_id()),
        ]
        if id_card.card_type != 'student':
            details.append(('Role', 'Staff'))
        for label, value in details:
            pdf.setFillColor(colors.white)
            pdf.roundRect(detail_x, detail_y, detail_width, 13, 3, fill=1, stroke=0)
            pdf.setFillColor(colors.HexColor('#64748b'))
            pdf.setFont('Helvetica-Bold', 5.5)
            pdf.drawString(detail_x + 5, detail_y + 4, label)
            _draw_fit_text(pdf, value, detail_x + 42, detail_y + 4, detail_width - 47, font_name='Helvetica-Bold', font_size=6, min_size=4.2, color=colors.HexColor('#0f172a'))
            detail_y -= 16
        pdf.setStrokeColor(colors.HexColor('#c7bfae'))
        pdf.setLineWidth(.7)
        pdf.roundRect(x, y, card_width, card_height, 9, fill=0, stroke=1)
        return

    pdf.setFillColor(colors.white)
    pdf.roundRect(x, y, card_width, card_height, 9, fill=1, stroke=0)
    pdf.setFillColor(primary)
    pdf.roundRect(x, y + card_height - 50, card_width, 50, 9, fill=1, stroke=0)
    pdf.setFillColor(accent)
    pdf.rect(x, y + card_height - 64, card_width, 18, fill=1, stroke=0)
    _draw_wrapped_text(
        pdf,
        f'This card remains the property of {school_name}. If found, please return it to the school office.',
        x + 12,
        y + card_height - 18,
        card_width - 24,
        font_name='Helvetica-Bold',
        font_size=6,
        line_height=7,
        max_lines=3,
        color=colors.white,
    )

    qr_buffer = _qr_buffer(id_card.barcode_data)
    pdf.drawImage(ImageReader(qr_buffer), x + card_width - 72, y + 46, 54, 54, preserveAspectRatio=True, mask='auto')

    contact_y = y + 92
    info = [
        ('Issued', id_card.issue_date.strftime('%d %b %Y')),
    ]
    if getattr(school, 'school_motto', ''):
        info.append(('Motto', school.school_motto))
    for label, value in info[:4]:
        pdf.setFillColor(colors.HexColor('#0f172a'))
        pdf.setFont('Helvetica-Bold', 5.8)
        pdf.drawString(x + 12, contact_y, f'{label}:')
        _draw_fit_text(pdf, value, x + 42, contact_y, card_width - 120, font_name='Helvetica', font_size=5.8, min_size=4, color=colors.HexColor('#334155'))
        contact_y -= 10

    barcode_buffer = _barcode_buffer(id_card.barcode_data)
    pdf.setFillColor(colors.HexColor('#0f172a'))
    pdf.setFont('Helvetica-Bold', 6)
    pdf.drawCentredString(x + card_width / 2, y + 27, id_card.card_number)
    pdf.drawImage(ImageReader(barcode_buffer), x + 18, y + 7, card_width - 36, 18, preserveAspectRatio=True, mask='auto')
    pdf.setStrokeColor(colors.HexColor('#c7bfae'))
    pdf.setLineWidth(.7)
    pdf.roundRect(x, y, card_width, card_height, 9, fill=0, stroke=1)


def _hex_to_rgb(hex_color, fallback=(29, 78, 216)):
    hex_color = _safe_hex_color(hex_color, '#%02x%02x%02x' % fallback).lstrip('#')
    return tuple(int(hex_color[index:index + 2], 16) for index in (0, 2, 4))


def _pil_font(size, bold=False):
    font_names = ['arialbd.ttf', 'DejaVuSans-Bold.ttf'] if bold else ['arial.ttf', 'DejaVuSans.ttf']
    for font_name in font_names:
        try:
            return ImageFont.truetype(font_name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _draw_pil_fit_text(draw, text, xy, max_width, font_size, fill, bold=False, min_size=12):
    text = str(text or '')
    size = font_size
    while size > min_size:
        font = _pil_font(size, bold=bold)
        bbox = draw.textbbox((0, 0), text, font=font)
        if bbox[2] - bbox[0] <= max_width:
            draw.text(xy, text, fill=fill, font=font)
            return
        size -= 1
    draw.text(xy, text, fill=fill, font=_pil_font(min_size, bold=bold))


def _wrap_pil_lines(draw, text, font, max_width, max_lines=3):
    words = str(text or '').split()
    lines = []
    current = ''
    for word in words:
        candidate = f'{current} {word}'.strip()
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
        if len(lines) >= max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    return lines


def _paste_fit(base, image, box):
    x, y, width, height = box
    image = image.convert('RGBA')
    image.thumbnail((width, height), Image.LANCZOS)
    offset_x = x + (width - image.width) // 2
    offset_y = y + (height - image.height) // 2
    base.alpha_composite(image, (offset_x, offset_y))


def _field_pil_image(file_field):
    if not file_field:
        return None
    try:
        path = getattr(file_field, 'path', '')
        if path and os.path.exists(path):
            return Image.open(path).convert('RGBA')
    except Exception:
        pass
    try:
        file_field.open('rb')
        image = Image.open(BytesIO(file_field.read())).convert('RGBA')
        file_field.close()
        return image
    except Exception:
        return None


def _rounded_rectangle(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _generate_card_png(id_card, school, theme, side='front'):
    primary = _hex_to_rgb(theme['primary'])
    secondary = _hex_to_rgb(theme['secondary'])
    accent = _hex_to_rgb(theme['accent'])
    cream = (246, 241, 231)
    ink = (15, 23, 42)
    muted = (71, 85, 105)
    card_x, card_y = 44, 40
    card_width, card_height = 1012, 638
    image = Image.new('RGBA', (1100, 720), cream + (255,))
    draw = ImageDraw.Draw(image)
    holder = id_card.get_holder()
    school_name = getattr(school, 'school_name', '') or 'School Portal'
    school_address = getattr(school, 'school_address', '') or 'Official Identification Card'

    if side == 'front':
        _rounded_rectangle(draw, (card_x, card_y, card_x + card_width, card_y + card_height), 32, primary)
        draw.rectangle((card_x + int(card_width * .56), card_y, card_x + card_width, card_y + card_height), fill=secondary)
        draw.ellipse((card_x + 800, card_y - 90, card_x + 1120, card_y + 230), fill=accent)

        logo_box = (card_x + 36, card_y + 34, 96, 96)
        _rounded_rectangle(draw, (logo_box[0], logo_box[1], logo_box[0] + logo_box[2], logo_box[1] + logo_box[3]), 22, (255, 255, 255))
        logo = _field_pil_image(getattr(school, 'school_logo', None))
        if logo:
            _paste_fit(image, logo, (logo_box[0] + 10, logo_box[1] + 10, logo_box[2] - 20, logo_box[3] - 20))
        else:
            _draw_pil_fit_text(draw, 'SCHOOL', (logo_box[0] + 12, logo_box[1] + 38), 72, 16, primary, bold=True)

        _draw_pil_fit_text(draw, school_name.upper(), (card_x + 150, card_y + 44), 760, 30, (255, 255, 255), bold=True, min_size=16)
        address_font = _pil_font(18, bold=True)
        for index, line in enumerate(_wrap_pil_lines(draw, school_address, address_font, 760, max_lines=2)):
            draw.text((card_x + 150, card_y + 82 + (index * 22)), line, fill=accent, font=address_font)

        photo_box = (card_x + 62, card_y + 226, 230, 230)
        _rounded_rectangle(draw, (photo_box[0], photo_box[1], photo_box[0] + photo_box[2], photo_box[1] + photo_box[3]), 115, (255, 255, 255), outline=accent, width=10)
        photo_field = getattr(holder, 'passport_photo', None) if id_card.card_type == 'student' else None
        if id_card.card_type != 'student':
            try:
                photo_field = holder.bio_data.passport_photo
            except (AttributeError, ObjectDoesNotExist):
                photo_field = None
        photo = _field_pil_image(photo_field)
        if photo:
            _paste_fit(image, photo, (photo_box[0] + 10, photo_box[1] + 10, photo_box[2] - 20, photo_box[3] - 20))
        else:
            _draw_pil_fit_text(draw, 'ID', (photo_box[0] + 86, photo_box[1] + 92), 80, 52, muted, bold=True)

        _draw_pil_fit_text(draw, holder.user.get_full_name().upper() or holder.user.username.upper(), (card_x + 340, card_y + 225), 610, 42, (255, 255, 255), bold=True, min_size=20)
        _rounded_rectangle(draw, (card_x + 340, card_y + 285, card_x + 500, card_y + 326), 20, accent)
        _draw_pil_fit_text(draw, id_card.get_holder_role().upper(), (card_x + 370, card_y + 297), 120, 15, (255, 255, 255), bold=True, min_size=10)

        details = [
            ('ID No.', id_card.get_holder_id()),
        ]
        if id_card.card_type != 'student':
            details.append(('Role', 'Staff'))
        y = card_y + 350
        for label, value in details:
            _rounded_rectangle(draw, (card_x + 340, y, card_x + 930, y + 48), 10, (255, 255, 255))
            draw.text((card_x + 360, y + 14), label, fill=muted, font=_pil_font(16, bold=True))
            _draw_pil_fit_text(draw, value, (card_x + 470, y + 13), 430, 18, ink, bold=True, min_size=12)
            y += 62
    else:
        _rounded_rectangle(draw, (card_x, card_y, card_x + card_width, card_y + card_height), 32, (255, 255, 255))
        _rounded_rectangle(draw, (card_x, card_y, card_x + card_width, card_y + 185), 32, primary)
        draw.rectangle((card_x, card_y + 140, card_x + card_width, card_y + 210), fill=accent)
        instruction = f'This card remains the property of {school_name}. If found, please return it to the school office.'
        instruction_font = _pil_font(22, bold=True)
        for index, line in enumerate(_wrap_pil_lines(draw, instruction, instruction_font, 880, max_lines=3)):
            draw.text((card_x + 44, card_y + 42 + (index * 28)), line, fill=(255, 255, 255), font=instruction_font)

        qr_image = qrcode.make(id_card.barcode_data).convert('RGBA')
        _rounded_rectangle(draw, (card_x + 750, card_y + 245, card_x + 930, card_y + 425), 18, (255, 255, 255), outline=accent, width=8)
        _paste_fit(image, qr_image, (card_x + 765, card_y + 260, 150, 150))

        info = [
            ('Issued', id_card.issue_date.strftime('%d %b %Y')),
        ]
        if getattr(school, 'school_motto', ''):
            info.append(('Motto', school.school_motto))
        y = card_y + 260
        for label, value in info[:4]:
            draw.text((card_x + 46, y), f'{label}:', fill=ink, font=_pil_font(20, bold=True))
            _draw_pil_fit_text(draw, value, (card_x + 150, y), 540, 20, muted, bold=False, min_size=13)
            y += 42

        barcode_image = Image.open(_barcode_buffer(id_card.barcode_data)).convert('RGBA')
        _draw_pil_fit_text(draw, id_card.card_number, (card_x + 330, card_y + 500), 380, 18, ink, bold=True, min_size=12)
        _paste_fit(image, barcode_image, (card_x + 110, card_y + 530, 790, 78))

    card_region = image.crop((card_x, card_y, card_x + card_width, card_y + card_height))
    card_mask = Image.new('L', (card_width, card_height), 0)
    mask_draw = ImageDraw.Draw(card_mask)
    mask_draw.rounded_rectangle((0, 0, card_width - 1, card_height - 1), radius=32, fill=255)
    draw.rectangle((card_x, card_y, card_x + card_width, card_y + card_height), fill=cream + (255,))
    image.paste(card_region, (card_x, card_y), card_mask)

    draw = ImageDraw.Draw(image)
    _rounded_rectangle(draw, (card_x, card_y, card_x + card_width, card_y + card_height), 32, None, outline=(199, 191, 174), width=4)
    output = BytesIO()
    image.convert('RGB').save(output, format='PNG', optimize=True)
    output.seek(0)
    return output


@login_required
@role_required(STAFF_CARD_ROLES)
@feature_required('attendance_id_cards')
def download_id_card_image(request, card_id, side):
    """Download one side of an ID card as a high-resolution PNG."""
    side = str(side or '').lower()
    if side not in {'front', 'back'}:
        return HttpResponse('Invalid card side', status=400)

    id_card = get_object_or_404(_id_card_queryset(request), id=card_id, is_active=True)
    if not _can_manage_or_own_staff_card(request, id_card):
        return HttpResponse('You may only download your own staff ID card.', status=403)
    school = _school_settings(request)
    image_buffer = _generate_card_png(id_card, school, _card_theme(school), side=side)

    response = HttpResponse(image_buffer.getvalue(), content_type='image/png')
    response['Content-Disposition'] = f'attachment; filename="id_card_{id_card.card_number}_{side}.png"'
    return response


@login_required
@role_required(STAFF_CARD_ROLES)
@feature_required('attendance_id_cards')
def download_id_card(request, card_id):
    """Download ID card as PDF"""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    
    id_card = get_object_or_404(_id_card_queryset(request), id=card_id)
    if not _can_manage_or_own_staff_card(request, id_card):
        return HttpResponse('You may only download your own staff ID card.', status=403)
    school = _school_settings(request)
    theme = _card_theme(school)
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="id_card_{id_card.card_number}.pdf"'

    pdf = canvas.Canvas(response, pagesize=A4)
    page_width, page_height = A4
    card_width = 85.6 * mm
    card_height = 54 * mm
    x = (page_width - card_width) / 2
    front_y = page_height - (18 * mm) - card_height
    back_y = front_y - (12 * mm) - card_height

    pdf.setTitle(f'ID Card - {id_card.get_holder_name()}')
    _draw_pdf_page_background(pdf, page_width, page_height)
    _draw_id_card_pdf(pdf, id_card, school, theme, ImageReader, x, front_y, card_width, card_height, side='front')
    pdf.setFillColor(colors.HexColor('#5f574a'))
    pdf.setFont('Helvetica-Bold', 8)
    pdf.drawCentredString(page_width / 2, front_y - 12, 'FRONT')
    _draw_id_card_pdf(pdf, id_card, school, theme, ImageReader, x, back_y, card_width, card_height, side='back')
    pdf.setFillColor(colors.HexColor('#5f574a'))
    pdf.setFont('Helvetica-Bold', 8)
    pdf.drawCentredString(page_width / 2, back_y - 12, 'BACK')

    pdf.showPage()
    pdf.save()
    
    return response


@login_required
@role_required(['super_admin', 'administrator'])
@feature_required('attendance_id_cards')
def download_id_cards_pdf(request):
    """Download selected or all tenant ID cards as a print-ready PDF."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader

    cards, card_ids = _selected_id_cards(request)
    cards = list(cards)
    school = _school_settings(request)
    theme = _card_theme(school)

    response = HttpResponse(content_type='application/pdf')
    filename = 'id_cards_selected.pdf' if card_ids else 'id_cards_bulk.pdf'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    pdf = canvas.Canvas(response, pagesize=A4)
    page_width, page_height = A4
    card_width = 85.6 * mm
    card_height = 54 * mm
    gap_x = 8 * mm
    gap_y = 7 * mm
    left = (page_width - ((card_width * 2) + gap_x)) / 2
    top = page_height - (12 * mm) - card_height
    slots = []
    for row in range(4):
        y = top - (row * (card_height + gap_y))
        slots.append((left, y))
        slots.append((left + card_width + gap_x, y))

    pdf.setTitle('ID Cards')
    _draw_pdf_page_background(pdf, page_width, page_height)

    if not cards:
        pdf.setFillColor(colors.HexColor('#5f574a'))
        pdf.setFont('Helvetica-Bold', 12)
        pdf.drawCentredString(page_width / 2, page_height / 2, 'No ID cards found.')
    else:
        slot_index = 0
        for id_card in cards:
            for side in ('front', 'back'):
                if slot_index >= len(slots):
                    pdf.showPage()
                    _draw_pdf_page_background(pdf, page_width, page_height)
                    slot_index = 0
                x, y = slots[slot_index]
                _draw_id_card_pdf(pdf, id_card, school, theme, ImageReader, x, y, card_width, card_height, side=side)
                slot_index += 1

    pdf.showPage()
    pdf.save()

    return response


@login_required
@role_required(['security', 'super_admin'])
@feature_required('attendance_visitors')
def visitor_log(request):
    """Log visitor check-in"""
    if request.method == 'POST':
        visitor = Visitor.objects.create(
            name=request.POST.get('name'),
            phone=request.POST.get('phone'),
            email=request.POST.get('email', ''),
            id_number=request.POST.get('id_number', ''),
            purpose=request.POST.get('purpose'),
            person_to_see=request.POST.get('person_to_see'),
            department=request.POST.get('department', ''),
            notes=request.POST.get('notes', ''),
            logged_by=request.user
        )
        messages.success(request, f'Visitor {visitor.name} checked in successfully!')
        return redirect('attendance:visitor_log')
    
    today = timezone.now().date()
    visitors_today = Visitor.objects.filter(check_in_time__date=today)
    all_visitors = Visitor.objects.all()[:50]
    
    context = {
        'visitors_today': visitors_today,
        'all_visitors': all_visitors,
        'active_visitors': visitors_today.filter(check_out_time__isnull=True),
    }
    return render(request, 'attendance/visitor_log.html', context)

@login_required
@role_required(['security', 'super_admin'])
@feature_required('attendance_visitors')
def visitor_checkout(request, visitor_id):
    """Check out a visitor"""
    visitor = get_object_or_404(Visitor, id=visitor_id)
    visitor.check_out_time = timezone.now()
    visitor.save()
    messages.success(request, f'Visitor {visitor.name} checked out successfully!')
    return redirect('attendance:visitor_log')

@login_required
@role_required(['security', 'super_admin'])
@feature_required('attendance_visitors')
def visitor_report(request):
    """Visitor attendance report"""
    date_from = request.GET.get('date_from', timezone.now().date())
    date_to = request.GET.get('date_to', timezone.now().date())
    
    visitors = Visitor.objects.filter(
        check_in_time__date__gte=date_from,
        check_in_time__date__lte=date_to
    )
    
    context = {
        'visitors': visitors,
        'date_from': date_from,
        'date_to': date_to,
        'total_visitors': visitors.count(),
        'checked_out': visitors.filter(check_out_time__isnull=False).count(),
    }
    return render(request, 'attendance/visitor_report.html', context)
