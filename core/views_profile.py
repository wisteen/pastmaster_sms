from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required

@login_required
def user_profile(request):
    user = request.user
    
    if user.has_role('student'):
        return redirect('student_biodata_view', student_id=user.student.id)
    elif user.has_role('super_admin'):
        return redirect('core:school_admin_dashboard')
    elif user.has_any_role(['subject_teacher', 'class_teacher', 'accountant', 'librarian', 'security']):
        try:
            return redirect('staff_biodata_view', teacher_id=user.teacher.id)
        except:
            return redirect('core:dashboard')
    
    return redirect('core:dashboard')

