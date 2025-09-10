"""
Giveaway Service Integration
Handles giveaway management and operations
"""

import requests
import logging
from typing import Dict, Any, Optional
from config.settings import Config

logger = logging.getLogger(__name__)

class TelegiveService:
    """Giveaway service client"""
    
    def __init__(self):
        self.base_url = Config.TELEGIVE_GIVEAWAY_URL
        self.timeout = 30
    
    def _make_request(self, method: str, endpoint: str, 
                     headers: Optional[Dict[str, str]] = None,
                     json_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make HTTP request to giveaway service"""
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
                logger.error(f"Giveaway service error {response.status_code}: {response.text}")
                return {
                    'success': False,
                    'error': f'Giveaway service returned {response.status_code}',
                    'error_code': 'GIVEAWAY_SERVICE_ERROR'
                }
                
        except requests.exceptions.Timeout:
            logger.error(f"Giveaway service timeout for {endpoint}")
            return {
                'success': False,
                'error': 'Giveaway service timeout',
                'error_code': 'GIVEAWAY_SERVICE_TIMEOUT'
            }
        except requests.exceptions.ConnectionError:
            logger.error(f"Giveaway service connection error for {endpoint}")
            return {
                'success': False,
                'error': 'Giveaway service unavailable',
                'error_code': 'GIVEAWAY_SERVICE_UNAVAILABLE'
            }
        except Exception as e:
            logger.error(f"Giveaway service request failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'GIVEAWAY_SERVICE_REQUEST_FAILED'
            }
    
    def get_giveaway_by_id(self, giveaway_id: int, auth_token: str) -> Dict[str, Any]:
        """Get giveaway information by ID"""
        headers = {'Authorization': f'Bearer {auth_token}'}
        return self._make_request(
            'GET',
            f'/api/giveaways/{giveaway_id}',
            headers=headers
        )
    
    def get_giveaway_by_token(self, result_token: str) -> Dict[str, Any]:
        """Get giveaway information by result token"""
        return self._make_request(
            'GET',
            f'/api/giveaways/token/{result_token}'
        )
    
    def update_giveaway_message_id(self, giveaway_id: int, message_id: int, 
                                  auth_token: str) -> Dict[str, Any]:
        """Update giveaway with posted message ID"""
        headers = {'Authorization': f'Bearer {auth_token}'}
        return self._make_request(
            'PUT',
            f'/api/giveaways/{giveaway_id}/message-id',
            headers=headers,
            json_data={'message_id': message_id}
        )
    
    def update_conclusion_message_id(self, giveaway_id: int, message_id: int, 
                                   auth_token: str) -> Dict[str, Any]:
        """Update giveaway with conclusion message ID"""
        headers = {'Authorization': f'Bearer {auth_token}'}
        return self._make_request(
            'PUT',
            f'/api/giveaways/{giveaway_id}/conclusion-message-id',
            headers=headers,
            json_data={'message_id': message_id}
        )
    
    def get_giveaway_participants(self, giveaway_id: int, 
                                auth_token: str) -> Dict[str, Any]:
        """Get all participants for a giveaway"""
        headers = {'Authorization': f'Bearer {auth_token}'}
        return self._make_request(
            'GET',
            f'/api/giveaways/{giveaway_id}/participants',
            headers=headers
        )
    
    def get_giveaway_winners(self, giveaway_id: int, 
                           auth_token: str) -> Dict[str, Any]:
        """Get winners for a giveaway"""
        headers = {'Authorization': f'Bearer {auth_token}'}
        return self._make_request(
            'GET',
            f'/api/giveaways/{giveaway_id}/winners',
            headers=headers
        )
    
    def mark_giveaway_published(self, giveaway_id: int, publish_data: Dict[str, Any], 
                              auth_token: str) -> Dict[str, Any]:
        """Mark giveaway as published"""
        headers = {'Authorization': f'Bearer {auth_token}'}
        return self._make_request(
            'PUT',
            f'/api/giveaways/{giveaway_id}/publish',
            headers=headers,
            json_data=publish_data
        )
    
    def mark_giveaway_concluded(self, giveaway_id: int, conclusion_data: Dict[str, Any], 
                              auth_token: str) -> Dict[str, Any]:
        """Mark giveaway as concluded"""
        headers = {'Authorization': f'Bearer {auth_token}'}
        return self._make_request(
            'PUT',
            f'/api/giveaways/{giveaway_id}/conclude',
            headers=headers,
            json_data=conclusion_data
        )
    
    def log_giveaway_interaction(self, giveaway_id: int, interaction_data: Dict[str, Any], 
                               auth_token: str) -> Dict[str, Any]:
        """Log giveaway interaction"""
        headers = {'Authorization': f'Bearer {auth_token}'}
        return self._make_request(
            'POST',
            f'/api/giveaways/{giveaway_id}/interactions',
            headers=headers,
            json_data=interaction_data
        )

# Global giveaway service instance
telegive_service = TelegiveService()

def get_giveaway_by_id(giveaway_id: int, auth_token: str) -> Dict[str, Any]:
    """Get giveaway by ID (convenience function)"""
    return telegive_service.get_giveaway_by_id(giveaway_id, auth_token)

def get_giveaway_by_token(result_token: str) -> Dict[str, Any]:
    """Get giveaway by token (convenience function)"""
    return telegive_service.get_giveaway_by_token(result_token)

def update_giveaway_message_id(giveaway_id: int, message_id: int, 
                             auth_token: str) -> Dict[str, Any]:
    """Update giveaway message ID (convenience function)"""
    return telegive_service.update_giveaway_message_id(giveaway_id, message_id, auth_token)

def update_conclusion_message_id(giveaway_id: int, message_id: int, 
                               auth_token: str) -> Dict[str, Any]:
    """Update conclusion message ID (convenience function)"""
    return telegive_service.update_conclusion_message_id(giveaway_id, message_id, auth_token)

def get_giveaway_participants(giveaway_id: int, auth_token: str) -> Dict[str, Any]:
    """Get giveaway participants (convenience function)"""
    return telegive_service.get_giveaway_participants(giveaway_id, auth_token)

def get_giveaway_winners(giveaway_id: int, auth_token: str) -> Dict[str, Any]:
    """Get giveaway winners (convenience function)"""
    return telegive_service.get_giveaway_winners(giveaway_id, auth_token)

def mark_giveaway_published(giveaway_id: int, publish_data: Dict[str, Any], 
                          auth_token: str) -> Dict[str, Any]:
    """Mark giveaway published (convenience function)"""
    return telegive_service.mark_giveaway_published(giveaway_id, publish_data, auth_token)

def mark_giveaway_concluded(giveaway_id: int, conclusion_data: Dict[str, Any], 
                          auth_token: str) -> Dict[str, Any]:
    """Mark giveaway concluded (convenience function)"""
    return telegive_service.mark_giveaway_concluded(giveaway_id, conclusion_data, auth_token)

def log_giveaway_interaction(giveaway_id: int, interaction_data: Dict[str, Any], 
                           auth_token: str) -> Dict[str, Any]:
    """Log giveaway interaction (convenience function)"""
    return telegive_service.log_giveaway_interaction(giveaway_id, interaction_data, auth_token)

