from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db.models import Q
from datetime import datetime, timedelta
import barcode
from barcode.writer import ImageWriter
import qrcode
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import base64
import json

from .models import Student, Teacher, User, SchoolSettings, StudentFee
from .models_attendance import IDCard, AttendanceSession, AttendanceRecord, Visitor
from .decorators import role_required
from .decorators_features import feature_required

@login_required
@role_required(['super_admin'])
@feature_required('attendance_id_cards')
def generate_id_card(request, card_type, holder_id):
    """Generate ID card for student or teacher"""
    
    if card_type == 'student':
        holder = get_object_or_404(Student, id=holder_id)
        card_number = f"STU-{holder.student_id}"
        barcode_data = f"STUDENT-{holder.student_id}"
    else:
        holder = get_object_or_404(Teacher, id=holder_id)
        card_number = f"TCH-{holder.employee_id}"
        barcode_data = f"TEACHER-{holder.employee_id}"
    
    # Create or update ID card
    id_card, created = IDCard.objects.get_or_create(
        **{card_type: holder},
        defaults={
            'card_number': card_number,
            'barcode_data': barcode_data,
            'card_type': card_type,
            'expiry_date': timezone.now().date() + timedelta(days=365)
        }
    )
    
    # Generate barcode
    barcode_class = barcode.get_barcode_class('code128')
    barcode_instance = barcode_class(barcode_data, writer=ImageWriter())
    
    barcode_buffer = BytesIO()
    barcode_instance.write(barcode_buffer)
    
    # Generate QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(barcode_data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    qr_buffer = BytesIO()
    qr_img.save(qr_buffer, format='PNG')
    qr_buffer.seek(0)
    
    # Get school settings
    school = SchoolSettings.objects.first()
    
    context = {
        'id_card': id_card,
        'holder': holder,
        'school': school,
        'barcode_base64': base64.b64encode(barcode_buffer.getvalue()).decode(),
        'qrcode_base64': base64.b64encode(qr_buffer.getvalue()).decode(),
    }
    
    return render(request, 'attendance/id_card.html', context)

@login_required
@role_required(['super_admin'])
@feature_required('attendance_id_cards')
def bulk_generate_id_cards(request):
    """Bulk generate ID cards for students or teachers"""
    
    if request.method == 'POST':
        card_type = request.POST.get('card_type')
        selected_ids = request.POST.getlist('selected_ids')
        
        generated_count = 0
        
        for holder_id in selected_ids:
            if card_type == 'student':
                holder = Student.objects.filter(id=holder_id).first()
                if holder:
                    card_number = f"STU-{holder.student_id}"
                    barcode_data = f"STUDENT-{holder.student_id}"
            else:
                holder = Teacher.objects.filter(id=holder_id).first()
                if holder:
                    card_number = f"TCH-{holder.employee_id}"
                    barcode_data = f"TEACHER-{holder.employee_id}"
            
            if holder:
                IDCard.objects.get_or_create(
                    **{card_type: holder},
                    defaults={
                        'card_number': card_number,
                        'barcode_data': barcode_data,
                        'card_type': card_type,
                        'expiry_date': timezone.now().date() + timedelta(days=365)
                    }
                )
                generated_count += 1
        
        return JsonResponse({'success': True, 'count': generated_count})
    
    students = Student.objects.all()
    teachers = Teacher.objects.all()
    
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
    
    session, created = AttendanceSession.objects.get_or_create(
        date=today,
        session_type=session_type,
        defaults={'created_by': request.user}
    )
    
    # Get today's attendance records
    today_records = AttendanceRecord.objects.filter(
        session=session
    ).select_related('student__user', 'teacher__user', 'id_card').order_by('-check_in_time')[:10]
    
    context = {
        'session': session,
        'recent_records': today_records,
    }
    
    return render(request, 'attendance/mark_attendance.html', context)

@login_required
def scan_barcode(request):
    """API endpoint to process scanned barcode"""
    
    if request.method == 'POST':
        data = json.loads(request.body)
        barcode_data = data.get('barcode')
        
        try:
            # Find ID card
            id_card = IDCard.objects.get(barcode_data=barcode_data, is_active=True)
            
            # Check expiry
            if id_card.expiry_date < timezone.now().date():
                return JsonResponse({
                    'success': False,
                    'error': 'ID card has expired'
                })
            
            # Get current session
            today = timezone.now().date()
            current_hour = timezone.now().hour
            session_type = 'morning' if current_hour < 12 else 'afternoon'
            
            session, _ = AttendanceSession.objects.get_or_create(
                date=today,
                session_type=session_type,
                defaults={'created_by': request.user}
            )
            
            # Check if already marked
            existing = AttendanceRecord.objects.filter(
                session=session,
                id_card=id_card
            ).first()
            
            if existing:
                # If already checked in, mark checkout
                if not existing.check_out_time:
                    existing.check_out_time = timezone.now()
                    existing.save()
                    
                    holder = id_card.get_holder()
                    return JsonResponse({
                        'success': True,
                        'data': {
                            'name': holder.user.get_full_name(),
                            'id': id_card.get_holder_id(),
                            'type': id_card.card_type,
                            'photo': id_card.get_photo(),
                            'has_outstanding_fees': existing.has_outstanding_fees() if id_card.student else False,
                            'fee_balance': float(existing.get_fee_balance()) if id_card.student else 0,
                            'check_in_time': existing.check_in_time.strftime('%H:%M:%S'),
                            'check_out_time': existing.check_out_time.strftime('%H:%M:%S'),
                            'action': 'checkout'
                        }
                    })
                else:
                    return JsonResponse({
                        'success': False,
                        'error': 'Already checked out for this session'
                    })
            
            # Create attendance record
            record = AttendanceRecord.objects.create(
                session=session,
                id_card=id_card,
                student=id_card.student,
                teacher=id_card.teacher,
                status='present',
                marked_by=request.user
            )
            
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
                    'type': id_card.card_type,
                    'photo': photo_url,
                    'has_outstanding_fees': has_fees,
                    'fee_balance': float(fee_balance),
                    'check_in_time': record.check_in_time.strftime('%H:%M:%S'),
                    'action': 'checkin'
                }
            })
            
        except IDCard.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Invalid ID card'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})

@login_required
@role_required(['super_admin', 'class_teacher', 'subject_teacher', 'accountant', 'security'])
@feature_required('attendance_reports')
def attendance_report(request):
    """View attendance reports"""
    
    date_from = request.GET.get('date_from', timezone.now().date() - timedelta(days=7))
    date_to = request.GET.get('date_to', timezone.now().date())
    
    sessions = AttendanceSession.objects.filter(
        date__range=[date_from, date_to]
    ).prefetch_related('records')
    
    context = {
        'sessions': sessions,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'attendance/report.html', context)

@login_required
@role_required(['super_admin', 'class_teacher', 'subject_teacher', 'accountant', 'security'])
def student_attendance_detail(request, student_id):
    """View individual student attendance details"""
    
    student = get_object_or_404(Student, id=student_id)
    
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
@role_required(['super_admin'])
@feature_required('attendance_id_cards')
def id_card_list(request):
    """List all ID cards"""
    
    card_type = request.GET.get('type', 'all')
    
    if card_type == 'student':
        cards = IDCard.objects.filter(card_type='student').select_related('student__user')
    elif card_type == 'teacher':
        cards = IDCard.objects.filter(card_type='teacher').select_related('teacher__user')
    else:
        cards = IDCard.objects.all().select_related('student__user', 'teacher__user')
    
    context = {
        'cards': cards,
        'card_type': card_type,
    }
    
    return render(request, 'attendance/id_card_list.html', context)

@login_required
@role_required(['super_admin'])
def download_id_card(request, card_id):
    """Download ID card as PDF"""
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    
    id_card = get_object_or_404(IDCard, id=card_id)
    holder = id_card.get_holder()
    school = SchoolSettings.objects.first()
    
    # Generate barcode
    barcode_class = barcode.get_barcode_class('code128')
    barcode_instance = barcode_class(id_card.barcode_data, writer=ImageWriter())
    
    buffer = BytesIO()
    barcode_instance.write(buffer)
    buffer.seek(0)
    
    # Create PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="id_card_{id_card.card_number}.pdf"'
    
    p = canvas.Canvas(response, pagesize=letter)
    
    # Draw ID card
    p.setFont("Helvetica-Bold", 16)
    p.drawString(100, 750, school.school_name if school else "School Name")
    
    p.setFont("Helvetica", 12)
    p.drawString(100, 720, f"Name: {id_card.get_holder_name()}")
    p.drawString(100, 700, f"ID: {id_card.get_holder_id()}")
    p.drawString(100, 680, f"Type: {id_card.get_card_type_display()}")
    p.drawString(100, 660, f"Valid Until: {id_card.expiry_date}")
    
    # Add barcode
    p.drawImage(ImageReader(buffer), 100, 500, width=200, height=100)
    
    p.showPage()
    p.save()
    
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
