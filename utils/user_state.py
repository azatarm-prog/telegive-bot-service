"""
User state management utilities
Handles user conversation states and context
"""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from config.settings import Config

logger = logging.getLogger(__name__)

# In-memory state storage (for development)
# In production, this should use Redis
_user_states = {}

class UserStateManager:
    """Manages user conversation states"""
    
    def __init__(self, use_redis: bool = False):
        self.use_redis = use_redis
        self.ttl = Config.USER_STATE_TTL
        
        if use_redis:
            try:
                import redis
                self.redis_client = redis.from_url(Config.REDIS_URL)
                self.redis_client.ping()  # Test connection
                logger.info("Connected to Redis for user state management")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}. Using in-memory storage.")
                self.use_redis = False
    
    def set_user_state(self, user_id: int, state_data: Dict[str, Any]) -> bool:
        """Set user state"""
        try:
            state_data['timestamp'] = datetime.now().isoformat()
            
            if self.use_redis:
                key = f"user_state:{user_id}"
                self.redis_client.setex(
                    key, 
                    self.ttl, 
                    json.dumps(state_data)
                )
            else:
                # In-memory storage with TTL simulation
                expiry = datetime.now() + timedelta(seconds=self.ttl)
                _user_states[user_id] = {
                    'data': state_data,
                    'expiry': expiry
                }
            
            return True
        except Exception as e:
            logger.error(f"Failed to set user state for {user_id}: {e}")
            return False
    
    def get_user_state(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user state"""
        try:
            if self.use_redis:
                key = f"user_state:{user_id}"
                state_json = self.redis_client.get(key)
                if state_json:
                    return json.loads(state_json)
            else:
                # In-memory storage with TTL check
                if user_id in _user_states:
                    state_entry = _user_states[user_id]
                    if datetime.now() < state_entry['expiry']:
                        return state_entry['data']
                    else:
                        # Expired, remove it
                        del _user_states[user_id]
            
            return None
        except Exception as e:
            logger.error(f"Failed to get user state for {user_id}: {e}")
            return None
    
    def clear_user_state(self, user_id: int) -> bool:
        """Clear user state"""
        try:
            if self.use_redis:
                key = f"user_state:{user_id}"
                self.redis_client.delete(key)
            else:
                if user_id in _user_states:
                    del _user_states[user_id]
            
            return True
        except Exception as e:
            logger.error(f"Failed to clear user state for {user_id}: {e}")
            return False
    
    def update_user_state(self, user_id: int, updates: Dict[str, Any]) -> bool:
        """Update specific fields in user state"""
        current_state = self.get_user_state(user_id) or {}
        current_state.update(updates)
        return self.set_user_state(user_id, current_state)

# Global state manager instance
state_manager = UserStateManager()

def set_user_state(user_id: int, state: str, **kwargs) -> bool:
    """Set user state with additional context"""
    state_data = {
        'state': state,
        **kwargs
    }
    return state_manager.set_user_state(user_id, state_data)

def get_user_state(user_id: int) -> Optional[Dict[str, Any]]:
    """Get user state"""
    return state_manager.get_user_state(user_id)

def clear_user_state(user_id: int) -> bool:
    """Clear user state"""
    return state_manager.clear_user_state(user_id)

def is_user_in_state(user_id: int, expected_state: str) -> bool:
    """Check if user is in expected state"""
    state_data = get_user_state(user_id)
    return state_data and state_data.get('state') == expected_state

def get_user_context(user_id: int, key: str, default=None):
    """Get specific context value from user state"""
    state_data = get_user_state(user_id)
    return state_data.get(key, default) if state_data else default

def update_user_context(user_id: int, **kwargs) -> bool:
    """Update user context without changing state"""
    return state_manager.update_user_state(user_id, kwargs)

# Common state constants
class UserStates:
    IDLE = 'idle'
    WAITING_CAPTCHA = 'waiting_captcha'
    PARTICIPATING = 'participating'
    CHECKING_RESULTS = 'checking_results'
    SUBSCRIPTION_CHECK = 'subscription_check'

# Context keys
class ContextKeys:
    GIVEAWAY_ID = 'giveaway_id'
    CAPTCHA_QUESTION = 'captcha_question'
    CAPTCHA_ANSWER = 'captcha_answer'
    PARTICIPATION_TOKEN = 'participation_token'
    RESULT_TOKEN = 'result_token'
    CHANNEL_ID = 'channel_id'
    MESSAGE_ID = 'message_id'

