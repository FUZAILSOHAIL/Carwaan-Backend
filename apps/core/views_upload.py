# apps/core/views_upload.py
import os
import tempfile
import zipfile
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)

@api_view(['POST'])
@permission_classes([IsAuthenticated])  # Remove if you don't need authentication
def upload_zip_file(request):
    """
    API endpoint to receive and save ZIP files from Flutter app
    Accepts multipart/form-data with 'zip_file' field
    """
    try:
        # Check if file is present
        if 'zip_file' not in request.FILES:
            return Response({
                'error': 'No zip_file provided in request'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        zip_file = request.FILES['zip_file']
        
        # Validate file type
        if not zip_file.name.endswith('.zip'):
            return Response({
                'error': 'File must be a ZIP archive'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate file size (max 100MB)
        max_size = 100 * 1024 * 1024  # 100MB
        if zip_file.size > max_size:
            return Response({
                'error': f'File too large. Maximum size is {max_size // (1024*1024)}MB'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create uploads directory if it doesn't exist
        upload_dir = getattr(settings, 'ZIP_UPLOAD_DIR', '/tmp/carwaan_uploads')
        os.makedirs(upload_dir, exist_ok=True)
        
        # Generate unique filename
        user_id = request.user.id if hasattr(request, 'user') and request.user.is_authenticated else 'anonymous'
        import uuid
        from datetime import datetime
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        filename = f"user_{user_id}_{timestamp}_{unique_id}.zip"
        
        # Save file to disk
        file_path = os.path.join(upload_dir, filename)
        
        with open(file_path, 'wb+') as destination:
            for chunk in zip_file.chunks():
                destination.write(chunk)
        
        # Optional: Validate ZIP file integrity
        try:
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                file_count = len(zip_ref.namelist())
                logger.info(f"✅ ZIP file validated: {file_count} files inside")
        except zipfile.BadZipFile:
            os.remove(file_path)  # Clean up invalid file
            return Response({
                'error': 'Invalid ZIP file format'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Log successful upload
        logger.info(f"📦 ZIP file uploaded successfully: {file_path} ({zip_file.size} bytes)")
        
        # Return success response
        return Response({
            'status': 'success',
            'message': 'ZIP file uploaded successfully',
            'filename': filename,
            'file_path': file_path,
            'size_bytes': zip_file.size,
            'size_mb': round(zip_file.size / (1024 * 1024), 2),
            'file_count': file_count,
            'upload_time': datetime.now().isoformat()
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"❌ Error uploading ZIP file: {str(e)}")
        return Response({
            'error': f'Upload failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_uploaded_files(request):
    """
    Optional: List all uploaded ZIP files for the authenticated user
    """
    try:
        upload_dir = getattr(settings, 'ZIP_UPLOAD_DIR', '/tmp/carwaan_uploads')
        
        if not os.path.exists(upload_dir):
            return Response({
                'files': [],
                'count': 0
            })
        
        user_id = request.user.id if hasattr(request, 'user') and request.user.is_authenticated else 'anonymous'
        user_prefix = f"user_{user_id}_"
        
        files = []
        for filename in os.listdir(upload_dir):
            if filename.startswith(user_prefix) and filename.endswith('.zip'):
                file_path = os.path.join(upload_dir, filename)
                file_stats = os.stat(file_path)
                
                files.append({
                    'filename': filename,
                    'size_bytes': file_stats.st_size,
                    'size_mb': round(file_stats.st_size / (1024 * 1024), 2),
                    'upload_time': file_stats.st_mtime,
                })
        
        # Sort by upload time (newest first)
        files.sort(key=lambda x: x['upload_time'], reverse=True)
        
        return Response({
            'files': files,
            'count': len(files)
        })
        
    except Exception as e:
        logger.error(f"❌ Error listing files: {str(e)}")
        return Response({
            'error': f'Failed to list files: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_uploaded_file(request, filename):
    """
    Optional: Delete a specific uploaded ZIP file
    """
    try:
        upload_dir = getattr(settings, 'ZIP_UPLOAD_DIR', '/tmp/carwaan_uploads')
        user_id = request.user.id if hasattr(request, 'user') and request.user.is_authenticated else 'anonymous'
        
        # Security check: ensure user can only delete their own files
        if not filename.startswith(f"user_{user_id}_"):
            return Response({
                'error': 'Permission denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        file_path = os.path.join(upload_dir, filename)
        
        if not os.path.exists(file_path):
            return Response({
                'error': 'File not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        os.remove(file_path)
        logger.info(f"🗑️ Deleted file: {file_path}")
        
        return Response({
            'status': 'success',
            'message': f'File {filename} deleted successfully'
        })
        
    except Exception as e:
        logger.error(f"❌ Error deleting file: {str(e)}")
        return Response({
            'error': f'Failed to delete file: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
