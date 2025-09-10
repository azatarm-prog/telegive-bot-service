"""
Webhook routes
Handles incoming Telegram webhook requests
"""

import logging
from flask import Blueprint, request, jsonify
from utils.webhook_handler import process_webhook_update, validate_webhook_update

logger = logging.getLogger(__name__)

webhook_bp = Blueprint('webhook', __name__)

@webhook_bp.route('/webhook/<bot_token>', methods=['POST'])
def handle_webhook(bot_token):
    """Handle incoming Telegram webhook"""
    try:
        # Validate bot token format
        if not bot_token or len(bot_token) < 10:
            logger.warning(f"Invalid bot token format: {bot_token[:10]}...")
            return jsonify({
                'success': False,
                'error': 'Invalid bot token format',
                'error_code': 'INVALID_BOT_TOKEN_FORMAT'
            }), 400
        
        # Get JSON data from request
        try:
            update_data = request.get_json(force=True)
        except Exception as e:
            logger.error(f"Failed to parse JSON: {e}")
            return jsonify({
                'success': False,
                'error': 'Invalid JSON data',
                'error_code': 'INVALID_JSON'
            }), 400
        
        if not update_data:
            logger.warning("Empty update data received")
            return jsonify({
                'success': False,
                'error': 'Empty update data',
                'error_code': 'EMPTY_UPDATE_DATA'
            }), 400
        
        # Validate update structure
        validation_result = validate_webhook_update(update_data)
        if not validation_result.get('valid'):
            logger.warning(f"Invalid update structure: {validation_result.get('error')}")
            return jsonify({
                'success': False,
                'error': validation_result.get('error'),
                'error_code': validation_result.get('error_code')
            }), 400
        
        # Process the update
        result = process_webhook_update(update_data, bot_token)
        
        # Telegram expects 200 OK for successful webhook processing
        # regardless of the actual processing result
        if result.get('success') or result.get('duplicate'):
            return '', 200
        else:
            # Log the error but still return 200 to Telegram
            logger.error(f"Webhook processing failed: {result.get('error')}")
            return '', 200
            
    except Exception as e:
        logger.error(f"Webhook handler error: {e}")
        # Always return 200 to Telegram to avoid webhook retries
        return '', 200

@webhook_bp.route('/webhook/<bot_token>', methods=['GET'])
def webhook_info(bot_token):
    """Get webhook information (for debugging)"""
    try:
        if not bot_token or len(bot_token) < 10:
            return jsonify({
                'success': False,
                'error': 'Invalid bot token format',
                'error_code': 'INVALID_BOT_TOKEN_FORMAT'
            }), 400
        
        from utils.telegram_client import TelegramClient
        
        client = TelegramClient(bot_token)
        webhook_info = client.get_webhook_info()
        
        return jsonify(webhook_info)
        
    except Exception as e:
        logger.error(f"Error getting webhook info: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'error_code': 'WEBHOOK_INFO_ERROR'
        }), 500

@webhook_bp.route('/webhook/<bot_token>/set', methods=['POST'])
def set_webhook(bot_token):
    """Set webhook URL for bot"""
    try:
        if not bot_token or len(bot_token) < 10:
            return jsonify({
                'success': False,
                'error': 'Invalid bot token format',
                'error_code': 'INVALID_BOT_TOKEN_FORMAT'
            }), 400
        
        data = request.get_json()
        webhook_url = data.get('webhook_url') if data else None
        
        if not webhook_url:
            return jsonify({
                'success': False,
                'error': 'Missing webhook_url',
                'error_code': 'MISSING_WEBHOOK_URL'
            }), 400
        
        from utils.telegram_client import setup_webhook
        
        result = setup_webhook(bot_token, webhook_url)
        
        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 500
            
    except Exception as e:
        logger.error(f"Error setting webhook: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'error_code': 'WEBHOOK_SETUP_ERROR'
        }), 500

@webhook_bp.route('/webhook/<bot_token>/delete', methods=['POST'])
def delete_webhook(bot_token):
    """Delete webhook for bot"""
    try:
        if not bot_token or len(bot_token) < 10:
            return jsonify({
                'success': False,
                'error': 'Invalid bot token format',
                'error_code': 'INVALID_BOT_TOKEN_FORMAT'
            }), 400
        
        from utils.telegram_client import TelegramClient
        
        client = TelegramClient(bot_token)
        result = client.set_webhook('')  # Empty URL deletes webhook
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error deleting webhook: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'error_code': 'WEBHOOK_DELETE_ERROR'
        }), 500

