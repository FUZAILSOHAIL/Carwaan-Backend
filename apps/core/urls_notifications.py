from django.urls import path
from .views_notifications import (
    NotificationSettingsView,
    UserNotificationsView,
    NotificationDetailView,
    AdminNotificationView,
    mark_notification_read,
    mark_all_notifications_read,
    notification_summary,
    update_device_token,
    admin_notification_stats,
)

urlpatterns = [
    # User notification settings
    path('settings/', NotificationSettingsView.as_view(), name='notification-settings'),
    
    # User notifications
    path('', UserNotificationsView.as_view(), name='user-notifications'),
    path('<uuid:pk>/', NotificationDetailView.as_view(), name='notification-detail'),
    path('summary/', notification_summary, name='notification-summary'),
    
    # Notification actions
    path('<uuid:notification_id>/read/', mark_notification_read, name='mark-notification-read'),
    path('mark-all-read/', mark_all_notifications_read, name='mark-all-notifications-read'),
    
    # Device tokens
    path('device-token/', update_device_token, name='update-device-token'),
    
    # Admin endpoints
    path('admin/send/', AdminNotificationView.as_view(), name='admin-send-notification'),
    path('admin/stats/', admin_notification_stats, name='admin-notification-stats'),
]
