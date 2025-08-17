"""
Google Drive service for file uploads and management.
"""
import os
import json
import logging
from typing import Optional, Dict, Any
from django.conf import settings
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account
from google.auth.exceptions import GoogleAuthError

logger = logging.getLogger(__name__)


class GoogleDriveService:
    """Service for handling Google Drive operations."""

    def __init__(self):
        self.service = None
        self.credentials = None
        self._initialize_service()

    def _initialize_service(self):
        """Initialize Google Drive service with credentials."""
        try:
            # Get service account file path
            service_account_file = getattr(settings, 'GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE', None)
            
            if not service_account_file:
                logger.warning("Google Drive service account file not configured")
                return

            # Check if file exists
            if not os.path.exists(service_account_file):
                logger.warning(f"Google Drive service account file not found: {service_account_file}")
                return

            # Load credentials
            self.credentials = service_account.Credentials.from_service_account_file(
                service_account_file,
                scopes=['https://www.googleapis.com/auth/drive.file']
            )

            # Build service
            self.service = build('drive', 'v3', credentials=self.credentials)
            logger.info("Google Drive service initialized successfully")

        except FileNotFoundError:
            logger.warning("Google Drive service account file not found")
        except json.JSONDecodeError:
            logger.error("Invalid Google Drive service account file format")
        except GoogleAuthError as e:
            logger.error(f"Google Drive authentication error: {e}")
        except Exception as e:
            logger.error(f"Failed to initialize Google Drive service: {e}")

    def is_available(self) -> bool:
        """Check if Google Drive service is available."""
        return self.service is not None

    def upload_file(self, file_path: str, filename: Optional[str] = None, 
                   folder_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Upload a file to Google Drive.
        
        Args:
            file_path: Path to the file to upload
            filename: Custom filename (optional)
            folder_id: Parent folder ID (optional)
            
        Returns:
            Dict with file info or None if failed
        """
        if not self.is_available():
            logger.warning("Google Drive service not available")
            return None

        try:
            if not os.path.exists(file_path):
                logger.error(f"File not found: {file_path}")
                return None

            # Prepare file metadata
            file_metadata = {
                'name': filename or os.path.basename(file_path)
            }
            
            if folder_id:
                file_metadata['parents'] = [folder_id]

            # Create media upload
            media = MediaFileUpload(file_path, resumable=True)

            # Upload file
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,name,size,webViewLink'
            ).execute()

            logger.info(f"File uploaded to Google Drive: {file['name']} (ID: {file['id']})")
            
            return {
                'id': file['id'],
                'name': file['name'],
                'size': file.get('size'),
                'web_view_link': file.get('webViewLink'),
                'success': True
            }

        except Exception as e:
            logger.error(f"Failed to upload file to Google Drive: {e}")
            return None

    def delete_file(self, file_id: str) -> bool:
        """
        Delete a file from Google Drive.
        
        Args:
            file_id: Google Drive file ID
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_available():
            logger.warning("Google Drive service not available")
            return False

        try:
            self.service.files().delete(fileId=file_id).execute()
            logger.info(f"File deleted from Google Drive: {file_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete file from Google Drive: {e}")
            return False

    def get_file_info(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a file in Google Drive.
        
        Args:
            file_id: Google Drive file ID
            
        Returns:
            Dict with file info or None if failed
        """
        if not self.is_available():
            logger.warning("Google Drive service not available")
            return None

        try:
            file = self.service.files().get(
                fileId=file_id,
                fields='id,name,size,webViewLink,createdTime,modifiedTime'
            ).execute()

            return {
                'id': file['id'],
                'name': file['name'],
                'size': file.get('size'),
                'web_view_link': file.get('webViewLink'),
                'created_time': file.get('createdTime'),
                'modified_time': file.get('modifiedTime'),
                'success': True
            }

        except Exception as e:
            logger.error(f"Failed to get file info from Google Drive: {e}")
            return None

    def create_folder(self, folder_name: str, parent_id: Optional[str] = None) -> Optional[str]:
        """
        Create a folder in Google Drive.
        
        Args:
            folder_name: Name of the folder
            parent_id: Parent folder ID (optional)
            
        Returns:
            Folder ID if successful, None otherwise
        """
        if not self.is_available():
            logger.warning("Google Drive service not available")
            return None

        try:
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            
            if parent_id:
                file_metadata['parents'] = [parent_id]

            folder = self.service.files().create(
                body=file_metadata,
                fields='id'
            ).execute()

            logger.info(f"Folder created in Google Drive: {folder_name} (ID: {folder['id']})")
            return folder['id']

        except Exception as e:
            logger.error(f"Failed to create folder in Google Drive: {e}")
            return None

    def list_files(self, folder_id: Optional[str] = None, limit: int = 100) -> Optional[list]:
        """
        List files in Google Drive.
        
        Args:
            folder_id: Folder ID to list files from (optional)
            limit: Maximum number of files to return
            
        Returns:
            List of files or None if failed
        """
        if not self.is_available():
            logger.warning("Google Drive service not available")
            return None

        try:
            query = f"'{folder_id}' in parents" if folder_id else None
            
            results = self.service.files().list(
                q=query,
                pageSize=limit,
                fields="nextPageToken, files(id, name, size, webViewLink, createdTime)"
            ).execute()

            return results.get('files', [])

        except Exception as e:
            logger.error(f"Failed to list files from Google Drive: {e}")
            return None


# Create a global instance
google_drive_service = GoogleDriveService()
