/**
 * Financial Management JavaScript
 * Handles dynamic interactions, HTMX integration, and financial-specific functionality
 */

// Financial Management Namespace
const Financial = {
    // Configuration
    config: {
        searchDelay: 300,
        chartColors: {
            primary: '#0d6efd',
            success: '#198754',
            warning: '#ffc107',
            danger: '#dc3545',
            info: '#0dcaf0',
            secondary: '#6c757d'
        },
        currency: {
            symbol: '₦',
            locale: 'en-NG'
        }
    },

    // Initialize financial module
    init: function() {
        this.initializeComponents();
        this.bindEvents();
        this.initializeHTMX();
        this.initializeCharts();
        console.log('Financial Management System initialized');
    },

    // Initialize components
    initializeComponents: function() {
        this.initializeTooltips();
        this.initializePopovers();
        this.initializeModals();
        this.initializeFilters();
        this.initializeSearch();
    },

    // Initialize Bootstrap tooltips
    initializeTooltips: function() {
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function(tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    },

    // Initialize Bootstrap popovers
    initializePopovers: function() {
        const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
        popoverTriggerList.map(function(popoverTriggerEl) {
            return new bootstrap.Popover(popoverTriggerEl);
        });
    },

    // Initialize modals
    initializeModals: function() {
        const modals = document.querySelectorAll('.financial-modal');
        modals.forEach(modal => {
            modal.addEventListener('show.bs.modal', function(event) {
                Financial.handleModalShow(event);
            });
            modal.addEventListener('hidden.bs.modal', function(event) {
                Financial.handleModalHidden(event);
            });
        });
    },

    // Initialize filters
    initializeFilters: function() {
        const filterForms = document.querySelectorAll('.financial-filters form');
        filterForms.forEach(form => {
            const inputs = form.querySelectorAll('input, select');
            inputs.forEach(input => {
                input.addEventListener('change', function() {
                    Financial.handleFilterChange(form);
                });
            });
        });
    },

    // Initialize search functionality
    initializeSearch: function() {
        const searchInputs = document.querySelectorAll('.financial-search input[type="search"]');
        searchInputs.forEach(input => {
            let searchTimeout;
            input.addEventListener('input', function() {
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => {
                    Financial.handleSearch(input);
                }, Financial.config.searchDelay);
            });
        });
    },

    // Bind events
    bindEvents: function() {
        // Form validation
        document.addEventListener('submit', function(event) {
            if (event.target.classList.contains('financial-form')) {
                Financial.handleFormSubmit(event);
            }
        });

        // Real-time field validation
        document.addEventListener('input', function(event) {
            if (event.target.classList.contains('monetary-field')) {
                Financial.formatMonetaryField(event.target);
                Financial.validateMonetaryField(event.target);
            }
            if (event.target.classList.contains('percentage-field')) {
                Financial.validatePercentageField(event.target);
            }
        });

        document.addEventListener('blur', function(event) {
            if (event.target.classList.contains('monetary-field')) {
                Financial.validateMonetaryField(event.target);
            }
            if (event.target.classList.contains('percentage-field')) {
                Financial.validatePercentageField(event.target);
            }
            if (event.target.type === 'date') {
                Financial.validateDateField(event.target);
            }
        });

        // Balance validation for payment forms
        document.addEventListener('change', function(event) {
            if (event.target.name === 'student_fee') {
                Financial.updatePaymentBalance(event.target);
            }
            if (event.target.name === 'amount' && event.target.form.classList.contains('payment-form')) {
                Financial.validatePaymentAmount(event.target);
            }
        });

        // Scholarship amount/percentage mutual exclusion
        document.addEventListener('input', function(event) {
            if (event.target.name === 'amount' && event.target.form.classList.contains('scholarship-form')) {
                Financial.handleScholarshipAmountChange(event.target);
            }
            if (event.target.name === 'percentage' && event.target.form.classList.contains('scholarship-form')) {
                Financial.handleScholarshipPercentageChange(event.target);
            }
        });

        // Payroll calculation updates
        document.addEventListener('change', function(event) {
            if (event.target.form && event.target.form.classList.contains('payroll-structure-form')) {
                Financial.updatePayrollCalculations(event.target.form);
            }
        });

        // Bulk operations
        document.addEventListener('click', function(event) {
            if (event.target.classList.contains('bulk-select-all')) {
                Financial.handleBulkSelectAll(event.target);
            }
            if (event.target.classList.contains('bulk-action-btn')) {
                Financial.handleBulkAction(event.target);
            }
        });
    },

    // Initialize HTMX
    initializeHTMX: function() {
        // HTMX event listeners
        document.addEventListener('htmx:beforeRequest', function(event) {
            Financial.showLoading(event.target);
        });

        document.addEventListener('htmx:afterRequest', function(event) {
            Financial.hideLoading(event.target);
            if (event.detail.successful) {
                Financial.handleHTMXSuccess(event);
            } else {
                Financial.handleHTMXError(event);
            }
        });

        document.addEventListener('htmx:responseError', function(event) {
            Financial.showAlert('Error loading content. Please try again.', 'danger');
        });

        // Configure HTMX
        htmx.config.defaultSwapStyle = 'innerHTML';
        htmx.config.defaultSwapDelay = 100;
        htmx.config.defaultSettleDelay = 100;
    },

    // Initialize charts
    initializeCharts: function() {
        const chartContainers = document.querySelectorAll('.financial-chart-container');
        chartContainers.forEach(container => {
            const chartType = container.dataset.chartType;
            const chartData = container.dataset.chartData;
            
            if (chartType && chartData) {
                try {
                    const data = JSON.parse(chartData);
                    Financial.createChart(container, chartType, data);
                } catch (error) {
                    console.error('Error parsing chart data:', error);
                }
            }
        });
    },

    // Create chart
    createChart: function(container, type, data) {
        const canvas = container.querySelector('canvas');
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const config = Financial.getChartConfig(type, data);
        
        new Chart(ctx, config);
    },

    // Get chart configuration
    getChartConfig: function(type, data) {
        const baseConfig = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            if (type === 'doughnut' || type === 'pie') {
                                return context.label + ': ' + Financial.formatCurrency(context.parsed);
                            }
                            return Financial.formatCurrency(context.parsed.y || context.parsed);
                        }
                    }
                }
            }
        };

        switch (type) {
            case 'line':
                return {
                    type: 'line',
                    data: data,
                    options: {
                        ...baseConfig,
                        scales: {
                            y: {
                                beginAtZero: true,
                                ticks: {
                                    callback: function(value) {
                                        return Financial.formatCurrency(value);
                                    }
                                }
                            }
                        }
                    }
                };
            case 'bar':
                return {
                    type: 'bar',
                    data: data,
                    options: {
                        ...baseConfig,
                        scales: {
                            y: {
                                beginAtZero: true,
                                ticks: {
                                    callback: function(value) {
                                        return Financial.formatCurrency(value);
                                    }
                                }
                            }
                        }
                    }
                };
            case 'doughnut':
            case 'pie':
                return {
                    type: type,
                    data: data,
                    options: baseConfig
                };
            default:
                return {
                    type: 'line',
                    data: data,
                    options: baseConfig
                };
        }
    },

    // Handle modal show
    handleModalShow: function(event) {
        const modal = event.target;
        const form = modal.querySelector('form');
        if (form) {
            Financial.resetForm(form);
        }
    },

    // Handle modal hidden
    handleModalHidden: function(event) {
        const modal = event.target;
        const form = modal.querySelector('form');
        if (form) {
            Financial.resetForm(form);
        }
    },

    // Handle filter change
    handleFilterChange: function(form) {
        const formData = new FormData(form);
        const params = new URLSearchParams(formData);
        
        // Update URL without page reload
        const url = new URL(window.location);
        params.forEach((value, key) => {
            if (value) {
                url.searchParams.set(key, value);
            } else {
                url.searchParams.delete(key);
            }
        });
        
        window.history.replaceState({}, '', url);
        
        // Trigger HTMX request if configured
        const target = form.dataset.htmxTarget;
        if (target) {
            htmx.ajax('GET', url.toString(), {
                target: target,
                swap: 'innerHTML'
            });
        }
    },

    // Handle search
    handleSearch: function(input) {
        const query = input.value.trim();
        const minLength = parseInt(input.dataset.minLength) || 2;
        
        if (query.length >= minLength) {
            const searchUrl = input.dataset.searchUrl;
            if (searchUrl) {
                const url = new URL(searchUrl, window.location.origin);
                url.searchParams.set('q', query);
                
                htmx.ajax('GET', url.toString(), {
                    target: input.dataset.resultsTarget || '#search-results',
                    swap: 'innerHTML'
                });
            }
        } else {
            const resultsTarget = document.querySelector(input.dataset.resultsTarget || '#search-results');
            if (resultsTarget) {
                resultsTarget.innerHTML = '';
            }
        }
    },

    // Handle form submit
    handleFormSubmit: function(event) {
        const form = event.target;
        
        // Validate form
        if (!Financial.validateForm(form)) {
            event.preventDefault();
            return false;
        }
        
        // Show loading state
        Financial.showFormLoading(form);
    },

    // Validate form
    validateForm: function(form) {
        let isValid = true;
        const errors = [];

        // Clear previous validation states
        Financial.clearAllFieldErrors(form);

        // Validate required fields
        const requiredFields = form.querySelectorAll('[required]');
        requiredFields.forEach(field => {
            if (!field.value.trim()) {
                Financial.showFieldError(field, 'This field is required');
                isValid = false;
                errors.push(`${Financial.getFieldLabel(field)} is required`);
            }
        });

        // Validate monetary fields
        const monetaryFields = form.querySelectorAll('.monetary-field');
        monetaryFields.forEach(field => {
            if (field.value && !Financial.validateMonetaryField(field)) {
                isValid = false;
                errors.push(`${Financial.getFieldLabel(field)} must be a valid positive amount`);
            }
        });

        // Validate percentage fields
        const percentageFields = form.querySelectorAll('.percentage-field');
        percentageFields.forEach(field => {
            if (field.value && !Financial.validatePercentageField(field)) {
                isValid = false;
                errors.push(`${Financial.getFieldLabel(field)} must be between 0 and 100`);
            }
        });

        // Validate date fields
        const dateFields = form.querySelectorAll('input[type="date"]');
        dateFields.forEach(field => {
            if (field.value && !Financial.validateDateField(field)) {
                isValid = false;
                errors.push(`${Financial.getFieldLabel(field)} has an invalid date`);
            }
        });

        // Form-specific validations
        if (form.classList.contains('fee-structure-form')) {
            isValid = Financial.validateFeeStructureForm(form) && isValid;
        } else if (form.classList.contains('payment-form')) {
            isValid = Financial.validatePaymentForm(form) && isValid;
        } else if (form.classList.contains('scholarship-form')) {
            isValid = Financial.validateScholarshipForm(form) && isValid;
        } else if (form.classList.contains('payroll-form')) {
            isValid = Financial.validatePayrollForm(form) && isValid;
        } else if (form.classList.contains('payroll-structure-form')) {
            isValid = Financial.validatePayrollStructureForm(form) && isValid;
        }

        // Show summary of errors if any
        if (!isValid && errors.length > 0) {
            Financial.showValidationSummary(form, errors);
        }

        return isValid;
    },

    // Validate fee structure form
    validateFeeStructureForm: function(form) {
        let isValid = true;
        
        // Check if at least one fee amount is specified
        const feeFields = form.querySelectorAll('.monetary-field');
        const hasAmount = Array.from(feeFields).some(field => 
            parseFloat(field.value) > 0
        );
        
        if (!hasAmount) {
            Financial.showAlert('At least one fee amount must be specified', 'warning');
            isValid = false;
        }

        return isValid;
    },

    // Validate payment form
    validatePaymentForm: function(form) {
        let isValid = true;
        const amountField = form.querySelector('[name="amount"]');
        const studentFeeField = form.querySelector('[name="student_fee"]');
        
        if (amountField && studentFeeField && amountField.value && studentFeeField.value) {
            const amount = parseFloat(amountField.value);
            const balance = parseFloat(studentFeeField.dataset.balance || 0);
            
            if (amount > balance) {
                Financial.showFieldError(amountField, `Amount cannot exceed outstanding balance of ${Financial.formatCurrency(balance)}`);
                isValid = false;
            }
        }

        // Validate reference number for non-cash payments
        const paymentMethodField = form.querySelector('[name="payment_method"]');
        const referenceField = form.querySelector('[name="reference_number"]');
        
        if (paymentMethodField && referenceField) {
            const method = paymentMethodField.value;
            if (['bank_transfer', 'card', 'online'].includes(method) && !referenceField.value.trim()) {
                Financial.showFieldError(referenceField, 'Reference number is required for this payment method');
                isValid = false;
            }
        }

        return isValid;
    },

    // Validate scholarship form
    validateScholarshipForm: function(form) {
        let isValid = true;
        const amountField = form.querySelector('[name="amount"]');
        const percentageField = form.querySelector('[name="percentage"]');
        
        const hasAmount = amountField && parseFloat(amountField.value) > 0;
        const hasPercentage = percentageField && parseFloat(percentageField.value) > 0;
        
        if (!hasAmount && !hasPercentage) {
            Financial.showAlert('Either amount or percentage must be specified', 'warning');
            if (amountField) Financial.showFieldError(amountField, 'Specify amount or percentage');
            if (percentageField) Financial.showFieldError(percentageField, 'Specify amount or percentage');
            isValid = false;
        }
        
        if (hasAmount && hasPercentage) {
            Financial.showAlert('Specify either amount or percentage, not both', 'warning');
            Financial.showFieldError(amountField, 'Choose amount or percentage');
            Financial.showFieldError(percentageField, 'Choose amount or percentage');
            isValid = false;
        }

        return isValid;
    },

    // Validate payroll form
    validatePayrollForm: function(form) {
        let isValid = true;
        const monthField = form.querySelector('[name="month"]');
        
        if (monthField && monthField.value) {
            const selectedMonth = new Date(monthField.value + '-01');
            const today = new Date();
            const twoYearsAgo = new Date();
            twoYearsAgo.setFullYear(today.getFullYear() - 2);
            
            if (selectedMonth > today) {
                Financial.showFieldError(monthField, 'Payroll month cannot be in the future');
                isValid = false;
            } else if (selectedMonth < twoYearsAgo) {
                Financial.showFieldError(monthField, 'Payroll month cannot be more than 2 years in the past');
                isValid = false;
            }
        }

        return isValid;
    },

    // Validate payroll structure form
    validatePayrollStructureForm: function(form) {
        let isValid = true;
        const taxRateField = form.querySelector('[name="tax_rate"]');
        const pensionRateField = form.querySelector('[name="pension_rate"]');
        
        if (taxRateField && pensionRateField) {
            const taxRate = parseFloat(taxRateField.value) || 0;
            const pensionRate = parseFloat(pensionRateField.value) || 0;
            
            if (taxRate + pensionRate > 100) {
                Financial.showAlert('Combined tax and pension rates cannot exceed 100%', 'warning');
                Financial.showFieldError(taxRateField, 'Total rates exceed 100%');
                Financial.showFieldError(pensionRateField, 'Total rates exceed 100%');
                isValid = false;
            }
        }

        return isValid;
    },

    // Show field error
    showFieldError: function(field, message) {
        Financial.clearFieldError(field);
        
        field.classList.add('is-invalid');
        const feedback = document.createElement('div');
        feedback.className = 'invalid-feedback';
        feedback.textContent = message;
        field.parentNode.appendChild(feedback);
    },

    // Clear field error
    clearFieldError: function(field) {
        field.classList.remove('is-invalid');
        field.classList.add('is-valid');
        const feedback = field.parentNode.querySelector('.invalid-feedback');
        if (feedback) {
            feedback.remove();
        }
    },

    // Clear all field errors in form
    clearAllFieldErrors: function(form) {
        const invalidFields = form.querySelectorAll('.is-invalid');
        invalidFields.forEach(field => {
            Financial.clearFieldError(field);
        });
        
        // Remove validation summary
        const summary = form.querySelector('.validation-summary');
        if (summary) {
            summary.remove();
        }
    },

    // Get field label for error messages
    getFieldLabel: function(field) {
        const label = field.closest('.form-group')?.querySelector('label');
        if (label) {
            return label.textContent.replace('*', '').trim();
        }
        return field.name || field.id || 'Field';
    },

    // Show validation summary
    showValidationSummary: function(form, errors) {
        const existingSummary = form.querySelector('.validation-summary');
        if (existingSummary) {
            existingSummary.remove();
        }

        const summary = document.createElement('div');
        summary.className = 'alert alert-danger validation-summary';
        summary.innerHTML = `
            <h6>Please correct the following errors:</h6>
            <ul class="mb-0">
                ${errors.map(error => `<li>${error}</li>`).join('')}
            </ul>
        `;

        form.insertBefore(summary, form.firstChild);
    },

    // Format monetary field
    formatMonetaryField: function(input) {
        let value = input.value.replace(/[^\d.]/g, '');
        
        // Ensure only one decimal point
        const parts = value.split('.');
        if (parts.length > 2) {
            value = parts[0] + '.' + parts.slice(1).join('');
        }
        
        // Limit decimal places to 2
        if (parts[1] && parts[1].length > 2) {
            value = parts[0] + '.' + parts[1].substring(0, 2);
        }
        
        input.value = value;
        
        // Add visual formatting on blur
        if (document.activeElement !== input && value) {
            const numValue = parseFloat(value);
            if (!isNaN(numValue)) {
                input.dataset.rawValue = value;
                input.value = Financial.formatCurrency(numValue);
            }
        }
    },

    // Validate monetary field
    validateMonetaryField: function(input) {
        const value = input.dataset.rawValue || input.value.replace(/[^\d.]/g, '');
        const numValue = parseFloat(value);
        
        if (input.value && (isNaN(numValue) || numValue < 0)) {
            Financial.showFieldError(input, 'Please enter a valid positive amount');
            return false;
        } else if (input.value && numValue > 999999.99) {
            Financial.showFieldError(input, 'Amount exceeds maximum allowed value');
            return false;
        } else {
            Financial.clearFieldError(input);
            return true;
        }
    },

    // Validate percentage field
    validatePercentageField: function(input) {
        const value = parseFloat(input.value);
        
        if (input.value && (isNaN(value) || value < 0 || value > 100)) {
            Financial.showFieldError(input, 'Please enter a percentage between 0 and 100');
            return false;
        } else {
            Financial.clearFieldError(input);
            return true;
        }
    },

    // Validate date field
    validateDateField: function(input) {
        if (!input.value) return true;
        
        const date = new Date(input.value);
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        
        if (isNaN(date.getTime())) {
            Financial.showFieldError(input, 'Please enter a valid date');
            return false;
        }
        
        // Check for future date restriction
        if (input.classList.contains('no-future') && date > today) {
            Financial.showFieldError(input, 'Date cannot be in the future');
            return false;
        }
        
        // Check for past date restriction
        if (input.classList.contains('no-past') && date < today) {
            Financial.showFieldError(input, 'Date cannot be in the past');
            return false;
        }
        
        // Check date range for end dates
        if (input.name === 'end_date') {
            const startDateField = input.form.querySelector('[name="start_date"]');
            if (startDateField && startDateField.value) {
                const startDate = new Date(startDateField.value);
                if (date <= startDate) {
                    Financial.showFieldError(input, 'End date must be after start date');
                    return false;
                }
            }
        }
        
        Financial.clearFieldError(input);
        return true;
    },

    // Update payment balance display
    updatePaymentBalance: function(studentFeeSelect) {
        const selectedOption = studentFeeSelect.selectedOptions[0];
        if (selectedOption) {
            const balance = selectedOption.dataset.balance;
            const amountField = studentFeeSelect.form.querySelector('[name="amount"]');
            
            if (balance && amountField) {
                studentFeeSelect.dataset.balance = balance;
                amountField.max = balance;
                
                // Update balance display
                let balanceDisplay = studentFeeSelect.form.querySelector('.balance-display');
                if (!balanceDisplay) {
                    balanceDisplay = document.createElement('div');
                    balanceDisplay.className = 'balance-display text-info mt-1';
                    studentFeeSelect.parentNode.appendChild(balanceDisplay);
                }
                balanceDisplay.textContent = `Outstanding Balance: ${Financial.formatCurrency(parseFloat(balance))}`;
            }
        }
    },

    // Validate payment amount against balance
    validatePaymentAmount: function(amountField) {
        const studentFeeField = amountField.form.querySelector('[name="student_fee"]');
        if (!studentFeeField || !studentFeeField.dataset.balance) return true;
        
        const amount = parseFloat(amountField.value);
        const balance = parseFloat(studentFeeField.dataset.balance);
        
        if (amount > balance) {
            Financial.showFieldError(amountField, `Amount cannot exceed outstanding balance of ${Financial.formatCurrency(balance)}`);
            return false;
        } else {
            Financial.clearFieldError(amountField);
            return true;
        }
    },

    // Handle scholarship amount change
    handleScholarshipAmountChange: function(amountField) {
        const percentageField = amountField.form.querySelector('[name="percentage"]');
        if (percentageField && amountField.value) {
            percentageField.value = '';
            Financial.clearFieldError(percentageField);
        }
    },

    // Handle scholarship percentage change
    handleScholarshipPercentageChange: function(percentageField) {
        const amountField = percentageField.form.querySelector('[name="amount"]');
        if (amountField && percentageField.value) {
            amountField.value = '';
            Financial.clearFieldError(amountField);
        }
    },

    // Update payroll calculations
    updatePayrollCalculations: function(form) {
        const basicSalary = parseFloat(form.querySelector('[name="basic_salary"]')?.value) || 0;
        const houseAllowance = parseFloat(form.querySelector('[name="house_allowance"]')?.value) || 0;
        const transportAllowance = parseFloat(form.querySelector('[name="transport_allowance"]')?.value) || 0;
        const medicalAllowance = parseFloat(form.querySelector('[name="medical_allowance"]')?.value) || 0;
        const otherAllowances = parseFloat(form.querySelector('[name="other_allowances"]')?.value) || 0;
        const taxRate = parseFloat(form.querySelector('[name="tax_rate"]')?.value) || 0;
        const pensionRate = parseFloat(form.querySelector('[name="pension_rate"]')?.value) || 0;
        
        const grossSalary = basicSalary + houseAllowance + transportAllowance + medicalAllowance + otherAllowances;
        const taxDeduction = (grossSalary * taxRate) / 100;
        const pensionDeduction = (grossSalary * pensionRate) / 100;
        const netSalary = grossSalary - taxDeduction - pensionDeduction;
        
        // Update display elements
        let calculationDisplay = form.querySelector('.payroll-calculations');
        if (!calculationDisplay) {
            calculationDisplay = document.createElement('div');
            calculationDisplay.className = 'payroll-calculations card mt-3';
            calculationDisplay.innerHTML = `
                <div class="card-body">
                    <h6 class="card-title">Salary Calculations</h6>
                    <div class="row">
                        <div class="col-md-6">
                            <div class="gross-salary"></div>
                            <div class="tax-deduction"></div>
                            <div class="pension-deduction"></div>
                        </div>
                        <div class="col-md-6">
                            <div class="net-salary"></div>
                        </div>
                    </div>
                </div>
            `;
            form.appendChild(calculationDisplay);
        }
        
        calculationDisplay.querySelector('.gross-salary').innerHTML = 
            `<strong>Gross Salary:</strong> ${Financial.formatCurrency(grossSalary)}`;
        calculationDisplay.querySelector('.tax-deduction').innerHTML = 
            `<strong>Tax Deduction (${taxRate}%):</strong> ${Financial.formatCurrency(taxDeduction)}`;
        calculationDisplay.querySelector('.pension-deduction').innerHTML = 
            `<strong>Pension Deduction (${pensionRate}%):</strong> ${Financial.formatCurrency(pensionDeduction)}`;
        calculationDisplay.querySelector('.net-salary').innerHTML = 
            `<strong>Net Salary:</strong> <span class="text-success">${Financial.formatCurrency(netSalary)}</span>`;
    },

    // Legacy function aliases for backward compatibility
    formatAmount: function(input) {
        return Financial.formatMonetaryField(input);
    },

    validatePercentage: function(input) {
        return Financial.validatePercentageField(input);
    },

    validateDate: function(input) {
        return Financial.validateDateField(input);
    },

    // Handle bulk select all
    handleBulkSelectAll: function(checkbox) {
        const table = checkbox.closest('table');
        const checkboxes = table.querySelectorAll('tbody input[type="checkbox"]');
        
        checkboxes.forEach(cb => {
            cb.checked = checkbox.checked;
        });
        
        Financial.updateBulkActions();
    },

    // Handle bulk action
    handleBulkAction: function(button) {
        const selectedItems = document.querySelectorAll('tbody input[type="checkbox"]:checked');
        
        if (selectedItems.length === 0) {
            Financial.showAlert('Please select at least one item', 'warning');
            return;
        }
        
        const action = button.dataset.action;
        const confirmMessage = button.dataset.confirm;
        
        if (confirmMessage && !confirm(confirmMessage)) {
            return;
        }
        
        Financial.executeBulkAction(action, selectedItems);
    },

    // Execute bulk action
    executeBulkAction: function(action, selectedItems) {
        const ids = Array.from(selectedItems).map(item => item.value);
        
        const formData = new FormData();
        formData.append('action', action);
        formData.append('ids', JSON.stringify(ids));
        
        htmx.ajax('POST', window.location.pathname, {
            values: Object.fromEntries(formData),
            target: '#main-content',
            swap: 'innerHTML'
        });
    },

    // Update bulk actions
    updateBulkActions: function() {
        const selectedItems = document.querySelectorAll('tbody input[type="checkbox"]:checked');
        const bulkActions = document.querySelector('.bulk-actions');
        
        if (bulkActions) {
            if (selectedItems.length > 0) {
                bulkActions.style.display = 'block';
                bulkActions.querySelector('.selected-count').textContent = selectedItems.length;
            } else {
                bulkActions.style.display = 'none';
            }
        }
    },

    // Show loading
    showLoading: function(element) {
        const loader = element.querySelector('.htmx-indicator');
        if (loader) {
            loader.style.display = 'inline-block';
        }
        
        if (element.tagName === 'BUTTON') {
            element.disabled = true;
            element.dataset.originalText = element.innerHTML;
            element.innerHTML = '<span class="financial-loading"></span> Loading...';
        }
    },

    // Hide loading
    hideLoading: function(element) {
        const loader = element.querySelector('.htmx-indicator');
        if (loader) {
            loader.style.display = 'none';
        }
        
        if (element.tagName === 'BUTTON' && element.dataset.originalText) {
            element.disabled = false;
            element.innerHTML = element.dataset.originalText;
            delete element.dataset.originalText;
        }
    },

    // Show form loading
    showFormLoading: function(form) {
        const submitButton = form.querySelector('button[type="submit"]');
        if (submitButton) {
            Financial.showLoading(submitButton);
        }
    },

    // Handle HTMX success
    handleHTMXSuccess: function(event) {
        // Re-initialize components for new content
        Financial.initializeComponents();
        
        // Show success message if provided
        const response = event.detail.xhr.response;
        if (response.includes('alert-success')) {
            // Success message is already in the response
        }
    },

    // Handle HTMX error
    handleHTMXError: function(event) {
        const status = event.detail.xhr.status;
        let message = 'An error occurred. Please try again.';
        
        switch (status) {
            case 400:
                message = 'Invalid request. Please check your input.';
                break;
            case 403:
                message = 'You do not have permission to perform this action.';
                break;
            case 404:
                message = 'The requested resource was not found.';
                break;
            case 500:
                message = 'Server error. Please try again later.';
                break;
        }
        
        Financial.showAlert(message, 'danger');
    },

    // Reset form
    resetForm: function(form) {
        form.reset();
        const invalidFields = form.querySelectorAll('.is-invalid');
        invalidFields.forEach(field => {
            Financial.clearFieldError(field);
        });
    },

    // Show alert
    showAlert: function(message, type = 'info') {
        const alertContainer = document.querySelector('#alert-container') || document.body;
        
        const alert = document.createElement('div');
        alert.className = `alert alert-${type} alert-dismissible fade show financial-alert`;
        alert.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        alertContainer.insertBefore(alert, alertContainer.firstChild);
        
        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            if (alert.parentNode) {
                alert.remove();
            }
        }, 5000);
    },

    // Format currency
    formatCurrency: function(amount) {
        return new Intl.NumberFormat(Financial.config.currency.locale, {
            style: 'currency',
            currency: 'NGN',
            minimumFractionDigits: 0,
            maximumFractionDigits: 2
        }).format(amount);
    },

    // Utility functions
    utils: {
        // Debounce function
        debounce: function(func, wait) {
            let timeout;
            return function executedFunction(...args) {
                const later = () => {
                    clearTimeout(timeout);
                    func(...args);
                };
                clearTimeout(timeout);
                timeout = setTimeout(later, wait);
            };
        },

        // Throttle function
        throttle: function(func, limit) {
            let inThrottle;
            return function() {
                const args = arguments;
                const context = this;
                if (!inThrottle) {
                    func.apply(context, args);
                    inThrottle = true;
                    setTimeout(() => inThrottle = false, limit);
                }
            };
        },

        // Generate unique ID
        generateId: function() {
            return 'financial_' + Math.random().toString(36).substr(2, 9);
        }
    }
};

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    Financial.init();
});

// Export for use in other scripts
window.Financial = Financial;