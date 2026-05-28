"""
Enhanced Notification Tracking Service

This module provides advanced tracking capabilities for the notification system,
including delivery status monitoring, retry mechanisms, and detailed analytics.
"""

from django.db.models import Count, Q, Avg, F
from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging

from .models import NotificationLog, NotificationTemplate
from .services_notification import NotificationService

logger = logging.getLogger(__name__)


class NotificationTrackingService:
    """Service for tracking and analyzing notification delivery"""
    
    def __init__(self):
        self.notification_service = NotificationService()
    
    def get_delivery_statistics(self, days: int = 30) -> Dict[str, Any]:
        """Get comprehensive delivery statistics for the specified period"""
        start_date = timezone.now() - timedelta(days=days)
        
        # Basic statistics
        total_notifications = NotificationLog.objects.filter(created_at__gte=start_date).count()
        
        if total_notifications == 0:
            return {
                'total_notifications': 0,
                'success_rate': 0,
                'failure_rate': 0,
                'pending_rate': 0,
                'average_delivery_time': 0,
                'by_status': {},
                'by_type': {},
                'daily_breakdown': [],
                'retry_statistics': {},
                'template_performance': []
            }
        
        # Status breakdown
        status_stats = NotificationLog.objects.filter(
            created_at__gte=start_date
        ).values('status').annotate(count=Count('id')).order_by('-count')
        
        status_breakdown = {stat['status']: stat['count'] for stat in status_stats}
        
        # Type breakdown
        type_stats = NotificationLog.objects.filter(
            created_at__gte=start_date
        ).values('notification_type').annotate(
            total=Count('id'),
            sent=Count('id', filter=Q(status='sent')),
            failed=Count('id', filter=Q(status='failed')),
            pending=Count('id', filter=Q(status='pending'))
        ).order_by('-total')
        
        # Daily breakdown
        daily_stats = []
        for i in range(days):
            date = (timezone.now() - timedelta(days=i)).date()
            day_stats = NotificationLog.objects.filter(
                created_at__date=date
            ).aggregate(
                total=Count('id'),
                sent=Count('id', filter=Q(status='sent')),
                failed=Count('id', filter=Q(status='failed')),
                pending=Count('id', filter=Q(status='pending'))
            )
            
            daily_stats.append({
                'date': date.strftime('%Y-%m-%d'),
                'total': day_stats['total'],
                'sent': day_stats['sent'],
                'failed': day_stats['failed'],
                'pending': day_stats['pending'],
                'success_rate': (day_stats['sent'] / day_stats['total'] * 100) if day_stats['total'] > 0 else 0
            })
        
        # Retry statistics
        retry_stats = NotificationLog.objects.filter(
            created_at__gte=start_date,
            retry_count__gt=0
        ).aggregate(
            total_retries=Count('id'),
            avg_retries=Avg('retry_count'),
            max_retries=Count('id', filter=Q(retry_count__gte=3))
        )
        
        # Average delivery time (for sent notifications)
        sent_notifications = NotificationLog.objects.filter(
            created_at__gte=start_date,
            status='sent',
            sent_at__isnull=False
        )
        
        avg_delivery_time = 0
        if sent_notifications.exists():
            delivery_times = []
            for notification in sent_notifications:
                delivery_time = (notification.sent_at - notification.created_at).total_seconds()
                delivery_times.append(delivery_time)
            
            if delivery_times:
                avg_delivery_time = sum(delivery_times) / len(delivery_times)
        
        # Template performance
        template_performance = []
        for template in NotificationTemplate.objects.filter(is_active=True):
            template_logs = NotificationLog.objects.filter(
                created_at__gte=start_date,
                notification_type=template.template_type
            )
            
            if template_logs.exists():
                total = template_logs.count()
                sent = template_logs.filter(status='sent').count()
                failed = template_logs.filter(status='failed').count()
                
                template_performance.append({
                    'template_name': template.name,
                    'template_type': template.template_type,
                    'total_sent': total,
                    'success_count': sent,
                    'failure_count': failed,
                    'success_rate': (sent / total * 100) if total > 0 else 0
                })
        
        # Calculate rates
        sent_count = status_breakdown.get('sent', 0)
        failed_count = status_breakdown.get('failed', 0)
        pending_count = status_breakdown.get('pending', 0)
        
        return {
            'total_notifications': total_notifications,
            'success_rate': (sent_count / total_notifications * 100) if total_notifications > 0 else 0,
            'failure_rate': (failed_count / total_notifications * 100) if total_notifications > 0 else 0,
            'pending_rate': (pending_count / total_notifications * 100) if total_notifications > 0 else 0,
            'average_delivery_time': avg_delivery_time,
            'by_status': status_breakdown,
            'by_type': list(type_stats),
            'daily_breakdown': daily_stats,
            'retry_statistics': retry_stats,
            'template_performance': template_performance
        }
    
    def get_failed_notifications_analysis(self) -> Dict[str, Any]:
        """Analyze failed notifications to identify common issues"""
        failed_notifications = NotificationLog.objects.filter(status='failed')
        
        if not failed_notifications.exists():
            return {
                'total_failed': 0,
                'common_errors': [],
                'failure_by_type': [],
                'retryable_count': 0,
                'recommendations': []
            }
        
        # Common error analysis
        error_analysis = {}
        for notification in failed_notifications:
            error_msg = notification.error_message or 'Unknown error'
            # Categorize errors
            if 'email' in error_msg.lower():
                category = 'Email Delivery'
            elif 'template' in error_msg.lower():
                category = 'Template Error'
            elif 'timeout' in error_msg.lower():
                category = 'Timeout'
            elif 'connection' in error_msg.lower():
                category = 'Connection Error'
            else:
                category = 'Other'
            
            if category not in error_analysis:
                error_analysis[category] = {'count': 0, 'examples': []}
            
            error_analysis[category]['count'] += 1
            if len(error_analysis[category]['examples']) < 3:
                error_analysis[category]['examples'].append(error_msg[:100])
        
        # Failure by type
        failure_by_type = list(failed_notifications.values('notification_type').annotate(
            count=Count('id')
        ).order_by('-count'))
        
        # Retryable notifications
        retryable_count = failed_notifications.filter(
            retry_count__lt=F('max_retries')
        ).count()
        
        # Generate recommendations
        recommendations = []
        if error_analysis.get('Email Delivery', {}).get('count', 0) > 0:
            recommendations.append("Check email server configuration and credentials")
        if error_analysis.get('Template Error', {}).get('count', 0) > 0:
            recommendations.append("Review notification templates for syntax errors")
        if error_analysis.get('Timeout', {}).get('count', 0) > 0:
            recommendations.append("Consider increasing email timeout settings")
        if retryable_count > 0:
            recommendations.append(f"Retry {retryable_count} failed notifications that haven't exceeded max retries")
        
        return {
            'total_failed': failed_notifications.count(),
            'common_errors': [
                {'category': category, 'count': data['count'], 'examples': data['examples']}
                for category, data in error_analysis.items()
            ],
            'failure_by_type': failure_by_type,
            'retryable_count': retryable_count,
            'recommendations': recommendations
        }
    
    def get_notification_health_score(self) -> Dict[str, Any]:
        """Calculate overall notification system health score"""
        # Get statistics for the last 7 days
        stats = self.get_delivery_statistics(days=7)
        
        # Calculate health score based on multiple factors
        success_rate = stats['success_rate']
        failure_rate = stats['failure_rate']
        avg_delivery_time = stats['average_delivery_time']
        
        # Health score calculation (0-100)
        health_score = 0
        
        # Success rate component (60% of score)
        if success_rate >= 95:
            health_score += 60
        elif success_rate >= 90:
            health_score += 50
        elif success_rate >= 80:
            health_score += 40
        elif success_rate >= 70:
            health_score += 30
        else:
            health_score += 20
        
        # Delivery time component (20% of score)
        if avg_delivery_time <= 5:  # 5 seconds or less
            health_score += 20
        elif avg_delivery_time <= 30:  # 30 seconds or less
            health_score += 15
        elif avg_delivery_time <= 60:  # 1 minute or less
            health_score += 10
        else:
            health_score += 5
        
        # Failure rate component (20% of score)
        if failure_rate <= 1:
            health_score += 20
        elif failure_rate <= 5:
            health_score += 15
        elif failure_rate <= 10:
            health_score += 10
        else:
            health_score += 5
        
        # Determine health status
        if health_score >= 90:
            health_status = 'Excellent'
            health_color = 'success'
        elif health_score >= 75:
            health_status = 'Good'
            health_color = 'info'
        elif health_score >= 60:
            health_status = 'Fair'
            health_color = 'warning'
        else:
            health_status = 'Poor'
            health_color = 'danger'
        
        return {
            'health_score': health_score,
            'health_status': health_status,
            'health_color': health_color,
            'success_rate': success_rate,
            'failure_rate': failure_rate,
            'avg_delivery_time': avg_delivery_time,
            'total_notifications': stats['total_notifications']
        }
    
    def schedule_notification_cleanup(self, days_old: int = 90) -> Dict[str, int]:
        """Clean up old notification logs to maintain performance"""
        cutoff_date = timezone.now() - timedelta(days=days_old)
        
        # Count notifications to be deleted
        old_notifications = NotificationLog.objects.filter(created_at__lt=cutoff_date)
        count_to_delete = old_notifications.count()
        
        if count_to_delete == 0:
            return {'deleted': 0, 'message': 'No old notifications to clean up'}
        
        # Keep successful notifications for a shorter period, failed ones longer for analysis
        successful_cutoff = timezone.now() - timedelta(days=days_old // 2)
        failed_cutoff = timezone.now() - timedelta(days=days_old)
        
        # Delete old successful notifications
        deleted_successful = NotificationLog.objects.filter(
            created_at__lt=successful_cutoff,
            status='sent'
        ).delete()[0]
        
        # Delete very old failed notifications
        deleted_failed = NotificationLog.objects.filter(
            created_at__lt=failed_cutoff,
            status='failed'
        ).delete()[0]
        
        total_deleted = deleted_successful + deleted_failed
        
        logger.info(f"Cleaned up {total_deleted} old notification logs")
        
        return {
            'deleted': total_deleted,
            'deleted_successful': deleted_successful,
            'deleted_failed': deleted_failed,
            'message': f'Successfully cleaned up {total_deleted} old notification logs'
        }
    
    def get_notification_trends(self, days: int = 30) -> Dict[str, Any]:
        """Get notification trends and patterns"""
        stats = self.get_delivery_statistics(days=days)
        
        # Calculate trends
        daily_data = stats['daily_breakdown']
        if len(daily_data) < 2:
            return {'trends': {}, 'patterns': {}}
        
        # Success rate trend
        recent_success_rate = sum(day['success_rate'] for day in daily_data[:7]) / 7
        older_success_rate = sum(day['success_rate'] for day in daily_data[7:14]) / 7 if len(daily_data) >= 14 else recent_success_rate
        
        success_trend = 'improving' if recent_success_rate > older_success_rate else 'declining' if recent_success_rate < older_success_rate else 'stable'
        
        # Volume trend
        recent_volume = sum(day['total'] for day in daily_data[:7])
        older_volume = sum(day['total'] for day in daily_data[7:14]) if len(daily_data) >= 14 else recent_volume
        
        volume_trend = 'increasing' if recent_volume > older_volume else 'decreasing' if recent_volume < older_volume else 'stable'
        
        # Peak days analysis
        peak_day = max(daily_data, key=lambda x: x['total'])
        
        return {
            'trends': {
                'success_rate': {
                    'trend': success_trend,
                    'recent_rate': recent_success_rate,
                    'previous_rate': older_success_rate,
                    'change': recent_success_rate - older_success_rate
                },
                'volume': {
                    'trend': volume_trend,
                    'recent_volume': recent_volume,
                    'previous_volume': older_volume,
                    'change': recent_volume - older_volume
                }
            },
            'patterns': {
                'peak_day': peak_day,
                'average_daily_volume': sum(day['total'] for day in daily_data) / len(daily_data),
                'most_active_notification_type': max(stats['by_type'], key=lambda x: x['total'])['notification_type'] if stats['by_type'] else None
            }
        }
    
    def generate_notification_report(self, days: int = 30) -> Dict[str, Any]:
        """Generate comprehensive notification system report"""
        stats = self.get_delivery_statistics(days=days)
        health = self.get_notification_health_score()
        failed_analysis = self.get_failed_notifications_analysis()
        trends = self.get_notification_trends(days=days)
        
        return {
            'report_period': f"Last {days} days",
            'generated_at': timezone.now().isoformat(),
            'summary': {
                'total_notifications': stats['total_notifications'],
                'success_rate': stats['success_rate'],
                'health_score': health['health_score'],
                'health_status': health['health_status']
            },
            'statistics': stats,
            'health': health,
            'failed_analysis': failed_analysis,
            'trends': trends,
            'recommendations': self._generate_recommendations(stats, health, failed_analysis, trends)
        }
    
    def _generate_recommendations(self, stats: Dict, health: Dict, failed_analysis: Dict, trends: Dict) -> List[str]:
        """Generate actionable recommendations based on analysis"""
        recommendations = []
        
        # Health-based recommendations
        if health['health_score'] < 75:
            recommendations.append("System health is below optimal. Review failed notifications and email configuration.")
        
        # Success rate recommendations
        if stats['success_rate'] < 90:
            recommendations.append("Success rate is below 90%. Consider reviewing email templates and server configuration.")
        
        # Delivery time recommendations
        if stats['average_delivery_time'] > 60:
            recommendations.append("Average delivery time is high. Consider optimizing email server performance.")
        
        # Trend-based recommendations
        if trends['trends']['success_rate']['trend'] == 'declining':
            recommendations.append("Success rate is declining. Investigate recent changes to email configuration or templates.")
        
        if trends['trends']['volume']['trend'] == 'increasing':
            recommendations.append("Notification volume is increasing. Monitor system performance and consider scaling.")
        
        # Failed notification recommendations
        if failed_analysis['retryable_count'] > 0:
            recommendations.append(f"Retry {failed_analysis['retryable_count']} failed notifications that haven't exceeded max retries.")
        
        # Template recommendations
        poor_templates = [t for t in stats['template_performance'] if t['success_rate'] < 80]
        if poor_templates:
            recommendations.append(f"Review templates with low success rates: {', '.join(t['template_name'] for t in poor_templates)}")
        
        return recommendations