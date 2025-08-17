"""
Direct OAuth Token Exchange for Admin Setup

This creates a simple endpoint for exchanging authorization codes for tokens.
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
import requests
import os
import logging

logger = logging.getLogger(__name__)

@csrf_exempt
@require_http_methods(["POST"])
def exchange_auth_code(request):
    """Exchange authorization code for access token"""
    try:
        data = json.loads(request.body)
        auth_code = data.get('code')
        
        if not auth_code:
            return JsonResponse({
                'error': 'Authorization code is required'
            }, status=400)
        
        # Get OAuth credentials from environment
        client_id = os.getenv('GOOGLE_OAUTH_CLIENT_ID')
        client_secret = os.getenv('GOOGLE_OAUTH_CLIENT_SECRET')
        
        if not client_id or not client_secret:
            return JsonResponse({
                'error': 'OAuth credentials not configured'
            }, status=500)
        
        # Exchange code for tokens
        redirect_uri = "http://localhost:8000/api/auth/google/callback/"
        
        token_data = {
            'code': auth_code,
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code'
        }
        
        response = requests.post('https://oauth2.googleapis.com/token', data=token_data)
        
        if response.status_code == 200:
            tokens = response.json()
            
            # Log success
            logger.info("✅ Successfully exchanged auth code for tokens")
            
            return JsonResponse({
                'access_token': tokens.get('access_token'),
                'refresh_token': tokens.get('refresh_token'),
                'expires_in': tokens.get('expires_in'),
                'scope': tokens.get('scope'),
                'token_type': tokens.get('token_type')
            })
        else:
            error_data = response.json() if response.headers.get('content-type') == 'application/json' else {}
            logger.error(f"❌ Token exchange failed: {response.status_code} - {error_data}")
            
            return JsonResponse({
                'error': 'Token exchange failed',
                'details': error_data.get('error_description', 'Unknown error')
            }, status=400)
            
    except json.JSONDecodeError:
        return JsonResponse({
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"❌ Auth code exchange error: {str(e)}")
        return JsonResponse({
            'error': f'Server error: {str(e)}'
        }, status=500)

@csrf_exempt
@require_http_methods(["GET"])
def get_oauth_url(request):
    """Get the OAuth authorization URL"""
    try:
        client_id = os.getenv('GOOGLE_OAUTH_CLIENT_ID')
        
        if not client_id:
            return JsonResponse({
                'error': 'OAuth client ID not configured'
            }, status=500)
        
        redirect_uri = "http://localhost:8000/api/auth/google/callback/"
        scope = "https://www.googleapis.com/auth/drive.file"
        
        auth_url = f"https://accounts.google.com/oauth/authorize?client_id={client_id}&redirect_uri={redirect_uri}&scope={scope}&response_type=code&access_type=offline&prompt=consent"
        
        return JsonResponse({
            'auth_url': auth_url
        })
        
    except Exception as e:
        logger.error(f"❌ OAuth URL generation error: {str(e)}")
        return JsonResponse({
            'error': f'Server error: {str(e)}'
        }, status=500)
