"""
Channel Service Integration
Handles channel management and configuration
"""

import requests
import logging
from typing import Dict, Any, Optional
from config.settings import Config

logger = logging.getLogger(__name__)

class ChannelService:
    """Channel service client"""
    
    def __init__(self):
        self.base_url = Config.TELEGIVE_CHANNEL_URL
        self.timeout = 30
    
    def _make_request(self, method: str, endpoint: str, 
                     headers: Optional[Dict[str, str]] = None,
                     json_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make HTTP request to channel service"""
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
                logger.error(f"Channel service error {response.status_code}: {response.text}")
                return {
                    'success': False,
                    'error': f'Channel service returned {response.status_code}',
                    'error_code': 'CHANNEL_SERVICE_ERROR'
                }
                
        except requests.exceptions.Timeout:
            logger.error(f"Channel service timeout for {endpoint}")
            return {
                'success': False,
                'error': 'Channel service timeout',
                'error_code': 'CHANNEL_SERVICE_TIMEOUT'
            }
        except requests.exceptions.ConnectionError:
            logger.error(f"Channel service connection error for {endpoint}")
            return {
                'success': False,
                'error': 'Channel service unavailable',
                'error_code': 'CHANNEL_SERVICE_UNAVAILABLE'
            }
        except Exception as e:
            logger.error(f"Channel service request failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'CHANNEL_SERVICE_REQUEST_FAILED'
            }
    
    def get_channel_info(self, account_id: int, auth_token: str) -> Dict[str, Any]:
        """Get channel information for account"""
        headers = {'Authorization': f'Bearer {auth_token}'}
        return self._make_request(
            'GET',
            f'/api/channels/account/{account_id}',
            headers=headers
        )
    
    def get_channel_by_id(self, channel_id: int, auth_token: str) -> Dict[str, Any]:
        """Get specific channel information"""
        headers = {'Authorization': f'Bearer {auth_token}'}
        return self._make_request(
            'GET',
            f'/api/channels/{channel_id}',
            headers=headers
        )
    
    def verify_bot_admin_status(self, channel_id: int, bot_token: str, 
                               auth_token: str) -> Dict[str, Any]:
        """Verify that bot is admin in the channel"""
        headers = {'Authorization': f'Bearer {auth_token}'}
        return self._make_request(
            'POST',
            f'/api/channels/{channel_id}/verify-bot-admin',
            headers=headers,
            json_data={'bot_token': bot_token}
        )
    
    def update_channel_stats(self, channel_id: int, stats_data: Dict[str, Any], 
                           auth_token: str) -> Dict[str, Any]:
        """Update channel statistics"""
        headers = {'Authorization': f'Bearer {auth_token}'}
        return self._make_request(
            'PUT',
            f'/api/channels/{channel_id}/stats',
            headers=headers,
            json_data=stats_data
        )
    
    def log_channel_activity(self, channel_id: int, activity_data: Dict[str, Any], 
                           auth_token: str) -> Dict[str, Any]:
        """Log channel activity"""
        headers = {'Authorization': f'Bearer {auth_token}'}
        return self._make_request(
            'POST',
            f'/api/channels/{channel_id}/activity',
            headers=headers,
            json_data=activity_data
        )
    
    def get_subscription_requirements(self, giveaway_id: int, 
                                    auth_token: str) -> Dict[str, Any]:
        """Get subscription requirements for giveaway"""
        headers = {'Authorization': f'Bearer {auth_token}'}
        return self._make_request(
            'GET',
            f'/api/channels/giveaway/{giveaway_id}/subscription-requirements',
            headers=headers
        )

# Global channel service instance
channel_service = ChannelService()

def get_channel_info(account_id: int, auth_token: str) -> Dict[str, Any]:
    """Get channel information (convenience function)"""
    return channel_service.get_channel_info(account_id, auth_token)

def get_channel_by_id(channel_id: int, auth_token: str) -> Dict[str, Any]:
    """Get channel by ID (convenience function)"""
    return channel_service.get_channel_by_id(channel_id, auth_token)

def verify_bot_admin_status(channel_id: int, bot_token: str, 
                          auth_token: str) -> Dict[str, Any]:
    """Verify bot admin status (convenience function)"""
    return channel_service.verify_bot_admin_status(channel_id, bot_token, auth_token)

def update_channel_stats(channel_id: int, stats_data: Dict[str, Any], 
                       auth_token: str) -> Dict[str, Any]:
    """Update channel stats (convenience function)"""
    return channel_service.update_channel_stats(channel_id, stats_data, auth_token)

def log_channel_activity(channel_id: int, activity_data: Dict[str, Any], 
                       auth_token: str) -> Dict[str, Any]:
    """Log channel activity (convenience function)"""
    return channel_service.log_channel_activity(channel_id, activity_data, auth_token)

def get_subscription_requirements(giveaway_id: int, auth_token: str) -> Dict[str, Any]:
    """Get subscription requirements (convenience function)"""
    return channel_service.get_subscription_requirements(giveaway_id, auth_token)

