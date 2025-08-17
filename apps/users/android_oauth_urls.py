# URL patterns for Android OAuth integration
from django.urls import path
from . import android_oauth_views

android_oauth_urlpatterns = [
    # Android OAuth endpoints
    path('auth/google/android-verify/', android_oauth_views.verify_android_google_token, name='verify_android_google_token'),
    path('auth/google/android-status/', android_oauth_views.android_auth_status, name='android_auth_status'),
    path('auth/google/android-revoke/', android_oauth_views.revoke_android_auth, name='revoke_android_auth'),
    
    # Android backup upload
    path('backup/android-upload/', android_oauth_views.upload_with_android_token, name='android_upload'),
]
