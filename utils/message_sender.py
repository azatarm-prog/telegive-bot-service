"""
Message sending utilities
Handles sending messages, photos, and other media via Telegram
"""

import logging
import asyncio
from typing import Dict, Any, Optional, List
from telegram import Bot, InlineKeyboardMarkup
from telegram.error import TelegramError, Forbidden, BadRequest
from config.settings import Config
from models import db, MessageDeliveryLog
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class MessageSender:
    """Handles message sending operations"""
    
    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.bot = Bot(token=bot_token)
        self.max_message_length = Config.MAX_MESSAGE_LENGTH
        self.batch_size = Config.BULK_MESSAGE_BATCH_SIZE
        self.retry_attempts = Config.MESSAGE_RETRY_ATTEMPTS
    
    async def send_text_message(self, chat_id: int, text: str, 
                               parse_mode: str = 'HTML',
                               reply_markup: Optional[InlineKeyboardMarkup] = None) -> Dict[str, Any]:
        """Send text message to chat"""
        try:
            # Truncate message if too long
            if len(text) > self.max_message_length:
                text = text[:self.max_message_length-3] + '...'
            
            message = await self.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup
            )
            
            return {
                'success': True,
                'message_id': message.message_id,
                'chat_id': message.chat_id,
                'sent_at': datetime.now(timezone.utc).isoformat()
            }
            
        except Forbidden as e:
            error_code = 'USER_BLOCKED_BOT' if 'blocked' in str(e).lower() else 'FORBIDDEN'
            return {
                'success': False,
                'error': str(e),
                'error_code': error_code
            }
        except BadRequest as e:
            error_code = 'CHAT_NOT_FOUND' if 'chat not found' in str(e).lower() else 'BAD_REQUEST'
            return {
                'success': False,
                'error': str(e),
                'error_code': error_code
            }
        except TelegramError as e:
            logger.error(f"Failed to send message: {e}")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'MESSAGE_SEND_FAILED'
            }
    
    async def send_photo_message(self, chat_id: int, photo_path: str, 
                                caption: str = '', parse_mode: str = 'HTML',
                                reply_markup: Optional[InlineKeyboardMarkup] = None) -> Dict[str, Any]:
        """Send photo message to chat"""
        try:
            # Truncate caption if too long
            if len(caption) > 1024:  # Telegram caption limit
                caption = caption[:1021] + '...'
            
            with open(photo_path, 'rb') as photo:
                message = await self.bot.send_photo(
                    chat_id=chat_id,
                    photo=photo,
                    caption=caption,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup
                )
            
            return {
                'success': True,
                'message_id': message.message_id,
                'chat_id': message.chat_id,
                'sent_at': datetime.now(timezone.utc).isoformat()
            }
            
        except FileNotFoundError:
            return {
                'success': False,
                'error': f'Photo file not found: {photo_path}',
                'error_code': 'FILE_NOT_FOUND'
            }
        except Forbidden as e:
            error_code = 'USER_BLOCKED_BOT' if 'blocked' in str(e).lower() else 'FORBIDDEN'
            return {
                'success': False,
                'error': str(e),
                'error_code': error_code
            }
        except BadRequest as e:
            if 'wrong file identifier' in str(e).lower():
                error_code = 'MEDIA_UPLOAD_FAILED'
            elif 'chat not found' in str(e).lower():
                error_code = 'CHAT_NOT_FOUND'
            else:
                error_code = 'BAD_REQUEST'
            return {
                'success': False,
                'error': str(e),
                'error_code': error_code
            }
        except TelegramError as e:
            logger.error(f"Failed to send photo: {e}")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'PHOTO_SEND_FAILED'
            }
    
    async def send_bulk_messages(self, recipients: List[Dict[str, Any]], 
                                giveaway_id: int) -> Dict[str, Any]:
        """Send bulk messages to multiple recipients"""
        delivered = 0
        failed = 0
        blocked_users = 0
        failed_deliveries = []
        
        # Process in batches to respect rate limits
        for i in range(0, len(recipients), self.batch_size):
            batch = recipients[i:i + self.batch_size]
            
            for recipient in batch:
                user_id = recipient['user_id']
                is_winner = recipient['is_winner']
                message = recipient.get('winner_message' if is_winner else 'loser_message', '')
                message_type = 'winner' if is_winner else 'loser'
                
                # Log delivery attempt
                delivery_log = MessageDeliveryLog(
                    giveaway_id=giveaway_id,
                    user_id=user_id,
                    message_type=message_type,
                    delivery_status='pending'
                )
                db.session.add(delivery_log)
                db.session.commit()
                
                # Send message
                result = await self.send_text_message(user_id, message)
                
                if result['success']:
                    delivered += 1
                    delivery_log.delivery_status = 'sent'
                    delivery_log.telegram_message_id = result['message_id']
                    delivery_log.delivered_at = datetime.now(timezone.utc)
                else:
                    failed += 1
                    delivery_log.delivery_status = 'failed'
                    delivery_log.error_code = result.get('error_code')
                    delivery_log.error_description = result.get('error')
                    
                    if result.get('error_code') == 'USER_BLOCKED_BOT':
                        blocked_users += 1
                    
                    failed_deliveries.append({
                        'user_id': user_id,
                        'error_code': result.get('error_code'),
                        'error': result.get('error')
                    })
                
                delivery_log.delivery_attempts += 1
                delivery_log.last_attempt_at = datetime.now(timezone.utc)
                db.session.commit()
            
            # Rate limiting delay between batches
            if i + self.batch_size < len(recipients):
                await asyncio.sleep(2)  # 2 second delay between batches
        
        return {
            'success': True,
            'delivered': delivered,
            'failed': failed,
            'delivery_summary': {
                'winners_notified': sum(1 for r in recipients if r['is_winner'] and r['user_id'] not in [f['user_id'] for f in failed_deliveries]),
                'losers_notified': sum(1 for r in recipients if not r['is_winner'] and r['user_id'] not in [f['user_id'] for f in failed_deliveries]),
                'blocked_users': blocked_users,
                'failed_deliveries': failed_deliveries
            }
        }

def send_dm_message(user_id: int, message: str, bot_token: str = None, 
                   parse_mode: str = 'HTML', 
                   reply_markup: Optional[InlineKeyboardMarkup] = None) -> Dict[str, Any]:
    """Send direct message to user (synchronous wrapper)"""
    if not bot_token:
        return {
            'success': False,
            'error': 'Bot token is required',
            'error_code': 'MISSING_BOT_TOKEN'
        }
    
    sender = MessageSender(bot_token)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(
            sender.send_text_message(user_id, message, parse_mode, reply_markup)
        )
        return result
    finally:
        loop.close()

def post_giveaway_with_media(channel_id: int, giveaway_data: Dict[str, Any], 
                           media_file_path: str = None, bot_token: str = None) -> Dict[str, Any]:
    """Post giveaway message with optional media (synchronous wrapper)"""
    if not bot_token:
        return {
            'success': False,
            'error': 'Bot token is required',
            'error_code': 'MISSING_BOT_TOKEN'
        }
    
    sender = MessageSender(bot_token)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        from utils.keyboard_builder import build_participate_keyboard
        keyboard = build_participate_keyboard(giveaway_data['id'])
        
        if media_file_path:
            result = loop.run_until_complete(
                sender.send_photo_message(
                    channel_id, 
                    media_file_path, 
                    giveaway_data['main_body'],
                    reply_markup=keyboard
                )
            )
        else:
            result = loop.run_until_complete(
                sender.send_text_message(
                    channel_id, 
                    giveaway_data['main_body'],
                    reply_markup=keyboard
                )
            )
        return result
    finally:
        loop.close()

