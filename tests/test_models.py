"""
Unit tests for database models
"""

import pytest
from datetime import datetime, timezone
from models import db, BotInteraction, MessageDeliveryLog, WebhookProcessingLog

class TestBotInteraction:
    """Test BotInteraction model"""
    
    def test_create_bot_interaction(self, app):
        """Test creating a bot interaction"""
        with app.app_context():
            interaction = BotInteraction(
                user_id=12345,
                interaction_type='message',
                message_text='Hello bot',
                success=True
            )
            
            db.session.add(interaction)
            db.session.commit()
            
            assert interaction.id is not None
            assert interaction.user_id == 12345
            assert interaction.interaction_type == 'message'
            assert interaction.message_text == 'Hello bot'
            assert interaction.success is True
            assert interaction.interaction_timestamp is not None
    
    def test_bot_interaction_with_giveaway(self, app):
        """Test bot interaction with giveaway reference"""
        with app.app_context():
            interaction = BotInteraction(
                user_id=12345,
                interaction_type='callback_query',
                giveaway_id=100,
                callback_data='participate:100',
                success=True
            )
            
            db.session.add(interaction)
            db.session.commit()
            
            assert interaction.giveaway_id == 100
            assert interaction.callback_data == 'participate:100'
    
    def test_bot_interaction_error_case(self, app):
        """Test bot interaction with error"""
        with app.app_context():
            interaction = BotInteraction(
                user_id=12345,
                interaction_type='message',
                message_text='/start',
                success=False,
                error_message='Bot token invalid'
            )
            
            db.session.add(interaction)
            db.session.commit()
            
            assert interaction.success is False
            assert interaction.error_message == 'Bot token invalid'

class TestMessageDeliveryLog:
    """Test MessageDeliveryLog model"""
    
    def test_create_delivery_log(self, app):
        """Test creating a message delivery log"""
        with app.app_context():
            delivery_log = MessageDeliveryLog(
                giveaway_id=100,
                user_id=12345,
                message_type='winner',
                delivery_status='sent'
            )
            
            db.session.add(delivery_log)
            db.session.commit()
            
            assert delivery_log.id is not None
            assert delivery_log.giveaway_id == 100
            assert delivery_log.user_id == 12345
            assert delivery_log.message_type == 'winner'
            assert delivery_log.delivery_status == 'sent'
            assert delivery_log.scheduled_at is not None
    
    def test_delivery_log_with_telegram_info(self, app):
        """Test delivery log with Telegram message info"""
        with app.app_context():
            delivery_log = MessageDeliveryLog(
                giveaway_id=100,
                user_id=12345,
                message_type='loser',
                delivery_status='sent',
                telegram_message_id=98765,
                delivered_at=datetime.now(timezone.utc)
            )
            
            db.session.add(delivery_log)
            db.session.commit()
            
            assert delivery_log.telegram_message_id == 98765
            assert delivery_log.delivered_at is not None
    
    def test_delivery_log_failed_with_retry(self, app):
        """Test failed delivery log with retry information"""
        with app.app_context():
            delivery_log = MessageDeliveryLog(
                giveaway_id=100,
                user_id=12345,
                message_type='winner',
                delivery_status='failed',
                delivery_attempts=2,
                error_code='USER_BLOCKED_BOT',
                error_description='User has blocked the bot'
            )
            
            db.session.add(delivery_log)
            db.session.commit()
            
            assert delivery_log.delivery_status == 'failed'
            assert delivery_log.delivery_attempts == 2
            assert delivery_log.error_code == 'USER_BLOCKED_BOT'
            assert delivery_log.error_description == 'User has blocked the bot'

class TestWebhookProcessingLog:
    """Test WebhookProcessingLog model"""
    
    def test_create_webhook_log(self, app):
        """Test creating a webhook processing log"""
        with app.app_context():
            webhook_log = WebhookProcessingLog(
                update_id=123456,
                update_type='message',
                user_id=12345,
                chat_id=-100123456789,
                processing_status='processed'
            )
            
            db.session.add(webhook_log)
            db.session.commit()
            
            assert webhook_log.id is not None
            assert webhook_log.update_id == 123456
            assert webhook_log.update_type == 'message'
            assert webhook_log.user_id == 12345
            assert webhook_log.chat_id == -100123456789
            assert webhook_log.processing_status == 'processed'
            assert webhook_log.received_at is not None
    
    def test_webhook_log_with_message_text(self, app):
        """Test webhook log with message text"""
        with app.app_context():
            webhook_log = WebhookProcessingLog(
                update_id=123456,
                update_type='message',
                user_id=12345,
                chat_id=12345,
                message_text='/start',
                processing_status='processed',
                processing_time_ms=150
            )
            
            db.session.add(webhook_log)
            db.session.commit()
            
            assert webhook_log.message_text == '/start'
            assert webhook_log.processing_time_ms == 150
    
    def test_webhook_log_callback_query(self, app):
        """Test webhook log for callback query"""
        with app.app_context():
            webhook_log = WebhookProcessingLog(
                update_id=123456,
                update_type='callback_query',
                user_id=12345,
                chat_id=-100123456789,
                callback_data='participate:100',
                processing_status='processed',
                response_sent=True,
                response_type='text'
            )
            
            db.session.add(webhook_log)
            db.session.commit()
            
            assert webhook_log.callback_data == 'participate:100'
            assert webhook_log.response_sent is True
            assert webhook_log.response_type == 'text'
    
    def test_webhook_log_failed_processing(self, app):
        """Test webhook log for failed processing"""
        with app.app_context():
            webhook_log = WebhookProcessingLog(
                update_id=123456,
                update_type='message',
                user_id=12345,
                chat_id=12345,
                processing_status='failed',
                error_message='Invalid bot token'
            )
            
            db.session.add(webhook_log)
            db.session.commit()
            
            assert webhook_log.processing_status == 'failed'
            assert webhook_log.error_message == 'Invalid bot token'

class TestModelRelationships:
    """Test model relationships and constraints"""
    
    def test_unique_update_id_constraint(self, app):
        """Test that update_id is unique in webhook logs"""
        with app.app_context():
            # Create first webhook log
            webhook_log1 = WebhookProcessingLog(
                update_id=123456,
                update_type='message',
                user_id=12345,
                processing_status='processed'
            )
            db.session.add(webhook_log1)
            db.session.commit()
            
            # Try to create second webhook log with same update_id
            webhook_log2 = WebhookProcessingLog(
                update_id=123456,
                update_type='callback_query',
                user_id=67890,
                processing_status='processed'
            )
            db.session.add(webhook_log2)
            
            with pytest.raises(Exception):  # Should raise integrity error
                db.session.commit()
    
    def test_model_timestamps(self, app):
        """Test that timestamps are set correctly"""
        with app.app_context():
            before_creation = datetime.now(timezone.utc)
            
            interaction = BotInteraction(
                user_id=12345,
                interaction_type='message',
                success=True
            )
            db.session.add(interaction)
            db.session.commit()
            
            after_creation = datetime.now(timezone.utc)
            
            assert before_creation <= interaction.interaction_timestamp <= after_creation
    
    def test_model_string_representations(self, app):
        """Test model string representations"""
        with app.app_context():
            interaction = BotInteraction(
                user_id=12345,
                interaction_type='message',
                success=True
            )
            
            delivery_log = MessageDeliveryLog(
                giveaway_id=100,
                user_id=12345,
                message_type='winner',
                delivery_status='sent'
            )
            
            webhook_log = WebhookProcessingLog(
                update_id=123456,
                update_type='message',
                user_id=12345,
                processing_status='processed'
            )
            
            # Test that string representations don't raise errors
            str(interaction)
            str(delivery_log)
            str(webhook_log)

