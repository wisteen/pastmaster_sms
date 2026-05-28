/**
 * Financial Charts JavaScript Module
 * Provides Chart.js integration for financial data visualization
 * 
 * Requirements: 6.1, 6.2, 6.3, 6.4, 6.5
 */

class FinancialCharts {
    constructor() {
        this.chartColors = {
            primary: '#0d6efd',
            secondary: '#6c757d',
            success: '#198754',
            danger: '#dc3545',
            warning: '#ffc107',
            info: '#0dcaf0',
            light: '#f8f9fa',
            dark: '#212529'
        };
        
        this.chartInstances = {};
        this.defaultOptions = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top'
                }
            }
        };
    }

    /**
     * Initialize all charts on the page
     */
    initializeCharts() {
        // Fee Collection Trends Chart
        if (document.getElementById('feeCollectionChart')) {
            this.createFeeCollectionChart();
        }
        
        // Payment Status Distribution Chart
        if (document.getElementById('paymentStatusChart')) {
            this.createPaymentStatusChart();
        }
        
        // Income vs Expenses Chart
        if (document.getElementById('incomeExpenseChart')) {
            this.createIncomeExpenseChart();
        }
        
        // Expense Breakdown Chart
        if (document.getElementById('expenseBreakdownChart')) {
            this.createExpenseBreakdownChart();
        }
        
        // Scholarship Distribution Chart
        if (document.getElementById('scholarshipChart')) {
            this.createScholarshipChart();
        }
        
        // Class-wise Fee Collection Chart
        if (document.getElementById('classWiseChart')) {
            this.createClassWiseChart();
        }
    }

    /**
     * Create Fee Collection Trends Line Chart
     */
    createFeeCollectionChart(data = null) {
        const ctx = document.getElementById('feeCollectionChart');
        if (!ctx) return;

        const chartData = data || window.chartData?.fee_trends || {
            labels: [],
            data: []
        };

        if (this.chartInstances.feeCollection) {
            this.chartInstances.feeCollection.destroy();
        }

        this.chartInstances.feeCollection = new Chart(ctx, {
            type: 'line',
            data: {
                labels: chartData.labels,
                datasets: [{
                    label: 'Fee Collections ($)',
                    data: chartData.data,
                    borderColor: this.chartColors.primary,
                    backgroundColor: this.chartColors.primary + '20',
                    tension: 0.4,
                    fill: true,
                    pointBackgroundColor: this.chartColors.primary,
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2,
                    pointRadius: 4
                }]
            },
            options: {
                ...this.defaultOptions,
                plugins: {
                    ...this.defaultOptions.plugins,
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return 'Collections: $' + context.parsed.y.toLocaleString();
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return '$' + value.toLocaleString();
                            }
                        }
                    }
                },
                interaction: {
                    intersect: false,
                    mode: 'index'
                }
            }
        });
    }

    /**
     * Create Payment Status Doughnut Chart
     */
    createPaymentStatusChart(data = null) {
        const ctx = document.getElementById('paymentStatusChart');
        if (!ctx) return;

        const chartData = data || window.chartData?.payment_status || {
            labels: [],
            data: []
        };

        if (this.chartInstances.paymentStatus) {
            this.chartInstances.paymentStatus.destroy();
        }

        this.chartInstances.paymentStatus = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: chartData.labels,
                datasets: [{
                    data: chartData.data,
                    backgroundColor: [
                        this.chartColors.success,
                        this.chartColors.warning,
                        this.chartColors.danger,
                        this.chartColors.info
                    ],
                    borderWidth: 2,
                    borderColor: '#fff'
                }]
            },
            options: {
                ...this.defaultOptions,
                plugins: {
                    ...this.defaultOptions.plugins,
                    legend: {
                        position: 'bottom'
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = ((context.parsed / total) * 100).toFixed(1);
                                return context.label + ': ' + context.parsed + ' (' + percentage + '%)';
                            }
                        }
                    }
                }
            }
        });
    }

    /**
     * Create Income vs Expenses Bar Chart
     */
    createIncomeExpenseChart(data = null) {
        const ctx = document.getElementById('incomeExpenseChart');
        if (!ctx) return;

        const chartData = data || window.chartData?.income_expense || {
            labels: [],
            income: [],
            expenses: [],
            profit: []
        };

        if (this.chartInstances.incomeExpense) {
            this.chartInstances.incomeExpense.destroy();
        }

        this.chartInstances.incomeExpense = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: chartData.labels,
                datasets: [{
                    label: 'Income',
                    data: chartData.income,
                    backgroundColor: this.chartColors.success,
                    borderColor: this.chartColors.success,
                    borderWidth: 1
                }, {
                    label: 'Expenses',
                    data: chartData.expenses,
                    backgroundColor: this.chartColors.danger,
                    borderColor: this.chartColors.danger,
                    borderWidth: 1
                }, {
                    label: 'Net Profit',
                    data: chartData.profit,
                    backgroundColor: this.chartColors.primary,
                    borderColor: this.chartColors.primary,
                    borderWidth: 2,
                    type: 'line',
                    tension: 0.4,
                    pointBackgroundColor: this.chartColors.primary,
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2,
                    pointRadius: 4
                }]
            },
            options: {
                ...this.defaultOptions,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return '$' + value.toLocaleString();
                            }
                        }
                    }
                },
                plugins: {
                    ...this.defaultOptions.plugins,
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return context.dataset.label + ': $' + context.parsed.y.toLocaleString();
                            }
                        }
                    }
                }
            }
        });
    }

    /**
     * Create Expense Breakdown Pie Chart
     */
    createExpenseBreakdownChart(data = null) {
        const ctx = document.getElementById('expenseBreakdownChart');
        if (!ctx) return;

        const chartData = data || window.chartData?.expense_breakdown || {
            labels: [],
            data: []
        };

        if (this.chartInstances.expenseBreakdown) {
            this.chartInstances.expenseBreakdown.destroy();
        }

        // Generate colors for each category
        const colors = this.generateColors(chartData.labels.length);

        this.chartInstances.expenseBreakdown = new Chart(ctx, {
            type: 'pie',
            data: {
                labels: chartData.labels,
                datasets: [{
                    data: chartData.data,
                    backgroundColor: colors,
                    borderWidth: 2,
                    borderColor: '#fff'
                }]
            },
            options: {
                ...this.defaultOptions,
                plugins: {
                    ...this.defaultOptions.plugins,
                    legend: {
                        position: 'bottom'
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = ((context.parsed / total) * 100).toFixed(1);
                                return context.label + ': $' + context.parsed.toLocaleString() + ' (' + percentage + '%)';
                            }
                        }
                    }
                }
            }
        });
    }

    /**
     * Create Scholarship Distribution Chart
     */
    createScholarshipChart(data = null) {
        const ctx = document.getElementById('scholarshipChart');
        if (!ctx) return;

        const chartData = data || window.chartData?.scholarship_distribution || {
            labels: [],
            amounts: [],
            counts: []
        };

        if (this.chartInstances.scholarship) {
            this.chartInstances.scholarship.destroy();
        }

        this.chartInstances.scholarship = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: chartData.labels,
                datasets: [{
                    label: 'Amount ($)',
                    data: chartData.amounts,
                    backgroundColor: this.chartColors.info,
                    borderColor: this.chartColors.info,
                    borderWidth: 1,
                    yAxisID: 'y'
                }, {
                    label: 'Recipients',
                    data: chartData.counts,
                    backgroundColor: this.chartColors.warning,
                    borderColor: this.chartColors.warning,
                    borderWidth: 1,
                    yAxisID: 'y1'
                }]
            },
            options: {
                ...this.defaultOptions,
                scales: {
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return '$' + value.toLocaleString();
                            }
                        }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        beginAtZero: true,
                        grid: {
                            drawOnChartArea: false,
                        },
                        ticks: {
                            callback: function(value) {
                                return value + ' recipients';
                            }
                        }
                    }
                },
                plugins: {
                    ...this.defaultOptions.plugins,
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                if (context.datasetIndex === 0) {
                                    return 'Amount: $' + context.parsed.y.toLocaleString();
                                } else {
                                    return 'Recipients: ' + context.parsed.y;
                                }
                            }
                        }
                    }
                }
            }
        });
    }

    /**
     * Create Class-wise Fee Collection Chart
     */
    createClassWiseChart(data = null) {
        const ctx = document.getElementById('classWiseChart');
        if (!ctx) return;

        const chartData = data || window.chartData?.class_wise || {
            labels: [],
            collection_rates: [],
            total_fees: []
        };

        if (this.chartInstances.classWise) {
            this.chartInstances.classWise.destroy();
        }

        this.chartInstances.classWise = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: chartData.labels,
                datasets: [{
                    label: 'Collection Rate (%)',
                    data: chartData.collection_rates,
                    backgroundColor: this.chartColors.success,
                    borderColor: this.chartColors.success,
                    borderWidth: 1,
                    yAxisID: 'y'
                }, {
                    label: 'Total Fees ($)',
                    data: chartData.total_fees,
                    backgroundColor: this.chartColors.primary,
                    borderColor: this.chartColors.primary,
                    borderWidth: 1,
                    yAxisID: 'y1',
                    type: 'line',
                    tension: 0.4
                }]
            },
            options: {
                ...this.defaultOptions,
                scales: {
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        beginAtZero: true,
                        max: 100,
                        ticks: {
                            callback: function(value) {
                                return value + '%';
                            }
                        }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        beginAtZero: true,
                        grid: {
                            drawOnChartArea: false,
                        },
                        ticks: {
                            callback: function(value) {
                                return '$' + value.toLocaleString();
                            }
                        }
                    }
                }
            }
        });
    }

    /**
     * Update chart data dynamically
     */
    updateChart(chartName, newData) {
        const chart = this.chartInstances[chartName];
        if (!chart) return;

        chart.data = newData;
        chart.update('active');
    }

    /**
     * Refresh chart data from server
     */
    async refreshChartData(chartType, params = {}) {
        try {
            const queryString = new URLSearchParams(params).toString();
            const response = await fetch(`/financial/analytics/data/${chartType}/?${queryString}`);
            const data = await response.json();
            
            switch (chartType) {
                case 'fee_trends':
                    this.createFeeCollectionChart(data);
                    break;
                case 'payment_status':
                    this.createPaymentStatusChart(data);
                    break;
                case 'income_expense':
                    this.createIncomeExpenseChart(data);
                    break;
                case 'expense_breakdown':
                    this.createExpenseBreakdownChart(data);
                    break;
                case 'scholarship_distribution':
                    this.createScholarshipChart(data);
                    break;
                case 'class_wise':
                    this.createClassWiseChart(data);
                    break;
            }
        } catch (error) {
            console.error('Failed to refresh chart data:', error);
        }
    }

    /**
     * Export chart as image
     */
    exportChart(chartName, filename = null) {
        const chart = this.chartInstances[chartName];
        if (!chart) return;

        const url = chart.toBase64Image();
        const link = document.createElement('a');
        link.download = filename || `${chartName}_chart.png`;
        link.href = url;
        link.click();
    }

    /**
     * Generate colors for charts
     */
    generateColors(count) {
        const baseColors = Object.values(this.chartColors);
        const colors = [];
        
        for (let i = 0; i < count; i++) {
            colors.push(baseColors[i % baseColors.length]);
        }
        
        return colors;
    }

    /**
     * Destroy all chart instances
     */
    destroyAllCharts() {
        Object.values(this.chartInstances).forEach(chart => {
            if (chart) chart.destroy();
        });
        this.chartInstances = {};
    }

    /**
     * Resize all charts
     */
    resizeCharts() {
        Object.values(this.chartInstances).forEach(chart => {
            if (chart) chart.resize();
        });
    }
}

// Global instance
window.FinancialCharts = FinancialCharts;

// Auto-initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    if (typeof Chart !== 'undefined') {
        window.financialCharts = new FinancialCharts();
        window.financialCharts.initializeCharts();
        
        // Handle window resize
        window.addEventListener('resize', function() {
            window.financialCharts.resizeCharts();
        });
    }
});

// Export functions for global access
window.refreshAnalytics = function() {
    if (window.financialCharts) {
        window.financialCharts.destroyAllCharts();
        window.financialCharts.initializeCharts();
    }
};

window.exportChart = function(chartName, filename) {
    if (window.financialCharts) {
        window.financialCharts.exportChart(chartName, filename);
    }
};

window.updateChartPeriod = function(chartType, months) {
    if (window.financialCharts) {
        window.financialCharts.refreshChartData(chartType, { months: months });
    }
};