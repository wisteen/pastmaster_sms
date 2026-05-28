from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.db.models import Q, Count, Sum
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from datetime import datetime, timedelta
from .models import *
from .decorators_features import feature_required

@login_required
@feature_required('library_management')
def library_dashboard(request):
    """Main library dashboard"""
    # Library statistics
    total_books = Book.objects.count()
    available_books = Book.objects.filter(status='available').count()
    borrowed_books = BookBorrowing.objects.filter(status='active').count()
    overdue_books = BookBorrowing.objects.filter(status='overdue').count()
    
    # Update overdue status for active borrowings
    from django.utils import timezone
    active_borrowings = BookBorrowing.objects.filter(status='active')
    for borrowing in active_borrowings:
        if borrowing.is_overdue():
            borrowing.status = 'overdue'
            borrowing.save()
    
    # Recalculate overdue count after update
    overdue_books = BookBorrowing.objects.filter(status='overdue').count()
    
    # Digital resources
    digital_resources = DigitalResource.objects.filter(is_active=True).count()
    
    # Recent activity
    recent_borrowings = BookBorrowing.objects.select_related('book').order_by('-borrowed_date')[:5]
    
    context = {
        'user': request.user,
        'total_books': total_books,
        'available_books': available_books,
        'borrowed_books': borrowed_books,
        'overdue_books': overdue_books,
        'digital_resources': digital_resources,
        'recent_borrowings': recent_borrowings,
    }
    
    return render(request, 'library/dashboard.html', context)

@login_required
@feature_required('library_books')
def book_catalog(request):
    """Book catalog with search and filter"""
    search_query = request.GET.get('search', '')
    category_id = request.GET.get('category', '')
    book_type = request.GET.get('type', '')
    
    books = Book.objects.select_related('category')
    
    if search_query:
        books = books.filter(
            Q(title__icontains=search_query) |
            Q(author__icontains=search_query) |
            Q(isbn__icontains=search_query)
        )
    
    if category_id:
        books = books.filter(category_id=category_id)
    
    if book_type:
        books = books.filter(book_type=book_type)
    
    books = books.order_by('title')
    
    categories = BookCategory.objects.all()
    
    context = {
        'books': books,
        'categories': categories,
        'search_query': search_query,
        'selected_category': category_id,
        'selected_type': book_type,
    }
    
    return render(request, 'library/catalog.html', context)

@login_required
@feature_required('library_books')
def add_book(request):
    """Add new book to catalog"""
    if not request.user.has_any_role(['super_admin', 'librarian']):
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        Book.objects.create(
            title=request.POST.get('title'),
            author=request.POST.get('author'),
            isbn=request.POST.get('isbn', ''),
            category_id=request.POST.get('category'),
            book_type=request.POST.get('book_type', 'physical'),
            publisher=request.POST.get('publisher', ''),
            publication_year=request.POST.get('publication_year') or None,
            pages=request.POST.get('pages') or None,
            copies_total=int(request.POST.get('copies_total', 1)),
            copies_available=int(request.POST.get('copies_total', 1)),
            location=request.POST.get('location', ''),
            description=request.POST.get('description', ''),
        )
        
        messages.success(request, 'Book added successfully')
        return redirect('book_catalog')
    
    categories = BookCategory.objects.all()
    return render(request, 'library/add_book.html', {'categories': categories})

@login_required
def borrow_book(request, book_id):
    """Request to borrow a physical book (librarian approval required)"""
    book = get_object_or_404(Book, id=book_id)
    
    # Only physical books need librarian approval
    if book.book_type != 'physical':
        messages.error(request, 'Digital books can be accessed directly from Digital Resources')
        return redirect('digital_resources')
    
    # Only librarian/admin can issue physical books
    if not request.user.has_any_role(['super_admin', 'librarian']):
        messages.error(request, 'Only librarian can issue books')
        return redirect('core:dashboard')
    
    # Check if book is available
    if not book.is_available():
        messages.error(request, 'Book is not available for borrowing')
        return redirect('book_catalog')
    
    # Librarian issues book - need to specify borrower
    return redirect('manage_borrowings')

@login_required
def return_book(request, borrowing_id):
    """Return a borrowed book (librarian processes return)"""
    borrowing = get_object_or_404(BookBorrowing, id=borrowing_id)
    
    # Only librarian can process physical book returns
    if not request.user.has_any_role(['super_admin', 'librarian']):
        messages.error(request, 'Physical books must be returned to the librarian')
        return redirect('my_borrowings')
    
    # Calculate fine if overdue
    if borrowing.is_overdue():
        borrowing.calculate_fine()
    
    # Update borrowing record
    borrowing.returned_date = timezone.now()
    borrowing.status = 'returned'
    borrowing.save()
    
    # Update book availability
    book = borrowing.book
    book.copies_available += 1
    if book.status == 'borrowed' and book.copies_available > 0:
        book.status = 'available'
    book.save()
    
    fine_message = f' Fine: ₦{borrowing.fine_amount}' if borrowing.fine_amount > 0 else ''
    messages.success(request, f'Book "{book.title}" returned successfully.{fine_message}')
    
    if request.user.has_role('student'):
        return redirect('my_borrowings')
    else:
        return redirect('manage_borrowings')

@login_required
def my_borrowings(request):
    """User's borrowing history"""
    if request.user.has_role('student'):
        borrower = Student.objects.get(user=request.user)
        content_type = ContentType.objects.get_for_model(Student)
    elif request.user.has_any_role(['subject_teacher', 'class_teacher']):
        borrower = Teacher.objects.get(user=request.user)
        content_type = ContentType.objects.get_for_model(Teacher)
    else:
        return redirect('core:dashboard')
    
    borrowings = BookBorrowing.objects.filter(
        borrower_content_type=content_type,
        borrower_object_id=borrower.id
    ).select_related('book').order_by('-borrowed_date')
    
    return render(request, 'library/my_borrowings.html', {'borrowings': borrowings})

@login_required
@feature_required('library_borrowing')
def manage_borrowings(request):
    """Manage all borrowings (admin/librarian view)"""
    if not request.user.has_any_role(['super_admin', 'librarian']):
        return redirect('core:dashboard')
    
    status_filter = request.GET.get('status', '')
    search_query = request.GET.get('search', '')
    
    borrowings = BookBorrowing.objects.select_related('book')
    
    if status_filter:
        borrowings = borrowings.filter(status=status_filter)
    
    if search_query:
        borrowings = borrowings.filter(
            Q(book__title__icontains=search_query)
        )
    
    borrowings = borrowings.order_by('-borrowed_date')
    
    context = {
        'borrowings': borrowings,
        'status_filter': status_filter,
        'search_query': search_query,
    }
    
    return render(request, 'library/manage_borrowings.html', context)

@login_required
def issue_book(request, book_id):
    """Librarian issues a physical book to a borrower"""
    if not request.user.has_any_role(['super_admin', 'librarian']):
        messages.error(request, 'Only librarian can issue books')
        return redirect('core:dashboard')
    
    book = get_object_or_404(Book, id=book_id)
    
    if book.book_type != 'physical':
        messages.error(request, 'Only physical books need to be issued')
        return redirect('book_catalog')
    
    if not book.is_available():
        messages.error(request, 'Book is not available')
        return redirect('book_catalog')
    
    if request.method == 'POST':
        borrower_type = request.POST.get('borrower_type')
        
        if borrower_type == 'student':
            borrower_id = request.POST.get('student_id')
            try:
                borrower = Student.objects.get(student_id=borrower_id)
                content_type = ContentType.objects.get_for_model(Student)
                max_books = 3
                loan_days = 14
            except Student.DoesNotExist:
                messages.error(request, f'Student with ID {borrower_id} not found')
                return redirect('issue_book', book_id=book_id)
        elif borrower_type == 'teacher':
            borrower_id = request.POST.get('teacher_id')
            try:
                borrower = Teacher.objects.get(employee_id=borrower_id)
                content_type = ContentType.objects.get_for_model(Teacher)
                max_books = 5
                loan_days = 30
            except Teacher.DoesNotExist:
                messages.error(request, f'Teacher with ID {borrower_id} not found')
                return redirect('issue_book', book_id=book_id)
        else:
            messages.error(request, 'Invalid borrower type')
            return redirect('issue_book', book_id=book_id)
        
        # Check borrowing limits
        active_borrowings = BookBorrowing.objects.filter(
            borrower_content_type=content_type,
            borrower_object_id=borrower.id,
            status='active'
        ).count()
        
        if active_borrowings >= max_books:
            messages.error(request, f'Borrower has reached maximum limit ({max_books} books)')
            return redirect('book_catalog')
        
        # Create borrowing record
        due_date = timezone.now().date() + timedelta(days=loan_days)
        
        BookBorrowing.objects.create(
            book=book,
            borrower_content_type=content_type,
            borrower_object_id=borrower.id,
            due_date=due_date,
            issued_by=request.user
        )
        
        # Update book availability
        book.copies_available -= 1
        if book.copies_available == 0:
            book.status = 'borrowed'
        book.save()
        
        messages.success(request, f'Book issued to {borrower.user.get_full_name()}. Due: {due_date}')
        return redirect('manage_borrowings')
    
    students = Student.objects.select_related('user').all()[:50]
    teachers = Teacher.objects.select_related('user').all()[:50]
    
    return render(request, 'library/issue_book.html', {
        'book': book,
        'students': students,
        'teachers': teachers
    })

@login_required
def digital_resources(request):
    """Digital resources library"""
    resource_type = request.GET.get('type', '')
    category_id = request.GET.get('category', '')
    search_query = request.GET.get('search', '')
    
    resources = DigitalResource.objects.filter(is_active=True)
    
    # Filter by access level
    if request.user.has_role('student'):
        resources = resources.filter(access_level__in=['public', 'students'])
    elif request.user.has_any_role(['subject_teacher', 'class_teacher']):
        resources = resources.filter(access_level__in=['public', 'students', 'teachers'])
    
    if resource_type:
        resources = resources.filter(resource_type=resource_type)
    
    if category_id:
        resources = resources.filter(category_id=category_id)
    
    if search_query:
        resources = resources.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    resources = resources.select_related('category').order_by('title')
    categories = BookCategory.objects.all()
    
    context = {
        'resources': resources,
        'categories': categories,
        'selected_type': resource_type,
        'selected_category': category_id,
        'search_query': search_query,
    }
    
    return render(request, 'library/digital_resources.html', context)

@login_required
def download_resource(request, resource_id):
    """Download digital resource"""
    resource = get_object_or_404(DigitalResource, id=resource_id, is_active=True)
    
    # Check access permissions
    if request.user.has_role('student') and resource.access_level not in ['public', 'students']:
        messages.error(request, 'Access denied')
        return redirect('digital_resources')
    
    if request.user.has_any_role(['subject_teacher', 'class_teacher']) and resource.access_level == 'restricted':
        messages.error(request, 'Access denied')
        return redirect('digital_resources')
    
    # Increment download count
    resource.increment_download()
    
    if resource.file:
        response = HttpResponse(resource.file.read(), content_type='application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{resource.title}"'
        return response
    elif resource.url:
        return redirect(resource.url)
    else:
        messages.error(request, 'Resource file not found')
        return redirect('digital_resources')

@login_required
def add_digital_resource(request):
    """Add new digital resource"""
    if not request.user.has_any_role(['super_admin', 'librarian']):
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        resource = DigitalResource.objects.create(
            title=request.POST.get('title'),
            description=request.POST.get('description', ''),
            resource_type=request.POST.get('resource_type'),
            category_id=request.POST.get('category'),
            url=request.POST.get('url', ''),
            access_level=request.POST.get('access_level', 'students'),
            created_by=request.user
        )
        
        if request.FILES.get('file'):
            resource.file = request.FILES['file']
            resource.file_size = request.FILES['file'].size
            resource.save()
        
        messages.success(request, 'Digital resource added successfully')
        return redirect('digital_resources')
    
    categories = BookCategory.objects.all()
    return render(request, 'library/add_digital_resource.html', {'categories': categories})



