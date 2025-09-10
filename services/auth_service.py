"""
Auth Service Integration
Handles authentication and authorization with the auth service
"""

import requests
import logging
from typing import Dict, Any, Optional
from config.settings import Config

logger = logging.getLogger(__name__)

class AuthService:
    """Auth service client"""
    
    def __init__(self):
        self.base_url = Config.TELEGIVE_AUTH_URL
        self.timeout = 30
    
    def _make_request(self, method: str, endpoint: str, 
                     headers: Optional[Dict[str, str]] = None,
                     json_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make HTTP request to auth service"""
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
                logger.error(f"Auth service error {response.status_code}: {response.text}")
                return {
                    'success': False,
                    'error': f'Auth service returned {response.status_code}',
                    'error_code': 'AUTH_SERVICE_ERROR'
                }
                
        except requests.exceptions.Timeout:
            logger.error(f"Auth service timeout for {endpoint}")
            return {
                'success': False,
                'error': 'Auth service timeout',
                'error_code': 'AUTH_SERVICE_TIMEOUT'
            }
        except requests.exceptions.ConnectionError:
            logger.error(f"Auth service connection error for {endpoint}")
            return {
                'success': False,
                'error': 'Auth service unavailable',
                'error_code': 'AUTH_SERVICE_UNAVAILABLE'
            }
        except Exception as e:
            logger.error(f"Auth service request failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'AUTH_SERVICE_REQUEST_FAILED'
            }
    
    def validate_service_token(self, token: str) -> Dict[str, Any]:
        """Validate service authentication token"""
        return self._make_request(
            'POST',
            '/api/auth/validate-service-token',
            json_data={'token': token}
        )
    
    def get_account_info(self, account_id: int, auth_token: str) -> Dict[str, Any]:
        """Get account information"""
        headers = {'Authorization': f'Bearer {auth_token}'}
        return self._make_request(
            'GET',
            f'/api/accounts/{account_id}',
            headers=headers
        )
    
    def get_bot_token(self, account_id: int, auth_token: str) -> Dict[str, Any]:
        """Get bot token for account"""
        headers = {'Authorization': f'Bearer {auth_token}'}
        return self._make_request(
            'GET',
            f'/api/accounts/{account_id}/bot-token',
            headers=headers
        )
    
    def verify_bot_ownership(self, account_id: int, bot_token: str, auth_token: str) -> Dict[str, Any]:
        """Verify that the bot token belongs to the account"""
        headers = {'Authorization': f'Bearer {auth_token}'}
        return self._make_request(
            'POST',
            f'/api/accounts/{account_id}/verify-bot',
            headers=headers,
            json_data={'bot_token': bot_token}
        )
    
    def log_bot_interaction(self, account_id: int, interaction_data: Dict[str, Any], 
                           auth_token: str) -> Dict[str, Any]:
        """Log bot interaction for analytics"""
        headers = {'Authorization': f'Bearer {auth_token}'}
        return self._make_request(
            'POST',
            f'/api/accounts/{account_id}/bot-interactions',
            headers=headers,
            json_data=interaction_data
        )

# Global auth service instance
auth_service = AuthService()

def validate_service_token(token: str) -> Dict[str, Any]:
    """Validate service token (convenience function)"""
    return auth_service.validate_service_token(token)

def get_account_info(account_id: int, auth_token: str) -> Dict[str, Any]:
    """Get account information (convenience function)"""
    return auth_service.get_account_info(account_id, auth_token)

def get_bot_token(account_id: int, auth_token: str) -> Dict[str, Any]:
    """Get bot token for account (convenience function)"""
    return auth_service.get_bot_token(account_id, auth_token)

def verify_bot_ownership(account_id: int, bot_token: str, auth_token: str) -> Dict[str, Any]:
    """Verify bot ownership (convenience function)"""
    return auth_service.verify_bot_ownership(account_id, bot_token, auth_token)

def log_bot_interaction(account_id: int, interaction_data: Dict[str, Any], 
                       auth_token: str) -> Dict[str, Any]:
    """Log bot interaction (convenience function)"""
    return auth_service.log_bot_interaction(account_id, interaction_data, auth_token)

