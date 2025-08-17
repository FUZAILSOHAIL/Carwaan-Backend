# Android OAuth Views for Google Drive Integration
from django.shortcuts import redirect
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework import permissions, status
from rest_framework.response import Response
from google.auth.transport import requests
from google.oauth2 import id_token
import logging
import requests as http_requests

logger = logging.getLogger(__name__)

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def verify_android_google_token(request):
    """Verify Google ID token from Android app and authenticate user"""
    try:
        access_token = request.data.get('access_token')
        id_token_str = request.data.get('id_token')
        user_info = request.data.get('user_info', {})
        
        if not access_token or not id_token_str:
            return Response({
                "error": "Access token and ID token are required"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Verify the ID token
        try:
            # Verify token with Google
            idinfo = id_token.verify_oauth2_token(
                id_token_str, 
                requests.Request(), 
                "1038122554209-0k201vnjvrr4igv5ci6e4momk1j4fcas.apps.googleusercontent.com"
            )
            
            # Verify the issuer
            if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
                raise ValueError('Invalid issuer')
                
        except ValueError as e:
            logger.error(f"❌ Invalid ID token: {str(e)}")
            return Response({
                "error": f"Invalid ID token: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Extract user information
        google_user_id = idinfo['sub']
        email = idinfo['email']
        name = idinfo.get('name', '')
        picture = idinfo.get('picture', '')
        
        # Find or create user
        from apps.users.models import User
        try:
            user = User.objects.get(email=email)
            # Update user info if needed
            if not user.first_name and name:
                names = name.split(' ', 1)
                user.first_name = names[0]
                if len(names) > 1:
                    user.last_name = names[1]
                user.save()
        except User.DoesNotExist:
            # Create new user
            names = name.split(' ', 1) if name else ['', '']
            user = User.objects.create_user(
                username=email,  # Use email as username
                email=email,
                first_name=names[0],
                last_name=names[1] if len(names) > 1 else '',
                email_verified=True,  # Google has verified the email
            )
        
        # Store Google access token in session for Drive operations
        request.session['google_access_token'] = access_token
        request.session['google_user_id'] = google_user_id
        
        # Create authentication response
        from .views import create_auth_response
        auth_response = create_auth_response(user, "Google authentication successful")
        
        # Add Google Drive capabilities info
        auth_response['google_drive_enabled'] = True
        auth_response['access_token_stored'] = True
        
        return Response(auth_response)
        
    except Exception as e:
        logger.error(f"❌ Android Google auth failed: {str(e)}")
        return Response({
            "error": f"Authentication failed: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def upload_with_android_token(request):
    """Upload backup using stored Google access token from Android"""
    try:
        # Check if we have a stored Google access token
        access_token = request.session.get('google_access_token')
        if not access_token:
            return Response({
                "error": "No Google access token found. Please sign in with Google first.",
                "google_auth_required": True
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Verify token is still valid
        token_info_response = http_requests.get(
            f'https://www.googleapis.com/oauth2/v1/tokeninfo?access_token={access_token}'
        )
        
        if token_info_response.status_code != 200:
            return Response({
                "error": "Google access token has expired. Please sign in again.",
                "google_auth_required": True
            }, status=status.HTTP_401_UNAUTHORIZED)
        
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
        
        # File size limit for direct user uploads (larger than service account)
        max_size = 100 * 1024 * 1024  # 100MB for user's own Drive
        if zip_file.size > max_size:
            return Response({
                "error": f"File too large. Maximum size is {max_size // (1024*1024)}MB.",
                "current_size": f"{zip_file.size // (1024*1024)}MB"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create backup record
        from apps.users.models import ImageBackup
        backup = ImageBackup.objects.create(
            user=request.user,
            filename=zip_file.name,
            image_count=int(image_count) if image_count else 0,
            file_size=zip_file.size
        )
        
        backup.mark_as_uploading()
        
        try:
            # Upload directly to user's Google Drive using their access token
            upload_result = _upload_to_user_drive(
                access_token=access_token,
                file_data=zip_file.read(),
                filename=zip_file.name
            )
            
            if upload_result['success']:
                # Mark as completed
                drive_info = {
                    'file_id': upload_result['file_id'],
                    'name': upload_result['name'],
                    'web_view_link': upload_result['web_view_link'],
                    'size': upload_result.get('size'),
                    'upload_strategy': 'android_user_drive'
                }
                backup.mark_as_completed(drive_info)
                
                return Response({
                    "message": "Images uploaded successfully to your Google Drive",
                    "backup": backup.to_dict(),
                    "google_drive_info": drive_info
                }, status=status.HTTP_201_CREATED)
            else:
                backup.mark_as_failed(upload_result['error'])
                return Response({
                    "error": f"Upload failed: {upload_result['error']}",
                    "backup_id": backup.id
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except Exception as e:
            backup.mark_as_failed(str(e))
            logger.error(f"❌ Android upload failed: {str(e)}")
            return Response({
                "error": f"Upload failed: {str(e)}",
                "backup_id": backup.id
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    except Exception as e:
        logger.error(f"❌ Android upload preparation failed: {str(e)}")
        return Response({
            "error": f"Upload preparation failed: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _upload_to_user_drive(access_token, file_data, filename):
    """Upload file to user's Google Drive using their access token"""
    try:
        import io
        import json
        
        # First, create or get backup folder
        folder_id = _create_backup_folder(access_token)
        
        # Prepare file metadata
        metadata = {
            'name': filename,
            'parents': [folder_id] if folder_id else []
        }
        
        # Create multipart upload
        files = {
            'metadata': (None, json.dumps(metadata), 'application/json'),
            'data': (filename, io.BytesIO(file_data), 'application/zip')
        }
        
        headers = {
            'Authorization': f'Bearer {access_token}'
        }
        
        response = http_requests.post(
            'https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,name,webViewLink,size',
            headers=headers,
            files=files
        )
        
        if response.status_code == 200:
            data = response.json()
            return {
                'success': True,
                'file_id': data['id'],
                'name': data['name'],
                'web_view_link': data['webViewLink'],
                'size': data.get('size')
            }
        else:
            return {
                'success': False,
                'error': f'Google Drive API error: {response.status_code} - {response.text}'
            }
            
    except Exception as e:
        return {
            'success': False,
            'error': f'Upload error: {str(e)}'
        }


def _create_backup_folder(access_token):
    """Create or get backup folder in user's Google Drive"""
    try:
        folder_name = 'Carwaan Backups'
        
        # Search for existing folder
        search_response = http_requests.get(
            'https://www.googleapis.com/drive/v3/files',
            headers={'Authorization': f'Bearer {access_token}'},
            params={
                'q': f'name="{folder_name}" and mimeType="application/vnd.google-apps.folder" and trashed=false',
                'fields': 'files(id,name)'
            }
        )
        
        if search_response.status_code == 200:
            files = search_response.json().get('files', [])
            if files:
                return files[0]['id']
        
        # Create new folder
        create_response = http_requests.post(
            'https://www.googleapis.com/drive/v3/files',
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            },
            json={
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
        )
        
        if create_response.status_code == 200:
            return create_response.json()['id']
        else:
            logger.warning(f"Failed to create backup folder: {create_response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Error creating backup folder: {str(e)}")
        return None


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def android_auth_status(request):
    """Check Android Google authentication status"""
    access_token = request.session.get('google_access_token')
    google_user_id = request.session.get('google_user_id')
    
    if access_token:
        # Verify token is still valid
        token_info_response = http_requests.get(
            f'https://www.googleapis.com/oauth2/v1/tokeninfo?access_token={access_token}'
        )
        
        token_valid = token_info_response.status_code == 200
        
        return Response({
            "authenticated": token_valid,
            "google_user_id": google_user_id if token_valid else None,
            "drive_access": token_valid,
            "token_valid": token_valid
        })
    else:
        return Response({
            "authenticated": False,
            "google_user_id": None,
            "drive_access": False,
            "token_valid": False
        })


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def revoke_android_auth(request):
    """Revoke Android Google authentication"""
    try:
        access_token = request.session.get('google_access_token')
        
        if access_token:
            # Revoke token with Google
            revoke_response = http_requests.post(
                f'https://oauth2.googleapis.com/revoke?token={access_token}'
            )
            
            # Clear session data regardless of revoke response
            request.session.pop('google_access_token', None)
            request.session.pop('google_user_id', None)
            
            return Response({
                "message": "Google authentication revoked successfully",
                "revoked": revoke_response.status_code == 200
            })
        else:
            return Response({
                "message": "No active Google authentication found"
            })
            
    except Exception as e:
        return Response({
            "error": f"Failed to revoke authentication: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
