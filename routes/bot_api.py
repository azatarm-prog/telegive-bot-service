"""
Bot API routes
Handles bot operations and inter-service communication
"""

import logging
import os
import tempfile
from flask import Blueprint, request, jsonify
from datetime import datetime, timezone
from utils.message_sender import MessageSender, send_dm_message
from utils.keyboard_builder import build_participate_keyboard, build_view_results_keyboard
from services.auth_service import get_bot_token, verify_bot_ownership
from services.media_service import download_file, get_file_info
from models import db, MessageDeliveryLog

logger = logging.getLogger(__name__)

bot_api_bp = Blueprint('bot_api', __name__)

@bot_api_bp.route('/post-giveaway', methods=['POST'])
def post_giveaway():
    """Post giveaway message to channel"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Missing request data',
                'error_code': 'MISSING_REQUEST_DATA'
            }), 400
        
        account_id = data.get('account_id')
        giveaway_data = data.get('giveaway_data', {})
        auth_token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if not account_id or not giveaway_data:
            return jsonify({
                'success': False,
                'error': 'Missing required fields',
                'error_code': 'MISSING_REQUIRED_FIELDS'
            }), 400
        
        if not auth_token:
            return jsonify({
                'success': False,
                'error': 'Missing authorization token',
                'error_code': 'MISSING_AUTH_TOKEN'
            }), 401
        
        # Get bot token for account
        bot_token_result = get_bot_token(account_id, auth_token)
        if not bot_token_result.get('success'):
            return jsonify(bot_token_result), 400
        
        bot_token = bot_token_result.get('bot_token')
        channel_id = giveaway_data.get('channel_id')
        giveaway_id = giveaway_data.get('id')
        main_body = giveaway_data.get('main_body', '')
        media_file_id = giveaway_data.get('media_file_id')
        
        if not channel_id or not giveaway_id:
            return jsonify({
                'success': False,
                'error': 'Missing channel_id or giveaway_id',
                'error_code': 'MISSING_CHANNEL_OR_GIVEAWAY_ID'
            }), 400
        
        # Create message sender
        sender = MessageSender(bot_token)
        
        # Build participate keyboard
        keyboard = build_participate_keyboard(giveaway_id)
        
        # Handle media if present
        media_file_path = None
        if media_file_id:
            # Download media file
            file_result = download_file(media_file_id, auth_token)
            if file_result.get('success'):
                # Save to temporary file
                with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                    temp_file.write(file_result['content'])
                    media_file_path = temp_file.name
        
        # Send message
        if media_file_path:
            result = sender.send_photo_message(
                chat_id=channel_id,
                photo_path=media_file_path,
                caption=main_body,
                reply_markup=keyboard
            )
            # Clean up temporary file
            try:
                os.unlink(media_file_path)
            except:
                pass
        else:
            result = sender.send_text_message(
                chat_id=channel_id,
                text=main_body,
                reply_markup=keyboard
            )
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'message_id': result['message_id'],
                'channel_id': channel_id,
                'posted_at': result['sent_at'],
                'inline_keyboard_attached': True
            })
        else:
            return jsonify(result), 500
            
    except Exception as e:
        logger.error(f"Error posting giveaway: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'error_code': 'POST_GIVEAWAY_ERROR'
        }), 500

@bot_api_bp.route('/post-conclusion', methods=['POST'])
def post_conclusion():
    """Post conclusion message with VIEW RESULTS button"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Missing request data',
                'error_code': 'MISSING_REQUEST_DATA'
            }), 400
        
        account_id = data.get('account_id')
        giveaway_id = data.get('giveaway_id')
        conclusion_message = data.get('conclusion_message', '')
        result_token = data.get('result_token')
        auth_token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if not all([account_id, giveaway_id, result_token]):
            return jsonify({
                'success': False,
                'error': 'Missing required fields',
                'error_code': 'MISSING_REQUIRED_FIELDS'
            }), 400
        
        if not auth_token:
            return jsonify({
                'success': False,
                'error': 'Missing authorization token',
                'error_code': 'MISSING_AUTH_TOKEN'
            }), 401
        
        # Get bot token for account
        bot_token_result = get_bot_token(account_id, auth_token)
        if not bot_token_result.get('success'):
            return jsonify(bot_token_result), 400
        
        bot_token = bot_token_result.get('bot_token')
        channel_id = data.get('channel_id')
        
        if not channel_id:
            return jsonify({
                'success': False,
                'error': 'Missing channel_id',
                'error_code': 'MISSING_CHANNEL_ID'
            }), 400
        
        # Create message sender
        sender = MessageSender(bot_token)
        
        # Build VIEW RESULTS keyboard
        keyboard = build_view_results_keyboard(result_token)
        
        # Send conclusion message
        result = sender.send_text_message(
            chat_id=channel_id,
            text=conclusion_message,
            reply_markup=keyboard
        )
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'message_id': result['message_id'],
                'channel_id': channel_id,
                'posted_at': result['sent_at'],
                'view_results_button_attached': True
            })
        else:
            return jsonify(result), 500
            
    except Exception as e:
        logger.error(f"Error posting conclusion: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'error_code': 'POST_CONCLUSION_ERROR'
        }), 500

@bot_api_bp.route('/send-bulk-messages', methods=['POST'])
def send_bulk_messages():
    """Send bulk messages to participants"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Missing request data',
                'error_code': 'MISSING_REQUEST_DATA'
            }), 400
        
        giveaway_id = data.get('giveaway_id')
        participants = data.get('participants', [])
        winner_message = data.get('winner_message', '')
        loser_message = data.get('loser_message', '')
        auth_token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if not all([giveaway_id, participants, winner_message, loser_message]):
            return jsonify({
                'success': False,
                'error': 'Missing required fields',
                'error_code': 'MISSING_REQUIRED_FIELDS'
            }), 400
        
        if not auth_token:
            return jsonify({
                'success': False,
                'error': 'Missing authorization token',
                'error_code': 'MISSING_AUTH_TOKEN'
            }), 401
        
        # Get bot token (assuming first participant's account)
        # In practice, this should be determined from the giveaway
        account_id = data.get('account_id')
        if not account_id:
            return jsonify({
                'success': False,
                'error': 'Missing account_id',
                'error_code': 'MISSING_ACCOUNT_ID'
            }), 400
        
        bot_token_result = get_bot_token(account_id, auth_token)
        if not bot_token_result.get('success'):
            return jsonify(bot_token_result), 400
        
        bot_token = bot_token_result.get('bot_token')
        
        # Prepare recipients with messages
        recipients = []
        for participant in participants:
            user_id = participant.get('user_id')
            is_winner = participant.get('is_winner', False)
            
            if user_id:
                recipients.append({
                    'user_id': user_id,
                    'is_winner': is_winner,
                    'winner_message': winner_message,
                    'loser_message': loser_message
                })
        
        # Create message sender and send bulk messages
        sender = MessageSender(bot_token)
        result = sender.send_bulk_messages(recipients, giveaway_id)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error sending bulk messages: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'error_code': 'BULK_MESSAGES_ERROR'
        }), 500

@bot_api_bp.route('/send-dm', methods=['POST'])
def send_dm():
    """Send direct message to user"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Missing request data',
                'error_code': 'MISSING_REQUEST_DATA'
            }), 400
        
        user_id = data.get('user_id')
        message = data.get('message', '')
        parse_mode = data.get('parse_mode', 'HTML')
        reply_markup = data.get('reply_markup')
        auth_token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if not user_id or not message:
            return jsonify({
                'success': False,
                'error': 'Missing user_id or message',
                'error_code': 'MISSING_USER_ID_OR_MESSAGE'
            }), 400
        
        if not auth_token:
            return jsonify({
                'success': False,
                'error': 'Missing authorization token',
                'error_code': 'MISSING_AUTH_TOKEN'
            }), 401
        
        # Get bot token
        account_id = data.get('account_id')
        if not account_id:
            return jsonify({
                'success': False,
                'error': 'Missing account_id',
                'error_code': 'MISSING_ACCOUNT_ID'
            }), 400
        
        bot_token_result = get_bot_token(account_id, auth_token)
        if not bot_token_result.get('success'):
            return jsonify(bot_token_result), 400
        
        bot_token = bot_token_result.get('bot_token')
        
        # Send message
        result = send_dm_message(user_id, message, bot_token, parse_mode, reply_markup)
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'message_id': result['message_id'],
                'delivered_at': result['sent_at']
            })
        else:
            return jsonify(result), 500
            
    except Exception as e:
        logger.error(f"Error sending DM: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'error_code': 'SEND_DM_ERROR'
        }), 500

@bot_api_bp.route('/user-info/<int:user_id>', methods=['GET'])
def get_user_info(user_id):
    """Get user information from Telegram"""
    try:
        auth_token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if not auth_token:
            return jsonify({
                'success': False,
                'error': 'Missing authorization token',
                'error_code': 'MISSING_AUTH_TOKEN'
            }), 401
        
        # This would typically get user info via Telegram API
        # For now, return a placeholder response
        return jsonify({
            'success': True,
            'user_info': {
                'id': user_id,
                'username': None,
                'first_name': 'User',
                'last_name': None,
                'is_bot': False,
                'language_code': 'en'
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting user info: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'error_code': 'USER_INFO_ERROR'
        }), 500

@bot_api_bp.route('/check-membership', methods=['POST'])
def check_membership():
    """Check user channel membership"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Missing request data',
                'error_code': 'MISSING_REQUEST_DATA'
            }), 400
        
        bot_token = data.get('bot_token')
        channel_id = data.get('channel_id')
        user_id = data.get('user_id')
        
        if not all([bot_token, channel_id, user_id]):
            return jsonify({
                'success': False,
                'error': 'Missing required fields',
                'error_code': 'MISSING_REQUIRED_FIELDS'
            }), 400
        
        from utils.telegram_client import check_channel_membership
        
        result = check_channel_membership(bot_token, channel_id, user_id)
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'is_member': result['is_member'],
                'membership_status': result['status'],
                'checked_at': datetime.now(timezone.utc).isoformat()
            })
        else:
            return jsonify(result), 500
            
    except Exception as e:
        logger.error(f"Error checking membership: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'error_code': 'MEMBERSHIP_CHECK_ERROR'
        }), 500

@bot_api_bp.route('/delivery-status/<int:giveaway_id>', methods=['GET'])
def get_delivery_status(giveaway_id):
    """Get message delivery status for giveaway"""
    try:
        auth_token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if not auth_token:
            return jsonify({
                'success': False,
                'error': 'Missing authorization token',
                'error_code': 'MISSING_AUTH_TOKEN'
            }), 401
        
        # Get delivery statistics
        delivery_logs = MessageDeliveryLog.query.filter_by(giveaway_id=giveaway_id).all()
        
        total_participants = len(delivery_logs)
        messages_sent = len([log for log in delivery_logs if log.delivery_status == 'sent'])
        delivery_failed = len([log for log in delivery_logs if log.delivery_status == 'failed'])
        users_blocked_bot = len([log for log in delivery_logs if log.error_code == 'USER_BLOCKED_BOT'])
        pending_delivery = len([log for log in delivery_logs if log.delivery_status == 'pending'])
        
        failed_deliveries = []
        for log in delivery_logs:
            if log.delivery_status == 'failed':
                failed_deliveries.append({
                    'user_id': log.user_id,
                    'error_code': log.error_code,
                    'last_attempt': log.last_attempt_at.isoformat() if log.last_attempt_at else None
                })
        
        return jsonify({
            'success': True,
            'delivery_stats': {
                'total_participants': total_participants,
                'messages_sent': messages_sent,
                'delivery_failed': delivery_failed,
                'users_blocked_bot': users_blocked_bot,
                'pending_delivery': pending_delivery
            },
            'failed_deliveries': failed_deliveries
        })
        
    except Exception as e:
        logger.error(f"Error getting delivery status: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'error_code': 'DELIVERY_STATUS_ERROR'
        }), 500

