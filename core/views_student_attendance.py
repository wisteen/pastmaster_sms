from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import Student, Term
from .models_daily_attendance import DailyAttendanceSession, DailyAttendanceRecord
import json


@login_required
@require_http_methods(["POST"])
def student_check_in_out(request):
    """
    API endpoint for student check-in/check-out
    This creates a notification event that can be picked up by mobile apps
    """
    try:
        data = json.loads(request.body)
        action = data.get('action')  # 'in' or 'out'
        
        # Get student
        try:
            student = Student.objects.get(user=request.user)
        except Student.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Student profile not found'})
        
        # Get or create today's attendance session
        today = timezone.now().date()
        
        # Get active term
        try:
            active_term = Term.objects.get(is_active=True)
        except Term.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'No active term found'})
        
        session, created = DailyAttendanceSession.objects.get_or_create(
            date=today,
            school_class=student.school_class,
            term=active_term,
            defaults={'marked_by': request.user}
        )
        
        # Get or create attendance record
        attendance, created = DailyAttendanceRecord.objects.get_or_create(
            session=session,
            student=student,
            defaults={'morning_status': 'absent', 'afternoon_status': 'absent'}
        )
        
        current_time = timezone.now()
        
        if action == 'in':
            if not attendance.morning_time:
                attendance.morning_time = current_time.time()
                attendance.morning_status = 'present'
                attendance.save()
                
                message = f"✓ Checked in successfully at {current_time.strftime('%I:%M %p')}"
                
                # Create notification record (can be picked up by mobile app)
                create_attendance_notification(student, 'check_in', current_time)
                
                return JsonResponse({
                    'success': True,
                    'message': message,
                    'action': 'check_in',
                    'time': current_time.isoformat()
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': f"Already checked in at {attendance.morning_time.strftime('%I:%M %p')}"
                })
                
        elif action == 'out':
            if attendance.morning_time and not attendance.afternoon_time:
                attendance.afternoon_time = current_time.time()
                attendance.afternoon_status = 'present'
                attendance.save()
                
                message = f"✓ Checked out successfully at {current_time.strftime('%I:%M %p')}"
                
                # Create notification record
                create_attendance_notification(student, 'check_out', current_time)
                
                return JsonResponse({
                    'success': True,
                    'message': message,
                    'action': 'check_out',
                    'time': current_time.isoformat()
                })
            elif not attendance.morning_time:
                return JsonResponse({
                    'success': False,
                    'message': 'Please check in first before checking out'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': f"Already checked out at {attendance.afternoon_time.strftime('%I:%M %p')}"
                })
        else:
            return JsonResponse({'success': False, 'message': 'Invalid action'})
            
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


def create_attendance_notification(student, action, timestamp):
    """
    Create a notification record that can be consumed by mobile apps
    This can be extended to use Firebase Cloud Messaging, OneSignal, etc.
    """
    from .models import User
    
    # Create notification for parents (if parent accounts exist)
    # You can extend this to store in a Notification model
    notification_data = {
        'student_id': student.id,
        'student_name': student.user.get_full_name(),
        'action': action,
        'timestamp': timestamp.isoformat(),
        'message': f"{student.user.get_full_name()} has {action.replace('_', ' ')} at {timestamp.strftime('%I:%M %p')}"
    }
    
    # Store notification (you can create a Notification model for this)
    # For now, this returns the data that can be pushed to mobile apps
    return notification_data
