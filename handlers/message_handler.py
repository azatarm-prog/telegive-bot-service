"""
Message handlers
Handles incoming text messages from users
"""

import logging
from typing import Dict, Any
from utils.user_state import (
    get_user_state, set_user_state, clear_user_state, 
    UserStates, ContextKeys
)
from utils.message_sender import send_dm_message
from utils.keyboard_builder import build_continue_keyboard
from services.participant_service import validate_captcha, get_captcha_question

logger = logging.getLogger(__name__)

def handle_message(message: Dict[str, Any], bot_token: str) -> Dict[str, Any]:
    """Handle incoming text message"""
    try:
        user_id = message.get('from', {}).get('id')
        chat_id = message.get('chat', {}).get('id')
        message_id = message.get('message_id')
        text = message.get('text', '').strip()
        
        if not user_id or not text:
            return {
                'success': False,
                'error': 'Invalid message data',
                'error_code': 'INVALID_MESSAGE_DATA'
            }
        
        # Check if this is a private chat
        is_private = message.get('chat', {}).get('type') == 'private'
        
        if not is_private:
            # Ignore messages from groups/channels
            return {
                'success': True,
                'message': 'Group message ignored',
                'response_sent': False
            }
        
        # Get user state
        user_state = get_user_state(user_id)
        current_state = user_state.get('state', UserStates.IDLE) if user_state else UserStates.IDLE
        
        # Handle based on current state and message content
        if text.startswith('/'):
            result = handle_command(user_id, text, bot_token)
        elif current_state == UserStates.WAITING_CAPTCHA:
            result = handle_captcha_answer(user_id, text, user_state, bot_token)
        else:
            result = handle_general_message(user_id, text, bot_token)
        
        # Note: Bot interaction logging is handled at the webhook level
        # to avoid circular imports
        
        return result
        
    except Exception as e:
        logger.error(f"Error handling message: {e}")
        return {
            'success': False,
            'error': str(e),
            'error_code': 'MESSAGE_HANDLER_ERROR'
        }

def handle_command(user_id: int, command: str, bot_token: str) -> Dict[str, Any]:
    """Handle bot commands"""
    command = command.lower()
    
    if command == '/start':
        return handle_start_command(user_id, bot_token)
    elif command == '/help':
        return handle_help_command(user_id, bot_token)
    elif command == '/cancel':
        return handle_cancel_command(user_id, bot_token)
    else:
        return handle_unknown_command(user_id, command, bot_token)

def handle_start_command(user_id: int, bot_token: str) -> Dict[str, Any]:
    """Handle /start command"""
    welcome_message = """
🤖 <b>Welcome to Telegive Bot!</b>

I help you participate in giveaways and check results.

<b>How to use:</b>
• Click the PARTICIPATE button on giveaway posts
• I'll guide you through the participation process
• Use VIEW RESULTS button to check if you won

<b>Commands:</b>
/help - Show this help message
/cancel - Cancel current operation

Good luck! 🍀
"""
    
    result = send_dm_message(user_id, welcome_message, bot_token)
    
    if result['success']:
        # Clear any existing state
        clear_user_state(user_id)
        
        return {
            'success': True,
            'response_sent': True,
            'response_type': 'text',
            'response_text': welcome_message
        }
    else:
        return result

def handle_help_command(user_id: int, bot_token: str) -> Dict[str, Any]:
    """Handle /help command"""
    help_message = """
🆘 <b>Telegive Bot Help</b>

<b>Participating in Giveaways:</b>
1. Find a giveaway post in a channel
2. Click the 🎁 PARTICIPATE button
3. Follow the instructions I send you
4. Complete any required steps (captcha, subscriptions)

<b>Checking Results:</b>
1. Click the 🏆 VIEW RESULTS button on concluded giveaways
2. I'll tell you if you won or not

<b>Commands:</b>
/start - Start over
/help - Show this help
/cancel - Cancel current operation

<b>Need more help?</b>
Contact the giveaway organizer if you have issues with a specific giveaway.
"""
    
    result = send_dm_message(user_id, help_message, bot_token)
    
    if result['success']:
        return {
            'success': True,
            'response_sent': True,
            'response_type': 'text',
            'response_text': help_message
        }
    else:
        return result

def handle_cancel_command(user_id: int, bot_token: str) -> Dict[str, Any]:
    """Handle /cancel command"""
    user_state = get_user_state(user_id)
    
    if user_state and user_state.get('state') != UserStates.IDLE:
        clear_user_state(user_id)
        cancel_message = "✅ Operation cancelled. You can start a new giveaway participation anytime!"
    else:
        cancel_message = "ℹ️ No active operation to cancel."
    
    result = send_dm_message(user_id, cancel_message, bot_token)
    
    if result['success']:
        return {
            'success': True,
            'response_sent': True,
            'response_type': 'text',
            'response_text': cancel_message
        }
    else:
        return result

def handle_unknown_command(user_id: int, command: str, bot_token: str) -> Dict[str, Any]:
    """Handle unknown commands"""
    unknown_message = f"❓ Unknown command: {command}\n\nUse /help to see available commands."
    
    result = send_dm_message(user_id, unknown_message, bot_token)
    
    if result['success']:
        return {
            'success': True,
            'response_sent': True,
            'response_type': 'text',
            'response_text': unknown_message
        }
    else:
        return result

def handle_captcha_answer(user_id: int, answer: str, user_state: Dict[str, Any], 
                         bot_token: str) -> Dict[str, Any]:
    """Handle captcha answer from user"""
    giveaway_id = user_state.get(ContextKeys.GIVEAWAY_ID)
    
    if not giveaway_id:
        error_message = "❌ Session expired. Please try participating again."
        clear_user_state(user_id)
        
        result = send_dm_message(user_id, error_message, bot_token)
        if result['success']:
            return {
                'success': True,
                'response_sent': True,
                'response_type': 'text',
                'response_text': error_message
            }
        else:
            return result
    
    # Validate captcha answer
    validation_result = validate_captcha(giveaway_id, user_id, answer)
    
    if not validation_result.get('success'):
        error_message = "❌ Error validating captcha. Please try again."
        
        result = send_dm_message(user_id, error_message, bot_token)
        if result['success']:
            return {
                'success': True,
                'response_sent': True,
                'response_type': 'text',
                'response_text': error_message
            }
        else:
            return result
    
    if validation_result.get('captcha_completed'):
        # Captcha correct
        success_message = "✅ <b>Captcha completed successfully!</b>\n\n🎉 You are now participating in the giveaway!\n\nGood luck! 🍀"
        clear_user_state(user_id)
        
        result = send_dm_message(user_id, success_message, bot_token)
        if result['success']:
            return {
                'success': True,
                'response_sent': True,
                'response_type': 'text',
                'response_text': success_message
            }
        else:
            return result
    else:
        # Captcha incorrect, get new question
        captcha_result = get_captcha_question(giveaway_id, user_id)
        
        if captcha_result.get('success'):
            question = captcha_result.get('captcha_question', 'Please solve: 2 + 2 = ?')
            retry_message = f"❌ Incorrect answer. Please try again.\n\n🧮 <b>Solve this:</b> {question}\n\nType your answer:"
            
            result = send_dm_message(user_id, retry_message, bot_token)
            if result['success']:
                return {
                    'success': True,
                    'response_sent': True,
                    'response_type': 'text',
                    'response_text': retry_message
                }
            else:
                return result
        else:
            error_message = "❌ Error getting new captcha. Please try participating again."
            clear_user_state(user_id)
            
            result = send_dm_message(user_id, error_message, bot_token)
            if result['success']:
                return {
                    'success': True,
                    'response_sent': True,
                    'response_type': 'text',
                    'response_text': error_message
                }
            else:
                return result

def handle_general_message(user_id: int, text: str, bot_token: str) -> Dict[str, Any]:
    """Handle general messages when user is not in a specific state"""
    general_message = """
ℹ️ <b>How to participate in giveaways:</b>

1. Find a giveaway post in a channel
2. Click the 🎁 PARTICIPATE button
3. I'll guide you through the process

Use /help for more information.
"""
    
    result = send_dm_message(user_id, general_message, bot_token)
    
    if result['success']:
        return {
            'success': True,
            'response_sent': True,
            'response_type': 'text',
            'response_text': general_message
        }
    else:
        return result

