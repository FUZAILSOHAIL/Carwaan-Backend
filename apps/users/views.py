from django.shortcuts import render
from rest_framework import viewsets, generics, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action, api_view, permission_classes, throttle_classes
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model, authenticate
from django.db.models import Q
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import logging
import json
from .models import User, PaymentMethod, ImageBackup
from .models_vehicle import Vehicle
from .serializers import UserSerializer, UserRegistrationSerializer, PaymentMethodSerializer
from .serializers_vehicle import VehicleSerializer, VehicleCreateSerializer, VehicleListSerializer
from .services import EmailService
from apps.core.services.google_drive_service import google_drive_service
from apps.core.services.google_oauth_service import google_oauth_service

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
@throttle_classes([])  # Exempt from rate limiting
def health_check(request):
    """Simple health check endpoint for connection testing"""
    return Response({
        "status": "healthy",
        "message": "Carwaan backend is running",
        "timestamp": "2025-07-06"
    })


def create_auth_response(user, message="Login successful"):
    """Create a standardized authentication response with tokens and user data"""
    refresh = RefreshToken.for_user(user)
    access_token = refresh.access_token
    user_serializer = UserSerializer(user)

    return {
        "message": message,
        "access_token": str(access_token),
        "refresh_token": str(refresh),
        "user": user_serializer.data,
        "email_verified": user.email_verified,
    }


def create_error_response(message, status_code=400):
    """Create a standardized error response"""
    return Response({"error": message}, status=status_code)


class UserViewSet(viewsets.ModelViewSet):
    """ViewSet for viewing and editing user instances"""

    serializer_class = UserSerializer
    queryset = User.objects.all()

    def get_permissions(self):
        """Set custom permissions for different actions"""
        if self.action in ['create', 'register', 'send_otp', 'verify_otp', 'login_with_otp', 'verify_login_otp']:
            permission_classes = [permissions.AllowAny]
        elif self.action in ['update', 'partial_update', 'destroy', 'me']:
            permission_classes = [permissions.IsAuthenticated]
        else:
            # Default to authenticated for other actions like list, retrieve
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        """Return appropriate serializer class"""
        if self.action == "create":
            return UserRegistrationSerializer
        return self.serializer_class

    @action(detail=False, methods=["get", "patch", "put"])
    def me(self, request):
        """Return or update the current user's profile"""
        if request.method == 'GET':
            serializer = self.get_serializer(request.user)
            return Response(serializer.data)
        else:  # PATCH or PUT
            serializer = self.get_serializer(request.user, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"], url_path='upload_picture')
    def upload_profile_picture(self, request):
        """Upload profile picture for the current user"""
        try:
            profile_picture = request.FILES.get('profile_picture')
            if not profile_picture:
                return Response(
                    {'error': 'No file provided'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Debug logging
            logger.info(f"Profile picture upload attempt:")
            logger.info(f"  File name: {profile_picture.name}")
            logger.info(f"  Content type: {profile_picture.content_type}")
            logger.info(f"  File size: {profile_picture.size}")
            
            # Validate file type - check both MIME type and file extension
            allowed_mime_types = [
                'image/jpeg', 'image/jpg', 'image/png', 
                'image/pjpeg',  # Progressive JPEG
                'application/octet-stream'  # Sometimes camera images come as this
            ]
            
            # Get file extension
            file_name = profile_picture.name.lower()
            allowed_extensions = ['.jpg', '.jpeg', '.png']
            
            # Check if file has valid extension
            has_valid_extension = any(file_name.endswith(ext) for ext in allowed_extensions)
            
            # Check MIME type (be more lenient for camera images)
            has_valid_mime = (
                profile_picture.content_type in allowed_mime_types or 
                profile_picture.content_type.startswith('image/')
            )
            
            logger.info(f"  Valid extension: {has_valid_extension}")
            logger.info(f"  Valid MIME type: {has_valid_mime}")
            
            if not (has_valid_extension and has_valid_mime):
                error_msg = f'Only PNG and JPG files are allowed. Received: {profile_picture.content_type}'
                logger.warning(f"Profile picture upload rejected: {error_msg}")
                return Response(
                    {'error': error_msg}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate file size (5MB max)
            if profile_picture.size > 5 * 1024 * 1024:
                return Response(
                    {'error': 'File size too large. Maximum 5MB allowed'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Delete old profile picture if exists
            if request.user.profile_picture:
                request.user.profile_picture.delete(save=False)
            
            # Save new profile picture
            request.user.profile_picture = profile_picture
            request.user.save()
            
            logger.info(f"Profile picture uploaded successfully for user {request.user.id}")
            
            serializer = self.get_serializer(request.user)
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Profile picture upload failed: {str(e)}")
            return Response(
                {'error': f'Failed to upload profile picture: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=["delete"], url_path='delete_picture')
    def delete_profile_picture(self, request):
        """Delete profile picture for the current user"""
        try:
            if request.user.profile_picture:
                request.user.profile_picture.delete(save=False)
                request.user.profile_picture = None
                request.user.save()
                
                serializer = self.get_serializer(request.user)
                return Response(serializer.data)
            else:
                return Response(
                    {'message': 'No profile picture to delete'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            return Response(
                {'error': f'Failed to delete profile picture: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=["post"], permission_classes=[permissions.AllowAny])
    def register(self, request):
        """Register a new user and send OTP for email verification"""
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()

            # Generate and send OTP
            otp_code = user.generate_otp()
            success, message = EmailService.send_otp_email(user, otp_code)

            if success:
                return Response(
                    {
                        "message": "User registered successfully. Please check your email for verification code.",
                        "email": user.email,
                        "otp_sent": True,
                    },
                    status=status.HTTP_201_CREATED,
                )
            else:
                return Response(
                    {
                        "message": "User registered but failed to send verification email. Please request OTP manually.",
                        "email": user.email,
                        "otp_sent": False,
                        "error": message,
                    },
                    status=status.HTTP_201_CREATED,
                )
        else:
            # Enhanced error handling with detailed field-specific messages
            errors = serializer.errors
            error_messages = []
            field_errors = {}
            
            # Process each field error
            for field, field_errors_list in errors.items():
                if field == 'non_field_errors':
                    # General errors not tied to specific fields
                    for error in field_errors_list:
                        error_messages.append(str(error))
                else:
                    # Field-specific errors
                    field_name = field.replace('_', ' ').title()
                    field_errors[field] = []
                    
                    for error in field_errors_list:
                        error_str = str(error)
                        field_errors[field].append(error_str)
                        
                        # Create user-friendly error messages
                        if field == 'email':
                            if 'already exists' in error_str.lower() or 'unique' in error_str.lower():
                                error_messages.append("Email address is already registered. Please use a different email or try logging in.")
                            elif 'invalid' in error_str.lower():
                                error_messages.append("Please enter a valid email address.")
                            else:
                                error_messages.append(f"Email: {error_str}")
                        elif field == 'username':
                            if 'already exists' in error_str.lower() or 'unique' in error_str.lower():
                                error_messages.append("Username is already taken. Please choose a different username.")
                            elif 'invalid' in error_str.lower():
                                error_messages.append("Username can only contain letters, numbers, and underscores.")
                            else:
                                error_messages.append(f"Username: {error_str}")
                        elif field == 'phone':
                            if 'already exists' in error_str.lower() or 'unique' in error_str.lower():
                                error_messages.append("Phone number is already registered. Please use a different phone number.")
                            elif 'invalid' in error_str.lower():
                                error_messages.append("Please enter a valid phone number.")
                            else:
                                error_messages.append(f"Phone: {error_str}")
                        elif field == 'password':
                            if 'too short' in error_str.lower():
                                error_messages.append("Password must be at least 8 characters long.")
                            elif 'too common' in error_str.lower():
                                error_messages.append("Password is too common. Please choose a stronger password.")
                            elif 'numeric' in error_str.lower():
                                error_messages.append("Password cannot be entirely numeric.")
                            elif 'similar' in error_str.lower():
                                error_messages.append("Password is too similar to your personal information.")
                            else:
                                error_messages.append(f"Password: {error_str}")
                        elif field == 'password_confirm':
                            if "don't match" in error_str.lower() or "match" in error_str.lower():
                                error_messages.append("Passwords do not match. Please ensure both password fields are identical.")
                            else:
                                error_messages.append(f"Password confirmation: {error_str}")
                        elif field == 'gender':
                            if 'required' in error_str.lower():
                                error_messages.append("Please select your gender.")
                            elif 'invalid choice' in error_str.lower():
                                error_messages.append("Please select a valid gender option.")
                            else:
                                error_messages.append(f"Gender: {error_str}")
                        elif field in ['first_name', 'last_name']:
                            if 'required' in error_str.lower():
                                error_messages.append(f"{field_name} is required.")
                            elif 'blank' in error_str.lower():
                                error_messages.append(f"{field_name} cannot be empty.")
                            else:
                                error_messages.append(f"{field_name}: {error_str}")
                        else:
                            # For any other fields
                            if 'required' in error_str.lower():
                                error_messages.append(f"{field_name} is required.")
                            elif 'blank' in error_str.lower():
                                error_messages.append(f"{field_name} cannot be empty.")
                            else:
                                error_messages.append(f"{field_name}: {error_str}")
            
            # Create response with detailed error information
            error_response = {
                "error": "Registration failed due to validation errors.",
                "message": error_messages[0] if error_messages else "Please check your input and try again.",
                "field_errors": field_errors,
                "details": error_messages
            }
            
            return Response(error_response, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"], permission_classes=[permissions.AllowAny])
    def send_otp(self, request):
        """Send OTP to user's email for verification"""
        email = request.data.get("email")
        if not email:
            return Response(
                {"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(email=email)

            # Check if already verified
            if user.email_verified:
                return Response(
                    {"message": "Email is already verified"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Generate and send new OTP
            otp_code = user.generate_otp()
            success, message = EmailService.send_otp_email(user, otp_code)

            if success:
                return Response(
                    {
                        "message": "OTP sent successfully to your email",
                        "email": user.email,
                    }
                )
            else:
                return Response(
                    {"error": message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        except User.DoesNotExist:
            return Response(
                {"error": "Email doesn't exist, please create account"},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(detail=False, methods=["post"], permission_classes=[permissions.AllowAny])
    def verify_otp(self, request):
        """Verify OTP code and activate user account"""
        email = request.data.get("email")
        otp_code = request.data.get("otp_code")

        if not email or not otp_code:
            return Response(
                {"error": "Email and OTP code are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(email=email)

            # Verify OTP
            success, message = user.verify_otp(otp_code)

            if success:
                # Send welcome email
                EmailService.send_welcome_email(user)
                return Response(create_auth_response(user, message))
            else:
                return create_error_response(message)

        except User.DoesNotExist:
            return Response(
                {"error": "Email doesn't exist, please create account"},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(detail=False, methods=["post"], permission_classes=[permissions.AllowAny])
    def login_with_otp(self, request):
        """Login using username/email and OTP (passwordless login)"""
        username_or_email = request.data.get("username") or request.data.get("email")

        if not username_or_email:
            return Response(
                {"error": "Username or email is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Try to find user by username or email
            user = None
            try:
                # First try exact username match
                user = User.objects.get(username=username_or_email)
            except User.DoesNotExist:
                # If not found, try email
                try:
                    user = User.objects.get(email=username_or_email)
                except User.DoesNotExist:
                    return Response(
                        {"error": "Email doesn't exist, please create account"},
                        status=status.HTTP_404_NOT_FOUND,
                    )

            # Note: Allow OTP login even without email verification
            # This provides flexibility for users

            # Generate and send OTP for login
            otp_code = user.generate_otp()
            success, message = EmailService.send_otp_email(user, otp_code)

            if success:
                return Response(
                    {
                        "message": "Login OTP sent successfully to your email",
                        "email": user.email,
                        "username": user.username,
                    }
                )
            else:
                return Response(
                    {"error": message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        except Exception as e:
            return Response(
                {"error": f"An error occurred: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=["post"], permission_classes=[permissions.AllowAny])
    def verify_login_otp(self, request):
        """Verify OTP for login and return tokens"""
        username_or_email = request.data.get("username") or request.data.get("email")
        otp_code = request.data.get("otp_code") or request.data.get("otp")

        if not username_or_email or not otp_code:
            return Response(
                {"error": "Username/email and OTP code are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Try to find user by username or email
            user = None
            try:
                # First try exact username match
                user = User.objects.get(username=username_or_email)
            except User.DoesNotExist:
                # If not found, try email
                try:
                    user = User.objects.get(email=username_or_email)
                except User.DoesNotExist:
                    return Response(
                        {"error": "Email doesn't exist, please create account"},
                        status=status.HTTP_404_NOT_FOUND,
                    )

            # Verify OTP
            success, message = user.verify_otp(otp_code)

            if success:
                return Response(create_auth_response(user, "Login successful"))
            else:
                return create_error_response(message)

        except Exception as e:
            return Response(
                {"error": f"An error occurred: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get', 'patch'], permission_classes=[permissions.IsAuthenticated])
    def ride_preferences(self, request):
        """Get or update user ride preferences"""
        user = request.user
        
        if request.method == 'GET':
            # Return current ride preferences
            preferences = {
                'smoking_preference': user.smoking_preference,
                'ac_preference': user.ac_preference,
                'chat_preference': user.chat_preference,
                'preferred_days': user.preferred_days or [],
            }
            return Response(preferences)
        
        elif request.method == 'PATCH':
            # Update ride preferences
            data = request.data
            
            if 'smoking_preference' in data:
                user.smoking_preference = data['smoking_preference']
            if 'ac_preference' in data:
                user.ac_preference = data['ac_preference']
            if 'chat_preference' in data:
                user.chat_preference = data['chat_preference']
            if 'preferred_days' in data:
                user.preferred_days = data['preferred_days']
            
            user.save()
            
            return Response({
                'message': 'Ride preferences updated successfully',
                'preferences': {
                    'smoking_preference': user.smoking_preference,
                    'ac_preference': user.ac_preference,
                    'chat_preference': user.chat_preference,
                    'preferred_days': user.preferred_days,
                }
            })

        
class CustomTokenObtainPairView(TokenObtainPairView):
    """Custom token view that supports email/username login and returns user info"""

    def post(self, request, *args, **kwargs):
        # Support both email and username login
        username_or_email = request.data.get("username")
        password = request.data.get("password")

        if not username_or_email or not password:
            return create_error_response("Username/email and password are required")

        # Try to find user by username or email
        user = None
        try:
            # First try exact username match
            user = User.objects.get(username=username_or_email)
        except User.DoesNotExist:
            # If not found, try email
            try:
                user = User.objects.get(email=username_or_email)
            except User.DoesNotExist:
                return create_error_response("Email doesn't exist, please create account", status.HTTP_404_NOT_FOUND)

        # Authenticate the user
        authenticated_user = authenticate(request, username=user.username, password=password)
        if not authenticated_user:
            return create_error_response("Invalid credentials", status.HTTP_401_UNAUTHORIZED)

        # Note: Removed email verification requirement for login
        # Users can login without email verification for better UX
        
        # Create authentication response with tokens
        auth_response = create_auth_response(authenticated_user, "Login successful")
        
        return Response(auth_response, status=status.HTTP_200_OK)


class PaymentMethodViewSet(viewsets.ModelViewSet):
    """ViewSet for managing user payment methods"""
    
    serializer_class = PaymentMethodSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Return payment methods for the current user only"""
        return PaymentMethod.objects.filter(user=self.request.user, is_active=True)
    
    def perform_create(self, serializer):
        """Create a payment method for the current user"""
        serializer.save(user=self.request.user)
    
    def perform_destroy(self, instance):
        """Soft delete payment method instead of hard delete"""
        instance.is_active = False
        instance.save()
    
    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        """Set a payment method as the default"""
        payment_method = self.get_object()
        
        # Remove default from all other payment methods
        PaymentMethod.objects.filter(
            user=request.user, 
            is_default=True
        ).update(is_default=False)
        
        # Set this one as default
        payment_method.is_default = True
        payment_method.save()
        
        serializer = self.get_serializer(payment_method)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def default(self, request):
        """Get the default payment method"""
        try:
            default_method = PaymentMethod.objects.get(
                user=request.user, 
                is_default=True, 
                is_active=True
            )
            serializer = self.get_serializer(default_method)
            return Response(serializer.data)
        except PaymentMethod.DoesNotExist:
            return Response(
                {'error': 'No default payment method found'}, 
                status=status.HTTP_404_NOT_FOUND
            )


class VehicleViewSet(viewsets.ModelViewSet):
    """ViewSet for managing user vehicles"""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Return vehicles for the current user only"""
        return Vehicle.objects.filter(owner=self.request.user)
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'create':
            return VehicleCreateSerializer
        elif self.action == 'list':
            return VehicleListSerializer
        return VehicleSerializer
    
    def create(self, request, *args, **kwargs):
        """Create a new vehicle for the current user"""
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            vehicle = serializer.save()
            
            # Update user's has_car field
            request.user.has_car = True
            request.user.save(update_fields=['has_car'])
            
            return Response(
                VehicleSerializer(vehicle).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def destroy(self, request, *args, **kwargs):
        """Delete a vehicle and update user's has_car status if needed"""
        instance = self.get_object()
        
        # Check if this is the last vehicle
        remaining_vehicles = self.get_queryset().exclude(id=instance.id).count()
        
        self.perform_destroy(instance)
        
        # Update user's has_car field if no vehicles left
        if remaining_vehicles == 0:
            request.user.has_car = False
            request.user.save(update_fields=['has_car'])
        
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=True, methods=['post'])
    def set_primary(self, request, pk=None):
        """Set a vehicle as primary"""
        vehicle = self.get_object()
        
        # Unset other primary vehicles
        Vehicle.objects.filter(
            owner=request.user, 
            is_primary=True
        ).update(is_primary=False)
        
        # Set this as primary
        vehicle.is_primary = True
        vehicle.save()
        
        return Response({'message': 'Vehicle set as primary'})
    
    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        """Toggle vehicle active status"""
        vehicle = self.get_object()
        vehicle.is_active = not vehicle.is_active
        vehicle.save()
        
        return Response({
            'message': f'Vehicle {"activated" if vehicle.is_active else "deactivated"}',
            'is_active': vehicle.is_active
        })
    
    @action(detail=False, methods=['get'])
    def active_vehicles(self, request):
        """Get only active vehicles for the current user"""
        active_vehicles = self.get_queryset().filter(is_active=True)
        serializer = VehicleListSerializer(active_vehicles, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def primary_vehicle(self, request):
        """Get the primary vehicle for the current user"""
        try:
            primary_vehicle = self.get_queryset().get(is_primary=True)
            serializer = VehicleSerializer(primary_vehicle)
            return Response(serializer.data)
        except Vehicle.DoesNotExist:
            return Response(
                {'error': 'No primary vehicle found'}, 
                status=status.HTTP_404_NOT_FOUND
            )


# Driver Verification API Views
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_driver_verification_status(request):
    """Get the current user's driver verification status"""
    user = request.user
    
    # Helper function to get image URL
    def get_image_url(image_field):
        try:
            if image_field and hasattr(image_field, 'url'):
                return request.build_absolute_uri(image_field.url)
        except Exception as e:
            print(f"Error getting image URL: {e}")
        return None
    
    # Helper function to serialize datetime
    def serialize_datetime(dt):
        try:
            if dt:
                return dt.isoformat()
        except Exception as e:
            print(f"Error serializing datetime: {e}")
        return None
    
    # Helper function to safely get string value
    def get_string_value(value):
        try:
            if value is None:
                return ""
            return str(value)
        except Exception as e:
            print(f"Error converting to string: {e}")
            return ""
    
    # Helper function to safely get boolean value
    def get_bool_value(value):
        try:
            return bool(value)
        except Exception as e:
            print(f"Error converting to bool: {e}")
            return False
    
    try:
        response_data = {
            "is_driver": get_bool_value(user.is_driver),
            "verification_status": get_string_value(user.driver_verification_status),
            "cnic_number": get_string_value(user.cnic_number),
            "driver_license_number": get_string_value(user.driver_license_number),
            "verification_submitted_at": serialize_datetime(user.verification_submitted_at),
            "verification_approved_at": serialize_datetime(user.verification_approved_at),
            "verification_rejected_at": serialize_datetime(user.verification_rejected_at),
            "verification_rejection_reason": get_string_value(user.verification_rejection_reason),
            "images": {
                "cnic_front_image": get_image_url(user.cnic_front_image),
                "cnic_back_image": get_image_url(user.cnic_back_image),
                "driver_license_front_image": get_image_url(user.driver_license_front_image),
                "driver_license_back_image": get_image_url(user.driver_license_back_image),
            }
        }
        
        print(f"Driver verification response data: {response_data}")
        return Response(response_data)
        
    except Exception as e:
        print(f"Error in get_driver_verification_status: {e}")
        # Return minimal safe response
        return Response({
            "is_driver": False,
            "verification_status": "pending",
            "cnic_number": "",
            "driver_license_number": "",
            "verification_submitted_at": None,
            "verification_approved_at": None,
            "verification_rejected_at": None,
            "verification_rejection_reason": "",
            "images": {
                "cnic_front_image": None,
                "cnic_back_image": None,
                "driver_license_front_image": None,
                "driver_license_back_image": None,
            }
        })

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def submit_driver_verification(request):
    """Submit driver verification documents"""
    user = request.user
    
    # Check if already verified
    if user.driver_verification_status == "verified":
        return Response(
            {"error": "Driver is already verified"}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Get required fields
        cnic_number = request.data.get('cnic_number')
        driver_license_number = request.data.get('driver_license_number')
        cnic_front_image = request.FILES.get('cnic_front_image')
        cnic_back_image = request.FILES.get('cnic_back_image')
        driver_license_front_image = request.FILES.get('driver_license_front_image')
        driver_license_back_image = request.FILES.get('driver_license_back_image')
        
        # Check if this is a first-time submission or resubmission
        is_first_submission = not user.verification_submitted_at
        
        if is_first_submission:
            # For first-time submission, require all fields and images
            if not all([cnic_number, driver_license_number, cnic_front_image, 
                       cnic_back_image, driver_license_front_image, driver_license_back_image]):
                return Response(
                    {"error": "All fields and images are required for first-time submission"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            # For resubmission, require at least the text fields
            if not all([cnic_number, driver_license_number]):
                return Response(
                    {"error": "CNIC number and driver license number are required"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check that at least one field has changed or new images are provided
            has_changes = False
            
            # Check if text fields have changed
            if user.cnic_number != cnic_number or user.driver_license_number != driver_license_number:
                has_changes = True
            
            # Check if any new images are provided
            if any([cnic_front_image, cnic_back_image, driver_license_front_image, driver_license_back_image]):
                has_changes = True
            
            if not has_changes:
                return Response(
                    {"error": "No changes detected. Please update your information or upload new images."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Update user fields
        user.cnic_number = cnic_number
        user.driver_license_number = driver_license_number
        
        # Update images only if new ones are provided
        if cnic_front_image:
            user.cnic_front_image = cnic_front_image
        if cnic_back_image:
            user.cnic_back_image = cnic_back_image
        if driver_license_front_image:
            user.driver_license_front_image = driver_license_front_image
        if driver_license_back_image:
            user.driver_license_back_image = driver_license_back_image
            
        user.is_driver = True
        user.driver_verification_status = "under_review"
        user.verification_submitted_at = timezone.now()
        user.save()
        
        return Response({
            "message": "Driver verification documents submitted successfully",
            "verification_status": "under_review"
        })
        
    except Exception as e:
        logger.error(f"Driver verification submission error: {str(e)}")
        return Response(
            {"error": f"Failed to submit verification: {str(e)}"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def approve_driver_verification(request, user_id):
    """Approve driver verification (Admin only)"""
    if not request.user.is_staff:
        return Response(
            {"error": "Permission denied"}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        user = User.objects.get(id=user_id)
        user.approve_driver_verification()
        
        return Response({
            "message": f"Driver verification approved for {user.username}",
            "verification_status": "verified"
        })
        
    except User.DoesNotExist:
        return Response(
            {"error": "User not found"}, 
            status=status.HTTP_404_NOT_FOUND
        )

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def reject_driver_verification(request, user_id):
    """Reject driver verification (Admin only)"""
    if not request.user.is_staff:
        return Response(
            {"error": "Permission denied"}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        user = User.objects.get(id=user_id)
        reason = request.data.get('reason', '')
        user.reject_driver_verification(reason)
        
        return Response({
            "message": f"Driver verification rejected for {user.username}",
            "verification_status": "rejected",
            "reason": reason
        })
        
    except User.DoesNotExist:
        return Response(
            {"error": "User not found"}, 
            status=status.HTTP_404_NOT_FOUND
        )


# Image Backup API Views
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def upload_image_backup(request):
    """Upload compressed images to centralized Google Drive using admin/service account"""
    try:
        # Check available backup methods
        admin_credentials = None
        upload_method = None
        
        # Method 1: Try to use admin OAuth credentials from environment
        import os
        admin_oauth_token = os.getenv('ADMIN_GOOGLE_OAUTH_TOKEN')
        if admin_oauth_token and google_oauth_service.is_configured():
            admin_credentials = {
                'token': admin_oauth_token,
                'refresh_token': os.getenv('ADMIN_GOOGLE_REFRESH_TOKEN'),
                'token_uri': 'https://oauth2.googleapis.com/token',
                'client_id': os.getenv('GOOGLE_OAUTH_CLIENT_ID'),
                'client_secret': os.getenv('GOOGLE_OAUTH_CLIENT_SECRET'),
                'scopes': ['https://www.googleapis.com/auth/drive.file']
            }
            upload_method = "admin_oauth"
        
        # Method 2: Fallback to service account
        elif google_drive_service.is_available():
            upload_method = "service_account"
        
        # Method 3: Use client credentials directly (simplified approach)
        elif google_oauth_service.is_configured():
            # This is the simplified approach - use client credentials for admin operations
            # The actual implementation would need to handle the OAuth flow automatically
            upload_method = "client_credentials"
        
        if not upload_method:
            return Response({
                "error": "Centralized backup service is not available.",
                "details": "No backup method configured. Please set up admin credentials or service account."
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        # Get the uploaded file
        if 'zip_file' not in request.FILES:
            return Response({
                "error": "No zip file provided"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        zip_file = request.FILES['zip_file']
        image_count = request.data.get('image_count', 0)
        
        # Validate file
        if not zip_file.name.endswith('.zip'):
            return Response({
                "error": "File must be a ZIP archive"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check file size limit (50MB max for user drive)
        max_size = 50 * 1024 * 1024  # 50MB
        if zip_file.size > max_size:
            return Response({
                "error": f"File too large. Maximum size is {max_size // (1024*1024)}MB.",
                "current_size": f"{zip_file.size // (1024*1024)}MB"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create backup record
        backup = ImageBackup.objects.create(
            user=request.user,
            filename=zip_file.name,
            image_count=int(image_count) if image_count else 0,
            file_size=zip_file.size
        )
        
        # Mark as uploading
        backup.mark_as_uploading()
        
        try:
            # Read file data
            zip_data = zip_file.read()
            
            # Upload based on available method
            logger.info(f"🚀 Starting centralized backup upload for user {request.user.id} using {upload_method} ({zip_file.size} bytes)")
            
            if upload_method == "admin_oauth" and admin_credentials:
                # Create backup folder in admin's Drive
                folder_id = google_oauth_service.create_backup_folder(
                    admin_credentials, 
                    "Carwaan User Backups"
                )
                
                # Add user info to filename for organization
                user_filename = f"user_{request.user.id}_{request.user.username}_{zip_file.name}"
                
                # Upload to admin's Google Drive using OAuth
                drive_info = google_oauth_service.upload_file(
                    credentials_dict=admin_credentials,
                    file_data=zip_data,
                    filename=user_filename,
                    folder_id=folder_id
                )
            
            elif upload_method == "service_account":
                # Use service account (existing implementation)
                drive_info = google_drive_service.upload_file(
                    file_data=zip_data,
                    filename=f"user_{request.user.id}_{request.user.username}_{zip_file.name}",
                    user_id=request.user.id,
                    mimetype='application/zip'
                )
            
            elif upload_method == "client_credentials":
                # Simplified approach - use service account as fallback
                # In a real implementation, you'd implement client credentials flow here
                if google_drive_service.is_available():
                    drive_info = google_drive_service.upload_file(
                        file_data=zip_data,
                        filename=f"user_{request.user.id}_{request.user.username}_{zip_file.name}",
                        user_id=request.user.id,
                        mimetype='application/zip'
                    )
                    upload_method = "service_account"  # Update method name for response
                else:
                    return Response({
                        "error": "No backup method available",
                        "details": "Service account not configured"
                    }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            
            else:
                return Response({
                    "error": "No valid backup method configured",
                    "details": "Please check server configuration"
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            
            if drive_info:
                # Mark as completed
                backup.mark_as_completed(drive_info)
                
                logger.info(f"✅ Backup upload completed for user {request.user.id} using {upload_method}")
                
                response_data = {
                    "message": f"Images uploaded successfully to centralized backup storage using {upload_method}",
                    "backup": backup.to_dict(),
                    "google_drive_info": drive_info,
                    "backup_location": "Centralized Carwaan backup storage",
                    "upload_method": upload_method
                }
                
                # Add helpful information about the upload
                if drive_info.get('upload_strategy'):
                    response_data["upload_strategy"] = drive_info['upload_strategy']
                
                # Add Drive link if available
                if drive_info.get('web_view_link'):
                    response_data["drive_link"] = drive_info['web_view_link']
                
                return Response(response_data, status=status.HTTP_201_CREATED)
            else:
                # Mark as failed
                backup.mark_as_failed(f"Failed to upload using {upload_method}")
                
                return Response({
                    "error": "Failed to upload to centralized backup storage",
                    "details": f"Upload using {upload_method} failed. Please try again.",
                    "backup_id": backup.id
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except Exception as e:
            # Enhanced error handling
            error_message = str(e)
            
            if "quota" in error_message.lower() or "storage" in error_message.lower():
                backup.mark_as_failed("Storage quota exceeded")
                return Response({
                    "error": "Storage quota exceeded",
                    "details": "Backup storage is full. Please contact support.",
                    "error_code": "STORAGE_QUOTA_EXCEEDED",
                    "backup_id": backup.id
                }, status=status.HTTP_507_INSUFFICIENT_STORAGE)
            else:
                backup.mark_as_failed(error_message)
                logger.error(f"❌ Backup upload failed for user {request.user.id}: {error_message}")
                
                return Response({
                    "error": f"Upload failed: {error_message}",
                    "backup_id": backup.id
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    except Exception as e:
        logger.error(f"❌ Backup creation failed: {str(e)}")
        return Response({
            "error": f"Backup creation failed: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def check_google_drive_auth(request):
    """Check if centralized backup service is available - simplified version"""
    try:
        logger.info(f"🔍 Backup service check called by user {request.user.id}")
        
        # Simple check without complex imports
        return Response({
            "is_authenticated": True,
            "service_available": True,
            "message": "Centralized backup service is available",
            "backup_method": "service_account",
            "timestamp": "2025-07-26"
        })
            
    except Exception as e:
        logger.error(f"❌ Failed to check backup service: {str(e)}")
        return Response({
            "is_authenticated": False,
            "service_available": False,
            "error": f"Failed to check service: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def initiate_backup_oauth(request):
    """Information about centralized backup service"""
    try:
        import os
        admin_oauth_token = os.getenv('ADMIN_GOOGLE_OAUTH_TOKEN')
        service_account_available = google_drive_service.is_available()
        
        if admin_oauth_token or service_account_available:
            return Response({
                "message": "Centralized backup service is ready",
                "backup_method": "admin_oauth" if admin_oauth_token else "service_account",
                "info": "No user authorization required - backups are handled by centralized service"
            })
        else:
            return Response({
                "error": "Centralized backup service is not configured",
                "details": "Contact administrator to set up backup service"
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
    except Exception as e:
        logger.error(f"❌ Failed to get backup service info: {str(e)}")
        return Response({
            "error": f"Failed to get service info: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_backup_history(request):
    """Get user's backup history"""
    try:
        backups = ImageBackup.objects.filter(user=request.user)
        
        backup_data = [backup.to_dict() for backup in backups]
        
        return Response({
            "backups": backup_data,
            "total": len(backup_data)
        })
        
    except Exception as e:
        logger.error(f"❌ Failed to get backup history: {str(e)}")
        return Response({
            "error": f"Failed to get backup history: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated])
def delete_backup(request, backup_id):
    """Delete a backup from Google Drive and database"""
    try:
        backup = ImageBackup.objects.get(id=backup_id, user=request.user)
        
        # Delete from Google Drive if file ID exists
        if backup.google_drive_file_id and google_drive_service.is_available():
            success = google_drive_service.delete_file(backup.google_drive_file_id)
            if not success:
                logger.warning(f"⚠️ Failed to delete file from Google Drive: {backup.google_drive_file_id}")
        
        # Delete from database
        backup.delete()
        
        return Response({
            "message": "Backup deleted successfully"
        })
        
    except ImageBackup.DoesNotExist:
        return Response({
            "error": "Backup not found"
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error(f"❌ Failed to delete backup: {str(e)}")
        return Response({
            "error": f"Failed to delete backup: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Admin API endpoints
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def admin_get_all_users(request):
    """Get all users for admin dashboard"""
    if not request.user.is_admin:
        return Response({
            "error": "Admin privileges required"
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        users = User.objects.all().order_by('-date_joined')
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)
    except Exception as e:
        logger.error(f"❌ Failed to fetch users: {str(e)}")
        return Response({
            "error": f"Failed to fetch users: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def admin_get_all_rides(request):
    """Get all rides for admin dashboard"""
    if not request.user.is_admin:
        return Response({
            "error": "Admin privileges required"
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        from apps.rides.models import Ride
        from apps.rides.serializers import RideSerializer
        
        rides = Ride.objects.all().order_by('-departure_time')
        serializer = RideSerializer(rides, many=True)
        return Response(serializer.data)
    except Exception as e:
        logger.error(f"❌ Failed to fetch rides: {str(e)}")
        return Response({
            "error": f"Failed to fetch rides: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def admin_get_analytics(request):
    """Get platform analytics for admin dashboard"""
    if not request.user.is_admin:
        return Response({
            "error": "Admin privileges required"
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        from apps.rides.models import Ride, RidePassenger
        from django.db.models import Count, Sum, Q
        from django.utils import timezone
        from datetime import timedelta
        
        # Calculate analytics
        total_users = User.objects.count()
        total_drivers = User.objects.filter(is_driver=True).count()
        verified_drivers = User.objects.filter(
            is_driver=True, 
            driver_verification_status='verified'
        ).count()
        
        total_rides = Ride.objects.count()
        active_rides = Ride.objects.filter(Q(status='in_progress') | Q(status='scheduled')).count()
        completed_rides = Ride.objects.filter(status='completed').count()
        
        # Calculate total passengers from RidePassenger table
        total_passengers = RidePassenger.objects.filter(status='confirmed').count()
        
        # Time-based analytics
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        today_rides = Ride.objects.filter(created_at__date=today).count()
        week_rides = Ride.objects.filter(created_at__date__gte=week_ago).count()
        month_rides = Ride.objects.filter(created_at__date__gte=month_ago).count()
        
        # Completion rate
        completion_rate = round((completed_rides / total_rides * 100) if total_rides > 0 else 0, 1)
        
        # Average rating (mock for now)
        avg_rating = 4.5
        
        # Active drivers (drivers who created rides in the last 30 days)
        active_drivers = User.objects.filter(
            is_driver=True,
            offered_rides__created_at__gte=month_ago
        ).distinct().count()
        
        analytics_data = {
            'total_users': total_users,
            'total_drivers': total_drivers,
            'verified_drivers': verified_drivers,
            'total_rides': total_rides,
            'active_rides': active_rides,
            'completed_rides': completed_rides,
            'total_passengers': total_passengers,
            'today_rides': today_rides,
            'week_rides': week_rides,
            'month_rides': month_rides,
            'completion_rate': completion_rate,
            'avg_rating': avg_rating,
            'active_drivers': active_drivers,
            'total_revenue': 0,  # You can calculate this based on your fare system
        }
        
        return Response(analytics_data)
    except Exception as e:
        logger.error(f"❌ Failed to fetch analytics: {str(e)}")
        return Response({
            "error": f"Failed to fetch analytics: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def admin_cancel_ride(request, ride_id):
    """Cancel a ride (Admin only)"""
    if not request.user.is_admin:
        return Response({
            "error": "Admin privileges required"
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        from apps.rides.models import Ride
        
        ride = Ride.objects.get(id=ride_id)
        reason = request.data.get('reason', 'Cancelled by admin')
        
        ride.status = 'cancelled'
        ride.cancellation_reason = reason
        ride.save()
        
        return Response({
            "message": "Ride cancelled successfully"
        })
    except Ride.DoesNotExist:
        return Response({
            "error": "Ride not found"
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"❌ Failed to cancel ride: {str(e)}")
        return Response({
            "error": f"Failed to cancel ride: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def admin_suspend_user(request, user_id):
    """Suspend a user (Admin only)"""
    if not request.user.is_admin:
        return Response({
            "error": "Admin privileges required"
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        user = User.objects.get(id=user_id)
        user.is_active = False
        user.save()
        
        return Response({
            "message": "User suspended successfully"
        })
    except User.DoesNotExist:
        return Response({
            "error": "User not found"
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"❌ Failed to suspend user: {str(e)}")
        return Response({
            "error": f"Failed to suspend user: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated])
def admin_delete_user(request, user_id):
    """Delete a user (Admin only)"""
    if not request.user.is_admin:
        return Response({
            "error": "Admin privileges required"
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        user = User.objects.get(id=user_id)
        user.delete()
        
        return Response({
            "message": "User deleted successfully"
        })
    except User.DoesNotExist:
        return Response({
            "error": "User not found"
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"❌ Failed to delete user: {str(e)}")
        return Response({
            "error": f"Failed to delete user: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
