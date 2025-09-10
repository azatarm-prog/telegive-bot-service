"""
Message retry tasks
Handles retrying failed message deliveries
"""

import logging
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from models import db, MessageDeliveryLog
from utils.message_sender import send_dm_message
from services.auth_service import get_bot_token

logger = logging.getLogger(__name__)

class MessageRetryService:
    """Service for retrying failed message deliveries"""
    
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.max_retry_attempts = 3
        self.retry_intervals = [300, 900, 3600]  # 5 min, 15 min, 1 hour
        
    def start(self):
        """Start the retry service"""
        try:
            # Schedule retry job to run every 5 minutes
            self.scheduler.add_job(
                func=self.process_retry_queue,
                trigger='interval',
                minutes=5,
                id='message_retry_job',
                replace_existing=True
            )
            
            self.scheduler.start()
            logger.info("Message retry service started")
            
        except Exception as e:
            logger.error(f"Failed to start message retry service: {e}")
    
    def stop(self):
        """Stop the retry service"""
        try:
            self.scheduler.shutdown()
            logger.info("Message retry service stopped")
        except Exception as e:
            logger.error(f"Failed to stop message retry service: {e}")
    
    def process_retry_queue(self):
        """Process messages that need to be retried"""
        try:
            # Get failed messages that are eligible for retry
            eligible_messages = self._get_eligible_retry_messages()
            
            logger.info(f"Processing {len(eligible_messages)} messages for retry")
            
            for message_log in eligible_messages:
                self._retry_message_delivery(message_log)
                
        except Exception as e:
            logger.error(f"Error processing retry queue: {e}")
    
    def _get_eligible_retry_messages(self):
        """Get messages eligible for retry"""
        try:
            now = datetime.now(timezone.utc)
            
            # Get failed messages that haven't exceeded max attempts
            failed_messages = MessageDeliveryLog.query.filter(
                MessageDeliveryLog.delivery_status == 'failed',
                MessageDeliveryLog.delivery_attempts < self.max_retry_attempts,
                MessageDeliveryLog.error_code != 'USER_BLOCKED_BOT'  # Don't retry blocked users
            ).all()
            
            eligible_messages = []
            
            for message in failed_messages:
                # Check if enough time has passed for retry
                if self._is_ready_for_retry(message, now):
                    eligible_messages.append(message)
            
            return eligible_messages
            
        except Exception as e:
            logger.error(f"Error getting eligible retry messages: {e}")
            return []
    
    def _is_ready_for_retry(self, message_log, current_time):
        """Check if message is ready for retry based on attempt count and time"""
        if not message_log.last_attempt_at:
            return True
        
        attempt_index = min(message_log.delivery_attempts - 1, len(self.retry_intervals) - 1)
        retry_interval = self.retry_intervals[attempt_index]
        
        time_since_last_attempt = (current_time - message_log.last_attempt_at).total_seconds()
        
        return time_since_last_attempt >= retry_interval
    
    def _retry_message_delivery(self, message_log):
        """Retry delivering a specific message"""
        try:
            # Get the appropriate message content
            message_content = self._get_message_content(message_log)
            
            if not message_content:
                logger.error(f"No message content for delivery log {message_log.id}")
                return
            
            # Get bot token (this would need to be improved to get the correct token)
            # For now, we'll skip this retry if we can't determine the bot token
            bot_token = self._get_bot_token_for_message(message_log)
            
            if not bot_token:
                logger.warning(f"Cannot determine bot token for message {message_log.id}")
                return
            
            # Attempt to send the message
            result = send_dm_message(
                user_id=message_log.user_id,
                message=message_content,
                bot_token=bot_token
            )
            
            # Update delivery log
            message_log.delivery_attempts += 1
            message_log.last_attempt_at = datetime.now(timezone.utc)
            
            if result.get('success'):
                message_log.delivery_status = 'sent'
                message_log.telegram_message_id = result.get('message_id')
                message_log.delivered_at = datetime.now(timezone.utc)
                message_log.error_code = None
                message_log.error_description = None
                
                logger.info(f"Successfully retried message delivery to user {message_log.user_id}")
                
            else:
                # Update error information
                message_log.error_code = result.get('error_code')
                message_log.error_description = result.get('error')
                
                # If max attempts reached, mark as permanently failed
                if message_log.delivery_attempts >= self.max_retry_attempts:
                    message_log.delivery_status = 'permanently_failed'
                    logger.warning(f"Message to user {message_log.user_id} permanently failed after {message_log.delivery_attempts} attempts")
                
                logger.warning(f"Retry attempt {message_log.delivery_attempts} failed for user {message_log.user_id}: {result.get('error')}")
            
            db.session.commit()
            
        except Exception as e:
            logger.error(f"Error retrying message delivery for log {message_log.id}: {e}")
            db.session.rollback()
    
    def _get_message_content(self, message_log):
        """Get the appropriate message content based on message type"""
        # This would typically fetch the message content from the giveaway service
        # For now, return a generic message based on type
        
        message_templates = {
            'winner': '🎊 Congratulations! You are one of our lucky winners!',
            'loser': 'Thank you for participating! Better luck next time! 🍀',
            'participation_confirm': '🎉 You are now participating in the giveaway! Good luck! 🍀',
            'captcha': '🧮 Please solve the captcha to complete your participation.'
        }
        
        return message_templates.get(message_log.message_type, 'You have a message from the giveaway bot.')
    
    def _get_bot_token_for_message(self, message_log):
        """Get the appropriate bot token for the message"""
        # This would need to be implemented to get the correct bot token
        # based on the giveaway or account associated with the message
        # For now, return None to skip retry
        return None
    
    def add_message_for_retry(self, giveaway_id, user_id, message_type, error_code, error_description):
        """Add a message to the retry queue"""
        try:
            retry_log = MessageDeliveryLog(
                giveaway_id=giveaway_id,
                user_id=user_id,
                message_type=message_type,
                delivery_status='failed',
                delivery_attempts=1,
                error_code=error_code,
                error_description=error_description,
                last_attempt_at=datetime.now(timezone.utc)
            )
            
            db.session.add(retry_log)
            db.session.commit()
            
            logger.info(f"Added message for retry: user {user_id}, type {message_type}")
            
        except Exception as e:
            logger.error(f"Error adding message for retry: {e}")
            db.session.rollback()
    
    def get_retry_statistics(self):
        """Get statistics about retry operations"""
        try:
            total_failed = MessageDeliveryLog.query.filter_by(delivery_status='failed').count()
            permanently_failed = MessageDeliveryLog.query.filter_by(delivery_status='permanently_failed').count()
            pending_retry = MessageDeliveryLog.query.filter(
                MessageDeliveryLog.delivery_status == 'failed',
                MessageDeliveryLog.delivery_attempts < self.max_retry_attempts
            ).count()
            
            return {
                'total_failed_messages': total_failed,
                'permanently_failed_messages': permanently_failed,
                'pending_retry_messages': pending_retry,
                'max_retry_attempts': self.max_retry_attempts,
                'retry_intervals': self.retry_intervals
            }
            
        except Exception as e:
            logger.error(f"Error getting retry statistics: {e}")
            return {}

# Global retry service instance
retry_service = MessageRetryService()

def start_retry_service():
    """Start the message retry service"""
    retry_service.start()

def stop_retry_service():
    """Stop the message retry service"""
    retry_service.stop()

def add_message_for_retry(giveaway_id, user_id, message_type, error_code, error_description):
    """Add a message to the retry queue (convenience function)"""
    retry_service.add_message_for_retry(giveaway_id, user_id, message_type, error_code, error_description)

def get_retry_statistics():
    """Get retry statistics (convenience function)"""
    return retry_service.get_retry_statistics()

