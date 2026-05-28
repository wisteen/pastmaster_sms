/**
 * Enhanced Bulk Operations JavaScript
 * Provides comprehensive error handling, progress tracking, and user feedback
 */

class BulkOperationManager {
    constructor() {
        this.progressUpdateInterval = null;
        this.operationId = null;
        this.retryAttempts = 0;
        this.maxRetryAttempts = 3;
        this.errorThreshold = 0.5; // 50% error rate threshold
        this.init();
    }

    init() {
        this.bindEvents();
        this.setupProgressTracking();
        this.setupErrorHandling();
    }

    bindEvents() {
        // File upload validation
        document.addEventListener('change', (e) => {
            if (e.target.type === 'file' && e.target.accept.includes('.csv')) {
                this.validateCSVFile(e.target);
            }
        });

        // Form submission with validation
        document.addEventListener('submit', (e) => {
            if (e.target.classList.contains('bulk-operation-form')) {
                this.handleBulkOperationSubmit(e);
            }
        });

        // Progress tracking controls
        document.addEventListener('click', (e) => {
            if (e.target.matches('[data-action="cancel-operation"]')) {
                this.cancelOperation(e.target.dataset.operationId);
            } else if (e.target.matches('[data-action="retry-failed"]')) {
                this.retryFailedItems(e.target.dataset.operationId);
            } else if (e.target.matches('[data-action="download-report"]')) {
                this.downloadReport(e.target.dataset.operationId);
            }
        });
    }

    setupProgressTracking() {
        // Auto-start progress tracking if operation is running
        const operationElement = document.querySelector('[data-operation-id]');
        if (operationElement) {
            this.operationId = operationElement.dataset.operationId;
            const status = operationElement.dataset.operationStatus;
            
            if (status === 'running' || status === 'queued') {
                this.startProgressTracking();
            }
        }
    }

    setupErrorHandling() {
        // Global error handler for AJAX requests
        window.addEventListener('unhandledrejection', (e) => {
            console.error('Unhandled promise rejection:', e.reason);
            this.showNotification('An unexpected error occurred. Please try again.', 'error');
        });
    }

    validateCSVFile(fileInput) {
        const file = fileInput.files[0];
        if (!file) return;

        // Check file size (max 10MB)
        if (file.size > 10 * 1024 * 1024) {
            this.showNotification('File size exceeds 10MB limit. Please use a smaller file.', 'error');
            fileInput.value = '';
            return false;
        }

        // Check file type
        if (!file.name.toLowerCase().endsWith('.csv')) {
            this.showNotification('Please select a valid CSV file.', 'error');
            fileInput.value = '';
            return false;
        }

        // Preview file content
        this.previewCSVFile(file, fileInput);
        return true;
    }

    previewCSVFile(file, fileInput) {
        const reader = new FileReader();
        reader.onload = (e) => {
            const csv = e.target.result;
            const lines = csv.split('\n').filter(line => line.trim());
            
            if (lines.length < 2) {
                this.showNotification('CSV file must contain at least a header row and one data row.', 'error');
                fileInput.value = '';
                return;
            }

            // Show preview
            this.showCSVPreview(lines.slice(0, 6), lines.length - 1); // Show first 5 data rows
        };
        reader.readAsText(file);
    }

    showCSVPreview(lines, totalRows) {
        const previewContainer = document.getElementById('csv-preview');
        if (!previewContainer) return;

        const headers = lines[0].split(',').map(h => h.trim().replace(/"/g, ''));
        const dataRows = lines.slice(1);

        let html = `
            <div class="alert alert-info">
                <strong>CSV Preview:</strong> Showing first ${Math.min(5, dataRows.length)} of ${totalRows} data rows
            </div>
            <div class="table-responsive">
                <table class="table table-sm table-bordered">
                    <thead class="table-light">
                        <tr>
                            ${headers.map(h => `<th>${h}</th>`).join('')}
                        </tr>
                    </thead>
                    <tbody>
        `;

        dataRows.forEach(row => {
            const cells = row.split(',').map(c => c.trim().replace(/"/g, ''));
            html += `<tr>${cells.map(c => `<td>${c}</td>`).join('')}</tr>`;
        });

        html += `
                    </tbody>
                </table>
            </div>
        `;

        previewContainer.innerHTML = html;
        previewContainer.style.display = 'block';
    }

    handleBulkOperationSubmit(event) {
        event.preventDefault();
        
        const form = event.target;
        const formData = new FormData(form);
        const operationType = form.dataset.operationType;

        // Show confirmation dialog
        if (!this.confirmBulkOperation(operationType, formData)) {
            return;
        }

        // Disable form and show loading
        this.setFormLoading(form, true);

        // Submit the form
        this.submitBulkOperation(form, formData)
            .then(response => this.handleBulkOperationResponse(response, form))
            .catch(error => this.handleBulkOperationError(error, form));
    }

    confirmBulkOperation(operationType, formData) {
        const fileInput = formData.get('csv_file');
        const itemCount = fileInput && fileInput.size > 0 ? 'multiple items' : 'selected items';
        
        const messages = {
            'fee_structures': `Create fee structures for ${itemCount}? This will also create student fees for all students in the selected classes.`,
            'payments': `Process payments for ${itemCount}? This action cannot be undone.`,
            'payroll': `Generate payroll for selected staff members? This will create payroll records for the specified month.`,
            'scholarships': `Apply scholarships to ${itemCount}? This will create scholarship recipient records.`
        };

        const message = messages[operationType] || `Proceed with bulk ${operationType} operation?`;
        return confirm(message);
    }

    setFormLoading(form, loading) {
        const submitButton = form.querySelector('button[type="submit"]');
        const inputs = form.querySelectorAll('input, select, textarea');

        if (loading) {
            submitButton.disabled = true;
            submitButton.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Processing...';
            inputs.forEach(input => input.disabled = true);
        } else {
            submitButton.disabled = false;
            submitButton.innerHTML = submitButton.dataset.originalText || 'Submit';
            inputs.forEach(input => input.disabled = false);
        }
    }

    async submitBulkOperation(form, formData) {
        const response = await fetch(form.action, {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        return await response.json();
    }

    handleBulkOperationResponse(data, form) {
        this.setFormLoading(form, false);

        if (data.success) {
            this.operationId = data.operation_id;
            this.showNotification('Bulk operation started successfully!', 'success');
            
            // Redirect to progress page or show progress modal
            if (data.operation_id) {
                this.showProgressModal(data.operation_id, data.summary);
                this.startProgressTracking();
            }
        } else {
            this.handleValidationErrors(data);
        }
    }

    handleBulkOperationError(error, form) {
        this.setFormLoading(form, false);
        console.error('Bulk operation error:', error);
        this.showNotification('An error occurred while processing the bulk operation. Please try again.', 'error');
    }

    handleValidationErrors(data) {
        if (data.validation_errors) {
            let errorMessage = 'Validation errors found:\n';
            
            // Field errors
            if (data.validation_errors.field_errors) {
                Object.entries(data.validation_errors.field_errors).forEach(([field, errors]) => {
                    errors.forEach(error => {
                        errorMessage += `\n• ${field}: ${error.message}`;
                        if (error.item_index !== null) {
                            errorMessage += ` (Row ${error.item_index + 1})`;
                        }
                    });
                });
            }

            // Business rule errors
            if (data.validation_errors.business_rule_errors) {
                data.validation_errors.business_rule_errors.forEach(error => {
                    errorMessage += `\n• ${error.rule}: ${error.message}`;
                });
            }

            this.showNotification(errorMessage, 'error');
        } else {
            this.showNotification(data.error || 'Unknown error occurred', 'error');
        }
    }

    showProgressModal(operationId, summary) {
        const modal = document.getElementById('progressModal');
        if (!modal) {
            this.createProgressModal(operationId, summary);
        } else {
            this.updateProgressModal(summary);
            new bootstrap.Modal(modal).show();
        }
    }

    createProgressModal(operationId, summary) {
        const modalHtml = `
            <div class="modal fade" id="progressModal" tabindex="-1" data-bs-backdrop="static">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">
                                <i class="fas fa-chart-line me-2"></i>
                                Bulk Operation Progress
                            </h5>
                        </div>
                        <div class="modal-body">
                            <div class="row mb-3">
                                <div class="col-md-3 text-center">
                                    <h4 class="text-primary mb-0" id="modal-total-items">${summary.total_processed || 0}</h4>
                                    <small class="text-muted">Total Items</small>
                                </div>
                                <div class="col-md-3 text-center">
                                    <h4 class="text-success mb-0" id="modal-successful-items">${summary.successful || 0}</h4>
                                    <small class="text-muted">Successful</small>
                                </div>
                                <div class="col-md-3 text-center">
                                    <h4 class="text-danger mb-0" id="modal-failed-items">${summary.failed || 0}</h4>
                                    <small class="text-muted">Failed</small>
                                </div>
                                <div class="col-md-3 text-center">
                                    <h4 class="text-info mb-0" id="modal-progress-percent">${summary.success_rate || 0}%</h4>
                                    <small class="text-muted">Success Rate</small>
                                </div>
                            </div>
                            
                            <div class="mb-3">
                                <div class="d-flex justify-content-between align-items-center mb-2">
                                    <span class="fw-medium">Progress</span>
                                    <span class="text-muted" id="modal-progress-text">Processing...</span>
                                </div>
                                <div class="progress" style="height: 8px;">
                                    <div class="progress-bar bg-primary progress-bar-striped progress-bar-animated" 
                                         role="progressbar" style="width: 0%" id="modal-progress-bar"></div>
                                </div>
                            </div>
                            
                            <div class="alert alert-info" id="modal-status-message">
                                Operation started. Please wait while processing...
                            </div>
                            
                            <div id="modal-error-list" class="alert alert-danger" style="display: none;">
                                <h6>Recent Errors:</h6>
                                <ul id="modal-error-items"></ul>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-outline-danger" onclick="bulkOpManager.cancelOperation('${operationId}')">
                                <i class="fas fa-stop me-1"></i>Cancel
                            </button>
                            <button type="button" class="btn btn-outline-primary" onclick="bulkOpManager.viewDetailedProgress('${operationId}')">
                                <i class="fas fa-external-link-alt me-1"></i>View Details
                            </button>
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal" style="display: none;" id="modal-close-btn">
                                Close
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHtml);
        new bootstrap.Modal(document.getElementById('progressModal')).show();
    }

    startProgressTracking() {
        if (!this.operationId) return;

        this.progressUpdateInterval = setInterval(() => {
            this.updateProgress();
        }, 2000); // Update every 2 seconds
    }

    stopProgressTracking() {
        if (this.progressUpdateInterval) {
            clearInterval(this.progressUpdateInterval);
            this.progressUpdateInterval = null;
        }
    }

    async updateProgress() {
        if (!this.operationId) return;

        try {
            const response = await fetch(`/financial/bulk/progress/${this.operationId}/`);
            const data = await response.json();

            if (data.success) {
                this.updateProgressDisplay(data.progress);
                
                // Stop tracking if operation is complete
                if (['completed', 'failed', 'cancelled'].includes(data.progress.status)) {
                    this.stopProgressTracking();
                    this.handleOperationComplete(data.progress);
                }
            } else {
                this.retryAttempts++;
                if (this.retryAttempts >= this.maxRetryAttempts) {
                    this.stopProgressTracking();
                    this.showNotification('Lost connection to operation. Please refresh the page.', 'warning');
                }
            }
        } catch (error) {
            console.error('Progress update error:', error);
            this.retryAttempts++;
            if (this.retryAttempts >= this.maxRetryAttempts) {
                this.stopProgressTracking();
                this.showNotification('Connection error. Please refresh the page.', 'error');
            }
        }
    }

    updateProgressDisplay(progress) {
        // Update modal if visible
        const modal = document.getElementById('progressModal');
        if (modal && modal.classList.contains('show')) {
            document.getElementById('modal-total-items').textContent = progress.total_items;
            document.getElementById('modal-successful-items').textContent = progress.processed_items - progress.error_count;
            document.getElementById('modal-failed-items').textContent = progress.error_count;
            document.getElementById('modal-progress-percent').textContent = progress.progress_percentage.toFixed(1) + '%';
            document.getElementById('modal-progress-bar').style.width = progress.progress_percentage + '%';
            document.getElementById('modal-progress-text').textContent = progress.current_item || 'Processing...';

            // Update error list
            if (progress.recent_errors && progress.recent_errors.length > 0) {
                const errorList = document.getElementById('modal-error-list');
                const errorItems = document.getElementById('modal-error-items');
                errorItems.innerHTML = progress.recent_errors.map(error => 
                    `<li>${error.message}</li>`
                ).join('');
                errorList.style.display = 'block';
            }
        }

        // Update page elements if present
        const pageElements = {
            'processedItems': progress.processed_items,
            'successfulItems': progress.processed_items - progress.error_count,
            'failedItems': progress.error_count,
            'progressPercentage': progress.progress_percentage.toFixed(1) + '%',
            'progressBar': progress.progress_percentage + '%'
        };

        Object.entries(pageElements).forEach(([id, value]) => {
            const element = document.getElementById(id);
            if (element) {
                if (id === 'progressBar') {
                    element.style.width = value;
                } else {
                    element.textContent = value;
                }
            }
        });
    }

    handleOperationComplete(progress) {
        const modal = document.getElementById('progressModal');
        if (modal && modal.classList.contains('show')) {
            const statusMessage = document.getElementById('modal-status-message');
            const closeBtn = document.getElementById('modal-close-btn');
            
            if (progress.status === 'completed') {
                statusMessage.className = 'alert alert-success';
                statusMessage.innerHTML = '<i class="fas fa-check-circle me-2"></i>Operation completed successfully!';
            } else if (progress.status === 'failed') {
                statusMessage.className = 'alert alert-danger';
                statusMessage.innerHTML = '<i class="fas fa-exclamation-circle me-2"></i>Operation failed. Please check the error details.';
            } else if (progress.status === 'cancelled') {
                statusMessage.className = 'alert alert-warning';
                statusMessage.innerHTML = '<i class="fas fa-ban me-2"></i>Operation was cancelled.';
            }

            // Remove progress bar animation
            const progressBar = document.getElementById('modal-progress-bar');
            progressBar.classList.remove('progress-bar-animated', 'progress-bar-striped');

            // Show close button
            closeBtn.style.display = 'inline-block';
        }

        // Show completion notification
        const message = progress.status === 'completed' ? 
            'Bulk operation completed successfully!' : 
            `Bulk operation ${progress.status}. Check the report for details.`;
        
        this.showNotification(message, progress.status === 'completed' ? 'success' : 'warning');
    }

    async cancelOperation(operationId) {
        if (!confirm('Are you sure you want to cancel this operation?')) {
            return;
        }

        try {
            const response = await fetch(`/financial/bulk/cancel/${operationId}/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                }
            });

            const data = await response.json();
            if (data.success) {
                this.stopProgressTracking();
                this.showNotification('Operation cancelled successfully.', 'warning');
                
                // Close modal if open
                const modal = bootstrap.Modal.getInstance(document.getElementById('progressModal'));
                if (modal) {
                    modal.hide();
                }
            } else {
                this.showNotification('Failed to cancel operation: ' + data.error, 'error');
            }
        } catch (error) {
            this.showNotification('Error cancelling operation.', 'error');
        }
    }

    viewDetailedProgress(operationId) {
        window.open(`/financial/bulk/progress/${operationId}/`, '_blank');
    }

    downloadReport(operationId) {
        window.open(`/financial/bulk/report/${operationId}/`, '_blank');
    }

    showNotification(message, type = 'info') {
        // Remove existing notifications
        document.querySelectorAll('.bulk-notification').forEach(n => n.remove());

        const notification = document.createElement('div');
        notification.className = `alert alert-${type} alert-dismissible fade show position-fixed bulk-notification`;
        notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 350px; max-width: 500px;';
        
        const icons = {
            success: 'fas fa-check-circle',
            error: 'fas fa-exclamation-circle',
            warning: 'fas fa-exclamation-triangle',
            info: 'fas fa-info-circle'
        };

        notification.innerHTML = `
            <i class="${icons[type] || icons.info} me-2"></i>
            ${message.replace(/\n/g, '<br>')}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;

        document.body.appendChild(notification);

        // Auto-remove after 8 seconds for success/info, 12 seconds for warnings/errors
        const timeout = ['success', 'info'].includes(type) ? 8000 : 12000;
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, timeout);
    }

    // Cleanup on page unload
    cleanup() {
        this.stopProgressTracking();
    }
}

// Initialize the bulk operation manager
let bulkOpManager;
document.addEventListener('DOMContentLoaded', function() {
    bulkOpManager = new BulkOperationManager();
});

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (bulkOpManager) {
        bulkOpManager.cleanup();
    }
});