"""
Environment configuration management for Telegive Bot Service
Centralized environment configuration with validation and service discovery
"""

import os
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class Environment(Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"

@dataclass
class ServiceConfig:
    name: str
    port: int
    url: Optional[str] = None
    required: bool = True
    timeout: int = 10
    health_endpoint: str = "/health"

class EnvironmentManager:
    """Centralized environment configuration management"""
    
    def __init__(self):
        self.env = Environment(os.getenv('ENVIRONMENT', 'development'))
        self._config = self._load_config()
        self._validate_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration based on environment"""
        
        base_config = {
            'SECRET_KEY': self._get_required('SECRET_KEY'),
            'DATABASE_URL': self._get_required('DATABASE_URL'),
            'SERVICE_NAME': os.getenv('SERVICE_NAME', 'telegive-bot-service'),
            'SERVICE_PORT': int(os.getenv('SERVICE_PORT', 5000)),
            'FLASK_DEBUG': os.getenv('FLASK_DEBUG', 'False').lower() == 'true',
            'REDIS_URL': os.getenv('REDIS_URL'),
            'WEBHOOK_BASE_URL': os.getenv('WEBHOOK_BASE_URL', 'https://telegive-bot.railway.app'),
            'TELEGRAM_BOT_TOKEN': os.getenv('TELEGRAM_BOT_TOKEN'),
            'MAX_MESSAGE_LENGTH': int(os.getenv('MAX_MESSAGE_LENGTH', 4096)),
            'BULK_MESSAGE_BATCH_SIZE': int(os.getenv('BULK_MESSAGE_BATCH_SIZE', 50)),
            'MESSAGE_RETRY_ATTEMPTS': int(os.getenv('MESSAGE_RETRY_ATTEMPTS', 3)),
            'RATE_LIMIT_PER_MINUTE': int(os.getenv('RATE_LIMIT_PER_MINUTE', 30)),
        }
        
        # Service discovery configuration
        services_config = {
            'auth': ServiceConfig(
                name='auth',
                port=8001,
                url=os.getenv('TELEGIVE_AUTH_URL'),
                required=True,
                timeout=10
            ),
            'channel': ServiceConfig(
                name='channel',
                port=8002,
                url=os.getenv('TELEGIVE_CHANNEL_URL'),
                required=False,
                timeout=10
            ),
            'giveaway': ServiceConfig(
                name='giveaway',
                port=8006,
                url=os.getenv('TELEGIVE_GIVEAWAY_URL'),
                required=True,
                timeout=10
            ),
            'participant': ServiceConfig(
                name='participant',
                port=8004,
                url=os.getenv('TELEGIVE_PARTICIPANT_URL'),
                required=True,
                timeout=10
            ),
            'media': ServiceConfig(
                name='media',
                port=8005,
                url=os.getenv('TELEGIVE_MEDIA_URL'),
                required=False,
                timeout=10
            ),
        }
        
        # Environment-specific overrides
        if self.env == Environment.DEVELOPMENT:
            base_config.update({
                'FLASK_DEBUG': True,
                'LOG_LEVEL': 'DEBUG',
                'RATE_LIMIT_PER_MINUTE': 1000,  # More lenient in development
            })
            # Use localhost URLs for development if not specified
            for service in services_config.values():
                if not service.url:
                    service.url = f"http://localhost:{service.port}"
        
        elif self.env == Environment.STAGING:
            base_config.update({
                'FLASK_DEBUG': False,
                'LOG_LEVEL': 'INFO',
                'RATE_LIMIT_PER_MINUTE': 100,
            })
        
        elif self.env == Environment.PRODUCTION:
            base_config.update({
                'FLASK_DEBUG': False,
                'LOG_LEVEL': 'INFO',
                'RATE_LIMIT_PER_MINUTE': 30,
            })
            # Validate all required services have URLs in production
            for service in services_config.values():
                if service.required and not service.url:
                    logger.warning(f"Required service {service.name} URL not configured in production")
        
        base_config['SERVICES'] = services_config
        return base_config
    
    def _get_required(self, key: str) -> str:
        """Get required environment variable with fallback for development"""
        value = os.getenv(key)
        
        # Provide development defaults for required variables
        if not value and self.env == Environment.DEVELOPMENT:
            defaults = {
                'SECRET_KEY': 'dev-secret-key-change-in-production',
                'DATABASE_URL': 'sqlite:///telegive_bot_dev.db',
                'TELEGRAM_BOT_TOKEN': 'dev-bot-token-replace-with-real'
            }
            value = defaults.get(key)
        
        if not value:
            raise ValueError(f"Required environment variable {key} is not set")
        
        return value
    
    def _validate_config(self):
        """Validate configuration"""
        required_keys = ['SECRET_KEY', 'DATABASE_URL', 'SERVICE_NAME']
        
        for key in required_keys:
            if key not in self._config or not self._config[key]:
                raise ValueError(f"Required configuration {key} is missing")
        
        # Validate database URL format
        db_url = self._config['DATABASE_URL']
        if not (db_url.startswith(('postgresql://', 'sqlite:///', 'mysql://'))):
            raise ValueError("DATABASE_URL must be a valid database connection string")
        
        # Validate service port
        port = self._config['SERVICE_PORT']
        if not isinstance(port, int) or port < 1 or port > 65535:
            raise ValueError("SERVICE_PORT must be a valid port number (1-65535)")
        
        # Validate webhook URL format
        webhook_url = self._config['WEBHOOK_BASE_URL']
        if webhook_url and not webhook_url.startswith(('http://', 'https://')):
            raise ValueError("WEBHOOK_BASE_URL must be a valid HTTP/HTTPS URL")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self._config.get(key, default)
    
    def get_service_config(self, service_name: str) -> Optional[ServiceConfig]:
        """Get service configuration by name"""
        services = self._config.get('SERVICES', {})
        return services.get(service_name)
    
    def get_service_url(self, service_name: str) -> Optional[str]:
        """Get service URL by name"""
        service = self.get_service_config(service_name)
        return service.url if service else None
    
    def is_service_required(self, service_name: str) -> bool:
        """Check if service is required"""
        service = self.get_service_config(service_name)
        return service.required if service else False
    
    def get_all_service_urls(self) -> Dict[str, str]:
        """Get all configured service URLs"""
        services = self._config.get('SERVICES', {})
        return {name: service.url for name, service in services.items() if service.url}
    
    def get_required_services(self) -> List[str]:
        """Get list of required service names"""
        services = self._config.get('SERVICES', {})
        return [name for name, service in services.items() if service.required]
    
    def get_optional_services(self) -> List[str]:
        """Get list of optional service names"""
        services = self._config.get('SERVICES', {})
        return [name for name, service in services.items() if not service.required]
    
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.env == Environment.PRODUCTION
    
    def is_development(self) -> bool:
        """Check if running in development environment"""
        return self.env == Environment.DEVELOPMENT
    
    def is_staging(self) -> bool:
        """Check if running in staging environment"""
        return self.env == Environment.STAGING
    
    def get_flask_config(self) -> Dict[str, Any]:
        """Get Flask-specific configuration"""
        return {
            'SECRET_KEY': self._config['SECRET_KEY'],
            'SQLALCHEMY_DATABASE_URI': self._config['DATABASE_URL'],
            'SQLALCHEMY_TRACK_MODIFICATIONS': False,
            'DEBUG': self._config['FLASK_DEBUG'],
            'TESTING': False,
            'WTF_CSRF_ENABLED': True,
            'WTF_CSRF_TIME_LIMIT': 3600,
        }
    
    def get_logging_config(self) -> Dict[str, Any]:
        """Get logging configuration"""
        log_level = self._config.get('LOG_LEVEL', 'INFO')
        
        config = {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'standard': {
                    'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
                },
                'detailed': {
                    'format': '%(asctime)s [%(levelname)s] %(name)s:%(lineno)d: %(message)s'
                }
            },
            'handlers': {
                'default': {
                    'level': log_level,
                    'formatter': 'standard',
                    'class': 'logging.StreamHandler',
                    'stream': 'ext://sys.stdout'
                }
            },
            'loggers': {
                '': {
                    'handlers': ['default'],
                    'level': log_level,
                    'propagate': False
                },
                'telegive': {
                    'handlers': ['default'],
                    'level': log_level,
                    'propagate': False
                }
            }
        }
        
        return config
    
    def export_env_template(self) -> str:
        """Export environment template for documentation"""
        template = [
            "# Telegive Bot Service Configuration",
            "# Copy this file to .env and update with your values",
            "",
            "# Service Configuration",
            f"SERVICE_NAME={self._config['SERVICE_NAME']}",
            f"SERVICE_PORT={self._config['SERVICE_PORT']}",
            "SECRET_KEY=your-secret-key-here",
            "FLASK_DEBUG=False",
            "ENVIRONMENT=production",
            "",
            "# Database",
            "DATABASE_URL=postgresql://user:password@host:port/database",
            "",
            "# Telegram Bot",
            "TELEGRAM_BOT_TOKEN=your-bot-token-here",
            f"WEBHOOK_BASE_URL={self._config['WEBHOOK_BASE_URL']}",
            "",
            "# Message Configuration",
            f"MAX_MESSAGE_LENGTH={self._config['MAX_MESSAGE_LENGTH']}",
            f"BULK_MESSAGE_BATCH_SIZE={self._config['BULK_MESSAGE_BATCH_SIZE']}",
            f"MESSAGE_RETRY_ATTEMPTS={self._config['MESSAGE_RETRY_ATTEMPTS']}",
            f"RATE_LIMIT_PER_MINUTE={self._config['RATE_LIMIT_PER_MINUTE']}",
            "",
            "# External Services"
        ]
        
        services = self._config.get('SERVICES', {})
        for name, service in services.items():
            env_var = f"TELEGIVE_{name.upper()}_URL"
            example_url = f"https://telegive-{name}-production.up.railway.app"
            required_note = " # Required" if service.required else " # Optional"
            template.append(f"{env_var}={example_url}{required_note}")
        
        template.extend([
            "",
            "# Optional Services",
            "REDIS_URL=redis://localhost:6379",
            "",
            "# Logging",
            "LOG_LEVEL=INFO"
        ])
        
        return "\n".join(template)
    
    def validate_runtime_config(self) -> List[str]:
        """Validate runtime configuration and return list of issues"""
        issues = []
        
        # Check database connectivity
        try:
            import sqlalchemy
            engine = sqlalchemy.create_engine(self._config['DATABASE_URL'])
            with engine.connect() as conn:
                conn.execute(sqlalchemy.text('SELECT 1'))
        except Exception as e:
            issues.append(f"Database connection failed: {e}")
        
        # Check required services in production
        if self.is_production():
            for service_name in self.get_required_services():
                service_url = self.get_service_url(service_name)
                if not service_url:
                    issues.append(f"Required service {service_name} URL not configured")
        
        # Check Telegram bot token format
        bot_token = self._config.get('TELEGRAM_BOT_TOKEN')
        if bot_token and bot_token != 'dev-bot-token-replace-with-real':
            if not bot_token.count(':') == 1 or len(bot_token.split(':')[0]) < 8:
                issues.append("TELEGRAM_BOT_TOKEN format appears invalid")
        
        # Check webhook URL accessibility in production
        if self.is_production():
            webhook_url = self._config['WEBHOOK_BASE_URL']
            if webhook_url and webhook_url.startswith('http://'):
                issues.append("WEBHOOK_BASE_URL should use HTTPS in production")
        
        return issues
    
    def get_health_check_config(self) -> Dict[str, Any]:
        """Get health check configuration"""
        return {
            'database_timeout': 5,
            'service_timeout': 5,
            'telegram_api_timeout': 10,
            'health_check_interval': 30,
            'max_retries': 3,
            'retry_delay': 1
        }

# Global instance
env_manager = EnvironmentManager()

