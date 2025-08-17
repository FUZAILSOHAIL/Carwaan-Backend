from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import User, PaymentMethod
from .models_vehicle import Vehicle
from .serializers_vehicle import VehicleSerializer, VehicleListSerializer


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()
    average_rating = serializers.DecimalField(max_digits=3, decimal_places=2, coerce_to_string=False)
    profile_picture_url = serializers.SerializerMethodField()
    user_type = serializers.ReadOnlyField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name',
            'phone', 'profile_picture', 'profile_picture_url', 'is_verified', 'email_verified', 'role', 'user_type', 'bio', 'average_rating',
            'date_of_birth', 'address', 'home_address', 'workplace', 'workplace_address',
            'has_car', 'car_model', 'car_color', 'license_plate', 'gender',
            'smoking_preference', 'ac_preference', 'chat_preference',
            'preferred_days', 'home_latitude', 'home_longitude', 
            'workplace_latitude', 'workplace_longitude', 'driver_verification_status',
            'is_driver', 'total_driver_reviews', 'total_passenger_reviews',
            'driver_rating', 'passenger_rating', 'total_rides_offered', 'total_rides_taken'
        ]
        read_only_fields = ['is_verified', 'email_verified', 'average_rating', 'driver_verification_status', 
                           'total_driver_reviews', 'total_passenger_reviews', 'driver_rating', 
                           'passenger_rating', 'total_rides_offered', 'total_rides_taken', 'user_type']
    
    def get_profile_picture_url(self, obj):
        """Return full URL for profile picture"""
        if obj.profile_picture:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.profile_picture.url)
            return obj.profile_picture.url
        return None


class UserDetailSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()
    average_rating = serializers.DecimalField(max_digits=3, decimal_places=2, coerce_to_string=False)
    profile_picture_url = serializers.SerializerMethodField()
    home_latitude = serializers.DecimalField(max_digits=10, decimal_places=8, coerce_to_string=False, required=False, allow_null=True)
    home_longitude = serializers.DecimalField(max_digits=11, decimal_places=8, coerce_to_string=False, required=False, allow_null=True)
    workplace_latitude = serializers.DecimalField(max_digits=10, decimal_places=8, coerce_to_string=False, required=False, allow_null=True)
    workplace_longitude = serializers.DecimalField(max_digits=11, decimal_places=8, coerce_to_string=False, required=False, allow_null=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name',
            'phone', 'profile_picture', 'profile_picture_url', 'bio', 'date_of_birth', 'address',
            'is_verified', 'email_verified', 'role', 'average_rating', 'total_ratings',
            'workplace', 'home_address', 'home_latitude', 'home_longitude', 
            'workplace_address', 'workplace_latitude', 'workplace_longitude',
            'has_car', 'car_model', 'car_color', 'license_plate',
            'preferred_days', 'preferred_departure_times', 'preferred_music',
            'smoking_preference', 'ac_preference', 'chat_preference',
            'payment_methods', 'gender'
        ]
        read_only_fields = ['is_verified', 'email_verified', 'role', 'average_rating', 'total_ratings']
    
    def get_profile_picture_url(self, obj):
        """Return full URL for profile picture"""
        if obj.profile_picture:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.profile_picture.url)
            return obj.profile_picture.url
        return None


class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'phone', 'profile_picture', 'bio', 
            'date_of_birth', 'address', 'home_address', 'home_latitude', 'home_longitude',
            'workplace', 'workplace_address', 'workplace_latitude', 'workplace_longitude',
            'has_car', 'car_model', 'car_color', 'license_plate',
            'preferred_days', 'preferred_departure_times', 'preferred_music',
            'smoking_preference', 'ac_preference', 'chat_preference',
            'payment_methods', 'gender'
        ]
    
    def validate(self, data):
        # If user indicates they have a car, make sure car details are provided
        has_car = data.get('has_car', self.instance.has_car if self.instance else False)
        if has_car:
            car_model = data.get('car_model', self.instance.car_model if self.instance else '')
            car_color = data.get('car_color', self.instance.car_color if self.instance else '')
            license_plate = data.get('license_plate', self.instance.license_plate if self.instance else '')
            
            if not car_model or not car_color or not license_plate:
                raise serializers.ValidationError(
                    "Car model, color, and license plate are required if you have a car"
                )
                
        # Validate coordinates if provided
        home_lat = data.get('home_latitude')
        home_lng = data.get('home_longitude')
        
        if (home_lat is not None and home_lng is None) or (home_lat is None and home_lng is not None):
            raise serializers.ValidationError("Both home latitude and longitude must be provided together")
            
        workplace_lat = data.get('workplace_latitude')
        workplace_lng = data.get('workplace_longitude')
        
        if (workplace_lat is not None and workplace_lng is None) or (workplace_lat is None and workplace_lng is not None):
            raise serializers.ValidationError("Both workplace latitude and longitude must be provided together")
            
        return data


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    password_confirm = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    user_type = serializers.CharField(write_only=True, required=False, default='passenger')
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'password', 'password_confirm',
            'first_name', 'last_name', 'phone', 'gender', 'user_type'
        ]
        extra_kwargs = {
            'first_name': {'required': True},
            'last_name': {'required': True},
            'email': {'required': True},
            'gender': {'required': True}
        }
    
    def validate(self, data):
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError({"password_confirm": "Password fields don't match."})
        return data
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user_type = validated_data.pop('user_type', 'passenger')
        
        # Set role and is_driver based on user_type
        if user_type == 'admin':
            role = 'admin'
            is_driver = False
        elif user_type == 'driver':
            role = 'user'
            is_driver = True
        else:  # passenger or default
            role = 'user'
            is_driver = False
        
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            phone=validated_data.get('phone'),
            gender=validated_data.get('gender', 'prefer_not_to_say'),
            role=role,
            is_driver=is_driver
        )
        
        return user


class UserRatingSerializer(serializers.Serializer):
    """Serializer for rating users"""
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(max_length=500, required=False, allow_blank=True)


class SendOTPSerializer(serializers.Serializer):
    """Serializer for sending OTP"""
    email = serializers.EmailField(required=True)


class VerifyOTPSerializer(serializers.Serializer):
    """Serializer for verifying OTP"""
    email = serializers.EmailField(required=True)
    otp_code = serializers.CharField(max_length=6, min_length=6, required=True)
    
    def validate_otp_code(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("OTP code must contain only digits")
        return value


class LoginWithEmailSerializer(serializers.Serializer):
    """Serializer for email-based login"""
    email_or_username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, style={'input_type': 'password'})


class PaymentMethodSerializer(serializers.ModelSerializer):
    """Serializer for PaymentMethod model"""
    
    class Meta:
        model = PaymentMethod
        fields = [
            'id', 'type', 'holder_name', 'last_four', 'brand', 
            'expiry_month', 'expiry_year', 'phone_number', 
            'account_number', 'bank_name', 'is_default', 
            'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def validate(self, data):
        """Validate payment method data based on type"""
        payment_type = data.get('type')
        
        if payment_type == 'card':
            required_fields = ['last_four', 'brand', 'expiry_month', 'expiry_year']
            for field in required_fields:
                if not data.get(field):
                    raise serializers.ValidationError(f"{field} is required for card payments")
        
        elif payment_type in ['easypaisa', 'jazzcash']:
            if not data.get('phone_number'):
                raise serializers.ValidationError("Phone number is required for mobile wallet payments")
        
        elif payment_type == 'bank_transfer':
            required_fields = ['account_number', 'bank_name']
            for field in required_fields:
                if not data.get(field):
                    raise serializers.ValidationError(f"{field} is required for bank transfers")
        
        return data
    
    def create(self, validated_data):
        """Create a new payment method for the current user"""
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)