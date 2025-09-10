"""
Callback query handlers
Handles button clicks and inline keyboard interactions
"""

import logging
from typing import Dict, Any
from utils.user_state import (
    set_user_state, get_user_state, clear_user_state,
    UserStates, ContextKeys
)
from utils.message_sender import send_dm_message
from utils.keyboard_builder import extract_callback_data, build_continue_keyboard
from utils.webhook_handler import log_bot_interaction
from services.participant_service import (
    register_participation, check_participation_status, 
    validate_captcha, get_captcha_question, check_winner_status
)
from services.telegive_service import get_giveaway_by_token
from services.channel_service import get_subscription_requirements

logger = logging.getLogger(__name__)

def handle_callback_query(callback_query: Dict[str, Any], bot_token: str) -> Dict[str, Any]:
    """Handle incoming callback query"""
    try:
        user_id = callback_query.get('from', {}).get('id')
        callback_data = callback_query.get('data', '')
        message = callback_query.get('message', {})
        chat_id = message.get('chat', {}).get('id')
        message_id = message.get('message_id')
        
        if not user_id or not callback_data:
            return {
                'success': False,
                'error': 'Invalid callback query data',
                'error_code': 'INVALID_CALLBACK_DATA'
            }
        
        # Extract action and parameters from callback data
        callback_info = extract_callback_data(callback_data)
        action = callback_info['action']
        params = callback_info['params']
        
        # Determine if this is from a channel
        from_channel = message.get('chat', {}).get('type') in ['channel', 'supergroup']
        
        # Route to appropriate handler
        if action == 'participate':
            result = handle_participate_callback(user_id, params, bot_token, from_channel)
        elif action == 'view_results':
            result = handle_view_results_callback(user_id, params, bot_token)
        elif action == 'captcha':
            result = handle_captcha_callback(user_id, params, bot_token)
        elif action == 'check_subscription':
            result = handle_subscription_check_callback(user_id, params, bot_token)
        elif action == 'continue':
            result = handle_continue_callback(user_id, params, bot_token)
        elif action == 'retry':
            result = handle_retry_callback(user_id, params, bot_token)
        else:
            result = handle_unknown_callback(user_id, action, bot_token)
        
        # Log interaction
        log_bot_interaction(
            user_id=user_id,
            interaction_type='callback_query',
            callback_data=callback_data,
            response_sent=result.get('response_text'),
            success=result.get('success', True),
            error_message=result.get('error'),
            chat_id=chat_id,
            message_id=message_id,
            from_channel=from_channel,
            giveaway_id=params[0] if params and params[0].isdigit() else None
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error handling callback query: {e}")
        return {
            'success': False,
            'error': str(e),
            'error_code': 'CALLBACK_HANDLER_ERROR'
        }

def handle_participate_callback(user_id: int, params: list, bot_token: str, 
                              from_channel: bool = False) -> Dict[str, Any]:
    """Handle participate button click"""
    if not params or not params[0].isdigit():
        return {
            'success': False,
            'error': 'Invalid giveaway ID',
            'error_code': 'INVALID_GIVEAWAY_ID'
        }
    
    giveaway_id = int(params[0])
    
    # Check if user is already participating
    participation_status = check_participation_status(giveaway_id, user_id)
    
    if not participation_status.get('success'):
        error_message = "❌ Error checking participation status. Please try again later."
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
    
    if participation_status.get('already_participating'):
        already_message = "ℹ️ You are already participating in this giveaway! Good luck! 🍀"
        result = send_dm_message(user_id, already_message, bot_token)
        if result['success']:
            return {
                'success': True,
                'response_sent': True,
                'response_type': 'text',
                'response_text': already_message
            }
        else:
            return result
    
    # Register participation
    user_info = {
        'user_id': user_id,
        'from_channel': from_channel
    }
    
    registration_result = register_participation(giveaway_id, user_id, user_info)
    
    if not registration_result.get('success'):
        error_message = "❌ Error registering participation. Please try again later."
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
    
    # Check if captcha is required
    if registration_result.get('requires_captcha'):
        captcha_question = registration_result.get('captcha_question', 'What is 2 + 2?')
        
        captcha_message = f"""
🧮 <b>Captcha Required</b>

To complete your participation, please solve this simple math problem:

<b>{captcha_question}</b>

Type your answer:
"""
        
        # Set user state to waiting for captcha
        set_user_state(
            user_id, 
            UserStates.WAITING_CAPTCHA,
            giveaway_id=giveaway_id,
            captcha_question=captcha_question
        )
        
        result = send_dm_message(user_id, captcha_message, bot_token)
        if result['success']:
            return {
                'success': True,
                'response_sent': True,
                'response_type': 'text',
                'response_text': captcha_message
            }
        else:
            return result
    
    # Check if subscription verification is required
    elif registration_result.get('requires_subscription'):
        subscription_requirements = registration_result.get('subscription_requirements', [])
        
        if subscription_requirements:
            subscription_message = """
📢 <b>Subscription Required</b>

To participate in this giveaway, you must be subscribed to the following channels:

"""
            for req in subscription_requirements:
                channel_username = req.get('channel_username', 'Unknown')
                subscription_message += f"• @{channel_username}\n"
            
            subscription_message += "\nPlease subscribe to all required channels and try again."
            
            result = send_dm_message(user_id, subscription_message, bot_token)
            if result['success']:
                return {
                    'success': True,
                    'response_sent': True,
                    'response_type': 'text',
                    'response_text': subscription_message
                }
            else:
                return result
    
    # Participation completed successfully
    success_message = "🎉 <b>Participation Successful!</b>\n\nYou are now participating in the giveaway!\n\nGood luck! 🍀"
    
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

def handle_view_results_callback(user_id: int, params: list, bot_token: str) -> Dict[str, Any]:
    """Handle VIEW RESULTS button click"""
    if not params:
        return {
            'success': False,
            'error': 'Missing result token',
            'error_code': 'MISSING_RESULT_TOKEN'
        }
    
    result_token = params[0]
    
    # Get giveaway info by token
    giveaway_result = get_giveaway_by_token(result_token)
    
    if not giveaway_result.get('success'):
        error_message = "❌ Error retrieving giveaway information. Please try again later."
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
    
    giveaway = giveaway_result.get('giveaway', {})
    giveaway_id = giveaway.get('id')
    
    if not giveaway_id:
        error_message = "❌ Invalid giveaway information."
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
    
    # Check if giveaway is finished
    if giveaway.get('status') != 'finished':
        pending_message = "⏳ This giveaway is still ongoing. Results will be available once it's finished."
        result = send_dm_message(user_id, pending_message, bot_token)
        if result['success']:
            return {
                'success': True,
                'response_sent': True,
                'response_type': 'text',
                'response_text': pending_message
            }
        else:
            return result
    
    # Check winner status
    winner_status = check_winner_status(giveaway_id, user_id)
    
    if not winner_status.get('success'):
        error_message = "❌ Error checking winner status. Please try again later."
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
    
    # Send appropriate message
    if winner_status.get('is_winner'):
        winner_message = giveaway.get('winner_message', '🎊 Congratulations! You are one of our lucky winners!')
        result = send_dm_message(user_id, winner_message, bot_token)
    else:
        loser_message = giveaway.get('loser_message', 'Thank you for participating! Better luck next time! 🍀')
        result = send_dm_message(user_id, loser_message, bot_token)
    
    if result['success']:
        return {
            'success': True,
            'response_sent': True,
            'response_type': 'text',
            'response_text': winner_message if winner_status.get('is_winner') else loser_message
        }
    else:
        return result

def handle_captcha_callback(user_id: int, params: list, bot_token: str) -> Dict[str, Any]:
    """Handle captcha button click (if using button-based captcha)"""
    if len(params) < 3:
        return {
            'success': False,
            'error': 'Invalid captcha callback data',
            'error_code': 'INVALID_CAPTCHA_DATA'
        }
    
    giveaway_id = int(params[0])
    option_index = int(params[1])
    answer = params[2]
    
    # Validate captcha
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
        success_message = "✅ <b>Captcha completed successfully!</b>\n\n🎉 You are now participating in the giveaway!\n\nGood luck! 🍀"
        clear_user_state(user_id)
    else:
        success_message = "❌ Incorrect answer. Please try again with the text input."
    
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

def handle_subscription_check_callback(user_id: int, params: list, bot_token: str) -> Dict[str, Any]:
    """Handle subscription check button click"""
    if not params or not params[0].isdigit():
        return {
            'success': False,
            'error': 'Invalid giveaway ID',
            'error_code': 'INVALID_GIVEAWAY_ID'
        }
    
    giveaway_id = int(params[0])
    
    # This would typically verify subscription and continue participation
    # For now, just send a confirmation message
    check_message = "✅ Subscription verified! Continuing with participation..."
    
    result = send_dm_message(user_id, check_message, bot_token)
    if result['success']:
        return {
            'success': True,
            'response_sent': True,
            'response_type': 'text',
            'response_text': check_message
        }
    else:
        return result

def handle_continue_callback(user_id: int, params: list, bot_token: str) -> Dict[str, Any]:
    """Handle continue button click"""
    continue_message = "✅ Continuing..."
    
    result = send_dm_message(user_id, continue_message, bot_token)
    if result['success']:
        return {
            'success': True,
            'response_sent': True,
            'response_type': 'text',
            'response_text': continue_message
        }
    else:
        return result

def handle_retry_callback(user_id: int, params: list, bot_token: str) -> Dict[str, Any]:
    """Handle retry button click"""
    retry_message = "🔄 Please try again..."
    
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

def handle_unknown_callback(user_id: int, action: str, bot_token: str) -> Dict[str, Any]:
    """Handle unknown callback action"""
    unknown_message = f"❓ Unknown action: {action}"
    
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

