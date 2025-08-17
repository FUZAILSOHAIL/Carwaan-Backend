from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

class NotificationSettings(models.Model):
    """User notification preferences"""
    user = models.OneToOneField('users.User', on_delete=models.CASCADE, related_name='notification_settings')
    notifications_enabled = models.BooleanField(default=True)
    ride_notifications_enabled = models.BooleanField(default=True)
    chat_notifications_enabled = models.BooleanField(default=True)
    promotional_notifications_enabled = models.BooleanField(default=False)
    sound_enabled = models.BooleanField(default=True)
    vibration_enabled = models.BooleanField(default=True)
    
    # Device tokens for push notifications
    fcm_token = models.TextField(blank=True, null=True, help_text="Firebase Cloud Messaging token")
    apns_token = models.TextField(blank=True, null=True, help_text="Apple Push Notification Service token")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'notification_settings'
        verbose_name = 'Notification Settings'
        verbose_name_plural = 'Notification Settings'
    
    def __str__(self):
        return f"{self.user.username}'s Notification Settings"

class Notification(models.Model):
    """Notification records"""
    NOTIFICATION_TYPES = [
        ('ride_booked', 'Ride Booked'),
        ('ride_confirmed', 'Ride Confirmed'),
        ('ride_cancelled', 'Ride Cancelled'),
        ('ride_completed', 'Ride Completed'),
        ('ride_reminder', 'Ride Reminder'),
        ('chat_message', 'Chat Message'),
        ('general', 'General Notification'),
        ('promotional', 'Promotional'),
    ]
    
    NOTIFICATION_STATUS = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('read', 'Read'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    body = models.TextField()
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='general')
    status = models.CharField(max_length=20, choices=NOTIFICATION_STATUS, default='pending')
    
    # Optional payload data
    data = models.JSONField(default=dict, blank=True, help_text="Additional notification data")
    
    # Related objects
    ride_id = models.CharField(max_length=100, blank=True, null=True)
    chat_id = models.CharField(max_length=100, blank=True, null=True)
    
    # Scheduling
    scheduled_for = models.DateTimeField(blank=True, null=True, help_text="When to send this notification")
    sent_at = models.DateTimeField(blank=True, null=True)
    read_at = models.DateTimeField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', '-created_at']),
            models.Index(fields=['notification_type']),
            models.Index(fields=['status']),
            models.Index(fields=['scheduled_for']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.recipient.username}"
    
    def mark_as_read(self):
        """Mark notification as read"""
        if self.status != 'read':
            self.status = 'read'
            self.read_at = timezone.now()
            self.save(update_fields=['status', 'read_at'])
    
    def mark_as_sent(self):
        """Mark notification as sent"""
        if self.status == 'pending':
            self.status = 'sent'
            self.sent_at = timezone.now()
            self.save(update_fields=['status', 'sent_at'])

class NotificationDeliveryLog(models.Model):
    """Log of notification delivery attempts"""
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name='delivery_logs')
    delivery_method = models.CharField(max_length=20, choices=[
        ('local', 'Local Notification'),
        ('fcm', 'Firebase Cloud Messaging'),
        ('apns', 'Apple Push Notification'),
        ('email', 'Email'),
        ('sms', 'SMS'),
    ])
    status = models.CharField(max_length=20, choices=[
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('retry', 'Retry'),
    ])
    response_data = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'notification_delivery_logs'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.notification.title} - {self.delivery_method} - {self.status}"
