# OAuth Views for Google Drive Integration
from django.shortcuts import redirect
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework import permissions, status
from rest_framework.response import Response
from apps.core.services.google_oauth_service import google_oauth_service
import logging

logger = logging.getLogger(__name__)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def initiate_google_oauth(request):
    """Initiate Google OAuth flow"""
    try:
        if not google_oauth_service.is_configured():
            return Response({
                "error": "Google OAuth not configured. Please set up OAuth client credentials."
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        # Generate state parameter for security
        state = f"user_{request.user.id}"
        
        # Get authorization URL
        auth_url = google_oauth_service.get_authorization_url(request, state)
        
        return Response({
            "authorization_url": auth_url,
            "message": "Redirect user to this URL to authorize Google Drive access"
        })
        
    except Exception as e:
        logger.error(f"❌ Failed to initiate OAuth: {str(e)}")
        return Response({
            "error": f"Failed to initiate OAuth: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def google_oauth_callback(request):
    """Handle Google OAuth callback"""
    try:
        # Get authorization code from query parameters
        authorization_code = request.GET.get('code')
        state = request.GET.get('state')
        error = request.GET.get('error')
        
        if error:
            logger.error(f"❌ OAuth error: {error}")
            return JsonResponse({
                "error": f"OAuth authorization failed: {error}"
            }, status=400)
        
        if not authorization_code:
            return JsonResponse({
                "error": "Authorization code not received"
            }, status=400)
        
        # Handle callback
        result = google_oauth_service.handle_callback(request, authorization_code)
        
        if result['success']:
            # Store OAuth credentials in session
            request.session['google_oauth_authorized'] = True
            request.session['google_user_info'] = result['user_info']
            
            return JsonResponse({
                "message": "Google Drive access authorized successfully",
                "user_info": result['user_info'],
                "status": "success"
            })
        else:
            return JsonResponse({
                "error": result['error']
            }, status=400)
            
    except Exception as e:
        logger.error(f"❌ OAuth callback failed: {str(e)}")
        return JsonResponse({
            "error": f"OAuth callback failed: {str(e)}"
        }, status=500)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def upload_with_oauth(request):
    """Upload backup using OAuth credentials"""
    try:
        # Check if user has OAuth credentials
        google_credentials = request.session.get('google_credentials')
        if not google_credentials:
            return Response({
                "error": "Google Drive not authorized. Please authorize access first.",
                "oauth_required": True
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Get the uploaded file
        if 'zip_file' not in request.FILES:
            return Response({
                "error": "No zip file provided"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        zip_file = request.FILES['zip_file']
        
        # Validate file
        if not zip_file.name.endswith('.zip'):
            return Response({
                "error": "File must be a ZIP archive"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create backup folder in user's Drive
        folder_id = google_oauth_service.create_backup_folder(google_credentials)
        
        # Upload file
        zip_data = zip_file.read()
        drive_info = google_oauth_service.upload_file(
            google_credentials,
            zip_data,
            zip_file.name,
            folder_id
        )
        
        if drive_info:
            # Create backup record in database
            from apps.users.models import ImageBackup
            backup = ImageBackup.objects.create(
                user=request.user,
                filename=zip_file.name,
                image_count=int(request.data.get('image_count', 0)),
                file_size=zip_file.size
            )
            backup.mark_as_completed(drive_info)
            
            return Response({
                "message": "Images uploaded successfully to your Google Drive",
                "backup": backup.to_dict(),
                "google_drive_info": drive_info
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                "error": "Failed to upload to Google Drive"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    except Exception as e:
        logger.error(f"❌ OAuth upload failed: {str(e)}")
        return Response({
            "error": f"Upload failed: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def oauth_status(request):
    """Check OAuth authorization status"""
    google_credentials = request.session.get('google_credentials')
    google_authorized = request.session.get('google_oauth_authorized', False)
    google_user_info = request.session.get('google_user_info', {})
    
    return Response({
        "authorized": google_authorized and google_credentials is not None,
        "user_info": google_user_info,
        "has_credentials": google_credentials is not None
    })


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def revoke_oauth(request):
    """Revoke OAuth authorization"""
    try:
        # Clear session data
        request.session.pop('google_credentials', None)
        request.session.pop('google_oauth_authorized', None)
        request.session.pop('google_user_info', None)
        request.session.pop('oauth_flow', None)
        
        return Response({
            "message": "Google Drive authorization revoked successfully"
        })
        
    except Exception as e:
        return Response({
            "error": f"Failed to revoke authorization: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
