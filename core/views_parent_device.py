from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .models import Student
from .models_parent_device import ParentDevice
import json


@csrf_exempt
@require_http_methods(["POST"])
def register_parent_device(request):
    """
    API endpoint for parents to register their device token
    Mobile app should call this when parent logs in
    """
    try:
        data = json.loads(request.body)
        student_id = data.get('student_id')  # Student ID or student number
        device_token = data.get('device_token')
        device_type = data.get('device_type', 'android')
        parent_name = data.get('parent_name', '')
        parent_phone = data.get('parent_phone', '')
        
        if not student_id or not device_token:
            return JsonResponse({
                'success': False,
                'message': 'student_id and device_token are required'
            })
        
        # Find student by ID or student number
        try:
            student = Student.objects.get(student_id=student_id)
        except Student.DoesNotExist:
            try:
                student = Student.objects.get(id=student_id)
            except Student.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'Student not found'
                })
        
        # Create or update device
        device, created = ParentDevice.objects.update_or_create(
            device_token=device_token,
            defaults={
                'student': student,
                'device_type': device_type,
                'parent_name': parent_name,
                'parent_phone': parent_phone,
                'is_active': True
            }
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Device registered successfully',
            'device_id': device.id,
            'student_name': student.user.get_full_name(),
            'student_class': student.school_class.name if student.school_class else ''
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })


@csrf_exempt
@require_http_methods(["POST"])
def unregister_parent_device(request):
    """
    API endpoint to unregister a device (when parent logs out)
    """
    try:
        data = json.loads(request.body)
        device_token = data.get('device_token')
        
        if not device_token:
            return JsonResponse({
                'success': False,
                'message': 'device_token is required'
            })
        
        ParentDevice.objects.filter(device_token=device_token).update(is_active=False)
        
        return JsonResponse({
            'success': True,
            'message': 'Device unregistered successfully'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })
