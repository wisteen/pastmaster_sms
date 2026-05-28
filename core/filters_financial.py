"""
Financial filtering system components for advanced search and filtering capabilities.
"""

from django.db.models import Q, Sum, Count
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import json


class FinancialFilterMixin:
    """Base mixin for financial filtering capabilities"""
    
    def get_filter_context(self):
        """Get context data for filter forms"""
        return {
            'date_ranges': self.get_date_range_options(),
            'status_choices': self.get_status_choices(),
            'amount_ranges': self.get_amount_range_options(),
            'search_fields': self.get_search_fields(),
            'payment_methods': self.get_payment_method_choices(),
            'classes': self.get_class_choices(),
            'terms': self.get_term_choices(),
        }
    
    def get_date_range_options(self):
        """Get predefined date range options"""
        today = timezone.now().date()
        return [
            ('today', 'Today', today, today),
            ('yesterday', 'Yesterday', today - timedelta(days=1), today - timedelta(days=1)),
            ('this_week', 'This Week', today - timedelta(days=today.weekday()), today),
            ('last_week', 'Last Week', 
             today - timedelta(days=today.weekday() + 7), 
             today - timedelta(days=today.weekday() + 1)),
            ('this_month', 'This Month', today.replace(day=1), today),
            ('last_month', 'Last Month', 
             (today.replace(day=1) - timedelta(days=1)).replace(day=1),
             today.replace(day=1) - timedelta(days=1)),
            ('this_year', 'This Year', today.replace(month=1, day=1), today),
            ('last_year', 'Last Year', 
             today.replace(year=today.year-1, month=1, day=1),
             today.replace(year=today.year-1, month=12, day=31)),
        ]
    
    def get_status_choices(self):
        """Get status choices based on model"""
        return []
    
    def get_amount_range_options(self):
        """Get predefined amount range options"""
        return [
            ('0-1000', '₦0 - ₦1,000', 0, 1000),
            ('1000-5000', '₦1,000 - ₦5,000', 1000, 5000),
            ('5000-10000', '₦5,000 - ₦10,000', 5000, 10000),
            ('10000-25000', '₦10,000 - ₦25,000', 10000, 25000),
            ('25000-50000', '₦25,000 - ₦50,000', 25000, 50000),
            ('50000+', '₦50,000+', 50000, None),
        ]
    
    def get_search_fields(self):
        """Get searchable fields for the model"""
        return []
    
    def get_payment_method_choices(self):
        """Get payment method choices"""
        from .models import FeePayment
        return FeePayment.PAYMENT_METHODS
    
    def get_class_choices(self):
        """Get school class choices"""
        from .models import SchoolClass
        return SchoolClass.objects.all().values_list('id', 'name')
    
    def get_term_choices(self):
        """Get term choices"""
        from .models import Term
        return Term.objects.all().values_list('id', 'name')
    
    def apply_filters(self, queryset, filters):
        """Apply multiple filters to queryset"""
        # Date range filtering
        if filters.get('date_from'):
            queryset = self.apply_date_from_filter(queryset, filters['date_from'])
        if filters.get('date_to'):
            queryset = self.apply_date_to_filter(queryset, filters['date_to'])
        
        # Predefined date range
        if filters.get('date_range'):
            queryset = self.apply_predefined_date_range(queryset, filters['date_range'])
        
        # Status filtering
        if filters.get('status'):
            queryset = self.apply_status_filter(queryset, filters['status'])
        
        # Amount range filtering
        if filters.get('amount_min'):
            queryset = self.apply_amount_min_filter(queryset, filters['amount_min'])
        if filters.get('amount_max'):
            queryset = self.apply_amount_max_filter(queryset, filters['amount_max'])
        
        # Predefined amount range
        if filters.get('amount_range'):
            queryset = self.apply_predefined_amount_range(queryset, filters['amount_range'])
        
        # Search filtering
        if filters.get('search'):
            queryset = self.apply_search(queryset, filters['search'])
        
        # Class filtering
        if filters.get('school_class'):
            queryset = self.apply_class_filter(queryset, filters['school_class'])
        
        # Term filtering
        if filters.get('term'):
            queryset = self.apply_term_filter(queryset, filters['term'])
        
        # Payment method filtering
        if filters.get('payment_method'):
            queryset = self.apply_payment_method_filter(queryset, filters['payment_method'])
        
        return queryset
    
    def apply_date_from_filter(self, queryset, date_from):
        """Apply date from filter - override in subclasses"""
        return queryset
    
    def apply_date_to_filter(self, queryset, date_to):
        """Apply date to filter - override in subclasses"""
        return queryset
    
    def apply_predefined_date_range(self, queryset, date_range):
        """Apply predefined date range filter"""
        ranges = dict([(r[0], (r[2], r[3])) for r in self.get_date_range_options()])
        if date_range in ranges:
            start_date, end_date = ranges[date_range]
            queryset = self.apply_date_from_filter(queryset, start_date)
            queryset = self.apply_date_to_filter(queryset, end_date)
        return queryset
    
    def apply_status_filter(self, queryset, status):
        """Apply status filter - override in subclasses"""
        return queryset
    
    def apply_amount_min_filter(self, queryset, amount_min):
        """Apply minimum amount filter - override in subclasses"""
        return queryset
    
    def apply_amount_max_filter(self, queryset, amount_max):
        """Apply maximum amount filter - override in subclasses"""
        return queryset
    
    def apply_predefined_amount_range(self, queryset, amount_range):
        """Apply predefined amount range filter"""
        ranges = dict([(r[0], (r[2], r[3])) for r in self.get_amount_range_options()])
        if amount_range in ranges:
            min_amount, max_amount = ranges[amount_range]
            queryset = self.apply_amount_min_filter(queryset, min_amount)
            if max_amount is not None:
                queryset = self.apply_amount_max_filter(queryset, max_amount)
        return queryset
    
    def apply_search(self, queryset, search_term):
        """Apply search filter - override in subclasses"""
        return queryset
    
    def apply_class_filter(self, queryset, school_class):
        """Apply class filter - override in subclasses"""
        return queryset
    
    def apply_term_filter(self, queryset, term):
        """Apply term filter - override in subclasses"""
        return queryset
    
    def apply_payment_method_filter(self, queryset, payment_method):
        """Apply payment method filter - override in subclasses"""
        return queryset
    
    def get_filter_state(self, request):
        """Get current filter state from request"""
        return {
            'date_from': request.GET.get('date_from'),
            'date_to': request.GET.get('date_to'),
            'date_range': request.GET.get('date_range'),
            'status': request.GET.get('status'),
            'amount_min': request.GET.get('amount_min'),
            'amount_max': request.GET.get('amount_max'),
            'amount_range': request.GET.get('amount_range'),
            'search': request.GET.get('search'),
            'school_class': request.GET.get('school_class'),
            'term': request.GET.get('term'),
            'payment_method': request.GET.get('payment_method'),
        }
    
    def persist_filter_state(self, request, filters):
        """Persist filter state in session"""
        if not hasattr(request, 'session'):
            return
        
        session_key = f"{self.__class__.__name__}_filters"
        request.session[session_key] = {k: v for k, v in filters.items() if v}
    
    def restore_filter_state(self, request):
        """Restore filter state from session"""
        if not hasattr(request, 'session'):
            return {}
        
        session_key = f"{self.__class__.__name__}_filters"
        return request.session.get(session_key, {})


class StudentFeeFilterMixin(FinancialFilterMixin):
    """Filter mixin for StudentFee model"""
    
    def get_status_choices(self):
        """Get status choices for StudentFee"""
        from .models import StudentFee
        return StudentFee.PAYMENT_STATUS
    
    def get_search_fields(self):
        """Get searchable fields for StudentFee"""
        return [
            'student__user__first_name',
            'student__user__last_name',
            'student__student_id',
            'fee_structure__name',
        ]
    
    def apply_date_from_filter(self, queryset, date_from):
        """Apply date from filter for StudentFee"""
        try:
            if isinstance(date_from, str):
                date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
            return queryset.filter(created_at__date__gte=date_from)
        except (ValueError, TypeError):
            return queryset
    
    def apply_date_to_filter(self, queryset, date_to):
        """Apply date to filter for StudentFee"""
        try:
            if isinstance(date_to, str):
                date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
            return queryset.filter(created_at__date__lte=date_to)
        except (ValueError, TypeError):
            return queryset
    
    def apply_status_filter(self, queryset, status):
        """Apply status filter for StudentFee"""
        return queryset.filter(status=status)
    
    def apply_amount_min_filter(self, queryset, amount_min):
        """Apply minimum amount filter for StudentFee"""
        try:
            amount_min = Decimal(str(amount_min))
            return queryset.filter(total_amount__gte=amount_min)
        except (ValueError, TypeError):
            return queryset
    
    def apply_amount_max_filter(self, queryset, amount_max):
        """Apply maximum amount filter for StudentFee"""
        try:
            amount_max = Decimal(str(amount_max))
            return queryset.filter(total_amount__lte=amount_max)
        except (ValueError, TypeError):
            return queryset
    
    def apply_search(self, queryset, search_term):
        """Apply search filter for StudentFee"""
        if not search_term:
            return queryset
        
        search_query = Q()
        for field in self.get_search_fields():
            search_query |= Q(**{f"{field}__icontains": search_term})
        
        return queryset.filter(search_query)
    
    def apply_class_filter(self, queryset, school_class):
        """Apply class filter for StudentFee"""
        try:
            class_id = int(school_class)
            return queryset.filter(student__school_class_id=class_id)
        except (ValueError, TypeError):
            return queryset
    
    def apply_term_filter(self, queryset, term):
        """Apply term filter for StudentFee"""
        try:
            term_id = int(term)
            return queryset.filter(fee_structure__term_id=term_id)
        except (ValueError, TypeError):
            return queryset


class FeePaymentFilterMixin(FinancialFilterMixin):
    """Filter mixin for FeePayment model"""
    
    def get_search_fields(self):
        """Get searchable fields for FeePayment"""
        return [
            'student_fee__student__user__first_name',
            'student_fee__student__user__last_name',
            'student_fee__student__student_id',
            'reference_number',
        ]
    
    def apply_date_from_filter(self, queryset, date_from):
        """Apply date from filter for FeePayment"""
        try:
            if isinstance(date_from, str):
                date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
            return queryset.filter(payment_date__date__gte=date_from)
        except (ValueError, TypeError):
            return queryset
    
    def apply_date_to_filter(self, queryset, date_to):
        """Apply date to filter for FeePayment"""
        try:
            if isinstance(date_to, str):
                date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
            return queryset.filter(payment_date__date__lte=date_to)
        except (ValueError, TypeError):
            return queryset
    
    def apply_amount_min_filter(self, queryset, amount_min):
        """Apply minimum amount filter for FeePayment"""
        try:
            amount_min = Decimal(str(amount_min))
            return queryset.filter(amount__gte=amount_min)
        except (ValueError, TypeError):
            return queryset
    
    def apply_amount_max_filter(self, queryset, amount_max):
        """Apply maximum amount filter for FeePayment"""
        try:
            amount_max = Decimal(str(amount_max))
            return queryset.filter(amount__lte=amount_max)
        except (ValueError, TypeError):
            return queryset
    
    def apply_search(self, queryset, search_term):
        """Apply search filter for FeePayment"""
        if not search_term:
            return queryset
        
        search_query = Q()
        for field in self.get_search_fields():
            search_query |= Q(**{f"{field}__icontains": search_term})
        
        return queryset.filter(search_query)
    
    def apply_class_filter(self, queryset, school_class):
        """Apply class filter for FeePayment"""
        try:
            class_id = int(school_class)
            return queryset.filter(student_fee__student__school_class_id=class_id)
        except (ValueError, TypeError):
            return queryset
    
    def apply_term_filter(self, queryset, term):
        """Apply term filter for FeePayment"""
        try:
            term_id = int(term)
            return queryset.filter(student_fee__fee_structure__term_id=term_id)
        except (ValueError, TypeError):
            return queryset
    
    def apply_payment_method_filter(self, queryset, payment_method):
        """Apply payment method filter for FeePayment"""
        return queryset.filter(payment_method=payment_method)


class ScholarshipFilterMixin(FinancialFilterMixin):
    """Filter mixin for Scholarship model"""
    
    def get_status_choices(self):
        """Get status choices for Scholarship"""
        return [
            ('active', 'Active'),
            ('inactive', 'Inactive'),
        ]
    
    def get_search_fields(self):
        """Get searchable fields for Scholarship"""
        return [
            'name',
            'description',
            'academic_year',
        ]
    
    def apply_date_from_filter(self, queryset, date_from):
        """Apply date from filter for Scholarship"""
        try:
            if isinstance(date_from, str):
                date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
            return queryset.filter(created_at__date__gte=date_from)
        except (ValueError, TypeError):
            return queryset
    
    def apply_date_to_filter(self, queryset, date_to):
        """Apply date to filter for Scholarship"""
        try:
            if isinstance(date_to, str):
                date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
            return queryset.filter(created_at__date__lte=date_to)
        except (ValueError, TypeError):
            return queryset
    
    def apply_status_filter(self, queryset, status):
        """Apply status filter for Scholarship"""
        if status == 'active':
            return queryset.filter(is_active=True)
        elif status == 'inactive':
            return queryset.filter(is_active=False)
        return queryset
    
    def apply_amount_min_filter(self, queryset, amount_min):
        """Apply minimum amount filter for Scholarship"""
        try:
            amount_min = Decimal(str(amount_min))
            return queryset.filter(amount__gte=amount_min)
        except (ValueError, TypeError):
            return queryset
    
    def apply_amount_max_filter(self, queryset, amount_max):
        """Apply maximum amount filter for Scholarship"""
        try:
            amount_max = Decimal(str(amount_max))
            return queryset.filter(amount__lte=amount_max)
        except (ValueError, TypeError):
            return queryset
    
    def apply_search(self, queryset, search_term):
        """Apply search filter for Scholarship"""
        if not search_term:
            return queryset
        
        search_query = Q()
        for field in self.get_search_fields():
            search_query |= Q(**{f"{field}__icontains": search_term})
        
        return queryset.filter(search_query)


class StaffPayrollFilterMixin(FinancialFilterMixin):
    """Filter mixin for StaffPayroll model"""
    
    def get_status_choices(self):
        """Get status choices for StaffPayroll"""
        return [
            ('paid', 'Paid'),
            ('unpaid', 'Unpaid'),
        ]
    
    def get_search_fields(self):
        """Get searchable fields for StaffPayroll"""
        return [
            'teacher__user__first_name',
            'teacher__user__last_name',
            'teacher__employee_id',
        ]
    
    def apply_date_from_filter(self, queryset, date_from):
        """Apply date from filter for StaffPayroll"""
        try:
            if isinstance(date_from, str):
                date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
            return queryset.filter(month__gte=date_from)
        except (ValueError, TypeError):
            return queryset
    
    def apply_date_to_filter(self, queryset, date_to):
        """Apply date to filter for StaffPayroll"""
        try:
            if isinstance(date_to, str):
                date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
            return queryset.filter(month__lte=date_to)
        except (ValueError, TypeError):
            return queryset
    
    def apply_status_filter(self, queryset, status):
        """Apply status filter for StaffPayroll"""
        if status == 'paid':
            return queryset.filter(is_paid=True)
        elif status == 'unpaid':
            return queryset.filter(is_paid=False)
        return queryset
    
    def apply_amount_min_filter(self, queryset, amount_min):
        """Apply minimum amount filter for StaffPayroll"""
        try:
            amount_min = Decimal(str(amount_min))
            return queryset.filter(net_salary__gte=amount_min)
        except (ValueError, TypeError):
            return queryset
    
    def apply_amount_max_filter(self, queryset, amount_max):
        """Apply maximum amount filter for StaffPayroll"""
        try:
            amount_max = Decimal(str(amount_max))
            return queryset.filter(net_salary__lte=amount_max)
        except (ValueError, TypeError):
            return queryset
    
    def apply_search(self, queryset, search_term):
        """Apply search filter for StaffPayroll"""
        if not search_term:
            return queryset
        
        search_query = Q()
        for field in self.get_search_fields():
            search_query |= Q(**{f"{field}__icontains": search_term})
        
        return queryset.filter(search_query)


class FinancialTransactionFilterMixin(FinancialFilterMixin):
    """Filter mixin for FinancialTransaction model"""
    
    def get_status_choices(self):
        """Get status choices for FinancialTransaction"""
        from .models import FinancialTransaction
        return FinancialTransaction.TRANSACTION_TYPES
    
    def get_search_fields(self):
        """Get searchable fields for FinancialTransaction"""
        return [
            'description',
            'reference_number',
            'category',
        ]
    
    def get_filter_state(self, request):
        """Get current filter state from request - override to add transaction-specific filters"""
        filters = super().get_filter_state(request)
        filters.update({
            'transaction_type': request.GET.get('transaction_type'),
            'category': request.GET.get('category'),
        })
        return filters
    
    def apply_filters(self, queryset, filters):
        """Apply filters including transaction-specific ones"""
        queryset = super().apply_filters(queryset, filters)
        
        # Transaction type filter
        if filters.get('transaction_type'):
            queryset = queryset.filter(transaction_type=filters['transaction_type'])
        
        # Category filter
        if filters.get('category'):
            queryset = queryset.filter(category=filters['category'])
        
        return queryset
    
    def apply_date_from_filter(self, queryset, date_from):
        """Apply date from filter for FinancialTransaction"""
        try:
            if isinstance(date_from, str):
                date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
            return queryset.filter(transaction_date__gte=date_from)
        except (ValueError, TypeError):
            return queryset
    
    def apply_date_to_filter(self, queryset, date_to):
        """Apply date to filter for FinancialTransaction"""
        try:
            if isinstance(date_to, str):
                date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
            return queryset.filter(transaction_date__lte=date_to)
        except (ValueError, TypeError):
            return queryset
    
    def apply_status_filter(self, queryset, status):
        """Apply status filter for FinancialTransaction"""
        return queryset.filter(transaction_type=status)
    
    def apply_amount_min_filter(self, queryset, amount_min):
        """Apply minimum amount filter for FinancialTransaction"""
        try:
            amount_min = Decimal(str(amount_min))
            return queryset.filter(amount__gte=amount_min)
        except (ValueError, TypeError):
            return queryset
    
    def apply_amount_max_filter(self, queryset, amount_max):
        """Apply maximum amount filter for FinancialTransaction"""
        try:
            amount_max = Decimal(str(amount_max))
            return queryset.filter(amount__lte=amount_max)
        except (ValueError, TypeError):
            return queryset
    
    def apply_search(self, queryset, search_term):
        """Apply search filter for FinancialTransaction"""
        if not search_term:
            return queryset
        
        search_query = Q()
        for field in self.get_search_fields():
            search_query |= Q(**{f"{field}__icontains": search_term})
        
        return queryset.filter(search_query)


class FilterStatePersistence:
    """Utility class for managing filter state persistence"""
    
    @staticmethod
    def save_filter_state(request, view_name, filters):
        """Save filter state to session"""
        if not hasattr(request, 'session'):
            return
        
        session_key = f"financial_filters_{view_name}"
        # Only save non-empty filters
        clean_filters = {k: v for k, v in filters.items() if v}
        request.session[session_key] = clean_filters
    
    @staticmethod
    def load_filter_state(request, view_name):
        """Load filter state from session"""
        if not hasattr(request, 'session'):
            return {}
        
        session_key = f"financial_filters_{view_name}"
        return request.session.get(session_key, {})
    
    @staticmethod
    def clear_filter_state(request, view_name):
        """Clear filter state from session"""
        if not hasattr(request, 'session'):
            return
        
        session_key = f"financial_filters_{view_name}"
        if session_key in request.session:
            del request.session[session_key]
    
    @staticmethod
    def merge_filters(session_filters, request_filters):
        """Merge session filters with request filters, giving priority to request"""
        merged = session_filters.copy()
        merged.update({k: v for k, v in request_filters.items() if v})
        return merged