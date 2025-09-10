"""
Telegram API client utilities
Handles low-level Telegram API interactions
"""

import requests
import logging
from typing import Dict, Any, Optional
from telegram import Bot
from telegram.error import TelegramError, Forbidden, BadRequest
from config.settings import Config

logger = logging.getLogger(__name__)

class TelegramClient:
    """Telegram API client wrapper"""
    
    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.bot = Bot(token=bot_token)
        self.api_base = Config.TELEGRAM_API_BASE
    
    async def get_me(self) -> Dict[str, Any]:
        """Get bot information"""
        try:
            bot_info = await self.bot.get_me()
            return {
                'success': True,
                'bot_info': {
                    'id': bot_info.id,
                    'username': bot_info.username,
                    'first_name': bot_info.first_name,
                    'is_bot': bot_info.is_bot
                }
            }
        except TelegramError as e:
            logger.error(f"Failed to get bot info: {e}")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'BOT_INFO_FAILED'
            }
    
    async def set_webhook(self, webhook_url: str) -> Dict[str, Any]:
        """Set webhook URL for the bot"""
        try:
            result = await self.bot.set_webhook(
                url=webhook_url,
                max_connections=100,
                allowed_updates=['message', 'callback_query']
            )
            return {
                'success': result,
                'webhook_url': webhook_url
            }
        except TelegramError as e:
            logger.error(f"Failed to set webhook: {e}")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'WEBHOOK_SETUP_FAILED'
            }
    
    async def get_webhook_info(self) -> Dict[str, Any]:
        """Get current webhook information"""
        try:
            webhook_info = await self.bot.get_webhook_info()
            return {
                'success': True,
                'webhook_info': {
                    'url': webhook_info.url,
                    'has_custom_certificate': webhook_info.has_custom_certificate,
                    'pending_update_count': webhook_info.pending_update_count,
                    'last_error_date': webhook_info.last_error_date,
                    'last_error_message': webhook_info.last_error_message,
                    'max_connections': webhook_info.max_connections,
                    'allowed_updates': webhook_info.allowed_updates
                }
            }
        except TelegramError as e:
            logger.error(f"Failed to get webhook info: {e}")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'WEBHOOK_INFO_FAILED'
            }
    
    async def get_chat_member(self, chat_id: int, user_id: int) -> Dict[str, Any]:
        """Get chat member information"""
        try:
            member = await self.bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            return {
                'success': True,
                'is_member': member.status in ['member', 'administrator', 'creator'],
                'status': member.status,
                'user_info': {
                    'id': member.user.id,
                    'username': member.user.username,
                    'first_name': member.user.first_name,
                    'last_name': member.user.last_name
                }
            }
        except Forbidden:
            return {
                'success': False,
                'error': 'Bot is not a member of the chat or lacks permissions',
                'error_code': 'BOT_NOT_MEMBER'
            }
        except BadRequest as e:
            if 'user not found' in str(e).lower():
                return {
                    'success': False,
                    'error': 'User not found',
                    'error_code': 'USER_NOT_FOUND'
                }
            return {
                'success': False,
                'error': str(e),
                'error_code': 'CHAT_MEMBER_CHECK_FAILED'
            }
        except TelegramError as e:
            logger.error(f"Failed to get chat member: {e}")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'CHAT_MEMBER_CHECK_FAILED'
            }

def validate_bot_token(bot_token: str) -> Dict[str, Any]:
    """Validate bot token by making a test API call"""
    try:
        bot = Bot(token=bot_token)
        bot_info = bot.get_me()
        return {
            'valid': True,
            'bot_info': {
                'id': bot_info.id,
                'username': bot_info.username,
                'first_name': bot_info.first_name,
                'is_bot': bot_info.is_bot
            }
        }
    except TelegramError as e:
        return {
            'valid': False,
            'error': str(e),
            'error_code': 'INVALID_BOT_TOKEN'
        }

def check_channel_membership(bot_token: str, channel_id: int, user_id: int) -> Dict[str, Any]:
    """Check if user is a member of the channel"""
    try:
        bot = Bot(token=bot_token)
        member = bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        return {
            'success': True,
            'is_member': member.status in ['member', 'administrator', 'creator'],
            'status': member.status
        }
    except Forbidden:
        return {
            'success': False,
            'error': 'Bot is not a member of the channel or lacks permissions',
            'error_code': 'BOT_NOT_MEMBER'
        }
    except BadRequest as e:
        if 'user not found' in str(e).lower():
            return {
                'success': False,
                'error': 'User not found',
                'error_code': 'USER_NOT_FOUND'
            }
        return {
            'success': False,
            'error': str(e),
            'error_code': 'MEMBERSHIP_CHECK_FAILED'
        }
    except TelegramError as e:
        logger.error(f"Failed to check membership: {e}")
        return {
            'success': False,
            'error': str(e),
            'error_code': 'MEMBERSHIP_CHECK_FAILED'
        }

def setup_webhook(bot_token: str, webhook_url: str) -> Dict[str, Any]:
    """Setup webhook for the bot"""
    try:
        bot = Bot(token=bot_token)
        result = bot.set_webhook(
            url=webhook_url,
            max_connections=100,
            allowed_updates=['message', 'callback_query']
        )
        return {
            'success': result,
            'webhook_url': webhook_url
        }
    except TelegramError as e:
        logger.error(f"Failed to setup webhook: {e}")
        return {
            'success': False,
            'error': str(e),
            'error_code': 'WEBHOOK_SETUP_FAILED'
        }

