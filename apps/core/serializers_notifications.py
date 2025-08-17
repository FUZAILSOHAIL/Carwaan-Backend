from rest_framework import serializers
from .models_notifications import Notification, NotificationSettings, NotificationDeliveryLog

class NotificationSettingsSerializer(serializers.ModelSerializer):
    """Serializer for user notification settings"""
    
    class Meta:
        model = NotificationSettings
        fields = [
            'notifications_enabled',
            'ride_notifications_enabled', 
            'chat_notifications_enabled',
            'promotional_notifications_enabled',
            'sound_enabled',
            'vibration_enabled',
            'fcm_token',
            'apns_token',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def update(self, instance, validated_data):
        """Update notification settings"""
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for notifications"""
    recipient_name = serializers.CharField(source='recipient.get_full_name', read_only=True)
    time_ago = serializers.SerializerMethodField()
    
    class Meta:
        model = Notification
        fields = [
            'id',
            'recipient',
            'recipient_name',
            'title',
            'body',
            'notification_type',
            'status',
            'data',
            'ride_id',
            'chat_id',
            'scheduled_for',
            'sent_at',
            'read_at',
            'created_at',
            'updated_at',
            'time_ago',
        ]
        read_only_fields = ['id', 'recipient', 'recipient_name', 'sent_at', 'read_at', 'created_at', 'updated_at', 'time_ago']
    
    def get_time_ago(self, obj):
        """Get human-readable time since creation"""
        from django.utils.timesince import timesince
        return timesince(obj.created_at)

class CreateNotificationSerializer(serializers.ModelSerializer):
    """Serializer for creating new notifications"""
    
    class Meta:
        model = Notification
        fields = [
            'recipient',
            'title',
            'body',
            'notification_type',
            'data',
            'ride_id',
            'chat_id',
            'scheduled_for',
        ]
    
    def create(self, validated_data):
        """Create a new notification"""
        return Notification.objects.create(**validated_data)

class NotificationDeliveryLogSerializer(serializers.ModelSerializer):
    """Serializer for notification delivery logs"""
    notification_title = serializers.CharField(source='notification.title', read_only=True)
    
    class Meta:
        model = NotificationDeliveryLog
        fields = [
            'id',
            'notification',
            'notification_title',
            'delivery_method',
            'status',
            'response_data',
            'error_message',
            'created_at',
        ]
        read_only_fields = ['id', 'notification_title', 'created_at']

class BulkNotificationSerializer(serializers.Serializer):
    """Serializer for sending bulk notifications"""
    recipient_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="List of user IDs to send notification to"
    )
    title = serializers.CharField(max_length=200)
    body = serializers.CharField()
    notification_type = serializers.ChoiceField(choices=Notification.NOTIFICATION_TYPES, default='general')
    data = serializers.JSONField(default=dict, required=False)
    ride_id = serializers.CharField(max_length=100, required=False, allow_blank=True)
    chat_id = serializers.CharField(max_length=100, required=False, allow_blank=True)
    scheduled_for = serializers.DateTimeField(required=False, allow_null=True)
    
    def validate_recipient_ids(self, value):
        """Validate that all recipient IDs exist"""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        if not value:
            raise serializers.ValidationError("At least one recipient is required")
        
        existing_ids = set(User.objects.filter(id__in=value).values_list('id', flat=True))
        invalid_ids = set(value) - existing_ids
        
        if invalid_ids:
            raise serializers.ValidationError(f"Invalid user IDs: {list(invalid_ids)}")
        
        return value

class DeviceTokenSerializer(serializers.Serializer):
    """Serializer for updating device tokens"""
    fcm_token = serializers.CharField(max_length=500, required=False, allow_blank=True)
    apns_token = serializers.CharField(max_length=500, required=False, allow_blank=True)
    
    def validate(self, data):
        """Ensure at least one token is provided"""
        if not data.get('fcm_token') and not data.get('apns_token'):
            raise serializers.ValidationError("At least one device token is required")
        return data
