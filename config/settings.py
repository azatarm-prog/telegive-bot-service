import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'postgresql://localhost/telegive_bot')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }
    
    # Security
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Service Configuration
    SERVICE_NAME = os.getenv('SERVICE_NAME', 'bot-service')
    SERVICE_PORT = int(os.getenv('SERVICE_PORT', 8006))
    
    # Other Services
    TELEGIVE_AUTH_URL = os.getenv('TELEGIVE_AUTH_URL', 'https://telegive-auth.railway.app')
    TELEGIVE_CHANNEL_URL = os.getenv('TELEGIVE_CHANNEL_URL', 'https://telegive-channel.railway.app')
    TELEGIVE_GIVEAWAY_URL = os.getenv('TELEGIVE_GIVEAWAY_URL', 'https://telegive-service.railway.app')
    TELEGIVE_PARTICIPANT_URL = os.getenv('TELEGIVE_PARTICIPANT_URL', 'https://telegive-participant.railway.app')
    TELEGIVE_MEDIA_URL = os.getenv('TELEGIVE_MEDIA_URL', 'https://telegive-media.railway.app')
    
    # Telegram Configuration
    TELEGRAM_API_BASE = os.getenv('TELEGRAM_API_BASE', 'https://api.telegram.org')
    WEBHOOK_BASE_URL = os.getenv('WEBHOOK_BASE_URL', 'https://telegive-bot.railway.app')
    
    # Bot Configuration
    MAX_MESSAGE_LENGTH = int(os.getenv('MAX_MESSAGE_LENGTH', 4096))
    BULK_MESSAGE_BATCH_SIZE = int(os.getenv('BULK_MESSAGE_BATCH_SIZE', 30))
    MESSAGE_RETRY_ATTEMPTS = int(os.getenv('MESSAGE_RETRY_ATTEMPTS', 3))
    WEBHOOK_TIMEOUT = int(os.getenv('WEBHOOK_TIMEOUT', 30))
    
    # Redis (optional, for user state management)
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
    USER_STATE_TTL = int(os.getenv('USER_STATE_TTL', 3600))
    
    # Testing
    TESTING = False

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'postgresql://test:test@localhost/test_telegive_bot'
    WTF_CSRF_ENABLED = False

