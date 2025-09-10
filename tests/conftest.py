"""
Test configuration and fixtures
"""

import pytest
import tempfile
import os
from app import create_app
from models import db

@pytest.fixture
def app():
    """Create application for testing"""
    # Create temporary database
    db_fd, db_path = tempfile.mkstemp()
    
    app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{db_path}',
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'WTF_CSRF_ENABLED': False
    })
    
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()
    
    os.close(db_fd)
    os.unlink(db_path)

@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()

@pytest.fixture
def runner(app):
    """Create test CLI runner"""
    return app.test_cli_runner()

@pytest.fixture
def sample_bot_interaction():
    """Sample bot interaction data"""
    return {
        'user_id': 12345,
        'interaction_type': 'message',
        'message_text': '/start',
        'success': True,
        'chat_id': 12345,
        'message_id': 1
    }

@pytest.fixture
def sample_message_delivery():
    """Sample message delivery data"""
    return {
        'giveaway_id': 100,
        'user_id': 12345,
        'message_type': 'winner',
        'delivery_status': 'sent',
        'telegram_message_id': 98765
    }

@pytest.fixture
def sample_webhook_log():
    """Sample webhook processing log data"""
    return {
        'update_id': 123456,
        'update_type': 'message',
        'user_id': 12345,
        'chat_id': 12345,
        'message_text': '/start',
        'processing_status': 'processed',
        'processing_time_ms': 150
    }

@pytest.fixture
def sample_telegram_message():
    """Sample Telegram message update"""
    return {
        'update_id': 123456,
        'message': {
            'message_id': 1,
            'from': {
                'id': 12345,
                'is_bot': False,
                'first_name': 'Test',
                'username': 'testuser',
                'language_code': 'en'
            },
            'chat': {
                'id': 12345,
                'first_name': 'Test',
                'username': 'testuser',
                'type': 'private'
            },
            'date': 1640995200,
            'text': '/start'
        }
    }

@pytest.fixture
def sample_callback_query():
    """Sample Telegram callback query update"""
    return {
        'update_id': 123457,
        'callback_query': {
            'id': 'callback_123',
            'from': {
                'id': 12345,
                'is_bot': False,
                'first_name': 'Test',
                'username': 'testuser',
                'language_code': 'en'
            },
            'message': {
                'message_id': 2,
                'from': {
                    'id': 987654321,
                    'is_bot': True,
                    'first_name': 'Bot',
                    'username': 'testbot'
                },
                'chat': {
                    'id': -100123456789,
                    'title': 'Test Channel',
                    'type': 'channel'
                },
                'date': 1640995200,
                'text': 'Giveaway message'
            },
            'data': 'participate:100'
        }
    }

@pytest.fixture
def sample_giveaway_data():
    """Sample giveaway data"""
    return {
        'id': 100,
        'account_id': 1,
        'channel_id': -100123456789,
        'title': 'Test Giveaway',
        'main_body': 'Win amazing prizes!',
        'status': 'active',
        'requires_captcha': True,
        'requires_subscription': False,
        'winner_message': 'Congratulations! You won!',
        'loser_message': 'Thank you for participating!'
    }

@pytest.fixture
def mock_telegram_response():
    """Mock successful Telegram API response"""
    return {
        'ok': True,
        'result': {
            'message_id': 123,
            'from': {
                'id': 987654321,
                'is_bot': True,
                'first_name': 'Bot',
                'username': 'testbot'
            },
            'chat': {
                'id': 12345,
                'first_name': 'Test',
                'username': 'testuser',
                'type': 'private'
            },
            'date': 1640995200,
            'text': 'Test message'
        }
    }

@pytest.fixture
def mock_service_response():
    """Mock successful service response"""
    return {
        'success': True,
        'data': {
            'id': 1,
            'status': 'active'
        }
    }

@pytest.fixture
def auth_headers():
    """Authentication headers for API requests"""
    return {
        'Authorization': 'Bearer test_auth_token',
        'Content-Type': 'application/json'
    }

class MockRedis:
    """Mock Redis client for testing"""
    
    def __init__(self):
        self.data = {}
    
    def get(self, key):
        return self.data.get(key)
    
    def set(self, key, value, ex=None):
        self.data[key] = value
        return True
    
    def delete(self, key):
        if key in self.data:
            del self.data[key]
            return 1
        return 0
    
    def exists(self, key):
        return key in self.data
    
    def expire(self, key, seconds):
        return True
    
    def flushall(self):
        self.data.clear()
        return True

@pytest.fixture
def mock_redis():
    """Mock Redis instance for testing"""
    return MockRedis()

@pytest.fixture
def mock_user_state(mock_redis):
    """Mock user state with Redis backend"""
    from utils.user_state import state_manager
    original_redis = state_manager.redis_client
    state_manager.redis_client = mock_redis
    yield mock_redis
    state_manager.redis_client = original_redis

# Test data constants
TEST_BOT_TOKEN = 'test_bot_token_123456789'
TEST_USER_ID = 12345
TEST_CHAT_ID = 12345
TEST_CHANNEL_ID = -100123456789
TEST_GIVEAWAY_ID = 100
TEST_MESSAGE_ID = 1
TEST_UPDATE_ID = 123456

# Helper functions for tests
def create_test_bot_interaction(app, **kwargs):
    """Create a test bot interaction in database"""
    from models import BotInteraction
    
    defaults = {
        'user_id': TEST_USER_ID,
        'interaction_type': 'message',
        'success': True
    }
    defaults.update(kwargs)
    
    with app.app_context():
        interaction = BotInteraction(**defaults)
        db.session.add(interaction)
        db.session.commit()
        return interaction

def create_test_message_delivery(app, **kwargs):
    """Create a test message delivery log in database"""
    from models import MessageDeliveryLog
    
    defaults = {
        'giveaway_id': TEST_GIVEAWAY_ID,
        'user_id': TEST_USER_ID,
        'message_type': 'winner',
        'delivery_status': 'sent'
    }
    defaults.update(kwargs)
    
    with app.app_context():
        delivery = MessageDeliveryLog(**defaults)
        db.session.add(delivery)
        db.session.commit()
        return delivery

def create_test_webhook_log(app, **kwargs):
    """Create a test webhook processing log in database"""
    from models import WebhookProcessingLog
    
    defaults = {
        'update_id': TEST_UPDATE_ID,
        'update_type': 'message',
        'user_id': TEST_USER_ID,
        'processing_status': 'processed'
    }
    defaults.update(kwargs)
    
    with app.app_context():
        webhook_log = WebhookProcessingLog(**defaults)
        db.session.add(webhook_log)
        db.session.commit()
        return webhook_log

