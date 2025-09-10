"""
Error handlers
Handles errors and exceptions in bot operations
"""

import logging
import traceback
from typing import Dict, Any, Optional
from telegram.error import TelegramError, Forbidden, BadRequest, TimedOut, NetworkError
from utils.message_sender import send_dm_message

logger = logging.getLogger(__name__)

def handle_error(error: Exception, update_data: Dict[str, Any], 
                bot_token: str) -> Dict[str, Any]:
    """Handle errors that occur during update processing"""
    try:
        error_type = type(error).__name__
        error_message = str(error)
        
        logger.error(f"Error processing update: {error_type}: {error_message}")
        logger.error(f"Update data: {update_data}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Extract user info if available
        user_id = None
        if 'message' in update_data:
            user_id = update_data['message'].get('from', {}).get('id')
        elif 'callback_query' in update_data:
            user_id = update_data['callback_query'].get('from', {}).get('id')
        
        # Handle specific error types
        if isinstance(error, TelegramError):
            return handle_telegram_error(error, user_id, bot_token)
        else:
            return handle_general_error(error, user_id, bot_token)
            
    except Exception as e:
        logger.error(f"Error in error handler: {e}")
        return {
            'success': False,
            'error': 'Critical error in error handler',
            'error_code': 'CRITICAL_ERROR'
        }

def handle_telegram_error(error: TelegramError, user_id: Optional[int], 
                         bot_token: str) -> Dict[str, Any]:
    """Handle Telegram-specific errors"""
    error_message = str(error).lower()
    
    if isinstance(error, Forbidden):
        if 'bot was blocked' in error_message:
            logger.info(f"User {user_id} has blocked the bot")
            return {
                'success': False,
                'error': 'User has blocked the bot',
                'error_code': 'USER_BLOCKED_BOT',
                'user_notification': False
            }
        elif 'chat not found' in error_message:
            logger.warning(f"Chat not found for user {user_id}")
            return {
                'success': False,
                'error': 'Chat not found',
                'error_code': 'CHAT_NOT_FOUND',
                'user_notification': False
            }
        else:
            logger.error(f"Forbidden error: {error}")
            return {
                'success': False,
                'error': 'Access forbidden',
                'error_code': 'FORBIDDEN',
                'user_notification': False
            }
    
    elif isinstance(error, BadRequest):
        if 'message is not modified' in error_message:
            # This is not really an error, just means message content is the same
            return {
                'success': True,
                'message': 'Message not modified (content unchanged)',
                'user_notification': False
            }
        elif 'message to edit not found' in error_message:
            logger.warning(f"Message to edit not found: {error}")
            return {
                'success': False,
                'error': 'Message to edit not found',
                'error_code': 'MESSAGE_NOT_FOUND',
                'user_notification': False
            }
        elif 'message text is empty' in error_message:
            logger.error(f"Empty message text: {error}")
            return {
                'success': False,
                'error': 'Message text is empty',
                'error_code': 'EMPTY_MESSAGE',
                'user_notification': False
            }
        else:
            logger.error(f"Bad request error: {error}")
            if user_id:
                send_user_error_notification(user_id, "Invalid request", bot_token)
            return {
                'success': False,
                'error': 'Bad request',
                'error_code': 'BAD_REQUEST',
                'user_notification': True
            }
    
    elif isinstance(error, TimedOut):
        logger.warning(f"Telegram API timeout: {error}")
        if user_id:
            send_user_error_notification(user_id, "Request timed out", bot_token)
        return {
            'success': False,
            'error': 'Request timed out',
            'error_code': 'TIMEOUT',
            'user_notification': True
        }
    
    elif isinstance(error, NetworkError):
        logger.error(f"Network error: {error}")
        if user_id:
            send_user_error_notification(user_id, "Network error", bot_token)
        return {
            'success': False,
            'error': 'Network error',
            'error_code': 'NETWORK_ERROR',
            'user_notification': True
        }
    
    else:
        logger.error(f"Unknown Telegram error: {error}")
        if user_id:
            send_user_error_notification(user_id, "Unknown error", bot_token)
        return {
            'success': False,
            'error': 'Unknown Telegram error',
            'error_code': 'UNKNOWN_TELEGRAM_ERROR',
            'user_notification': True
        }

def handle_general_error(error: Exception, user_id: Optional[int], 
                        bot_token: str) -> Dict[str, Any]:
    """Handle general Python exceptions"""
    error_type = type(error).__name__
    error_message = str(error)
    
    logger.error(f"General error: {error_type}: {error_message}")
    
    # Handle specific exception types
    if isinstance(error, ValueError):
        logger.error(f"Value error: {error}")
        if user_id:
            send_user_error_notification(user_id, "Invalid data", bot_token)
        return {
            'success': False,
            'error': 'Invalid data provided',
            'error_code': 'INVALID_DATA',
            'user_notification': True
        }
    
    elif isinstance(error, KeyError):
        logger.error(f"Key error: {error}")
        return {
            'success': False,
            'error': 'Missing required data',
            'error_code': 'MISSING_DATA',
            'user_notification': False
        }
    
    elif isinstance(error, ConnectionError):
        logger.error(f"Connection error: {error}")
        if user_id:
            send_user_error_notification(user_id, "Service temporarily unavailable", bot_token)
        return {
            'success': False,
            'error': 'Service connection error',
            'error_code': 'CONNECTION_ERROR',
            'user_notification': True
        }
    
    else:
        logger.error(f"Unhandled error: {error_type}: {error_message}")
        if user_id:
            send_user_error_notification(user_id, "Unexpected error", bot_token)
        return {
            'success': False,
            'error': 'Unexpected error occurred',
            'error_code': 'UNEXPECTED_ERROR',
            'user_notification': True
        }

def send_user_error_notification(user_id: int, error_type: str, bot_token: str) -> None:
    """Send error notification to user"""
    try:
        error_messages = {
            "Invalid request": "❌ Invalid request. Please try again.",
            "Request timed out": "⏱️ Request timed out. Please try again in a moment.",
            "Network error": "🌐 Network error. Please check your connection and try again.",
            "Unknown error": "❌ An unexpected error occurred. Please try again later.",
            "Invalid data": "❌ Invalid data provided. Please check your input and try again.",
            "Service temporarily unavailable": "🔧 Service is temporarily unavailable. Please try again later.",
            "Unexpected error": "❌ An unexpected error occurred. Please try again later."
        }
        
        message = error_messages.get(error_type, "❌ An error occurred. Please try again later.")
        message += "\n\nIf the problem persists, please contact support."
        
        result = send_dm_message(user_id, message, bot_token)
        
        if not result['success']:
            logger.error(f"Failed to send error notification to user {user_id}: {result.get('error')}")
            
    except Exception as e:
        logger.error(f"Error sending user notification: {e}")

def log_error_for_monitoring(error: Exception, context: Dict[str, Any]) -> None:
    """Log error for monitoring and alerting systems"""
    try:
        error_data = {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'context': context,
            'traceback': traceback.format_exc()
        }
        
        # In a production environment, this would send to monitoring services
        # like Sentry, DataDog, or custom logging systems
        logger.error(f"Error for monitoring: {error_data}")
        
    except Exception as e:
        logger.error(f"Error logging for monitoring: {e}")

def handle_rate_limit_error(error: Exception, user_id: Optional[int], 
                           bot_token: str) -> Dict[str, Any]:
    """Handle rate limiting errors"""
    logger.warning(f"Rate limit exceeded: {error}")
    
    if user_id:
        rate_limit_message = "⏱️ Too many requests. Please wait a moment and try again."
        send_dm_message(user_id, rate_limit_message, bot_token)
    
    return {
        'success': False,
        'error': 'Rate limit exceeded',
        'error_code': 'RATE_LIMITED',
        'user_notification': True,
        'retry_after': 60  # Suggest retry after 60 seconds
    }

def handle_service_unavailable_error(service_name: str, user_id: Optional[int], 
                                   bot_token: str) -> Dict[str, Any]:
    """Handle service unavailable errors"""
    logger.error(f"Service unavailable: {service_name}")
    
    if user_id:
        service_error_message = f"🔧 {service_name} is temporarily unavailable. Please try again later."
        send_dm_message(user_id, service_error_message, bot_token)
    
    return {
        'success': False,
        'error': f'{service_name} unavailable',
        'error_code': 'SERVICE_UNAVAILABLE',
        'user_notification': True,
        'service': service_name
    }

