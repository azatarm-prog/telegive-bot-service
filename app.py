#!/usr/bin/env python3
"""
Telegive Bot Service - Main Application
Enhanced with environment management, service discovery, comprehensive error handling,
logging, and monitoring
"""

import os
import logging
import logging.config
import time
import uuid
from flask import Flask, jsonify, request, g
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from datetime import datetime, timezone

# Import configuration and utilities
from config.environment import env_manager
from utils.error_handler import ErrorHandler
from utils.logging_config import configure_logging, log_request, get_logger
from utils.monitoring import start_monitoring, stop_monitoring, get_performance_monitor
from services.discovery import service_discovery

# Configure logging first
configure_logging()
logger = get_logger(__name__)

# Initialize Flask app
def create_app(config_override=None):
    """Application factory pattern"""
    app = Flask(__name__)
    
    # Load configuration from environment manager
    flask_config = env_manager.get_flask_config()
    if config_override:
        flask_config.update(config_override)
    
    app.config.update(flask_config)
    
    logger.info(f"Starting {env_manager.get('SERVICE_NAME')} in {env_manager.env.value} environment")
    
    # Initialize database
    from models import db
    db.init_app(app)
    
    # Initialize error handler
    error_handler = ErrorHandler()
    error_handler.init_app(app)
    
    # Configure CORS
    CORS(app, resources={
        r"/api/*": {
            "origins": [
                "https://telegive-frontend.vercel.app",
                "http://localhost:3000",
                "https://localhost:3000"
            ],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization", "X-Requested-With"],
            "supports_credentials": True
        },
        r"/health/*": {
            "origins": "*",
            "methods": ["GET"]
        },
        r"/webhook/*": {
            "origins": "*",
            "methods": ["POST"]
        }
    })
    
    # Request tracking middleware
    @app.before_request
    def before_request():
        """Set up request tracking"""
        g.request_id = str(uuid.uuid4())
        g.start_time = time.time()
        
        # Log request start
        logger.info("Request started", extra={
            'component': 'http_request',
            'request_id': g.request_id,
            'method': request.method,
            'path': request.path,
            'remote_addr': request.remote_addr,
            'user_agent': request.headers.get('User-Agent')
        })
    
    @app.after_request
    def after_request(response):
        """Log request completion and metrics"""
        if hasattr(g, 'start_time'):
            duration = time.time() - g.start_time
            
            # Log request completion
            log_request(request, response, duration)
            
            # Record performance metrics
            performance_monitor = get_performance_monitor()
            performance_monitor.record_request_metrics(
                method=request.method,
                path=request.path,
                status_code=response.status_code,
                duration=duration
            )
        
        # Add request ID to response headers
        if hasattr(g, 'request_id'):
            response.headers['X-Request-ID'] = g.request_id
        
        return response
    
    # Import and register blueprints
    from routes.webhook import webhook_bp
    from routes.bot_api import bot_api_bp
    from routes.health import health_bp
    from routes.admin import admin_bp
    
    app.register_blueprint(webhook_bp, url_prefix='/webhook')
    app.register_blueprint(bot_api_bp, url_prefix='/api')
    app.register_blueprint(health_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    
    # Set database reference for health routes
    from routes import health
    health.db = db
    
    # Initialize database manager
    from utils.database_manager import init_database_manager
    init_database_manager(db)
    
    # Application startup tasks
    @app.before_first_request
    def startup_tasks():
        """Tasks to run on application startup"""
        logger.info("Performing startup tasks...")
        
        # Validate runtime configuration
        config_issues = env_manager.validate_runtime_config()
        if config_issues:
            logger.warning(f"Configuration issues detected: {config_issues}")
        
        # Start monitoring
        start_monitoring()
        logger.info("Monitoring started")
        
        # Start service discovery monitoring
        if not env_manager.is_development():
            service_discovery.start_monitoring()
            logger.info("Service discovery monitoring started")
        
        # Create database tables if they don't exist
        try:
            db.create_all()
            logger.info("Database tables verified/created")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
    
    # Application shutdown tasks
    @app.teardown_appcontext
    def shutdown_session(exception=None):
        """Clean up database session"""
        db.session.remove()
    
    # Graceful shutdown handler
    def shutdown_handler():
        """Handle graceful shutdown"""
        logger.info("Shutting down application...")
        
        # Stop monitoring
        stop_monitoring()
        
        # Stop service discovery
        service_discovery.stop_monitoring()
        
        logger.info("Application shutdown complete")
    
    # Register shutdown handler
    import atexit
    atexit.register(shutdown_handler)
    
    # Root endpoint
    @app.route('/', methods=['GET'])
    def root():
        """Root endpoint with service information"""
        return jsonify({
            'service': env_manager.get('SERVICE_NAME'),
            'version': '1.0.0',
            'status': 'running',
            'environment': env_manager.env.value,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'request_id': getattr(g, 'request_id', None),
            'endpoints': {
                'health': '/health',
                'api': '/api',
                'webhook': '/webhook',
                'admin': '/admin',
                'metrics': '/health/metrics'
            }
        })
    
    # Service info endpoint
    @app.route('/info', methods=['GET'])
    def service_info():
        """Detailed service information"""
        return jsonify({
            'service': env_manager.get('SERVICE_NAME'),
            'version': '1.0.0',
            'environment': env_manager.env.value,
            'configuration': {
                'service_port': env_manager.get('SERVICE_PORT'),
                'webhook_base_url': env_manager.get('WEBHOOK_BASE_URL'),
                'max_message_length': env_manager.get('MAX_MESSAGE_LENGTH'),
                'bulk_message_batch_size': env_manager.get('BULK_MESSAGE_BATCH_SIZE'),
                'message_retry_attempts': env_manager.get('MESSAGE_RETRY_ATTEMPTS'),
                'rate_limit_per_minute': env_manager.get('RATE_LIMIT_PER_MINUTE')
            },
            'external_services': {
                'configured': list(env_manager.get_all_service_urls().keys()),
                'required': env_manager.get_required_services(),
                'optional': env_manager.get_optional_services()
            },
            'monitoring': {
                'logging_enabled': True,
                'metrics_enabled': True,
                'alerting_enabled': True
            },
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'request_id': getattr(g, 'request_id', None)
        })
    
    return app

# Create the application instance
app = create_app()

if __name__ == '__main__':
    # Get configuration from environment
    port = env_manager.get('SERVICE_PORT')
    debug = env_manager.get('FLASK_DEBUG')
    
    logger.info(f"Starting {env_manager.get('SERVICE_NAME')} on port {port}")
    
    # Run the application
    app.run(
        host='0.0.0.0',  # Listen on all interfaces for deployment
        port=port,
        debug=debug,
        threaded=True
    )

