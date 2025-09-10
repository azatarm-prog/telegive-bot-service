"""
Media Service Integration
Handles media file management and retrieval
"""

import requests
import logging
from typing import Dict, Any, Optional
from config.settings import Config

logger = logging.getLogger(__name__)

class MediaService:
    """Media service client"""
    
    def __init__(self):
        self.base_url = Config.TELEGIVE_MEDIA_URL
        self.timeout = 60  # Longer timeout for media operations
    
    def _make_request(self, method: str, endpoint: str, 
                     headers: Optional[Dict[str, str]] = None,
                     json_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make HTTP request to media service"""
        url = f"{self.base_url}{endpoint}"
        
        default_headers = {
            'Content-Type': 'application/json',
            'X-Service-Name': 'bot-service'
        }
        
        if headers:
            default_headers.update(headers)
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=default_headers,
                json=json_data,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Media service error {response.status_code}: {response.text}")
                return {
                    'success': False,
                    'error': f'Media service returned {response.status_code}',
                    'error_code': 'MEDIA_SERVICE_ERROR'
                }
                
        except requests.exceptions.Timeout:
            logger.error(f"Media service timeout for {endpoint}")
            return {
                'success': False,
                'error': 'Media service timeout',
                'error_code': 'MEDIA_SERVICE_TIMEOUT'
            }
        except requests.exceptions.ConnectionError:
            logger.error(f"Media service connection error for {endpoint}")
            return {
                'success': False,
                'error': 'Media service unavailable',
                'error_code': 'MEDIA_SERVICE_UNAVAILABLE'
            }
        except Exception as e:
            logger.error(f"Media service request failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'MEDIA_SERVICE_REQUEST_FAILED'
            }
    
    def get_file_info(self, file_id: int, auth_token: str) -> Dict[str, Any]:
        """Get media file information"""
        headers = {'Authorization': f'Bearer {auth_token}'}
        return self._make_request(
            'GET',
            f'/api/media/files/{file_id}',
            headers=headers
        )
    
    def download_file(self, file_id: int, auth_token: str) -> Dict[str, Any]:
        """Download media file"""
        headers = {'Authorization': f'Bearer {auth_token}'}
        url = f"{self.base_url}/api/media/files/{file_id}/download"
        
        try:
            response = requests.get(
                url,
                headers=headers,
                timeout=self.timeout,
                stream=True
            )
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'content': response.content,
                    'content_type': response.headers.get('Content-Type'),
                    'filename': response.headers.get('Content-Disposition', '').split('filename=')[-1].strip('"')
                }
            else:
                return {
                    'success': False,
                    'error': f'Download failed with status {response.status_code}',
                    'error_code': 'DOWNLOAD_FAILED'
                }
                
        except Exception as e:
            logger.error(f"File download failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'DOWNLOAD_REQUEST_FAILED'
            }
    
    def get_file_url(self, file_id: int, auth_token: str) -> Dict[str, Any]:
        """Get direct URL for media file"""
        headers = {'Authorization': f'Bearer {auth_token}'}
        return self._make_request(
            'GET',
            f'/api/media/files/{file_id}/url',
            headers=headers
        )
    
    def validate_file_access(self, file_id: int, account_id: int, 
                           auth_token: str) -> Dict[str, Any]:
        """Validate that account has access to file"""
        headers = {'Authorization': f'Bearer {auth_token}'}
        return self._make_request(
            'POST',
            f'/api/media/files/{file_id}/validate-access',
            headers=headers,
            json_data={'account_id': account_id}
        )
    
    def get_file_metadata(self, file_id: int, auth_token: str) -> Dict[str, Any]:
        """Get file metadata (size, type, dimensions, etc.)"""
        headers = {'Authorization': f'Bearer {auth_token}'}
        return self._make_request(
            'GET',
            f'/api/media/files/{file_id}/metadata',
            headers=headers
        )
    
    def log_file_usage(self, file_id: int, usage_data: Dict[str, Any], 
                      auth_token: str) -> Dict[str, Any]:
        """Log file usage for analytics"""
        headers = {'Authorization': f'Bearer {auth_token}'}
        return self._make_request(
            'POST',
            f'/api/media/files/{file_id}/usage',
            headers=headers,
            json_data=usage_data
        )

# Global media service instance
media_service = MediaService()

def get_file_info(file_id: int, auth_token: str) -> Dict[str, Any]:
    """Get file info (convenience function)"""
    return media_service.get_file_info(file_id, auth_token)

def download_file(file_id: int, auth_token: str) -> Dict[str, Any]:
    """Download file (convenience function)"""
    return media_service.download_file(file_id, auth_token)

def get_file_url(file_id: int, auth_token: str) -> Dict[str, Any]:
    """Get file URL (convenience function)"""
    return media_service.get_file_url(file_id, auth_token)

def validate_file_access(file_id: int, account_id: int, auth_token: str) -> Dict[str, Any]:
    """Validate file access (convenience function)"""
    return media_service.validate_file_access(file_id, account_id, auth_token)

def get_file_metadata(file_id: int, auth_token: str) -> Dict[str, Any]:
    """Get file metadata (convenience function)"""
    return media_service.get_file_metadata(file_id, auth_token)

def log_file_usage(file_id: int, usage_data: Dict[str, Any], auth_token: str) -> Dict[str, Any]:
    """Log file usage (convenience function)"""
    return media_service.log_file_usage(file_id, usage_data, auth_token)

