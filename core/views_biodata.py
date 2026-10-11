from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.db.models import Q
from django.core.exceptions import PermissionDenied
from datetime import datetime
import csv

from .models import Student, Teacher
from .models_biodata import (
    StudentBioData, Guardian, StaffBioData, StaffQualification,
    StaffGuarantor, StaffBankAccount, PaymentSchedule
)
from .forms_biodata import (
    StudentBioDataForm, GuardianForm, StaffBioDataForm,
    StaffQualificationForm, StaffGuarantorForm, StaffBankAccountForm,
    PaymentScheduleGeneratorForm
)
from .staffing import active_staff


@login_required
def student_biodata_view(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    can_edit = request.user.is_superuser or request.user.has_role('super_admin') or request.user.has_any_role(['subject_teacher', 'class_teacher'])
    user_student = getattr(request.user, 'student', None)
    
    # Students can only view their own data. Admin/staff accounts may have a
    # student role grant without having a Student profile attached.
    if request.user.has_role('student') and not can_edit and (not user_student or user_student.id != student_id):
        messages.error(request, 'You can only view your own bio-data')
        return redirect('core:dashboard')
    
    try:
        bio_data = StudentBioData.objects.get(student=student)
    except StudentBioData.DoesNotExist:
        bio_data = None
    
    if can_edit and request.method == 'POST':
        form = StudentBioDataForm(request.POST, request.FILES, instance=bio_data)
        if form.is_valid():
            bio_data = form.save(commit=False)
            bio_data.student = student
            bio_data.save()
            messages.success(request, 'Student bio-data updated successfully!')
            return redirect('student_biodata_view', student_id=student_id)
    else:
        form = StudentBioDataForm(instance=bio_data) if can_edit else None
    
    guardians = student.guardians.all()
    
    return render(request, 'biodata/student_biodata_detail.html', {
        'student': student,
        'bio_data': bio_data,
        'form': form,
        'guardians': guardians,
        'can_edit': can_edit,
    })


@login_required
def add_guardian(request, student_id):
    school = getattr(request, 'school', None)
    if not school:
        raise PermissionDenied('A school context is required.')
    if not (request.user.is_superuser or request.user.has_any_role(['super_admin', 'administrator', 'subject_teacher', 'class_teacher'])):
        raise PermissionDenied('You do not have permission to manage guardians.')
    student = get_object_or_404(Student.all_objects, id=student_id, school=school)
    
    if request.method == 'POST':
        form = GuardianForm(request.POST, request.FILES, school=student.school, student=student)
        if form.is_valid():
            guardian = form.save(commit=False)
            guardian.student = student
            guardian.save()
            messages.success(request, 'Guardian added successfully!')
            return redirect('student_biodata_view', student_id=student_id)
    else:
        form = GuardianForm(school=student.school, student=student)
    
    return render(request, 'biodata/add_guardian.html', {
        'student': student,
        'form': form,
    })


@login_required
def edit_guardian(request, guardian_id):
    school = getattr(request, 'school', None)
    if not school:
        raise PermissionDenied('A school context is required.')
    if not (request.user.is_superuser or request.user.has_any_role(['super_admin', 'administrator', 'subject_teacher', 'class_teacher'])):
        raise PermissionDenied('You do not have permission to manage guardians.')
    guardians = Guardian.all_objects.filter(student__school=school)
    guardian = get_object_or_404(guardians, id=guardian_id)
    
    if request.method == 'POST':
        form = GuardianForm(request.POST, request.FILES, instance=guardian, school=guardian.student.school, student=guardian.student)
        if form.is_valid():
            form.save()
            messages.success(request, 'Guardian updated successfully!')
            return redirect('student_biodata_view', student_id=guardian.student.id)
    else:
        form = GuardianForm(instance=guardian, school=guardian.student.school, student=guardian.student)
    
    return render(request, 'biodata/edit_guardian.html', {
        'guardian': guardian,
        'form': form,
    })


@login_required
def staff_biodata_view(request, teacher_id):
    teacher = get_object_or_404(Teacher, id=teacher_id)
    can_edit = request.user.is_superuser or request.user.has_role('super_admin') or request.user.has_any_role(['subject_teacher', 'class_teacher'])
    bio_data, created = StaffBioData.objects.get_or_create(
        teacher=teacher,
        defaults={
            'date_of_birth': datetime.now().date(),
            'place_of_birth': '',
            'state_of_origin': '',
            'lga': '',
            'religion': '',
            'marital_status': 'single',
            'home_address': '',
            'phone_number': '',
            'email': teacher.user.email,
            'emergency_contact_name': '',
            'emergency_contact_relationship': '',
            'emergency_contact_phone': '',
            'emergency_contact_address': '',
            'date_of_employment': datetime.now().date(),
            'employment_type': 'full_time',
            'department': '',
            'position': '',
        }
    )
    
    if can_edit and request.method == 'POST':
        form = StaffBioDataForm(request.POST, request.FILES, instance=bio_data)
        if form.is_valid():
            form.save()
            messages.success(request, 'Staff bio-data updated successfully!')
            return redirect('staff_biodata_view', teacher_id=teacher_id)
    else:
        form = StaffBioDataForm(instance=bio_data) if can_edit else None
    
    qualifications = bio_data.qualifications.all()
    guarantors = bio_data.guarantors.all()
    
    try:
        bank_account = bio_data.bank_account
    except StaffBankAccount.DoesNotExist:
        bank_account = None
    
    return render(request, 'biodata/staff_biodata_detail.html', {
        'teacher': teacher,
        'bio_data': bio_data,
        'form': form,
        'qualifications': qualifications,
        'guarantors': guarantors,
        'bank_account': bank_account,
        'can_edit': can_edit,
    })


@login_required
def add_qualification(request, teacher_id):
    teacher = get_object_or_404(Teacher, id=teacher_id)
    bio_data = get_object_or_404(StaffBioData, teacher=teacher)
    
    if request.method == 'POST':
        form = StaffQualificationForm(request.POST, request.FILES)
        if form.is_valid():
            qualification = form.save(commit=False)
            qualification.staff_bio_data = bio_data
            qualification.save()
            messages.success(request, 'Qualification added successfully!')
            return redirect('staff_biodata_view', teacher_id=teacher_id)
    else:
        form = StaffQualificationForm()
    
    return render(request, 'biodata/add_qualification.html', {
        'teacher': teacher,
        'form': form,
    })


@login_required
def add_guarantor(request, teacher_id):
    teacher = get_object_or_404(Teacher, id=teacher_id)
    bio_data = get_object_or_404(StaffBioData, teacher=teacher)
    
    if request.method == 'POST':
        form = StaffGuarantorForm(request.POST, request.FILES)
        if form.is_valid():
            guarantor = form.save(commit=False)
            guarantor.staff_bio_data = bio_data
            guarantor.save()
            messages.success(request, 'Guarantor added successfully!')
            return redirect('staff_biodata_view', teacher_id=teacher_id)
    else:
        form = StaffGuarantorForm()
    
    return render(request, 'biodata/add_guarantor.html', {
        'teacher': teacher,
        'form': form,
    })


@login_required
def manage_bank_account(request, teacher_id):
    teacher = get_object_or_404(Teacher, id=teacher_id)
    bio_data = get_object_or_404(StaffBioData, teacher=teacher)
    
    try:
        bank_account = bio_data.bank_account
    except StaffBankAccount.DoesNotExist:
        bank_account = None
    
    if request.method == 'POST':
        form = StaffBankAccountForm(request.POST, instance=bank_account)
        if form.is_valid():
            account = form.save(commit=False)
            account.staff_bio_data = bio_data
            account.save()
            messages.success(request, 'Bank account details saved successfully!')
            return redirect('staff_biodata_view', teacher_id=teacher_id)
    else:
        form = StaffBankAccountForm(instance=bank_account)
    
    return render(request, 'biodata/manage_bank_account.html', {
        'teacher': teacher,
        'form': form,
    })


@login_required
def generate_payment_schedule(request):
    if request.method == 'POST':
        form = PaymentScheduleGeneratorForm(request.POST)
        if form.is_valid():
            month = form.cleaned_data['month']
            
            # Get all teachers with bio data and bank accounts
            teachers = active_staff(getattr(request, 'school', None)).filter(
                bio_data__isnull=False,
                bio_data__bank_account__isnull=False
            ).select_related('bio_data__bank_account', 'user')
            
            schedules_created = 0
            for teacher in teachers:
                try:
                    # Get or create payment schedule
                    schedule, created = PaymentSchedule.objects.get_or_create(
                        teacher=teacher,
                        month=month,
                        defaults={
                            'staff_name': teacher.user.get_full_name(),
                            'bank_name': teacher.bio_data.bank_account.bank_name,
                            'account_number': teacher.bio_data.bank_account.account_number,
                            'amount': 0,  # Will be updated from payroll
                        }
                    )
                    
                    # Update from latest payroll if exists
                    from .models import StaffPayroll
                    payroll = StaffPayroll.objects.filter(
                        teacher=teacher,
                        month=month
                    ).first()
                    
                    if payroll:
                        schedule.amount = payroll.net_salary
                        schedule.staff_name = teacher.user.get_full_name()
                        schedule.bank_name = teacher.bio_data.bank_account.bank_name
                        schedule.account_number = teacher.bio_data.bank_account.account_number
                        schedule.save()
                    
                    if created:
                        schedules_created += 1
                        
                except Exception as e:
                    messages.warning(request, f'Error creating schedule for {teacher.user.get_full_name()}: {str(e)}')
            
            messages.success(request, f'Payment schedule generated! {schedules_created} new schedules created.')
            return redirect('view_payment_schedule', month=month.strftime('%Y-%m'))
    else:
        form = PaymentScheduleGeneratorForm()
    
    return render(request, 'biodata/generate_payment_schedule.html', {
        'form': form,
    })


@login_required
def view_payment_schedule(request, month):
    month_date = datetime.strptime(month, '%Y-%m').date()
    schedules = PaymentSchedule.objects.filter(month=month_date).select_related('teacher__user')
    
    total_amount = sum(s.amount for s in schedules)
    
    return render(request, 'biodata/view_payment_schedule.html', {
        'schedules': schedules,
        'month': month_date,
        'total_amount': total_amount,
    })


@login_required
def export_payment_schedule_csv(request, month):
    month_date = datetime.strptime(month, '%Y-%m').date()
    schedules = PaymentSchedule.objects.filter(month=month_date).select_related('teacher__user')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="payment_schedule_{month}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Staff Name', 'Bank Name', 'Account Number', 'Amount', 'Status'])
    
    for schedule in schedules:
        writer.writerow([
            schedule.staff_name,
            schedule.bank_name,
            schedule.account_number,
            schedule.amount,
            schedule.get_status_display(),
        ])
    
    return response


@login_required
def staff_list_biodata(request):
    # Only admin can view staff list
    if not request.user.has_role('super_admin'):
        messages.error(request, 'Access denied')
        return redirect('core:dashboard')
    
    teachers = Teacher.objects.all().select_related('user', 'bio_data')
    
    search = request.GET.get('search', '')
    if search:
        teachers = teachers.filter(
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(employee_id__icontains=search)
        )
    
    return render(request, 'biodata/staff_list.html', {
        'teachers': teachers,
        'search': search,
    })


@login_required
def student_list_biodata(request):
    # Only teachers and admin can view list
    if not request.user.has_any_role(['super_admin', 'subject_teacher', 'class_teacher']):
        messages.error(request, 'Access denied')
        return redirect('core:dashboard')
    
    students = Student.objects.all().select_related('user', 'school_class', 'bio_data')
    
    search = request.GET.get('search', '')
    if search:
        students = students.filter(
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(student_id__icontains=search)
        )
    
    return render(request, 'biodata/student_list.html', {
        'students': students,
        'search': search,
    })

