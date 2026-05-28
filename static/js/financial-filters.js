/**
 * Financial Filtering and Search System
 * Provides real-time search, auto-complete, and advanced filtering capabilities
 */

class FinancialFilterSystem {
    constructor(options = {}) {
        this.options = {
            searchDelay: 300,
            minSearchLength: 2,
            maxSuggestions: 10,
            enableAutoComplete: true,
            enableRealTimeSearch: true,
            enableFilterPersistence: true,
            ...options
        };
        
        this.searchTimeout = null;
        this.currentRequest = null;
        this.cache = new Map();
        
        this.init();
    }
    
    init() {
        this.bindEvents();
        this.initializeFilters();
        this.setupAutoComplete();
        
        // Load persisted filters if enabled
        if (this.options.enableFilterPersistence) {
            this.loadPersistedFilters();
        }
    }
    
    bindEvents() {
        // Search input events
        $(document).on('input', '.financial-search-input', (e) => {
            this.handleSearchInput(e);
        });
        
        // Filter change events
        $(document).on('change', '.financial-filter', (e) => {
            this.handleFilterChange(e);
        });
        
        // Clear filters button
        $(document).on('click', '.clear-filters-btn', (e) => {
            this.clearAllFilters(e);
        });
        
        // Apply filters button
        $(document).on('click', '.apply-filters-btn', (e) => {
            this.applyFilters(e);
        });
        
        // Date range presets
        $(document).on('change', '.date-range-preset', (e) => {
            this.handleDateRangePreset(e);
        });
        
        // Amount range presets
        $(document).on('change', '.amount-range-preset', (e) => {
            this.handleAmountRangePreset(e);
        });
        
        // Export filtered results
        $(document).on('click', '.export-filtered-btn', (e) => {
            this.exportFilteredResults(e);
        });
    }
    
    initializeFilters() {
        // Initialize date pickers
        $('.date-filter').each(function() {
            if ($(this).attr('type') !== 'date') {
                $(this).attr('type', 'date');
            }
        });
        
        // Initialize select2 for better dropdowns
        if ($.fn.select2) {
            $('.financial-select-filter').select2({
                placeholder: 'Select option...',
                allowClear: true,
                width: '100%'
            });
        }
        
        // Initialize amount inputs with formatting
        $('.amount-filter').on('input', function() {
            this.formatAmountInput($(this));
        }.bind(this));
    }
    
    setupAutoComplete() {
        if (!this.options.enableAutoComplete) return;
        
        $('.financial-search-input').each((index, element) => {
            const $input = $(element);
            const searchType = $input.data('search-type') || 'general';
            
            $input.autocomplete({
                source: (request, response) => {
                    this.getAutoCompleteSuggestions(request.term, searchType, response);
                },
                minLength: this.options.minSearchLength,
                delay: this.options.searchDelay,
                select: (event, ui) => {
                    this.handleAutoCompleteSelect(event, ui);
                }
            });
        });
    }
    
    handleSearchInput(event) {
        if (!this.options.enableRealTimeSearch) return;
        
        const $input = $(event.target);
        const searchTerm = $input.val().trim();
        
        // Clear previous timeout
        if (this.searchTimeout) {
            clearTimeout(this.searchTimeout);
        }
        
        // Set new timeout for search
        this.searchTimeout = setTimeout(() => {
            if (searchTerm.length >= this.options.minSearchLength || searchTerm.length === 0) {
                this.performSearch(searchTerm, $input);
            }
        }, this.options.searchDelay);
    }
    
    performSearch(searchTerm, $input) {
        const searchType = $input.data('search-type') || 'student_fee';
        const targetContainer = $input.data('target') || '.search-results';
        const isRealTimeSearch = searchTerm.length >= this.options.minSearchLength;
        
        // Cancel previous request
        if (this.currentRequest) {
            this.currentRequest.abort();
        }
        
        // Show loading indicator
        this.showLoadingIndicator(targetContainer);
        
        // Prepare search data
        const searchData = this.collectFilterData();
        searchData.search = searchTerm;
        searchData.search_type = searchType;
        
        // Choose endpoint based on whether we're doing real-time search or filtering
        const endpoint = isRealTimeSearch ? 
            this.getSearchEndpoint(searchType) : 
            this.getFilterEndpoint(searchType);
        
        // Make AJAX request
        this.currentRequest = $.ajax({
            url: endpoint,
            method: 'GET',
            data: searchData,
            success: (response) => {
                this.handleSearchResponse(response, targetContainer);
                if (searchTerm) {
                    this.highlightSearchResults(searchTerm);
                }
            },
            error: (xhr, status, error) => {
                if (status !== 'abort') {
                    this.handleSearchError(error, targetContainer);
                }
            },
            complete: () => {
                this.hideLoadingIndicator(targetContainer);
                this.currentRequest = null;
            }
        });
    }
    
    getAutoCompleteSuggestions(term, searchType, callback) {
        // Check cache first
        const cacheKey = `${searchType}_${term}`;
        if (this.cache.has(cacheKey)) {
            callback(this.cache.get(cacheKey));
            return;
        }
        
        $.ajax({
            url: this.getAutoCompleteEndpoint(searchType),
            method: 'GET',
            data: { term: term, limit: this.options.maxSuggestions },
            success: (response) => {
                const suggestions = this.formatAutoCompleteSuggestions(response, searchType);
                
                // Cache the results
                this.cache.set(cacheKey, suggestions);
                
                callback(suggestions);
            },
            error: () => {
                callback([]);
            }
        });
    }
    
    formatAutoCompleteSuggestions(response, searchType) {
        if (!response.suggestions) return [];
        
        return response.suggestions.map(item => {
            switch (searchType) {
                case 'student':
                    return {
                        label: `${item.name} (${item.student_id}) - ${item.class_name}`,
                        value: item.name,
                        data: item
                    };
                case 'teacher':
                    return {
                        label: `${item.name} (${item.employee_id})`,
                        value: item.name,
                        data: item
                    };
                case 'reference':
                    return {
                        label: `${item.reference_number} - ${item.description}`,
                        value: item.reference_number,
                        data: item
                    };
                default:
                    return {
                        label: item.label || item.name || item.value,
                        value: item.value || item.name,
                        data: item
                    };
            }
        });
    }
    
    handleAutoCompleteSelect(event, ui) {
        const $input = $(event.target);
        const searchType = $input.data('search-type');
        
        // Store selected data for potential use
        $input.data('selected-item', ui.item.data);
        
        // Trigger search with selected item
        if (this.options.enableRealTimeSearch) {
            setTimeout(() => {
                this.performSearch(ui.item.value, $input);
            }, 100);
        }
    }
    
    handleFilterChange(event) {
        const $filter = $(event.target);
        
        // Update dependent filters if needed
        this.updateDependentFilters($filter);
        
        // Apply filters if real-time is enabled
        if (this.options.enableRealTimeSearch) {
            this.applyFilters();
        }
        
        // Persist filters if enabled
        if (this.options.enableFilterPersistence) {
            this.persistFilters();
        }
    }
    
    updateDependentFilters($changedFilter) {
        const filterName = $changedFilter.attr('name');
        
        // Handle class-term dependencies
        if (filterName === 'school_class') {
            this.updateTermOptions($changedFilter.val());
        }
        
        // Handle date range dependencies
        if (filterName === 'date_from') {
            const dateFrom = $changedFilter.val();
            const $dateTo = $('input[name="date_to"]');
            if (dateFrom && $dateTo.val() && new Date(dateFrom) > new Date($dateTo.val())) {
                $dateTo.val(dateFrom);
            }
        }
    }
    
    updateTermOptions(classId) {
        if (!classId) return;
        
        const $termSelect = $('select[name="term"]');
        if ($termSelect.length === 0) return;
        
        $.ajax({
            url: '/financial/ajax/terms-by-class/',
            method: 'GET',
            data: { class_id: classId },
            success: (response) => {
                $termSelect.empty().append('<option value="">All Terms</option>');
                response.terms.forEach(term => {
                    $termSelect.append(`<option value="${term.id}">${term.name}</option>`);
                });
                
                if ($.fn.select2) {
                    $termSelect.trigger('change.select2');
                }
            }
        });
    }
    
    handleDateRangePreset(event) {
        const $preset = $(event.target);
        const range = $preset.val();
        
        if (!range) return;
        
        const ranges = this.getDateRangePresets();
        if (ranges[range]) {
            const { start, end } = ranges[range];
            $('input[name="date_from"]').val(start);
            $('input[name="date_to"]').val(end);
            
            // Clear custom date inputs if using preset
            $('input[name="date_range"]').val(range);
            
            if (this.options.enableRealTimeSearch) {
                this.applyFilters();
            }
        }
    }
    
    handleAmountRangePreset(event) {
        const $preset = $(event.target);
        const range = $preset.val();
        
        if (!range) return;
        
        const ranges = this.getAmountRangePresets();
        if (ranges[range]) {
            const { min, max } = ranges[range];
            $('input[name="amount_min"]').val(min || '');
            $('input[name="amount_max"]').val(max || '');
            
            // Clear custom amount inputs if using preset
            $('input[name="amount_range"]').val(range);
            
            if (this.options.enableRealTimeSearch) {
                this.applyFilters();
            }
        }
    }
    
    getDateRangePresets() {
        const today = new Date();
        const yesterday = new Date(today);
        yesterday.setDate(yesterday.getDate() - 1);
        
        const thisWeekStart = new Date(today);
        thisWeekStart.setDate(today.getDate() - today.getDay());
        
        const thisMonthStart = new Date(today.getFullYear(), today.getMonth(), 1);
        const lastMonthStart = new Date(today.getFullYear(), today.getMonth() - 1, 1);
        const lastMonthEnd = new Date(today.getFullYear(), today.getMonth(), 0);
        
        return {
            'today': {
                start: this.formatDate(today),
                end: this.formatDate(today)
            },
            'yesterday': {
                start: this.formatDate(yesterday),
                end: this.formatDate(yesterday)
            },
            'this_week': {
                start: this.formatDate(thisWeekStart),
                end: this.formatDate(today)
            },
            'this_month': {
                start: this.formatDate(thisMonthStart),
                end: this.formatDate(today)
            },
            'last_month': {
                start: this.formatDate(lastMonthStart),
                end: this.formatDate(lastMonthEnd)
            }
        };
    }
    
    getAmountRangePresets() {
        return {
            '0-1000': { min: 0, max: 1000 },
            '1000-5000': { min: 1000, max: 5000 },
            '5000-10000': { min: 5000, max: 10000 },
            '10000-25000': { min: 10000, max: 25000 },
            '25000-50000': { min: 25000, max: 50000 },
            '50000+': { min: 50000, max: null }
        };
    }
    
    collectFilterData() {
        const data = {};
        
        $('.financial-filter').each(function() {
            const $filter = $(this);
            const name = $filter.attr('name');
            const value = $filter.val();
            
            if (name && value) {
                data[name] = value;
            }
        });
        
        return data;
    }
    
    applyFilters(event) {
        if (event) {
            event.preventDefault();
        }
        
        const filterData = this.collectFilterData();
        const currentUrl = new URL(window.location);
        
        // Update URL parameters
        Object.keys(filterData).forEach(key => {
            if (filterData[key]) {
                currentUrl.searchParams.set(key, filterData[key]);
            } else {
                currentUrl.searchParams.delete(key);
            }
        });
        
        // Remove page parameter when applying new filters
        currentUrl.searchParams.delete('page');
        
        // Navigate to filtered URL
        window.location.href = currentUrl.toString();
    }
    
    clearAllFilters(event) {
        if (event) {
            event.preventDefault();
        }
        
        // Clear all filter inputs
        $('.financial-filter').each(function() {
            const $filter = $(this);
            if ($filter.is('select')) {
                $filter.val('').trigger('change');
            } else {
                $filter.val('');
            }
        });
        
        // Clear select2 selections
        if ($.fn.select2) {
            $('.financial-select-filter').val(null).trigger('change');
        }
        
        // Clear persisted filters
        if (this.options.enableFilterPersistence) {
            this.clearPersistedFilters();
        }
        
        // Apply cleared filters
        this.applyFilters();
    }
    
    exportFilteredResults(event) {
        if (event) {
            event.preventDefault();
        }
        
        const $btn = $(event.target);
        const exportFormat = $btn.data('format') || 'csv';
        const filterData = this.collectFilterData();
        
        // Add export format to data
        filterData.export_format = exportFormat;
        
        // Create form and submit
        const $form = $('<form>', {
            method: 'GET',
            action: $btn.data('export-url') || '/financial/export/'
        });
        
        Object.keys(filterData).forEach(key => {
            $form.append($('<input>', {
                type: 'hidden',
                name: key,
                value: filterData[key]
            }));
        });
        
        $form.appendTo('body').submit().remove();
    }
    
    persistFilters() {
        const filterData = this.collectFilterData();
        const viewName = this.getViewName();
        
        localStorage.setItem(`financial_filters_${viewName}`, JSON.stringify(filterData));
    }
    
    loadPersistedFilters() {
        const viewName = this.getViewName();
        const persistedData = localStorage.getItem(`financial_filters_${viewName}`);
        
        if (persistedData) {
            try {
                const filterData = JSON.parse(persistedData);
                this.applyPersistedFilters(filterData);
            } catch (e) {
                console.warn('Failed to load persisted filters:', e);
            }
        }
    }
    
    applyPersistedFilters(filterData) {
        Object.keys(filterData).forEach(key => {
            const $filter = $(`.financial-filter[name="${key}"]`);
            if ($filter.length && filterData[key]) {
                $filter.val(filterData[key]);
                if ($filter.is('select') && $.fn.select2) {
                    $filter.trigger('change.select2');
                }
            }
        });
    }
    
    clearPersistedFilters() {
        const viewName = this.getViewName();
        localStorage.removeItem(`financial_filters_${viewName}`);
    }
    
    getViewName() {
        return $('body').data('view-name') || 'default';
    }
    
    getSearchEndpoint(searchType) {
        const endpoints = {
            'student_fee': '/financial/ajax/search-student-fees/',
            'payment': '/financial/ajax/search-payments/',
            'scholarship': '/financial/ajax/search-scholarships/',
            'payroll': '/financial/ajax/search-payroll/',
            'transaction': '/financial/ajax/search-transactions/',
            'general': '/financial/ajax/search-student-fees/' // Default fallback
        };
        
        return endpoints[searchType] || '/financial/ajax/search-student-fees/';
    }
    
    getFilterEndpoint(searchType) {
        const endpoints = {
            'student_fee': '/financial/ajax/filter-student-fees/',
            'payment': '/financial/ajax/filter-payments/',
            'scholarship': '/financial/ajax/filter-scholarships/',
            'payroll': '/financial/ajax/filter-payroll/',
            'transaction': '/financial/ajax/filter-transactions/'
        };
        
        return endpoints[searchType] || '/financial/ajax/filter-student-fees/';
    }
    
    getAutoCompleteEndpoint(searchType) {
        const endpoints = {
            'student': '/financial/ajax/autocomplete-students/',
            'teacher': '/financial/ajax/autocomplete-teachers/',
            'reference': '/financial/ajax/autocomplete-references/',
            'general': '/financial/ajax/autocomplete-general/'
        };
        
        return endpoints[searchType] || '/financial/ajax/autocomplete/';
    }
    
    handleSearchResponse(response, targetContainer) {
        const $container = $(targetContainer);
        
        if (response.html) {
            $container.html(response.html);
        } else if (response.results) {
            this.renderSearchResults(response.results, $container);
        }
        
        // Update result count
        if (response.total_count !== undefined) {
            $('.results-count').text(response.total_count);
        }
        
        // Show "no results" message if needed
        if (response.results && response.results.length === 0) {
            $container.html('<div class="no-results">No results found matching your criteria.</div>');
        }
    }
    
    renderSearchResults(results, $container) {
        if (!results || results.length === 0) {
            $container.html('<div class="no-results">No results found matching your criteria.</div>');
            return;
        }
        
        // Detect result type based on first result structure
        const firstResult = results[0];
        let html = '';
        
        if (firstResult.student_name) {
            // Student fee results
            html = this.renderStudentFeeResults(results);
        } else if (firstResult.payment_method) {
            // Payment results
            html = this.renderPaymentResults(results);
        } else if (firstResult.scholarship_type) {
            // Scholarship results
            html = this.renderScholarshipResults(results);
        } else if (firstResult.teacher_name) {
            // Payroll results
            html = this.renderPayrollResults(results);
        } else if (firstResult.transaction_type) {
            // Transaction results
            html = this.renderTransactionResults(results);
        } else {
            // Generic results
            html = results.map(item => `
                <div class="search-result-item">
                    <div class="result-title">${item.title || item.name || 'Unknown'}</div>
                    <div class="result-details">${item.details || ''}</div>
                </div>
            `).join('');
        }
        
        $container.html(html);
    }
    
    renderStudentFeeResults(results) {
        return results.map(fee => `
            <div class="search-result-item" data-id="${fee.id}">
                <div class="result-header">
                    <div class="result-title">${fee.student_name}</div>
                    <div class="result-status status-${fee.status_class}">${fee.status}</div>
                </div>
                <div class="result-details">
                    <div class="detail-row">
                        <span class="detail-label">Student ID:</span>
                        <span class="detail-value">${fee.student_id}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Class:</span>
                        <span class="detail-value">${fee.class_name}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Fee Structure:</span>
                        <span class="detail-value">${fee.fee_structure}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Total:</span>
                        <span class="detail-value">₦${fee.total_amount.toLocaleString()}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Paid:</span>
                        <span class="detail-value">₦${fee.paid_amount.toLocaleString()}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Balance:</span>
                        <span class="detail-value balance">₦${fee.balance_amount.toLocaleString()}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Due Date:</span>
                        <span class="detail-value">${fee.due_date}</span>
                    </div>
                </div>
            </div>
        `).join('');
    }
    
    renderPaymentResults(results) {
        return results.map(payment => `
            <div class="search-result-item" data-id="${payment.id}">
                <div class="result-header">
                    <div class="result-title">${payment.student_name}</div>
                    <div class="result-amount">₦${payment.amount.toLocaleString()}</div>
                </div>
                <div class="result-details">
                    <div class="detail-row">
                        <span class="detail-label">Student ID:</span>
                        <span class="detail-value">${payment.student_id}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Class:</span>
                        <span class="detail-value">${payment.class_name}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Payment Method:</span>
                        <span class="detail-value">${payment.payment_method}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Reference:</span>
                        <span class="detail-value">${payment.reference_number || 'N/A'}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Date:</span>
                        <span class="detail-value">${payment.payment_date}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Received By:</span>
                        <span class="detail-value">${payment.received_by || 'N/A'}</span>
                    </div>
                </div>
            </div>
        `).join('');
    }
    
    renderScholarshipResults(results) {
        return results.map(scholarship => `
            <div class="search-result-item" data-id="${scholarship.id}">
                <div class="result-header">
                    <div class="result-title">${scholarship.name}</div>
                    <div class="result-status ${scholarship.is_active ? 'status-active' : 'status-inactive'}">
                        ${scholarship.is_active ? 'Active' : 'Inactive'}
                    </div>
                </div>
                <div class="result-details">
                    <div class="detail-row">
                        <span class="detail-label">Type:</span>
                        <span class="detail-value">${scholarship.scholarship_type}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Amount:</span>
                        <span class="detail-value">
                            ${scholarship.amount ? '₦' + scholarship.amount.toLocaleString() : 
                              scholarship.percentage ? scholarship.percentage + '%' : 'N/A'}
                        </span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Recipients:</span>
                        <span class="detail-value">${scholarship.active_recipients}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Total Awarded:</span>
                        <span class="detail-value">₦${scholarship.total_awarded.toLocaleString()}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Academic Year:</span>
                        <span class="detail-value">${scholarship.academic_year}</span>
                    </div>
                    ${scholarship.description ? `
                    <div class="detail-row">
                        <span class="detail-label">Description:</span>
                        <span class="detail-value">${scholarship.description}</span>
                    </div>
                    ` : ''}
                </div>
            </div>
        `).join('');
    }
    
    renderPayrollResults(results) {
        return results.map(payroll => `
            <div class="search-result-item" data-id="${payroll.id}">
                <div class="result-header">
                    <div class="result-title">${payroll.teacher_name}</div>
                    <div class="result-status ${payroll.is_paid ? 'status-paid' : 'status-unpaid'}">
                        ${payroll.is_paid ? 'Paid' : 'Unpaid'}
                    </div>
                </div>
                <div class="result-details">
                    <div class="detail-row">
                        <span class="detail-label">Employee ID:</span>
                        <span class="detail-value">${payroll.employee_id}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Month:</span>
                        <span class="detail-value">${payroll.month}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Gross Salary:</span>
                        <span class="detail-value">₦${payroll.gross_salary.toLocaleString()}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Net Salary:</span>
                        <span class="detail-value">₦${payroll.net_salary.toLocaleString()}</span>
                    </div>
                    ${payroll.payment_date ? `
                    <div class="detail-row">
                        <span class="detail-label">Payment Date:</span>
                        <span class="detail-value">${payroll.payment_date}</span>
                    </div>
                    ` : ''}
                </div>
            </div>
        `).join('');
    }
    
    renderTransactionResults(results) {
        return results.map(transaction => `
            <div class="search-result-item" data-id="${transaction.id}">
                <div class="result-header">
                    <div class="result-title">${transaction.description}</div>
                    <div class="result-amount ${transaction.transaction_type.toLowerCase()}">
                        ${transaction.transaction_type === 'Income' ? '+' : '-'}₦${transaction.amount.toLocaleString()}
                    </div>
                </div>
                <div class="result-details">
                    <div class="detail-row">
                        <span class="detail-label">Type:</span>
                        <span class="detail-value">${transaction.transaction_type}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Category:</span>
                        <span class="detail-value">${transaction.category}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Reference:</span>
                        <span class="detail-value">${transaction.reference_number || 'N/A'}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Date:</span>
                        <span class="detail-value">${transaction.transaction_date}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Created By:</span>
                        <span class="detail-value">${transaction.created_by || 'N/A'}</span>
                    </div>
                </div>
            </div>
        `).join('');
    }
    
    highlightSearchResults(searchTerm) {
        if (!searchTerm) return;
        
        $('.search-results').find('*').contents().filter(function() {
            return this.nodeType === 3; // Text nodes only
        }).each(function() {
            const text = this.textContent;
            const regex = new RegExp(`(${searchTerm})`, 'gi');
            if (regex.test(text)) {
                const highlighted = text.replace(regex, '<mark>$1</mark>');
                $(this).replaceWith(highlighted);
            }
        });
    }
    
    handleSearchError(error, targetContainer) {
        const $container = $(targetContainer);
        $container.html(`
            <div class="search-error">
                <i class="fas fa-exclamation-triangle"></i>
                <p>An error occurred while searching. Please try again.</p>
            </div>
        `);
        console.error('Search error:', error);
    }
    
    showLoadingIndicator(targetContainer) {
        const $container = $(targetContainer);
        $container.addClass('loading').prepend(`
            <div class="loading-indicator">
                <i class="fas fa-spinner fa-spin"></i>
                <span>Searching...</span>
            </div>
        `);
    }
    
    hideLoadingIndicator(targetContainer) {
        const $container = $(targetContainer);
        $container.removeClass('loading').find('.loading-indicator').remove();
    }
    
    formatAmountInput($input) {
        let value = $input.val().replace(/[^\d.]/g, '');
        
        // Ensure only one decimal point
        const parts = value.split('.');
        if (parts.length > 2) {
            value = parts[0] + '.' + parts.slice(1).join('');
        }
        
        // Limit decimal places to 2
        if (parts[1] && parts[1].length > 2) {
            value = parts[0] + '.' + parts[1].substring(0, 2);
        }
        
        $input.val(value);
    }
    
    formatDate(date) {
        return date.toISOString().split('T')[0];
    }
}

// Auto-complete endpoints for AJAX requests
class FinancialAutoComplete {
    static async getStudentSuggestions(term) {
        try {
            const response = await $.ajax({
                url: '/financial/ajax/autocomplete-students/',
                method: 'GET',
                data: { term: term, limit: 10 }
            });
            return response.suggestions || [];
        } catch (error) {
            console.error('Error fetching student suggestions:', error);
            return [];
        }
    }
    
    static async getTeacherSuggestions(term) {
        try {
            const response = await $.ajax({
                url: '/financial/ajax/autocomplete-teachers/',
                method: 'GET',
                data: { term: term, limit: 10 }
            });
            return response.suggestions || [];
        } catch (error) {
            console.error('Error fetching teacher suggestions:', error);
            return [];
        }
    }
    
    static async getReferenceSuggestions(term) {
        try {
            const response = await $.ajax({
                url: '/financial/ajax/autocomplete-references/',
                method: 'GET',
                data: { term: term, limit: 10 }
            });
            return response.suggestions || [];
        } catch (error) {
            console.error('Error fetching reference suggestions:', error);
            return [];
        }
    }
}

// Initialize the filter system when document is ready
$(document).ready(function() {
    // Initialize the main filter system
    window.financialFilterSystem = new FinancialFilterSystem({
        searchDelay: 300,
        minSearchLength: 2,
        maxSuggestions: 10,
        enableAutoComplete: true,
        enableRealTimeSearch: true,
        enableFilterPersistence: true
    });
    
    // Add custom CSS for loading states and highlights
    if (!$('#financial-filter-styles').length) {
        $('<style id="financial-filter-styles">').text(`
            .loading-indicator {
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
                color: #666;
            }
            .loading-indicator i {
                margin-right: 8px;
            }
            .search-results.loading {
                opacity: 0.6;
                pointer-events: none;
            }
            .search-result-item {
                padding: 10px;
                border-bottom: 1px solid #eee;
                cursor: pointer;
            }
            .search-result-item:hover {
                background-color: #f5f5f5;
            }
            .no-results {
                text-align: center;
                padding: 40px;
                color: #666;
            }
            .search-error {
                text-align: center;
                padding: 40px;
                color: #d32f2f;
            }
            mark {
                background-color: #fff3cd;
                padding: 0 2px;
                border-radius: 2px;
            }
            .filter-summary {
                background: #e3f2fd;
                border: 1px solid #bbdefb;
                border-radius: 4px;
                padding: 8px 12px;
                margin-bottom: 16px;
                font-size: 14px;
            }
            .filter-tag {
                display: inline-block;
                background: #2196f3;
                color: white;
                padding: 2px 8px;
                border-radius: 12px;
                margin: 2px;
                font-size: 12px;
            }
            .filter-tag .remove {
                margin-left: 4px;
                cursor: pointer;
                opacity: 0.8;
            }
            .filter-tag .remove:hover {
                opacity: 1;
            }
            .search-result-item {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                margin-bottom: 12px;
                background: white;
                transition: all 0.2s ease;
            }
            .search-result-item:hover {
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                border-color: #2196f3;
            }
            .result-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 12px 16px;
                border-bottom: 1px solid #f0f0f0;
                background: #fafafa;
                border-radius: 8px 8px 0 0;
            }
            .result-title {
                font-weight: 600;
                color: #333;
                font-size: 16px;
            }
            .result-status {
                padding: 4px 12px;
                border-radius: 16px;
                font-size: 12px;
                font-weight: 500;
                text-transform: uppercase;
            }
            .result-status.status-paid,
            .result-status.status-active {
                background: #e8f5e8;
                color: #2e7d32;
            }
            .result-status.status-unpaid,
            .result-status.status-pending {
                background: #fff3e0;
                color: #f57c00;
            }
            .result-status.status-overdue {
                background: #ffebee;
                color: #d32f2f;
            }
            .result-status.status-partial {
                background: #e3f2fd;
                color: #1976d2;
            }
            .result-status.status-inactive {
                background: #f5f5f5;
                color: #757575;
            }
            .result-amount {
                font-weight: 600;
                font-size: 16px;
            }
            .result-amount.income {
                color: #2e7d32;
            }
            .result-amount.expense {
                color: #d32f2f;
            }
            .result-details {
                padding: 16px;
            }
            .detail-row {
                display: flex;
                justify-content: space-between;
                margin-bottom: 8px;
                padding: 4px 0;
            }
            .detail-row:last-child {
                margin-bottom: 0;
            }
            .detail-label {
                font-weight: 500;
                color: #666;
                min-width: 120px;
            }
            .detail-value {
                color: #333;
                text-align: right;
                flex: 1;
            }
            .detail-value.balance {
                font-weight: 600;
                color: #d32f2f;
            }
            .search-results-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 16px 0;
                border-bottom: 1px solid #e0e0e0;
                margin-bottom: 16px;
            }
            .results-count {
                font-weight: 500;
                color: #666;
            }
            .results-actions {
                display: flex;
                gap: 8px;
            }
            .btn-sm {
                padding: 4px 12px;
                font-size: 12px;
                border-radius: 4px;
            }
            .auto-complete-dropdown {
                position: absolute;
                top: 100%;
                left: 0;
                right: 0;
                background: white;
                border: 1px solid #ddd;
                border-top: none;
                border-radius: 0 0 4px 4px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                z-index: 1000;
                max-height: 300px;
                overflow-y: auto;
            }
            .auto-complete-item {
                padding: 12px 16px;
                cursor: pointer;
                border-bottom: 1px solid #f0f0f0;
            }
            .auto-complete-item:hover {
                background: #f5f5f5;
            }
            .auto-complete-item:last-child {
                border-bottom: none;
            }
            .auto-complete-item .item-title {
                font-weight: 500;
                color: #333;
            }
            .auto-complete-item .item-details {
                font-size: 12px;
                color: #666;
                margin-top: 4px;
            }
        `).appendTo('head');
    }
});