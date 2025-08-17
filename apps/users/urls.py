from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    UserViewSet, PaymentMethodViewSet, VehicleViewSet, CustomTokenObtainPairView, 
    health_check, get_driver_verification_status, submit_driver_verification,
    approve_driver_verification, reject_driver_verification,
    upload_image_backup, get_backup_history, delete_backup,
    check_google_drive_auth,
    # Temporarily removed: initiate_backup_oauth
)
from .oauth_urls import oauth_urlpatterns
from .android_oauth_urls import android_oauth_urlpatterns
from .admin_urls import urlpatterns as admin_urlpatterns

router = DefaultRouter()
router.register('users', UserViewSet)
router.register('payment-methods', PaymentMethodViewSet, basename='paymentmethod')
router.register('vehicles', VehicleViewSet, basename='vehicle')

urlpatterns = [
    path('', include(router.urls)),
    path('test/', health_check, name='health_check'),
    path('auth/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/register/', UserViewSet.as_view({'post': 'register'}), name='register'),
    # OTP endpoints
    path('auth/send_otp/', UserViewSet.as_view({'post': 'send_otp'}), name='send_otp'),
    path('auth/verify_otp/', UserViewSet.as_view({'post': 'verify_otp'}), name='verify_otp'),
    path('auth/login_with_otp/', UserViewSet.as_view({'post': 'login_with_otp'}), name='login_with_otp'),
    path('auth/verify_login_otp/', UserViewSet.as_view({'post': 'verify_login_otp'}), name='verify_login_otp'),
    # Profile endpoints
    path('users/me/', UserViewSet.as_view({'get': 'me', 'patch': 'me', 'put': 'me'}), name='user_profile'),
    # Driver verification endpoints
    path('driver/verification/status/', get_driver_verification_status, name='driver_verification_status'),
    path('driver/verification/submit/', submit_driver_verification, name='submit_driver_verification'),
    path('admin/driver/verification/approve/<int:user_id>/', approve_driver_verification, name='approve_driver_verification'),
    path('admin/driver/verification/reject/<int:user_id>/', reject_driver_verification, name='reject_driver_verification'),
    # Image backup endpoints
    path('backup/upload/', upload_image_backup, name='upload_image_backup'),
    path('backup/history/', get_backup_history, name='get_backup_history'),
    path('backup/delete/<int:backup_id>/', delete_backup, name='delete_backup'),
    path('backup/auth/check/', check_google_drive_auth, name='check_google_drive_auth'),
    # path('backup/auth/initiate/', initiate_backup_oauth, name='initiate_backup_oauth'),  # Temporarily disabled
    # Test endpoint to verify routing
    path('backup/test/', health_check, name='backup_test'),
    # Legacy admin endpoints - these are deprecated, use admin_urls.py instead
    # path('admin/users/', admin_get_all_users, name='admin_get_all_users'),
    # path('admin/rides/', admin_get_all_rides, name='admin_get_all_rides'),
    # path('admin/analytics/', admin_get_analytics, name='admin_get_analytics'),
    # path('admin/rides/<int:ride_id>/cancel/', admin_cancel_ride, name='admin_cancel_ride'),
    # path('admin/users/<int:user_id>/suspend/', admin_suspend_user, name='admin_suspend_user'),
    # path('admin/users/<int:user_id>/delete/', admin_delete_user, name='admin_delete_user'),
] + oauth_urlpatterns + android_oauth_urlpatterns + admin_urlpatterns