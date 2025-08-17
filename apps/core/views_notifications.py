from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q
from .models_notifications import Notification, NotificationSettings, NotificationDeliveryLog
from .serializers_notifications import (
    NotificationSerializer, 
    CreateNotificationSerializer,
    NotificationSettingsSerializer,
    BulkNotificationSerializer,
    DeviceTokenSerializer,
    NotificationDeliveryLogSerializer
)
import logging

User = get_user_model()
logger = logging.getLogger(__name__)

class NotificationPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

class NotificationSettingsView(APIView):
    """Get and update user notification settings"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Get user's notification settings"""
        settings, created = NotificationSettings.objects.get_or_create(
            user=request.user,
            defaults={
                'notifications_enabled': True,
                'ride_notifications_enabled': True,
                'chat_notifications_enabled': True,
                'promotional_notifications_enabled': False,
                'sound_enabled': True,
                'vibration_enabled': True,
            }
        )
        
        serializer = NotificationSettingsSerializer(settings)
        return Response(serializer.data)
    
    def put(self, request):
        """Update user's notification settings"""
        settings, created = NotificationSettings.objects.get_or_create(
            user=request.user
        )
        
        serializer = NotificationSettingsSerializer(settings, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            logger.info(f"Updated notification settings for user {request.user.id}")
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UserNotificationsView(ListCreateAPIView):
    """List and create notifications for authenticated user"""
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = NotificationPagination
    
    def get_queryset(self):
        """Get notifications for current user with optional filtering"""
        queryset = Notification.objects.filter(recipient=self.request.user)
        
        # Filter by notification type
        notification_type = self.request.query_params.get('type', None)
        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)
        
        # Filter by status
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by read/unread
        unread_only = self.request.query_params.get('unread_only', None)
        if unread_only and unread_only.lower() == 'true':
            queryset = queryset.exclude(status='read')
        
        return queryset.select_related('recipient').order_by('-created_at')
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CreateNotificationSerializer
        return NotificationSerializer

class NotificationDetailView(RetrieveUpdateDestroyAPIView):
    """Get, update, or delete a specific notification"""
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)
    
    def patch(self, request, *args, **kwargs):
        """Mark notification as read when accessed"""
        notification = self.get_object()
        if notification.status != 'read':
            notification.mark_as_read()
        return super().patch(request, *args, **kwargs)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def mark_notification_read(request, notification_id):
    """Mark a specific notification as read"""
    try:
        notification = get_object_or_404(
            Notification, 
            id=notification_id, 
            recipient=request.user
        )
        notification.mark_as_read()
        
        return Response({
            'success': True,
            'message': 'Notification marked as read',
            'notification_id': str(notification.id)
        })
    except Exception as e:
        logger.error(f"Error marking notification as read: {str(e)}")
        return Response({
            'success': False,
            'message': 'Failed to mark notification as read'
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def mark_all_notifications_read(request):
    """Mark all notifications as read for the current user"""
    try:
        updated = Notification.objects.filter(
            recipient=request.user,
            status__in=['pending', 'sent', 'delivered']
        ).update(
            status='read',
            read_at=timezone.now()
        )
        
        return Response({
            'success': True,
            'message': f'Marked {updated} notifications as read'
        })
    except Exception as e:
        logger.error(f"Error marking all notifications as read: {str(e)}")
        return Response({
            'success': False,
            'message': 'Failed to mark notifications as read'
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def notification_summary(request):
    """Get notification summary for current user"""
    user_notifications = Notification.objects.filter(recipient=request.user)
    
    summary = {
        'total_notifications': user_notifications.count(),
        'unread_notifications': user_notifications.exclude(status='read').count(),
        'by_type': {},
        'recent_notifications': []
    }
    
    # Count by type
    for notification_type, _ in Notification.NOTIFICATION_TYPES:
        count = user_notifications.filter(notification_type=notification_type).count()
        if count > 0:
            summary['by_type'][notification_type] = count
    
    # Recent notifications (last 5)
    recent = user_notifications.order_by('-created_at')[:5]
    summary['recent_notifications'] = NotificationSerializer(recent, many=True).data
    
    return Response(summary)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def update_device_token(request):
    """Update user's device token for push notifications"""
    serializer = DeviceTokenSerializer(data=request.data)
    if serializer.is_valid():
        settings, created = NotificationSettings.objects.get_or_create(
            user=request.user
        )
        
        if 'fcm_token' in serializer.validated_data:
            settings.fcm_token = serializer.validated_data['fcm_token']
        if 'apns_token' in serializer.validated_data:
            settings.apns_token = serializer.validated_data['apns_token']
        
        settings.save()
        
        logger.info(f"Updated device token for user {request.user.id}")
        return Response({
            'success': True,
            'message': 'Device token updated successfully'
        })
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Admin/Staff only views
class AdminNotificationView(APIView):
    """Admin view for managing notifications"""
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    
    def post(self, request):
        """Send notification to specific users"""
        serializer = BulkNotificationSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            notifications_created = []
            
            for recipient_id in data['recipient_ids']:
                try:
                    recipient = User.objects.get(id=recipient_id)
                    notification = Notification.objects.create(
                        recipient=recipient,
                        title=data['title'],
                        body=data['body'],
                        notification_type=data['notification_type'],
                        data=data.get('data', {}),
                        ride_id=data.get('ride_id', ''),
                        chat_id=data.get('chat_id', ''),
                        scheduled_for=data.get('scheduled_for'),
                    )
                    notifications_created.append(str(notification.id))
                except User.DoesNotExist:
                    continue
            
            logger.info(f"Created {len(notifications_created)} notifications")
            return Response({
                'success': True,
                'message': f'Created {len(notifications_created)} notifications',
                'notification_ids': notifications_created
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, permissions.IsAdminUser])
def admin_notification_stats(request):
    """Get notification statistics for admin"""
    stats = {
        'total_notifications': Notification.objects.count(),
        'notifications_by_status': {},
        'notifications_by_type': {},
        'recent_activity': []
    }
    
    # Count by status
    for status_choice, _ in Notification.NOTIFICATION_STATUS:
        count = Notification.objects.filter(status=status_choice).count()
        if count > 0:
            stats['notifications_by_status'][status_choice] = count
    
    # Count by type
    for type_choice, _ in Notification.NOTIFICATION_TYPES:
        count = Notification.objects.filter(notification_type=type_choice).count()
        if count > 0:
            stats['notifications_by_type'][type_choice] = count
    
    # Recent delivery logs (last 10)
    recent_logs = NotificationDeliveryLog.objects.select_related('notification').order_by('-created_at')[:10]
    stats['recent_activity'] = NotificationDeliveryLogSerializer(recent_logs, many=True).data
    
    return Response(stats)

# Utility function for creating ride notifications
def create_ride_notification(recipient, ride_data, notification_type='ride_update'):
    """Helper function to create ride-related notifications"""
    try:
        # Check if user has ride notifications enabled
        settings = getattr(recipient, 'notification_settings', None)
        if settings and not settings.ride_notifications_enabled:
            return None
        
        title_map = {
            'ride_booked': '🎉 Ride Booked Successfully!',
            'ride_confirmed': '✅ Ride Confirmed',
            'ride_cancelled': '❌ Ride Cancelled',
            'ride_completed': '🏁 Ride Completed',
            'ride_reminder': '🚗 Ride Reminder',
        }
        
        body_map = {
            'ride_booked': f"You've joined a ride from {ride_data.get('pickup_location', 'your location')} to {ride_data.get('dropoff_location', 'destination')}",
            'ride_confirmed': f"Your ride from {ride_data.get('pickup_location', 'pickup')} has been confirmed",
            'ride_cancelled': f"Your ride from {ride_data.get('pickup_location', 'pickup')} has been cancelled",
            'ride_completed': f"Your ride to {ride_data.get('dropoff_location', 'destination')} has been completed",
            'ride_reminder': f"Your ride departs soon from {ride_data.get('pickup_location', 'pickup location')}",
        }
        
        notification = Notification.objects.create(
            recipient=recipient,
            title=title_map.get(notification_type, 'Ride Update'),
            body=body_map.get(notification_type, 'Your ride has been updated'),
            notification_type=notification_type,
            ride_id=ride_data.get('id', ''),
            data=ride_data
        )
        
        logger.info(f"Created ride notification {notification.id} for user {recipient.id}")
        return notification
        
    except Exception as e:
        logger.error(f"Error creating ride notification: {str(e)}")
        return None
