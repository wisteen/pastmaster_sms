"""
Demonstration script for the Export Services

This script shows how to use the various export services for financial data.
Run this script from Django shell: python manage.py shell < core/export_demo.py
"""

from core.services_export import (
    ExportService, FinancialExportService, ReceiptGenerator, PayrollSlipGenerator,
    export_student_fees, generate_payment_receipt
)
from core.models import User, StudentFee, FeePayment, StaffPayroll

def demo_export_services():
    """Demonstrate the export services functionality"""
    
    print("=== Financial Export Services Demo ===\n")
    
    # Initialize services
    financial_service = FinancialExportService()
    
    # Set a user (optional)
    try:
        user = User.objects.first()
        if user:
            financial_service.set_user(user)
            print(f"✓ Set user: {user.get_full_name()}")
        else:
            print("! No users found in database")
    except Exception as e:
        print(f"! Error setting user: {e}")
    
    print("\n--- Available Export Methods ---")
    
    # 1. Student Fees Export
    try:
        student_fees_count = StudentFee.objects.count()
        print(f"✓ Student Fees: {student_fees_count} records available")
        print("  - export_student_fees(export_format='csv')")
        print("  - export_student_fees(export_format='excel')")
        print("  - export_student_fees(export_format='pdf')")
    except Exception as e:
        print(f"! Error checking student fees: {e}")
    
    # 2. Fee Payments Export
    try:
        payments_count = FeePayment.objects.count()
        print(f"✓ Fee Payments: {payments_count} records available")
        print("  - export_fee_payments(export_format='csv')")
        print("  - export_fee_payments(export_format='excel')")
        print("  - export_fee_payments(export_format='pdf')")
    except Exception as e:
        print(f"! Error checking fee payments: {e}")
    
    # 3. Payroll Export
    try:
        payroll_count = StaffPayroll.objects.count()
        print(f"✓ Staff Payroll: {payroll_count} records available")
        print("  - export_payroll(export_format='csv')")
        print("  - export_payroll(export_format='excel')")
        print("  - export_payroll(export_format='pdf')")
    except Exception as e:
        print(f"! Error checking payroll: {e}")
    
    print("\n--- Receipt and Slip Generation ---")
    
    # 4. Payment Receipts
    try:
        latest_payment = FeePayment.objects.first()
        if latest_payment:
            print(f"✓ Latest Payment ID: {latest_payment.id}")
            print("  - generate_payment_receipt(payment_id, format='pdf')")
            print("  - generate_payment_receipt(payment_id, format='html')")
        else:
            print("! No payments found for receipt generation")
    except Exception as e:
        print(f"! Error checking payments: {e}")
    
    # 5. Payroll Slips
    try:
        latest_payroll = StaffPayroll.objects.first()
        if latest_payroll:
            print(f"✓ Latest Payroll ID: {latest_payroll.id}")
            print("  - generate_payroll_slip(payroll_id, format='pdf')")
            print("  - generate_payroll_slip(payroll_id, format='html')")
        else:
            print("! No payroll records found for slip generation")
    except Exception as e:
        print(f"! Error checking payroll: {e}")
    
    print("\n--- Export Formats Supported ---")
    print("✓ CSV - Enhanced with metadata and proper formatting")
    print("✓ Excel - Professional formatting with charts (requires openpyxl)")
    print("✓ PDF - Professional documents with school branding (requires reportlab)")
    print("✓ HTML - Printable receipts and slips")
    
    print("\n--- Usage Examples ---")
    print("""
# Export student fees to CSV
response = export_student_fees(export_format='csv')

# Export with filters
filters = {'class_id': 1, 'status': 'pending'}
response = financial_service.export_student_fees(filters=filters)

# Generate payment receipt
response = generate_payment_receipt(payment_id=1, format='pdf')

# Export payroll to Excel
response = financial_service.export_payroll(export_format='excel')
    """)
    
    print("\n=== Demo Complete ===")
    print("All export services are ready for use!")

if __name__ == "__main__":
    demo_export_services()