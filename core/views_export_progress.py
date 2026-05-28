"""
Views for export progress tracking
"""

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required

from .services_export import ExportProgressTracker


@login_required
@require_http_methods(["GET"])
def export_progress(request, export_id):
    """
    Get the progress of an export operation
    
    Args:
        request: HTTP request
        export_id: UUID of the export operation
    
    Returns:
        JSON response with progress data
    """
    tracker = ExportProgressTracker(export_id)
    progress_data = tracker.get_progress()
    
    return JsonResponse(progress_data)


@login_required
@require_http_methods(["POST"])
def cancel_export(request, export_id):
    """
    Cancel an ongoing export operation
    
    Args:
        request: HTTP request
        export_id: UUID of the export operation
    
    Returns:
        JSON response with cancellation status
    """
    tracker = ExportProgressTracker(export_id)
    tracker.mark_failed("Export cancelled by user")
    
    return JsonResponse({
        'status': 'cancelled',
        'message': 'Export operation cancelled successfully',
        'export_id': export_id
    })
