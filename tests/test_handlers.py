"""
Unit tests for message and callback handlers
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from handlers.message_handler import handle_message, handle_command, handle_start_command
from handlers.callback_handler import handle_callback_query, handle_participate_callback
from handlers.error_handler import handle_error, handle_telegram_error
from telegram.error import Forbidden, BadRequest, TimedOut

class TestMessageHandler:
    """Test message handler functions"""
    
    @patch('handlers.message_handler.send_dm_message')
    @patch('handlers.message_handler.get_user_state')
    @patch('handlers.message_handler.log_bot_interaction')
    def test_handle_start_command(self, mock_log, mock_get_state, mock_send_dm):
        """Test handling /start command"""
        # Setup mocks
        mock_get_state.return_value = None
        mock_send_dm.return_value = {
            'success': True,
            'message_id': 123,
            'sent_at': '2024-01-01T00:00:00Z'
        }
        
        # Test data
        message = {
            'from': {'id': 12345},
            'chat': {'id': 12345, 'type': 'private'},
            'message_id': 1,
            'text': '/start'
        }
        
        result = handle_message(message, 'test_bot_token')
        
        # Assertions
        assert result['success'] is True
        assert result['response_sent'] is True
        mock_send_dm.assert_called_once()
        mock_log.assert_called_once()
        
        # Check that welcome message was sent
        call_args = mock_send_dm.call_args[0]
        assert call_args[0] == 12345  # user_id
        assert 'Welcome to Telegive Bot!' in call_args[1]  # message text
    
    @patch('handlers.message_handler.send_dm_message')
    def test_handle_help_command(self, mock_send_dm):
        """Test handling /help command"""
        mock_send_dm.return_value = {
            'success': True,
            'message_id': 123,
            'sent_at': '2024-01-01T00:00:00Z'
        }
        
        result = handle_command(12345, '/help', 'test_bot_token')
        
        assert result['success'] is True
        mock_send_dm.assert_called_once()
        
        # Check that help message was sent
        call_args = mock_send_dm.call_args[0]
        assert 'Telegive Bot Help' in call_args[1]
    
    @patch('handlers.message_handler.send_dm_message')
    @patch('handlers.message_handler.clear_user_state')
    def test_handle_cancel_command(self, mock_clear_state, mock_send_dm):
        """Test handling /cancel command"""
        mock_send_dm.return_value = {
            'success': True,
            'message_id': 123,
            'sent_at': '2024-01-01T00:00:00Z'
        }
        
        result = handle_command(12345, '/cancel', 'test_bot_token')
        
        assert result['success'] is True
        mock_send_dm.assert_called_once()
        mock_clear_state.assert_called_once_with(12345)
    
    def test_handle_group_message_ignored(self):
        """Test that group messages are ignored"""
        message = {
            'from': {'id': 12345},
            'chat': {'id': -100123456789, 'type': 'supergroup'},
            'message_id': 1,
            'text': 'Hello group'
        }
        
        result = handle_message(message, 'test_bot_token')
        
        assert result['success'] is True
        assert result['response_sent'] is False
        assert 'Group message ignored' in result['message']
    
    @patch('handlers.message_handler.validate_captcha')
    @patch('handlers.message_handler.send_dm_message')
    @patch('handlers.message_handler.get_user_state')
    @patch('handlers.message_handler.clear_user_state')
    def test_handle_captcha_correct_answer(self, mock_clear_state, mock_get_state, 
                                         mock_send_dm, mock_validate):
        """Test handling correct captcha answer"""
        # Setup mocks
        mock_get_state.return_value = {
            'state': 'waiting_captcha',
            'giveaway_id': 100
        }
        mock_validate.return_value = {
            'success': True,
            'captcha_completed': True
        }
        mock_send_dm.return_value = {
            'success': True,
            'message_id': 123,
            'sent_at': '2024-01-01T00:00:00Z'
        }
        
        message = {
            'from': {'id': 12345},
            'chat': {'id': 12345, 'type': 'private'},
            'message_id': 1,
            'text': '4'
        }
        
        result = handle_message(message, 'test_bot_token')
        
        assert result['success'] is True
        mock_validate.assert_called_once_with(100, 12345, '4')
        mock_clear_state.assert_called_once_with(12345)
        
        # Check success message
        call_args = mock_send_dm.call_args[0]
        assert 'Captcha completed successfully!' in call_args[1]

class TestCallbackHandler:
    """Test callback query handler functions"""
    
    @patch('handlers.callback_handler.register_participation')
    @patch('handlers.callback_handler.check_participation_status')
    @patch('handlers.callback_handler.send_dm_message')
    @patch('handlers.callback_handler.extract_callback_data')
    def test_handle_participate_callback_success(self, mock_extract, mock_send_dm, 
                                               mock_check_status, mock_register):
        """Test successful participation callback"""
        # Setup mocks
        mock_extract.return_value = {
            'action': 'participate',
            'params': ['100']
        }
        mock_check_status.return_value = {
            'success': True,
            'already_participating': False
        }
        mock_register.return_value = {
            'success': True,
            'requires_captcha': False,
            'requires_subscription': False
        }
        mock_send_dm.return_value = {
            'success': True,
            'message_id': 123,
            'sent_at': '2024-01-01T00:00:00Z'
        }
        
        callback_query = {
            'from': {'id': 12345},
            'data': 'participate:100',
            'message': {
                'chat': {'id': -100123456789, 'type': 'channel'},
                'message_id': 1
            }
        }
        
        result = handle_callback_query(callback_query, 'test_bot_token')
        
        assert result['success'] is True
        mock_register.assert_called_once()
        
        # Check success message
        call_args = mock_send_dm.call_args[0]
        assert 'Participation Successful!' in call_args[1]
    
    @patch('handlers.callback_handler.check_participation_status')
    @patch('handlers.callback_handler.send_dm_message')
    @patch('handlers.callback_handler.extract_callback_data')
    def test_handle_participate_already_participating(self, mock_extract, mock_send_dm, 
                                                    mock_check_status):
        """Test participation when user already participating"""
        mock_extract.return_value = {
            'action': 'participate',
            'params': ['100']
        }
        mock_check_status.return_value = {
            'success': True,
            'already_participating': True
        }
        mock_send_dm.return_value = {
            'success': True,
            'message_id': 123,
            'sent_at': '2024-01-01T00:00:00Z'
        }
        
        callback_query = {
            'from': {'id': 12345},
            'data': 'participate:100',
            'message': {
                'chat': {'id': -100123456789, 'type': 'channel'},
                'message_id': 1
            }
        }
        
        result = handle_callback_query(callback_query, 'test_bot_token')
        
        assert result['success'] is True
        call_args = mock_send_dm.call_args[0]
        assert 'already participating' in call_args[1]
    
    @patch('handlers.callback_handler.get_giveaway_by_token')
    @patch('handlers.callback_handler.check_winner_status')
    @patch('handlers.callback_handler.send_dm_message')
    @patch('handlers.callback_handler.extract_callback_data')
    def test_handle_view_results_winner(self, mock_extract, mock_send_dm, 
                                      mock_check_winner, mock_get_giveaway):
        """Test view results for winner"""
        mock_extract.return_value = {
            'action': 'view_results',
            'params': ['result_token_123']
        }
        mock_get_giveaway.return_value = {
            'success': True,
            'giveaway': {
                'id': 100,
                'status': 'finished',
                'winner_message': 'Congratulations! You won!'
            }
        }
        mock_check_winner.return_value = {
            'success': True,
            'is_winner': True
        }
        mock_send_dm.return_value = {
            'success': True,
            'message_id': 123,
            'sent_at': '2024-01-01T00:00:00Z'
        }
        
        callback_query = {
            'from': {'id': 12345},
            'data': 'view_results:result_token_123',
            'message': {
                'chat': {'id': -100123456789, 'type': 'channel'},
                'message_id': 1
            }
        }
        
        result = handle_callback_query(callback_query, 'test_bot_token')
        
        assert result['success'] is True
        call_args = mock_send_dm.call_args[0]
        assert 'Congratulations! You won!' in call_args[1]

class TestErrorHandler:
    """Test error handler functions"""
    
    def test_handle_forbidden_user_blocked(self):
        """Test handling Forbidden error when user blocked bot"""
        error = Forbidden('Bot was blocked by the user')
        update_data = {
            'message': {
                'from': {'id': 12345}
            }
        }
        
        result = handle_telegram_error(error, 12345, 'test_bot_token')
        
        assert result['success'] is False
        assert result['error_code'] == 'USER_BLOCKED_BOT'
        assert result['user_notification'] is False
    
    def test_handle_bad_request_message_not_modified(self):
        """Test handling BadRequest when message is not modified"""
        error = BadRequest('Message is not modified')
        
        result = handle_telegram_error(error, 12345, 'test_bot_token')
        
        assert result['success'] is True
        assert 'not modified' in result['message']
    
    @patch('handlers.error_handler.send_user_error_notification')
    def test_handle_timeout_error(self, mock_send_notification):
        """Test handling timeout error"""
        error = TimedOut('Request timed out')
        
        result = handle_telegram_error(error, 12345, 'test_bot_token')
        
        assert result['success'] is False
        assert result['error_code'] == 'TIMEOUT'
        mock_send_notification.assert_called_once_with(12345, 'Request timed out', 'test_bot_token')
    
    def test_handle_general_value_error(self):
        """Test handling general ValueError"""
        error = ValueError('Invalid input data')
        
        result = handle_error(error, {}, 'test_bot_token')
        
        assert result['success'] is False
        assert result['error_code'] == 'INVALID_DATA'
    
    def test_handle_connection_error(self):
        """Test handling connection error"""
        error = ConnectionError('Service unavailable')
        
        result = handle_error(error, {}, 'test_bot_token')
        
        assert result['success'] is False
        assert result['error_code'] == 'CONNECTION_ERROR'

class TestHandlerIntegration:
    """Integration tests for handlers"""
    
    @patch('handlers.message_handler.send_dm_message')
    @patch('handlers.message_handler.log_bot_interaction')
    def test_complete_message_flow(self, mock_log, mock_send_dm):
        """Test complete message handling flow"""
        mock_send_dm.return_value = {
            'success': True,
            'message_id': 123,
            'sent_at': '2024-01-01T00:00:00Z'
        }
        
        message = {
            'from': {'id': 12345},
            'chat': {'id': 12345, 'type': 'private'},
            'message_id': 1,
            'text': '/start'
        }
        
        result = handle_message(message, 'test_bot_token')
        
        # Verify complete flow
        assert result['success'] is True
        assert result['response_sent'] is True
        assert result['response_type'] == 'text'
        
        # Verify logging was called with correct parameters
        mock_log.assert_called_once()
        log_call_args = mock_log.call_args[1]
        assert log_call_args['user_id'] == 12345
        assert log_call_args['interaction_type'] == 'message'
        assert log_call_args['message_text'] == '/start'
        assert log_call_args['success'] is True

