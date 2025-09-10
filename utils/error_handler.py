"""
Comprehensive error handling utilities for Telegive Bot Service
Provides standardized error handling, logging, and recovery mechanisms
"""

import logging
import traceback
import sys
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Callable
from functools import wraps
from flask import jsonify, request, current_app
import requests
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

class TelegiveError(Exception):
    """Base exception class for Telegive Bot Service"""
    
    def __init__(self, message: str, error_code: str = None, details: Dict[str, Any] = None):
        self.message = message
        self.error_code = error_code or 'TELEGIVE_ERROR'
        self.details = details or {}
        self.timestamp = datetime.now(timezone.utc)
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for JSON response"""
        return {
            'success': False,
            'error': self.message,
            'error_code': self.error_code,
            'details': self.details,
            'timestamp': self.timestamp.isoformat()
        }

class DatabaseError(TelegiveError):
    """Database-related errors"""
    
    def __init__(self, message: str, details: Dict[str, Any] = None):
        super().__init__(message, 'DATABASE_ERROR', details)

class ExternalServiceError(TelegiveError):
    """External service communication errors"""
    
    def __init__(self, service_name: str, message: str, details: Dict[str, Any] = None):
        self.service_name = service_name
        details = details or {}
        details['service'] = service_name
        super().__init__(message, 'EXTERNAL_SERVICE_ERROR', details)

class TelegramAPIError(TelegiveError):
    """Telegram API-related errors"""
    
    def __init__(self, message: str, api_response: Dict[str, Any] = None):
        details = {'api_response': api_response} if api_response else {}
        super().__init__(message, 'TELEGRAM_API_ERROR', details)

class ValidationError(TelegiveError):
    """Input validation errors"""
    
    def __init__(self, message: str, field: str = None, value: Any = None):
        details = {}
        if field:
            details['field'] = field
        if value is not None:
            details['value'] = str(value)
        super().__init__(message, 'VALIDATION_ERROR', details)

class RateLimitError(TelegiveError):
    """Rate limiting errors"""
    
    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = None):
        details = {'retry_after': retry_after} if retry_after else {}
        super().__init__(message, 'RATE_LIMIT_ERROR', details)

class AuthenticationError(TelegiveError):
    """Authentication/authorization errors"""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, 'AUTHENTICATION_ERROR')

class ConfigurationError(TelegiveError):
    """Configuration-related errors"""
    
    def __init__(self, message: str, config_key: str = None):
        details = {'config_key': config_key} if config_key else {}
        super().__init__(message, 'CONFIGURATION_ERROR', details)

class ErrorHandler:
    """Centralized error handling and logging"""
    
    def __init__(self, app=None):
        self.app = app
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize error handler with Flask app"""
        self.app = app
        
        # Register error handlers
        app.errorhandler(TelegiveError)(self.handle_telegive_error)
        app.errorhandler(SQLAlchemyError)(self.handle_database_error)
        app.errorhandler(requests.exceptions.RequestException)(self.handle_request_error)
        app.errorhandler(400)(self.handle_bad_request)
        app.errorhandler(401)(self.handle_unauthorized)
        app.errorhandler(403)(self.handle_forbidden)
        app.errorhandler(404)(self.handle_not_found)
        app.errorhandler(429)(self.handle_rate_limit)
        app.errorhandler(500)(self.handle_internal_error)
        app.errorhandler(503)(self.handle_service_unavailable)
        
        # Configure logging
        self._configure_logging()
    
    def _configure_logging(self):
        """Configure structured logging"""
        if not self.app.debug:
            # Production logging configuration
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(logging.Formatter(
                '%(asctime)s %(levelname)s [%(name)s] %(message)s'
            ))
            
            # Set log level based on environment
            log_level = logging.INFO
            if self.app.config.get('LOG_LEVEL'):
                log_level = getattr(logging, self.app.config['LOG_LEVEL'].upper(), logging.INFO)
            
            handler.setLevel(log_level)
            self.app.logger.addHandler(handler)
            self.app.logger.setLevel(log_level)
    
    def handle_telegive_error(self, error: TelegiveError):
        """Handle custom Telegive errors"""
        logger.error(f"Telegive error: {error.message}", extra={
            'error_code': error.error_code,
            'details': error.details,
            'request_path': request.path if request else None,
            'request_method': request.method if request else None
        })
        
        status_code = self._get_status_code_for_error(error)
        return jsonify(error.to_dict()), status_code
    
    def handle_database_error(self, error: SQLAlchemyError):
        """Handle database errors"""
        logger.error(f"Database error: {str(error)}", extra={
            'error_type': type(error).__name__,
            'request_path': request.path if request else None
        })
        
        # Convert to TelegiveError
        db_error = DatabaseError(
            "Database operation failed",
            details={'original_error': str(error)}
        )
        
        return jsonify(db_error.to_dict()), 500
    
    def handle_request_error(self, error: requests.exceptions.RequestException):
        """Handle HTTP request errors"""
        logger.error(f"Request error: {str(error)}", extra={
            'error_type': type(error).__name__,
            'request_path': request.path if request else None
        })
        
        # Convert to TelegiveError
        service_error = ExternalServiceError(
            "unknown",
            "External service request failed",
            details={'original_error': str(error)}
        )
        
        return jsonify(service_error.to_dict()), 503
    
    def handle_bad_request(self, error):
        """Handle 400 Bad Request"""
        validation_error = ValidationError("Invalid request data")
        return jsonify(validation_error.to_dict()), 400
    
    def handle_unauthorized(self, error):
        """Handle 401 Unauthorized"""
        auth_error = AuthenticationError("Authentication required")
        return jsonify(auth_error.to_dict()), 401
    
    def handle_forbidden(self, error):
        """Handle 403 Forbidden"""
        auth_error = AuthenticationError("Access forbidden")
        return jsonify(auth_error.to_dict()), 403
    
    def handle_not_found(self, error):
        """Handle 404 Not Found"""
        not_found_error = TelegiveError(
            "Resource not found",
            "NOT_FOUND",
            {'path': request.path if request else None}
        )
        return jsonify(not_found_error.to_dict()), 404
    
    def handle_rate_limit(self, error):
        """Handle 429 Rate Limit"""
        rate_limit_error = RateLimitError()
        return jsonify(rate_limit_error.to_dict()), 429
    
    def handle_internal_error(self, error):
        """Handle 500 Internal Server Error"""
        logger.error(f"Internal server error: {str(error)}", extra={
            'traceback': traceback.format_exc(),
            'request_path': request.path if request else None
        })
        
        internal_error = TelegiveError(
            "Internal server error",
            "INTERNAL_ERROR",
            {'error_id': self._generate_error_id()}
        )
        
        return jsonify(internal_error.to_dict()), 500
    
    def handle_service_unavailable(self, error):
        """Handle 503 Service Unavailable"""
        service_error = TelegiveError(
            "Service temporarily unavailable",
            "SERVICE_UNAVAILABLE"
        )
        return jsonify(service_error.to_dict()), 503
    
    def _get_status_code_for_error(self, error: TelegiveError) -> int:
        """Get appropriate HTTP status code for error"""
        status_map = {
            'VALIDATION_ERROR': 400,
            'AUTHENTICATION_ERROR': 401,
            'RATE_LIMIT_ERROR': 429,
            'DATABASE_ERROR': 500,
            'EXTERNAL_SERVICE_ERROR': 503,
            'TELEGRAM_API_ERROR': 502,
            'CONFIGURATION_ERROR': 500,
            'NOT_FOUND': 404
        }
        
        return status_map.get(error.error_code, 500)
    
    def _generate_error_id(self) -> str:
        """Generate unique error ID for tracking"""
        import uuid
        return str(uuid.uuid4())[:8]

def with_error_handling(func: Callable) -> Callable:
    """Decorator for automatic error handling"""
    
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except TelegiveError:
            # Re-raise custom errors to be handled by error handler
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error in {func.__name__}: {str(e)}")
            raise DatabaseError("Database operation failed")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error in {func.__name__}: {str(e)}")
            raise ExternalServiceError("unknown", "External service request failed")
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {str(e)}", extra={
                'traceback': traceback.format_exc()
            })
            raise TelegiveError(f"Unexpected error in {func.__name__}")
    
    return wrapper

def validate_required_fields(data: Dict[str, Any], required_fields: list) -> None:
    """Validate that required fields are present in data"""
    missing_fields = []
    
    for field in required_fields:
        if field not in data or data[field] is None:
            missing_fields.append(field)
    
    if missing_fields:
        raise ValidationError(
            f"Missing required fields: {', '.join(missing_fields)}",
            details={'missing_fields': missing_fields}
        )

def validate_field_types(data: Dict[str, Any], field_types: Dict[str, type]) -> None:
    """Validate field types in data"""
    type_errors = []
    
    for field, expected_type in field_types.items():
        if field in data and data[field] is not None:
            if not isinstance(data[field], expected_type):
                type_errors.append({
                    'field': field,
                    'expected_type': expected_type.__name__,
                    'actual_type': type(data[field]).__name__
                })
    
    if type_errors:
        raise ValidationError(
            "Invalid field types",
            details={'type_errors': type_errors}
        )

def safe_external_request(url: str, method: str = 'GET', timeout: int = 10, **kwargs) -> requests.Response:
    """Make a safe external request with error handling"""
    try:
        response = requests.request(method, url, timeout=timeout, **kwargs)
        response.raise_for_status()
        return response
    
    except requests.exceptions.Timeout:
        raise ExternalServiceError("unknown", f"Request to {url} timed out")
    except requests.exceptions.ConnectionError:
        raise ExternalServiceError("unknown", f"Could not connect to {url}")
    except requests.exceptions.HTTPError as e:
        raise ExternalServiceError("unknown", f"HTTP error {e.response.status_code}: {url}")
    except requests.exceptions.RequestException as e:
        raise ExternalServiceError("unknown", f"Request failed: {str(e)}")

def log_operation(operation_name: str, details: Dict[str, Any] = None):
    """Decorator to log operation start and completion"""
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = datetime.now(timezone.utc)
            
            logger.info(f"Starting operation: {operation_name}", extra={
                'operation': operation_name,
                'details': details or {},
                'start_time': start_time.isoformat()
            })
            
            try:
                result = func(*args, **kwargs)
                
                end_time = datetime.now(timezone.utc)
                duration = (end_time - start_time).total_seconds()
                
                logger.info(f"Completed operation: {operation_name}", extra={
                    'operation': operation_name,
                    'duration_seconds': duration,
                    'success': True
                })
                
                return result
                
            except Exception as e:
                end_time = datetime.now(timezone.utc)
                duration = (end_time - start_time).total_seconds()
                
                logger.error(f"Failed operation: {operation_name}", extra={
                    'operation': operation_name,
                    'duration_seconds': duration,
                    'success': False,
                    'error': str(e)
                })
                
                raise
        
        return wrapper
    return decorator

# Global error handler instance
error_handler = ErrorHandler()

