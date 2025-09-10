"""
Webhook handler utilities
Processes incoming Telegram webhook updates
"""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from models import db, WebhookProcessingLog, BotInteraction
from handlers.message_handler import handle_message
from handlers.callback_handler import handle_callback_query
from handlers.error_handler import handle_error

logger = logging.getLogger(__name__)

class WebhookProcessor:
    """Processes Telegram webhook updates"""
    
    def __init__(self):
        self.supported_update_types = ['message', 'callback_query', 'inline_query']
    
    def process_update(self, update_data: Dict[str, Any], bot_token: str) -> Dict[str, Any]:
        """Process incoming webhook update"""
        start_time = datetime.now(timezone.utc)
        
        # Extract update information
        update_id = update_data.get('update_id')
        if not update_id:
            return {
                'success': False,
                'error': 'Missing update_id',
                'error_code': 'INVALID_UPDATE'
            }
        
        # Check if update already processed
        existing_log = WebhookProcessingLog.query.filter_by(update_id=update_id).first()
        if existing_log:
            logger.warning(f"Duplicate update {update_id}, skipping")
            return {
                'success': True,
                'message': 'Update already processed',
                'duplicate': True
            }
        
        # Determine update type
        update_type = self._get_update_type(update_data)
        if not update_type:
            return {
                'success': False,
                'error': 'Unsupported update type',
                'error_code': 'UNSUPPORTED_UPDATE_TYPE'
            }
        
        # Extract basic info
        user_id, chat_id, message_text, callback_data = self._extract_update_info(update_data, update_type)
        
        # Create processing log
        processing_log = WebhookProcessingLog(
            update_id=update_id,
            update_type=update_type,
            user_id=user_id,
            chat_id=chat_id,
            message_text=message_text,
            callback_data=callback_data,
            processing_status='pending'
        )
        db.session.add(processing_log)
        db.session.commit()
        
        try:
            # Process based on update type
            if update_type == 'message':
                result = handle_message(update_data['message'], bot_token)
            elif update_type == 'callback_query':
                result = handle_callback_query(update_data['callback_query'], bot_token)
            elif update_type == 'inline_query':
                result = self._handle_inline_query(update_data['inline_query'], bot_token)
            else:
                result = {
                    'success': False,
                    'error': f'Handler not implemented for {update_type}',
                    'error_code': 'HANDLER_NOT_IMPLEMENTED'
                }
            
            # Update processing log
            end_time = datetime.now(timezone.utc)
            processing_time_ms = int((end_time - start_time).total_seconds() * 1000)
            
            processing_log.processing_status = 'processed' if result.get('success') else 'failed'
            processing_log.processing_time_ms = processing_time_ms
            processing_log.processed_at = end_time
            processing_log.response_sent = result.get('response_sent', False)
            processing_log.response_type = result.get('response_type')
            
            if not result.get('success'):
                processing_log.error_message = result.get('error', 'Unknown error')
            
            db.session.commit()
            
            return result
            
        except Exception as e:
            # Handle processing error
            logger.error(f"Error processing update {update_id}: {e}")
            
            end_time = datetime.now(timezone.utc)
            processing_time_ms = int((end_time - start_time).total_seconds() * 1000)
            
            processing_log.processing_status = 'failed'
            processing_log.processing_time_ms = processing_time_ms
            processing_log.processed_at = end_time
            processing_log.error_message = str(e)
            db.session.commit()
            
            return handle_error(e, update_data, bot_token)
    
    def _get_update_type(self, update_data: Dict[str, Any]) -> Optional[str]:
        """Determine the type of update"""
        for update_type in self.supported_update_types:
            if update_type in update_data:
                return update_type
        return None
    
    def _extract_update_info(self, update_data: Dict[str, Any], update_type: str) -> tuple:
        """Extract basic information from update"""
        user_id = None
        chat_id = None
        message_text = None
        callback_data = None
        
        if update_type == 'message':
            message = update_data['message']
            user_id = message.get('from', {}).get('id')
            chat_id = message.get('chat', {}).get('id')
            message_text = message.get('text')
        
        elif update_type == 'callback_query':
            callback_query = update_data['callback_query']
            user_id = callback_query.get('from', {}).get('id')
            chat_id = callback_query.get('message', {}).get('chat', {}).get('id')
            callback_data = callback_query.get('data')
        
        elif update_type == 'inline_query':
            inline_query = update_data['inline_query']
            user_id = inline_query.get('from', {}).get('id')
            message_text = inline_query.get('query')
        
        return user_id, chat_id, message_text, callback_data
    
    def _handle_inline_query(self, inline_query: Dict[str, Any], bot_token: str) -> Dict[str, Any]:
        """Handle inline query (basic implementation)"""
        # For now, just return empty results
        # This can be expanded later if inline queries are needed
        return {
            'success': True,
            'response_sent': False,
            'message': 'Inline query received but not processed'
        }

# Global webhook processor instance
webhook_processor = WebhookProcessor()

def process_webhook_update(update_data: Dict[str, Any], bot_token: str) -> Dict[str, Any]:
    """Process webhook update (convenience function)"""
    return webhook_processor.process_update(update_data, bot_token)

def validate_webhook_update(update_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate webhook update structure"""
    if not isinstance(update_data, dict):
        return {
            'valid': False,
            'error': 'Update data must be a dictionary',
            'error_code': 'INVALID_UPDATE_FORMAT'
        }
    
    if 'update_id' not in update_data:
        return {
            'valid': False,
            'error': 'Missing update_id',
            'error_code': 'MISSING_UPDATE_ID'
        }
    
    # Check for at least one supported update type
    supported_types = ['message', 'callback_query', 'inline_query']
    has_supported_type = any(update_type in update_data for update_type in supported_types)
    
    if not has_supported_type:
        return {
            'valid': False,
            'error': 'No supported update type found',
            'error_code': 'UNSUPPORTED_UPDATE_TYPE'
        }
    
    return {
        'valid': True,
        'update_id': update_data['update_id'],
        'update_types': [t for t in supported_types if t in update_data]
    }

def log_bot_interaction(user_id: int, interaction_type: str, 
                       giveaway_id: Optional[int] = None,
                       message_text: Optional[str] = None,
                       callback_data: Optional[str] = None,
                       response_sent: Optional[str] = None,
                       success: bool = True,
                       error_message: Optional[str] = None,
                       chat_id: Optional[int] = None,
                       message_id: Optional[int] = None,
                       from_channel: bool = False,
                       processing_time_ms: Optional[int] = None) -> None:
    """Log bot interaction to database"""
    try:
        interaction = BotInteraction(
            user_id=user_id,
            interaction_type=interaction_type,
            giveaway_id=giveaway_id,
            message_text=message_text,
            callback_data=callback_data,
            response_sent=response_sent,
            success=success,
            error_message=error_message,
            chat_id=chat_id,
            message_id=message_id,
            from_channel=from_channel,
            processing_time_ms=processing_time_ms,
            response_timestamp=datetime.now(timezone.utc) if response_sent else None
        )
        
        db.session.add(interaction)
        db.session.commit()
        
    except Exception as e:
        logger.error(f"Failed to log bot interaction: {e}")
        db.session.rollback()

