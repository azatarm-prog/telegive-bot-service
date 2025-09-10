"""
Unit tests for API routes
"""

import pytest
import json
from unittest.mock import patch, Mock
from flask import Flask

class TestWebhookRoutes:
    """Test webhook routes"""
    
    def test_webhook_post_valid_update(self, client):
        """Test webhook with valid update"""
        update_data = {
            'update_id': 123456,
            'message': {
                'message_id': 1,
                'from': {'id': 12345, 'first_name': 'Test'},
                'chat': {'id': 12345, 'type': 'private'},
                'text': '/start'
            }
        }
        
        with patch('routes.webhook.process_webhook_update') as mock_process:
            mock_process.return_value = {'success': True}
            
            response = client.post(
                '/webhook/test_bot_token',
                data=json.dumps(update_data),
                content_type='application/json'
            )
            
            assert response.status_code == 200
            mock_process.assert_called_once_with(update_data, 'test_bot_token')
    
    def test_webhook_post_invalid_json(self, client):
        """Test webhook with invalid JSON"""
        response = client.post(
            '/webhook/test_bot_token',
            data='invalid json',
            content_type='application/json'
        )
        
        assert response.status_code == 200  # Always return 200 to Telegram
    
    def test_webhook_post_empty_data(self, client):
        """Test webhook with empty data"""
        response = client.post(
            '/webhook/test_bot_token',
            data='',
            content_type='application/json'
        )
        
        assert response.status_code == 200
    
    def test_webhook_post_invalid_token(self, client):
        """Test webhook with invalid token format"""
        update_data = {
            'update_id': 123456,
            'message': {
                'message_id': 1,
                'from': {'id': 12345},
                'chat': {'id': 12345},
                'text': '/start'
            }
        }
        
        response = client.post(
            '/webhook/short',  # Too short token
            data=json.dumps(update_data),
            content_type='application/json'
        )
        
        assert response.status_code == 400
    
    @patch('routes.webhook.TelegramClient')
    def test_webhook_get_info(self, mock_client_class, client):
        """Test getting webhook info"""
        mock_client = Mock()
        mock_client.get_webhook_info.return_value = {
            'success': True,
            'webhook_url': 'https://example.com/webhook/token'
        }
        mock_client_class.return_value = mock_client
        
        response = client.get('/webhook/test_bot_token')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
    
    @patch('routes.webhook.setup_webhook')
    def test_webhook_set(self, mock_setup, client):
        """Test setting webhook URL"""
        mock_setup.return_value = {'success': True}
        
        response = client.post(
            '/webhook/test_bot_token/set',
            data=json.dumps({'webhook_url': 'https://example.com/webhook/token'}),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True

class TestBotApiRoutes:
    """Test bot API routes"""
    
    @patch('routes.bot_api.get_bot_token')
    @patch('routes.bot_api.MessageSender')
    def test_post_giveaway_success(self, mock_sender_class, mock_get_token, client):
        """Test successful giveaway posting"""
        # Setup mocks
        mock_get_token.return_value = {
            'success': True,
            'bot_token': 'test_bot_token'
        }
        
        mock_sender = Mock()
        mock_sender.send_text_message.return_value = {
            'success': True,
            'message_id': 123,
            'sent_at': '2024-01-01T00:00:00Z'
        }
        mock_sender_class.return_value = mock_sender
        
        request_data = {
            'account_id': 1,
            'giveaway_data': {
                'id': 100,
                'channel_id': -100123456789,
                'main_body': 'Test giveaway message'
            }
        }
        
        response = client.post(
            '/post-giveaway',
            data=json.dumps(request_data),
            content_type='application/json',
            headers={'Authorization': 'Bearer test_token'}
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['message_id'] == 123
    
    def test_post_giveaway_missing_auth(self, client):
        """Test giveaway posting without authorization"""
        request_data = {
            'account_id': 1,
            'giveaway_data': {
                'id': 100,
                'channel_id': -100123456789,
                'main_body': 'Test giveaway message'
            }
        }
        
        response = client.post(
            '/post-giveaway',
            data=json.dumps(request_data),
            content_type='application/json'
        )
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data['error_code'] == 'MISSING_AUTH_TOKEN'
    
    @patch('routes.bot_api.get_bot_token')
    @patch('routes.bot_api.MessageSender')
    def test_post_conclusion_success(self, mock_sender_class, mock_get_token, client):
        """Test successful conclusion posting"""
        mock_get_token.return_value = {
            'success': True,
            'bot_token': 'test_bot_token'
        }
        
        mock_sender = Mock()
        mock_sender.send_text_message.return_value = {
            'success': True,
            'message_id': 124,
            'sent_at': '2024-01-01T00:00:00Z'
        }
        mock_sender_class.return_value = mock_sender
        
        request_data = {
            'account_id': 1,
            'giveaway_id': 100,
            'channel_id': -100123456789,
            'conclusion_message': 'Giveaway concluded!',
            'result_token': 'result_token_123'
        }
        
        response = client.post(
            '/post-conclusion',
            data=json.dumps(request_data),
            content_type='application/json',
            headers={'Authorization': 'Bearer test_token'}
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['view_results_button_attached'] is True
    
    @patch('routes.bot_api.send_dm_message')
    def test_send_dm_success(self, mock_send_dm, client):
        """Test successful DM sending"""
        mock_send_dm.return_value = {
            'success': True,
            'message_id': 125,
            'sent_at': '2024-01-01T00:00:00Z'
        }
        
        with patch('routes.bot_api.get_bot_token') as mock_get_token:
            mock_get_token.return_value = {
                'success': True,
                'bot_token': 'test_bot_token'
            }
            
            request_data = {
                'account_id': 1,
                'user_id': 12345,
                'message': 'Test DM message'
            }
            
            response = client.post(
                '/send-dm',
                data=json.dumps(request_data),
                content_type='application/json',
                headers={'Authorization': 'Bearer test_token'}
            )
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            assert data['message_id'] == 125
    
    def test_user_info_success(self, client):
        """Test getting user info"""
        response = client.get(
            '/user-info/12345',
            headers={'Authorization': 'Bearer test_token'}
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['user_info']['id'] == 12345
    
    @patch('routes.bot_api.check_channel_membership')
    def test_check_membership_success(self, mock_check, client):
        """Test checking channel membership"""
        mock_check.return_value = {
            'success': True,
            'is_member': True,
            'status': 'member'
        }
        
        request_data = {
            'bot_token': 'test_bot_token',
            'channel_id': -100123456789,
            'user_id': 12345
        }
        
        response = client.post(
            '/check-membership',
            data=json.dumps(request_data),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['is_member'] is True

class TestHealthRoutes:
    """Test health check routes"""
    
    def test_health_check_success(self, client):
        """Test main health check"""
        with patch('routes.health.db.session.execute'):
            response = client.get('/health')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['service'] == 'bot-service'
            assert 'timestamp' in data
    
    def test_health_check_database_failure(self, client):
        """Test health check with database failure"""
        with patch('routes.health.db.session.execute', side_effect=Exception('DB Error')):
            response = client.get('/health')
            
            assert response.status_code == 503
            data = json.loads(response.data)
            assert data['status'] == 'unhealthy'
    
    def test_database_health_success(self, client):
        """Test database health check"""
        with patch('routes.health.db.session.execute'):
            with patch('routes.health.BotInteraction.query.count', return_value=10):
                with patch('routes.health.MessageDeliveryLog.query.count', return_value=5):
                    with patch('routes.health.WebhookProcessingLog.query.count', return_value=20):
                        response = client.get('/health/database')
                        
                        assert response.status_code == 200
                        data = json.loads(response.data)
                        assert data['database'] == 'connected'
                        assert data['statistics']['bot_interactions'] == 10
    
    @patch('routes.health.requests.get')
    def test_telegram_health_success(self, mock_get, client):
        """Test Telegram API health check"""
        mock_response = Mock()
        mock_response.status_code = 401  # Expected for invalid token
        mock_get.return_value = mock_response
        
        response = client.get('/health/telegram')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['telegram_api'] == 'accessible'
    
    def test_service_status(self, client):
        """Test service status endpoint"""
        with patch('routes.health.BotInteraction.query') as mock_query:
            mock_query.filter.return_value.count.return_value = 5
            mock_query.count.return_value = 100
            
            with patch('routes.health.MessageDeliveryLog.query') as mock_delivery_query:
                mock_delivery_query.filter.return_value.count.return_value = 3
                
                with patch('routes.health.WebhookProcessingLog.query') as mock_webhook_query:
                    mock_webhook_query.filter.return_value.count.return_value = 15
                    
                    response = client.get('/status')
                    
                    assert response.status_code == 200
                    data = json.loads(response.data)
                    assert data['service'] == 'bot-service'
                    assert 'statistics' in data
                    assert 'configuration' in data

class TestRouteIntegration:
    """Integration tests for routes"""
    
    @patch('routes.webhook.process_webhook_update')
    def test_webhook_to_handler_flow(self, mock_process, client):
        """Test complete webhook to handler flow"""
        mock_process.return_value = {
            'success': True,
            'response_sent': True,
            'response_type': 'text'
        }
        
        update_data = {
            'update_id': 123456,
            'message': {
                'message_id': 1,
                'from': {'id': 12345, 'first_name': 'Test'},
                'chat': {'id': 12345, 'type': 'private'},
                'text': '/start'
            }
        }
        
        response = client.post(
            '/webhook/test_bot_token',
            data=json.dumps(update_data),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        mock_process.assert_called_once()
        
        # Verify the update was processed with correct data
        call_args = mock_process.call_args[0]
        assert call_args[0] == update_data
        assert call_args[1] == 'test_bot_token'
    
    def test_error_handling_in_routes(self, client):
        """Test error handling in routes"""
        # Test with malformed JSON
        response = client.post(
            '/webhook/test_bot_token',
            data='{"invalid": json}',
            content_type='application/json'
        )
        
        # Should still return 200 to avoid Telegram retries
        assert response.status_code == 200
    
    def test_cors_headers(self, client):
        """Test CORS headers are present"""
        response = client.options('/health')
        
        # Flask-CORS should add appropriate headers
        # This test would need the actual CORS setup to verify headers

