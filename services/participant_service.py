"""
Participant Service Integration
Handles participant registration, captcha validation, and winner checking
"""

import requests
import logging
from typing import Dict, Any, Optional
from config.settings import Config

logger = logging.getLogger(__name__)

class ParticipantService:
    """Participant service client"""
    
    def __init__(self):
        self.base_url = Config.TELEGIVE_PARTICIPANT_URL
        self.timeout = 30
    
    def _make_request(self, method: str, endpoint: str, 
                     headers: Optional[Dict[str, str]] = None,
                     json_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make HTTP request to participant service"""
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
                logger.error(f"Participant service error {response.status_code}: {response.text}")
                return {
                    'success': False,
                    'error': f'Participant service returned {response.status_code}',
                    'error_code': 'PARTICIPANT_SERVICE_ERROR'
                }
                
        except requests.exceptions.Timeout:
            logger.error(f"Participant service timeout for {endpoint}")
            return {
                'success': False,
                'error': 'Participant service timeout',
                'error_code': 'PARTICIPANT_SERVICE_TIMEOUT'
            }
        except requests.exceptions.ConnectionError:
            logger.error(f"Participant service connection error for {endpoint}")
            return {
                'success': False,
                'error': 'Participant service unavailable',
                'error_code': 'PARTICIPANT_SERVICE_UNAVAILABLE'
            }
        except Exception as e:
            logger.error(f"Participant service request failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'PARTICIPANT_SERVICE_REQUEST_FAILED'
            }
    
    def register_participation(self, giveaway_id: int, user_id: int, 
                             user_info: Dict[str, Any]) -> Dict[str, Any]:
        """Register user participation in giveaway"""
        return self._make_request(
            'POST',
            '/api/participants/register',
            json_data={
                'giveaway_id': giveaway_id,
                'user_id': user_id,
                'user_info': user_info
            }
        )
    
    def check_participation_status(self, giveaway_id: int, user_id: int) -> Dict[str, Any]:
        """Check if user is already participating"""
        return self._make_request(
            'GET',
            f'/api/participants/status/{giveaway_id}/{user_id}'
        )
    
    def validate_captcha(self, giveaway_id: int, user_id: int, 
                        captcha_answer: str) -> Dict[str, Any]:
        """Validate captcha answer"""
        return self._make_request(
            'POST',
            '/api/participants/validate-captcha',
            json_data={
                'giveaway_id': giveaway_id,
                'user_id': user_id,
                'captcha_answer': captcha_answer
            }
        )
    
    def get_captcha_question(self, giveaway_id: int, user_id: int) -> Dict[str, Any]:
        """Get captcha question for user"""
        return self._make_request(
            'GET',
            f'/api/participants/captcha/{giveaway_id}/{user_id}'
        )
    
    def check_winner_status(self, giveaway_id: int, user_id: int) -> Dict[str, Any]:
        """Check if user is a winner"""
        return self._make_request(
            'GET',
            f'/api/participants/winner-status/{giveaway_id}/{user_id}'
        )
    
    def verify_subscription(self, giveaway_id: int, user_id: int, 
                          channel_id: int) -> Dict[str, Any]:
        """Verify user subscription to required channels"""
        return self._make_request(
            'POST',
            '/api/participants/verify-subscription',
            json_data={
                'giveaway_id': giveaway_id,
                'user_id': user_id,
                'channel_id': channel_id
            }
        )
    
    def get_participant_info(self, giveaway_id: int, user_id: int) -> Dict[str, Any]:
        """Get participant information"""
        return self._make_request(
            'GET',
            f'/api/participants/{giveaway_id}/{user_id}'
        )
    
    def update_participant_status(self, giveaway_id: int, user_id: int, 
                                status_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update participant status"""
        return self._make_request(
            'PUT',
            f'/api/participants/{giveaway_id}/{user_id}/status',
            json_data=status_data
        )
    
    def get_all_participants(self, giveaway_id: int, 
                           auth_token: str) -> Dict[str, Any]:
        """Get all participants for a giveaway"""
        headers = {'Authorization': f'Bearer {auth_token}'}
        return self._make_request(
            'GET',
            f'/api/participants/giveaway/{giveaway_id}',
            headers=headers
        )
    
    def mark_participation_complete(self, giveaway_id: int, user_id: int) -> Dict[str, Any]:
        """Mark participation as complete"""
        return self._make_request(
            'PUT',
            f'/api/participants/{giveaway_id}/{user_id}/complete'
        )

# Global participant service instance
participant_service = ParticipantService()

def register_participation(giveaway_id: int, user_id: int, 
                         user_info: Dict[str, Any]) -> Dict[str, Any]:
    """Register participation (convenience function)"""
    return participant_service.register_participation(giveaway_id, user_id, user_info)

def check_participation_status(giveaway_id: int, user_id: int) -> Dict[str, Any]:
    """Check participation status (convenience function)"""
    return participant_service.check_participation_status(giveaway_id, user_id)

def validate_captcha(giveaway_id: int, user_id: int, captcha_answer: str) -> Dict[str, Any]:
    """Validate captcha (convenience function)"""
    return participant_service.validate_captcha(giveaway_id, user_id, captcha_answer)

def get_captcha_question(giveaway_id: int, user_id: int) -> Dict[str, Any]:
    """Get captcha question (convenience function)"""
    return participant_service.get_captcha_question(giveaway_id, user_id)

def check_winner_status(giveaway_id: int, user_id: int) -> Dict[str, Any]:
    """Check winner status (convenience function)"""
    return participant_service.check_winner_status(giveaway_id, user_id)

def verify_subscription(giveaway_id: int, user_id: int, channel_id: int) -> Dict[str, Any]:
    """Verify subscription (convenience function)"""
    return participant_service.verify_subscription(giveaway_id, user_id, channel_id)

def get_participant_info(giveaway_id: int, user_id: int) -> Dict[str, Any]:
    """Get participant info (convenience function)"""
    return participant_service.get_participant_info(giveaway_id, user_id)

def update_participant_status(giveaway_id: int, user_id: int, 
                            status_data: Dict[str, Any]) -> Dict[str, Any]:
    """Update participant status (convenience function)"""
    return participant_service.update_participant_status(giveaway_id, user_id, status_data)

def get_all_participants(giveaway_id: int, auth_token: str) -> Dict[str, Any]:
    """Get all participants (convenience function)"""
    return participant_service.get_all_participants(giveaway_id, auth_token)

def mark_participation_complete(giveaway_id: int, user_id: int) -> Dict[str, Any]:
    """Mark participation complete (convenience function)"""
    return participant_service.mark_participation_complete(giveaway_id, user_id)

