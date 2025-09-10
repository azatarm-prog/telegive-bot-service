"""
Comprehensive logging configuration for Telegive Bot Service
Provides structured logging, log aggregation, and monitoring integration
"""

import os
import sys
import json
import logging
import logging.config
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from pythonjsonlogger import jsonlogger
import traceback

class StructuredFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional context"""
    
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        
        # Add timestamp in ISO format
        log_record['timestamp'] = datetime.now(timezone.utc).isoformat()
        
        # Add service information
        log_record['service'] = os.getenv('SERVICE_NAME', 'telegive-bot-service')
        log_record['environment'] = os.getenv('ENVIRONMENT', 'development')
        log_record['version'] = '1.0.0'
        
        # Add request context if available
        try:
            from flask import request, g
            if request:
                log_record['request_id'] = getattr(g, 'request_id', None)
                log_record['request_path'] = request.path
                log_record['request_method'] = request.method
                log_record['user_agent'] = request.headers.get('User-Agent')
                log_record['remote_addr'] = request.remote_addr
        except (ImportError, RuntimeError):
            # Flask not available or outside request context
            pass
        
        # Add process information
        log_record['process_id'] = os.getpid()
        log_record['thread_name'] = record.threadName
        
        # Ensure level is always present
        if 'level' not in log_record:
            log_record['level'] = record.levelname

class ContextFilter(logging.Filter):
    """Add contextual information to log records"""
    
    def filter(self, record):
        # Add correlation ID if available
        record.correlation_id = getattr(record, 'correlation_id', None)
        
        # Add user context if available
        record.user_id = getattr(record, 'user_id', None)
        record.telegram_user_id = getattr(record, 'telegram_user_id', None)
        
        # Add operation context
        record.operation = getattr(record, 'operation', None)
        record.component = getattr(record, 'component', None)
        
        return True

class SecurityFilter(logging.Filter):
    """Filter out sensitive information from logs"""
    
    SENSITIVE_PATTERNS = [
        'password', 'token', 'secret', 'key', 'auth',
        'credential', 'session', 'cookie'
    ]
    
    def filter(self, record):
        # Sanitize message
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            record.msg = self._sanitize_message(record.msg)
        
        # Sanitize args
        if hasattr(record, 'args') and record.args:
            record.args = tuple(
                self._sanitize_value(arg) for arg in record.args
            )
        
        return True
    
    def _sanitize_message(self, message: str) -> str:
        """Remove sensitive information from log message"""
        for pattern in self.SENSITIVE_PATTERNS:
            if pattern.lower() in message.lower():
                # Replace potential sensitive values
                import re
                # Pattern to match key=value or key: value
                pattern_regex = rf'({pattern}[=:]\s*)([^\s,\]}}]+)'
                message = re.sub(
                    pattern_regex, 
                    r'\1***REDACTED***', 
                    message, 
                    flags=re.IGNORECASE
                )
        return message
    
    def _sanitize_value(self, value: Any) -> Any:
        """Sanitize individual values"""
        if isinstance(value, str):
            return self._sanitize_message(value)
        elif isinstance(value, dict):
            return {k: '***REDACTED***' if any(p in str(k).lower() for p in self.SENSITIVE_PATTERNS) else v 
                   for k, v in value.items()}
        return value

class LoggingManager:
    """Centralized logging management"""
    
    def __init__(self):
        self.configured = False
        self.log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        self.log_format = os.getenv('LOG_FORMAT', 'json')  # json or text
        self.log_file = os.getenv('LOG_FILE', '/var/log/telegive-bot.log')
        self.enable_console = os.getenv('LOG_CONSOLE', 'true').lower() == 'true'
        self.enable_file = os.getenv('LOG_FILE_ENABLED', 'true').lower() == 'true'
        
    def configure_logging(self):
        """Configure application logging"""
        if self.configured:
            return
        
        # Create log directory if needed
        if self.enable_file:
            log_dir = os.path.dirname(self.log_file)
            if log_dir and not os.path.exists(log_dir):
                try:
                    os.makedirs(log_dir, exist_ok=True)
                except PermissionError:
                    # Fallback to /tmp if can't create in /var/log
                    self.log_file = '/tmp/telegive-bot.log'
                    os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        
        # Configure logging
        config = self._get_logging_config()
        logging.config.dictConfig(config)
        
        # Add custom filters
        self._add_filters()
        
        self.configured = True
        
        # Log configuration success
        logger = logging.getLogger(__name__)
        logger.info("Logging configuration completed", extra={
            'component': 'logging',
            'log_level': self.log_level,
            'log_format': self.log_format,
            'console_enabled': self.enable_console,
            'file_enabled': self.enable_file,
            'log_file': self.log_file if self.enable_file else None
        })
    
    def _get_logging_config(self) -> Dict[str, Any]:
        """Get logging configuration dictionary"""
        
        formatters = {}
        handlers = {}
        
        # Configure formatters
        if self.log_format == 'json':
            formatters['json'] = {
                '()': StructuredFormatter,
                'format': '%(timestamp)s %(level)s %(name)s %(message)s'
            }
            formatter_name = 'json'
        else:
            formatters['detailed'] = {
                'format': '%(asctime)s [%(levelname)s] %(name)s:%(lineno)d [%(process)d:%(threadName)s] %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            }
            formatter_name = 'detailed'
        
        # Configure handlers
        if self.enable_console:
            handlers['console'] = {
                'class': 'logging.StreamHandler',
                'level': self.log_level,
                'formatter': formatter_name,
                'stream': 'ext://sys.stdout'
            }
        
        if self.enable_file:
            handlers['file'] = {
                'class': 'logging.handlers.RotatingFileHandler',
                'level': self.log_level,
                'formatter': formatter_name,
                'filename': self.log_file,
                'maxBytes': 10 * 1024 * 1024,  # 10MB
                'backupCount': 5,
                'encoding': 'utf-8'
            }
        
        # Error file handler for errors and above
        if self.enable_file:
            error_log_file = self.log_file.replace('.log', '-error.log')
            handlers['error_file'] = {
                'class': 'logging.handlers.RotatingFileHandler',
                'level': 'ERROR',
                'formatter': formatter_name,
                'filename': error_log_file,
                'maxBytes': 10 * 1024 * 1024,  # 10MB
                'backupCount': 10,
                'encoding': 'utf-8'
            }
        
        # Configure loggers
        loggers = {
            '': {  # Root logger
                'level': self.log_level,
                'handlers': list(handlers.keys()),
                'propagate': False
            },
            'telegive': {
                'level': self.log_level,
                'handlers': list(handlers.keys()),
                'propagate': False
            },
            'werkzeug': {
                'level': 'WARNING',  # Reduce Flask request logging
                'handlers': list(handlers.keys()),
                'propagate': False
            },
            'urllib3': {
                'level': 'WARNING',  # Reduce HTTP client logging
                'handlers': list(handlers.keys()),
                'propagate': False
            }
        }
        
        return {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': formatters,
            'handlers': handlers,
            'loggers': loggers
        }
    
    def _add_filters(self):
        """Add custom filters to loggers"""
        context_filter = ContextFilter()
        security_filter = SecurityFilter()
        
        # Add filters to all handlers
        for handler in logging.getLogger().handlers:
            handler.addFilter(context_filter)
            handler.addFilter(security_filter)
    
    def get_logger(self, name: str) -> logging.Logger:
        """Get a logger with proper configuration"""
        if not self.configured:
            self.configure_logging()
        
        return logging.getLogger(name)
    
    def log_request(self, request, response=None, duration=None):
        """Log HTTP request details"""
        logger = self.get_logger('telegive.requests')
        
        log_data = {
            'component': 'http_request',
            'method': request.method,
            'path': request.path,
            'query_string': request.query_string.decode() if request.query_string else None,
            'user_agent': request.headers.get('User-Agent'),
            'remote_addr': request.remote_addr,
            'content_length': request.content_length,
        }
        
        if response:
            log_data.update({
                'status_code': response.status_code,
                'response_size': response.content_length
            })
        
        if duration:
            log_data['duration_ms'] = round(duration * 1000, 2)
        
        logger.info("HTTP request processed", extra=log_data)
    
    def log_database_operation(self, operation: str, table: str = None, duration: float = None, error: Exception = None):
        """Log database operations"""
        logger = self.get_logger('telegive.database')
        
        log_data = {
            'component': 'database',
            'operation': operation,
            'table': table
        }
        
        if duration:
            log_data['duration_ms'] = round(duration * 1000, 2)
        
        if error:
            log_data['error'] = str(error)
            log_data['error_type'] = type(error).__name__
            logger.error(f"Database operation failed: {operation}", extra=log_data)
        else:
            logger.info(f"Database operation completed: {operation}", extra=log_data)
    
    def log_external_service_call(self, service: str, endpoint: str, method: str = 'GET', 
                                 duration: float = None, status_code: int = None, error: Exception = None):
        """Log external service calls"""
        logger = self.get_logger('telegive.external_services')
        
        log_data = {
            'component': 'external_service',
            'service': service,
            'endpoint': endpoint,
            'method': method
        }
        
        if duration:
            log_data['duration_ms'] = round(duration * 1000, 2)
        
        if status_code:
            log_data['status_code'] = status_code
        
        if error:
            log_data['error'] = str(error)
            log_data['error_type'] = type(error).__name__
            logger.error(f"External service call failed: {service}", extra=log_data)
        else:
            logger.info(f"External service call completed: {service}", extra=log_data)
    
    def log_telegram_interaction(self, user_id: int, interaction_type: str, 
                                success: bool = True, error: Exception = None):
        """Log Telegram bot interactions"""
        logger = self.get_logger('telegive.telegram')
        
        log_data = {
            'component': 'telegram_bot',
            'telegram_user_id': user_id,
            'interaction_type': interaction_type,
            'success': success
        }
        
        if error:
            log_data['error'] = str(error)
            log_data['error_type'] = type(error).__name__
            logger.error(f"Telegram interaction failed: {interaction_type}", extra=log_data)
        else:
            logger.info(f"Telegram interaction: {interaction_type}", extra=log_data)
    
    def log_security_event(self, event_type: str, details: Dict[str, Any], severity: str = 'INFO'):
        """Log security-related events"""
        logger = self.get_logger('telegive.security')
        
        log_data = {
            'component': 'security',
            'event_type': event_type,
            'severity': severity,
            **details
        }
        
        if severity == 'CRITICAL':
            logger.critical(f"Security event: {event_type}", extra=log_data)
        elif severity == 'ERROR':
            logger.error(f"Security event: {event_type}", extra=log_data)
        elif severity == 'WARNING':
            logger.warning(f"Security event: {event_type}", extra=log_data)
        else:
            logger.info(f"Security event: {event_type}", extra=log_data)
    
    def log_performance_metric(self, metric_name: str, value: float, unit: str = 'ms', 
                              tags: Dict[str, str] = None):
        """Log performance metrics"""
        logger = self.get_logger('telegive.metrics')
        
        log_data = {
            'component': 'metrics',
            'metric_name': metric_name,
            'metric_value': value,
            'metric_unit': unit,
            'tags': tags or {}
        }
        
        logger.info(f"Performance metric: {metric_name}={value}{unit}", extra=log_data)

# Global logging manager instance
logging_manager = LoggingManager()

# Convenience functions
def get_logger(name: str) -> logging.Logger:
    """Get a properly configured logger"""
    return logging_manager.get_logger(name)

def configure_logging():
    """Configure application logging"""
    logging_manager.configure_logging()

def log_request(request, response=None, duration=None):
    """Log HTTP request"""
    logging_manager.log_request(request, response, duration)

def log_database_operation(operation: str, table: str = None, duration: float = None, error: Exception = None):
    """Log database operation"""
    logging_manager.log_database_operation(operation, table, duration, error)

def log_external_service_call(service: str, endpoint: str, method: str = 'GET', 
                             duration: float = None, status_code: int = None, error: Exception = None):
    """Log external service call"""
    logging_manager.log_external_service_call(service, endpoint, method, duration, status_code, error)

def log_telegram_interaction(user_id: int, interaction_type: str, success: bool = True, error: Exception = None):
    """Log Telegram interaction"""
    logging_manager.log_telegram_interaction(user_id, interaction_type, success, error)

def log_security_event(event_type: str, details: Dict[str, Any], severity: str = 'INFO'):
    """Log security event"""
    logging_manager.log_security_event(event_type, details, severity)

def log_performance_metric(metric_name: str, value: float, unit: str = 'ms', tags: Dict[str, str] = None):
    """Log performance metric"""
    logging_manager.log_performance_metric(metric_name, value, unit, tags)

