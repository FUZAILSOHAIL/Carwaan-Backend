import os
import io
import json
import logging
from typing import Optional, Dict, Any
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from django.conf import settings
from django.urls import reverse
from django.http import HttpRequest

logger = logging.getLogger(__name__)

class GoogleOAuthService:
    """Service for Google OAuth authentication and Drive API access"""
    
    def __init__(self):
        self.client_config = None
        self.scopes = [
            'https://www.googleapis.com/auth/drive.file',
            'https://www.googleapis.com/auth/userinfo.profile',
            'https://www.googleapis.com/auth/userinfo.email'
        ]
        self._load_client_config()
    
    def _load_client_config(self):
        """Load OAuth client configuration from environment or file"""
        try:
            # Try to load from environment variables first
            client_id = os.getenv('GOOGLE_OAUTH_CLIENT_ID')
            client_secret = os.getenv('GOOGLE_OAUTH_CLIENT_SECRET')
            
            if client_id and client_secret:
                self.client_config = {
                    "web": {
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs"
                    }
                }
                logger.info("✅ Google OAuth client config loaded from environment")
                return
            
            # Try to load from file
            client_config_file = os.getenv('GOOGLE_OAUTH_CLIENT_FILE', 'client_secret.json')
            client_config_path = os.path.join(settings.BASE_DIR, client_config_file)
            
            if os.path.exists(client_config_path):
                with open(client_config_path, 'r') as f:
                    file_config = json.load(f)
                
                # Handle both "web" and "installed" client types
                if "web" in file_config:
                    self.client_config = file_config
                    logger.info("✅ Google OAuth client config loaded from file (web)")
                elif "installed" in file_config:
                    # Convert installed client to web format (with warning)
                    installed_config = file_config["installed"]
                    if "client_secret" not in installed_config:
                        logger.error("❌ Desktop application client detected - missing client_secret")
                        logger.error("❌ Please create a Web Application OAuth client instead")
                        return
                    
                    self.client_config = {
                        "web": installed_config
                    }
                    logger.warning("⚠️ Using desktop client config - please create web application client")
                else:
                    logger.error("❌ Invalid client configuration format")
                    return
                    
                return
            
            logger.error("❌ Google OAuth client configuration not found")
            
        except Exception as e:
            logger.error(f"❌ Failed to load OAuth client config: {str(e)}")
    
    def is_configured(self) -> bool:
        """Check if OAuth service is properly configured"""
        return self.client_config is not None
    
    def get_authorization_url(self, request: HttpRequest, state: str = None) -> str:
        """Get authorization URL for OAuth flow"""
        if not self.is_configured():
            raise Exception("OAuth service not configured")
        
        # Build redirect URI
        redirect_uri = request.build_absolute_uri(reverse('google_oauth_callback'))
        
        # Create flow
        flow = Flow.from_client_config(
            self.client_config,
            scopes=self.scopes,
            redirect_uri=redirect_uri
        )
        
        # Generate authorization URL
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            state=state
        )
        
        # Store flow configuration in session for callback (not the flow object itself)
        request.session['oauth_client_config'] = self.client_config
        request.session['oauth_redirect_uri'] = redirect_uri
        request.session['oauth_scopes'] = self.scopes
        
        return authorization_url
    
    def handle_callback(self, request: HttpRequest, authorization_code: str) -> Dict[str, Any]:
        """Handle OAuth callback and exchange code for tokens"""
        try:
            # Retrieve flow configuration from session
            client_config = request.session.get('oauth_client_config')
            redirect_uri = request.session.get('oauth_redirect_uri')
            scopes = request.session.get('oauth_scopes')
            
            if not all([client_config, redirect_uri, scopes]):
                raise Exception("OAuth flow configuration not found in session")
            
            # Recreate flow
            flow = Flow.from_client_config(
                client_config,
                scopes=scopes,
                redirect_uri=redirect_uri
            )
            
            # Exchange authorization code for tokens
            flow.fetch_token(code=authorization_code)
            
            # Get credentials
            credentials = flow.credentials
            
            # Get user info
            user_info = self._get_user_info(credentials)
            
            # Store credentials in session or database
            request.session['google_credentials'] = credentials_to_dict(credentials)
            
            return {
                'success': True,
                'user_info': user_info,
                'credentials': credentials_to_dict(credentials)
            }
            
        except Exception as e:
            logger.error(f"❌ OAuth callback failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _get_user_info(self, credentials: Credentials) -> Dict[str, Any]:
        """Get user information from Google API"""
        try:
            # Build OAuth2 service
            oauth2_service = build('oauth2', 'v2', credentials=credentials)
            user_info = oauth2_service.userinfo().get().execute()
            
            return {
                'id': user_info.get('id'),
                'email': user_info.get('email'),
                'name': user_info.get('name'),
                'picture': user_info.get('picture'),
                'verified_email': user_info.get('verified_email', False)
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get user info: {str(e)}")
            return {}
    
    def create_drive_service(self, credentials_dict: Dict[str, Any]):
        """Create Google Drive service from credentials"""
        try:
            credentials = Credentials.from_authorized_user_info(credentials_dict)
            
            # Refresh credentials if needed
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            
            return build('drive', 'v3', credentials=credentials)
            
        except Exception as e:
            logger.error(f"❌ Failed to create Drive service: {str(e)}")
            return None
    
    def upload_file(self, credentials_dict: Dict[str, Any], file_data: bytes, 
                   filename: str, folder_id: str = None) -> Optional[Dict[str, Any]]:
        """Upload file to user's Google Drive"""
        try:
            drive_service = self.create_drive_service(credentials_dict)
            if not drive_service:
                return None
            
            # Create file metadata
            file_metadata = {
                'name': filename,
                'parents': [folder_id] if folder_id else []
            }
            
            # Create media upload
            media = MediaIoBaseUpload(
                io.BytesIO(file_data),
                mimetype='application/zip',
                resumable=True
            )
            
            # Upload file
            file = drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,name,size,webViewLink,createdTime'
            ).execute()
            
            logger.info(f"✅ File uploaded to user's Drive: {file.get('id')}")
            
            return {
                'file_id': file.get('id'),
                'name': file.get('name'),
                'size': file.get('size'),
                'web_view_link': file.get('webViewLink'),
                'created_time': file.get('createdTime'),
                'upload_strategy': 'oauth_user_drive'
            }
            
        except Exception as e:
            logger.error(f"❌ OAuth upload failed: {str(e)}")
            return None
    
    def create_backup_folder(self, credentials_dict: Dict[str, Any], folder_name: str = "Carwaan Backups") -> Optional[str]:
        """Create backup folder in user's Drive"""
        try:
            drive_service = self.create_drive_service(credentials_dict)
            if not drive_service:
                return None
            
            # Check if folder already exists
            results = drive_service.files().list(
                q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                fields='files(id, name)'
            ).execute()
            
            folders = results.get('files', [])
            if folders:
                logger.info(f"📁 Using existing backup folder: {folders[0]['id']}")
                return folders[0]['id']
            
            # Create new folder
            folder_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            
            folder = drive_service.files().create(
                body=folder_metadata,
                fields='id,name'
            ).execute()
            
            logger.info(f"📁 Created backup folder: {folder.get('id')}")
            return folder.get('id')
            
        except Exception as e:
            logger.error(f"❌ Failed to create backup folder: {str(e)}")
            return None


def credentials_to_dict(credentials: Credentials) -> Dict[str, Any]:
    """Convert credentials to dictionary for storage"""
    return {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }


# Global instance
google_oauth_service = GoogleOAuthService()
