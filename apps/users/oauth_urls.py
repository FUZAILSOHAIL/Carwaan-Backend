# URL patterns for OAuth integration
from django.urls import path
from . import oauth_views

oauth_urlpatterns = [
    # OAuth endpoints
    path('auth/google/initiate/', oauth_views.initiate_google_oauth, name='initiate_google_oauth'),
    path('auth/google/callback/', oauth_views.google_oauth_callback, name='google_oauth_callback'),
    path('auth/google/status/', oauth_views.oauth_status, name='oauth_status'),
    path('auth/google/revoke/', oauth_views.revoke_oauth, name='revoke_oauth'),
    
    # OAuth backup upload
    path('backup/oauth-upload/', oauth_views.upload_with_oauth, name='oauth_upload'),
]
