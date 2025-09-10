"""
Integration tests for the bot service
"""

import pytest
import json
from unittest.mock import patch, Mock
from conftest import (
    create_test_bot_interaction, create_test_message_delivery, 
    create_test_webhook_log, TEST_BOT_TOKEN, TEST_USER_ID
)

class TestWebhookIntegration:
    """Integration tests for webhook processing"""
    
    @patch('utils.webhook_handler.handle_message')
    @patch('utils.webhook_handler.log_bot_interaction')
    def test_complete_message_webhook_flow(self, mock_log, mock_handle, client, app):
        """Test complete webhook processing flow for message"""
        # Setup mock responses
        mock_handle.return_value = {
            'success': True,
            'response_sent': True,
            'response_type': 'text',
            'response_text': 'Welcome message'
        }
        
        # Webhook update data
        update_data = {
            'update_id': 123456,
            'message': {
                'message_id': 1,
                'from': {'id': TEST_USER_ID, 'first_name': 'Test'},
                'chat': {'id': TEST_USER_ID, 'type': 'private'},
                'text': '/start'
            }
        }
        
        # Send webhook request
        response = client.post(
            f'/webhook/{TEST_BOT_TOKEN}',
            data=json.dumps(update_data),
            content_type='application/json'
        )
        
        # Verify response
        assert response.status_code == 200
        
        # Verify handler was called
        mock_handle.assert_called_once()
        call_args = mock_handle.call_args[0]
        assert call_args[0] == update_data['message']
        assert call_args[1] == TEST_BOT_TOKEN
        
        # Verify webhook log was created
        with app.app_context():
            from models import WebhookProcessingLog
            webhook_log = WebhookProcessingLog.query.filter_by(update_id=123456).first()
            assert webhook_log is not None
            assert webhook_log.processing_status == 'processed'
            assert webhook_log.response_sent is True
    
    @patch('utils.webhook_handler.handle_callback_query')
    def test_complete_callback_webhook_flow(self, mock_handle, client, app):
        """Test complete webhook processing flow for callback query"""
        mock_handle.return_value = {
            'success': True,
            'response_sent': True,
            'response_type': 'text'
        }
        
        update_data = {
            'update_id': 123457,
            'callback_query': {
                'id': 'callback_123',
                'from': {'id': TEST_USER_ID, 'first_name': 'Test'},
                'message': {
                    'message_id': 2,
                    'chat': {'id': -100123456789, 'type': 'channel'}
                },
                'data': 'participate:100'
            }
        }
        
        response = client.post(
            f'/webhook/{TEST_BOT_TOKEN}',
            data=json.dumps(update_data),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        mock_handle.assert_called_once()
        
        # Verify webhook log
        with app.app_context():
            from models import WebhookProcessingLog
            webhook_log = WebhookProcessingLog.query.filter_by(update_id=123457).first()
            assert webhook_log is not None
            assert webhook_log.update_type == 'callback_query'
            assert webhook_log.callback_data == 'participate:100'
    
    def test_duplicate_update_handling(self, client, app):
        """Test handling of duplicate webhook updates"""
        # Create existing webhook log
        create_test_webhook_log(app, update_id=123456)
        
        update_data = {
            'update_id': 123456,
            'message': {
                'message_id': 1,
                'from': {'id': TEST_USER_ID},
                'chat': {'id': TEST_USER_ID, 'type': 'private'},
                'text': '/start'
            }
        }
        
        response = client.post(
            f'/webhook/{TEST_BOT_TOKEN}',
            data=json.dumps(update_data),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        
        # Verify only one log exists
        with app.app_context():
            from models import WebhookProcessingLog
            logs = WebhookProcessingLog.query.filter_by(update_id=123456).all()
            assert len(logs) == 1

class TestBotApiIntegration:
    """Integration tests for bot API endpoints"""
    
    @patch('routes.bot_api.get_bot_token')
    @patch('routes.bot_api.MessageSender')
    @patch('routes.bot_api.build_participate_keyboard')
    def test_complete_giveaway_posting_flow(self, mock_keyboard, mock_sender_class, 
                                          mock_get_token, client):
        """Test complete giveaway posting flow"""
        # Setup mocks
        mock_get_token.return_value = {
            'success': True,
            'bot_token': TEST_BOT_TOKEN
        }
        
        mock_keyboard.return_value = {
            'inline_keyboard': [[{
                'text': '🎁 PARTICIPATE',
                'callback_data': 'participate:100'
            }]]
        }
        
        mock_sender = Mock()
        mock_sender.send_text_message.return_value = {
            'success': True,
            'message_id': 123,
            'sent_at': '2024-01-01T00:00:00Z'
        }
        mock_sender_class.return_value = mock_sender
        
        # Request data
        request_data = {
            'account_id': 1,
            'giveaway_data': {
                'id': 100,
                'channel_id': -100123456789,
                'main_body': 'Win amazing prizes! 🎁'
            }
        }
        
        # Make request
        response = client.post(
            '/post-giveaway',
            data=json.dumps(request_data),
            content_type='application/json',
            headers={'Authorization': 'Bearer test_token'}
        )
        
        # Verify response
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['message_id'] == 123
        assert data['inline_keyboard_attached'] is True
        
        # Verify message sender was called correctly
        mock_sender.send_text_message.assert_called_once()
        call_args = mock_sender.send_text_message.call_args[1]
        assert call_args['chat_id'] == -100123456789
        assert call_args['text'] == 'Win amazing prizes! 🎁'
    
    @patch('routes.bot_api.get_bot_token')
    @patch('routes.bot_api.MessageSender')
    def test_bulk_message_sending_flow(self, mock_sender_class, mock_get_token, client):
        """Test bulk message sending flow"""
        mock_get_token.return_value = {
            'success': True,
            'bot_token': TEST_BOT_TOKEN
        }
        
        mock_sender = Mock()
        mock_sender.send_bulk_messages.return_value = {
            'success': True,
            'total_recipients': 2,
            'messages_sent': 2,
            'delivery_failures': 0
        }
        mock_sender_class.return_value = mock_sender
        
        request_data = {
            'account_id': 1,
            'giveaway_id': 100,
            'participants': [
                {'user_id': 12345, 'is_winner': True},
                {'user_id': 67890, 'is_winner': False}
            ],
            'winner_message': 'Congratulations! You won!',
            'loser_message': 'Thank you for participating!'
        }
        
        response = client.post(
            '/send-bulk-messages',
            data=json.dumps(request_data),
            content_type='application/json',
            headers={'Authorization': 'Bearer test_token'}
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['messages_sent'] == 2

class TestServiceIntegration:
    """Integration tests for service interactions"""
    
    @patch('services.auth_service.requests.request')
    def test_auth_service_integration(self, mock_request):
        """Test integration with auth service"""
        from services.auth_service import get_bot_token
        
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'success': True,
            'bot_token': TEST_BOT_TOKEN
        }
        mock_request.return_value = mock_response
        
        result = get_bot_token(1, 'test_auth_token')
        
        assert result['success'] is True
        assert result['bot_token'] == TEST_BOT_TOKEN
        
        # Verify request was made correctly
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[1]['headers']['Authorization'] == 'Bearer test_auth_token'
    
    @patch('services.participant_service.requests.request')
    def test_participant_service_integration(self, mock_request):
        """Test integration with participant service"""
        from services.participant_service import register_participation
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'success': True,
            'requires_captcha': True,
            'captcha_question': 'What is 2 + 2?'
        }
        mock_request.return_value = mock_response
        
        result = register_participation(100, TEST_USER_ID, {'user_id': TEST_USER_ID})
        
        assert result['success'] is True
        assert result['requires_captcha'] is True
        assert 'captcha_question' in result

class TestDatabaseIntegration:
    """Integration tests for database operations"""
    
    def test_bot_interaction_logging(self, app):
        """Test bot interaction logging to database"""
        from utils.webhook_handler import log_bot_interaction
        
        with app.app_context():
            log_bot_interaction(
                user_id=TEST_USER_ID,
                interaction_type='message',
                message_text='/start',
                response_sent='Welcome message',
                success=True,
                chat_id=TEST_USER_ID,
                message_id=1
            )
            
            from models import BotInteraction
            interaction = BotInteraction.query.filter_by(user_id=TEST_USER_ID).first()
            
            assert interaction is not None
            assert interaction.interaction_type == 'message'
            assert interaction.message_text == '/start'
            assert interaction.success is True
    
    def test_message_delivery_tracking(self, app):
        """Test message delivery tracking in database"""
        with app.app_context():
            delivery = create_test_message_delivery(
                app,
                giveaway_id=100,
                user_id=TEST_USER_ID,
                message_type='winner',
                delivery_status='sent'
            )
            
            from models import MessageDeliveryLog
            retrieved = MessageDeliveryLog.query.get(delivery.id)
            
            assert retrieved.giveaway_id == 100
            assert retrieved.user_id == TEST_USER_ID
            assert retrieved.message_type == 'winner'
            assert retrieved.delivery_status == 'sent'
    
    def test_webhook_processing_tracking(self, app):
        """Test webhook processing tracking in database"""
        with app.app_context():
            webhook_log = create_test_webhook_log(
                app,
                update_id=123456,
                update_type='message',
                user_id=TEST_USER_ID,
                processing_status='processed'
            )
            
            from models import WebhookProcessingLog
            retrieved = WebhookProcessingLog.query.get(webhook_log.id)
            
            assert retrieved.update_id == 123456
            assert retrieved.update_type == 'message'
            assert retrieved.user_id == TEST_USER_ID
            assert retrieved.processing_status == 'processed'

class TestErrorHandlingIntegration:
    """Integration tests for error handling"""
    
    @patch('utils.webhook_handler.handle_message')
    def test_webhook_error_handling(self, mock_handle, client, app):
        """Test webhook error handling and logging"""
        # Setup mock to raise exception
        mock_handle.side_effect = Exception('Test error')
        
        update_data = {
            'update_id': 123456,
            'message': {
                'message_id': 1,
                'from': {'id': TEST_USER_ID},
                'chat': {'id': TEST_USER_ID, 'type': 'private'},
                'text': '/start'
            }
        }
        
        response = client.post(
            f'/webhook/{TEST_BOT_TOKEN}',
            data=json.dumps(update_data),
            content_type='application/json'
        )
        
        # Should still return 200 to Telegram
        assert response.status_code == 200
        
        # Verify error was logged
        with app.app_context():
            from models import WebhookProcessingLog
            webhook_log = WebhookProcessingLog.query.filter_by(update_id=123456).first()
            assert webhook_log is not None
            assert webhook_log.processing_status == 'failed'
            assert webhook_log.error_message is not None
    
    def test_api_error_responses(self, client):
        """Test API error responses"""
        # Test missing authorization
        response = client.post(
            '/post-giveaway',
            data=json.dumps({'account_id': 1}),
            content_type='application/json'
        )
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data['error_code'] == 'MISSING_AUTH_TOKEN'
        
        # Test missing required fields
        response = client.post(
            '/post-giveaway',
            data=json.dumps({}),
            content_type='application/json',
            headers={'Authorization': 'Bearer test_token'}
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['error_code'] == 'MISSING_REQUIRED_FIELDS'

class TestEndToEndFlow:
    """End-to-end integration tests"""
    
    @patch('utils.message_sender.requests.post')
    @patch('services.participant_service.requests.request')
    @patch('handlers.callback_handler.extract_callback_data')
    def test_complete_participation_flow(self, mock_extract, mock_participant_service, 
                                       mock_telegram_api, client, app):
        """Test complete user participation flow"""
        # Setup mocks
        mock_extract.return_value = {
            'action': 'participate',
            'params': ['100']
        }
        
        # Mock participant service responses
        mock_participant_response = Mock()
        mock_participant_response.status_code = 200
        mock_participant_response.json.return_value = {
            'success': True,
            'already_participating': False
        }
        mock_participant_service.return_value = mock_participant_response
        
        # Mock Telegram API response
        mock_telegram_response = Mock()
        mock_telegram_response.status_code = 200
        mock_telegram_response.json.return_value = {
            'ok': True,
            'result': {'message_id': 123}
        }
        mock_telegram_api.return_value = mock_telegram_response
        
        # Simulate callback query webhook
        update_data = {
            'update_id': 123456,
            'callback_query': {
                'id': 'callback_123',
                'from': {'id': TEST_USER_ID, 'first_name': 'Test'},
                'message': {
                    'message_id': 2,
                    'chat': {'id': -100123456789, 'type': 'channel'}
                },
                'data': 'participate:100'
            }
        }
        
        response = client.post(
            f'/webhook/{TEST_BOT_TOKEN}',
            data=json.dumps(update_data),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        
        # Verify webhook was processed
        with app.app_context():
            from models import WebhookProcessingLog, BotInteraction
            
            webhook_log = WebhookProcessingLog.query.filter_by(update_id=123456).first()
            assert webhook_log is not None
            assert webhook_log.processing_status == 'processed'
            
            # Verify bot interaction was logged
            interaction = BotInteraction.query.filter_by(user_id=TEST_USER_ID).first()
            assert interaction is not None
            assert interaction.interaction_type == 'callback_query'

