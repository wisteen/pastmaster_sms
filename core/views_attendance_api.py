from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from .models_attendance import AttendanceSession, AttendanceRecord
from .models import Student
from .models_parent_device import ParentDevice
import json

@csrf_exempt
def mark_attendance(request):
    if request.method == 'POST':
        try:
            student_id = request.POST.get('student_id')
            session_id = request.POST.get('session_id')
            image = request.FILES.get('image')
            
            student = Student.objects.get(student_id=student_id)
            session = AttendanceSession.objects.get(id=session_id)
            
            # Check if already marked
            existing = AttendanceRecord.objects.filter(
                session=session,
                student=student
            ).first()
            
            if existing:
                return JsonResponse({
                    'success': False,
                    'message': 'Attendance already marked for this student'
                })
            
            # Create attendance record
            record = AttendanceRecord.objects.create(
                session=session,
                student=student,
                check_in_time=timezone.now(),
                status='present'
            )
            
            if image:
                record.photo = image
                record.save()
            
            # Send notification to parent
            send_parent_notification(student, 'check_in', record.check_in_time)
            
            return JsonResponse({
                'success': True,
                'message': f'Attendance marked for {student.user.get_full_name()}',
                'record_id': record.id
            })
            
        except Student.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Student not found'})
        except AttendanceSession.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Session not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

def get_active_session(request):
    today = timezone.now().date()
    session = AttendanceSession.objects.filter(date=today).first()
    
    if session:
        return JsonResponse({
            'success': True,
            'session_id': session.id,
            'date': str(session.date),
            'session_type': session.session_type
        })
    
    return JsonResponse({'success': False, 'message': 'No active session today'})

def get_today_attendance(request, session_id):
    try:
        session = AttendanceSession.objects.get(id=session_id)
        records = AttendanceRecord.objects.filter(session=session).select_related('student__user')
        
        data = [{
            'id': r.id,
            'student_name': r.student.user.get_full_name(),
            'student_id': r.student.student_id,
            'check_in_time': r.check_in_time.strftime('%H:%M:%S'),
            'status': r.status
        } for r in records]
        
        return JsonResponse(data, safe=False)
    except:
        return JsonResponse([], safe=False)


def send_parent_notification(student, action, timestamp):
    """
    Send push notification to parent's mobile app
    """
    notification_data = {
        'type': 'attendance',
        'student_id': student.id,
        'student_name': student.user.get_full_name(),
        'student_number': student.student_id,
        'action': action,
        'timestamp': timestamp.isoformat(),
        'time_formatted': timestamp.strftime('%I:%M %p'),
        'message': f"{student.user.get_full_name()} checked {'in' if action == 'check_in' else 'out'} at {timestamp.strftime('%I:%M %p')}"
    }
    
    # Send to all active parent devices
    try:
        from firebase_admin import messaging
        import firebase_admin
        
        if not firebase_admin._apps:
            import os
            cred_path = os.path.join(os.path.dirname(__file__), '..', 'firebase-credentials.json')
            if os.path.exists(cred_path):
                cred = firebase_admin.credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
        
        devices = ParentDevice.objects.filter(student=student, is_active=True)
        
        for device in devices:
            try:
                message = messaging.Message(
                    notification=messaging.Notification(
                        title='🎓 Student Attendance Alert',
                        body=notification_data['message']
                    ),
                    data=notification_data,
                    token=device.device_token
                )
                messaging.send(message)
                device.last_used = timezone.now()
                device.save(update_fields=['last_used'])
            except Exception as e:
                if 'invalid' in str(e).lower() or 'not-found' in str(e).lower():
                    device.is_active = False
                    device.save(update_fields=['is_active'])
    except ImportError:
        pass
    except Exception as e:
        print(f"Notification error: {e}")
    
    return notification_data
