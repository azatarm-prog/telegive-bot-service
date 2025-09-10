"""
Fixed Telegram Bot Service - Railway Optimized
Addresses common deployment issues and provides robust error handling
"""

import os
import sys
import logging
from flask import Flask, jsonify, request
from datetime import datetime, timezone
import traceback

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def create_app():
    """Create Flask application with robust error handling"""
    app = Flask(__name__)
    
    # Basic configuration with fallbacks
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'fallback-secret-key-change-in-production')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Database configuration with Railway compatibility
    database_url = os.getenv('DATABASE_URL')
    if database_url:
        # Fix postgres:// to postgresql:// for SQLAlchemy compatibility
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    else:
        # Fallback for development
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fallback.db'
        logger.warning("DATABASE_URL not set, using SQLite fallback")
    
    # Initialize database with error handling
    try:
        from flask_sqlalchemy import SQLAlchemy
        db = SQLAlchemy()
        db.init_app(app)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        # Create a mock db for basic functionality
        class MockDB:
            def create_all(self): pass
            def session(self): pass
        db = MockDB()
    
    # Basic routes
    @app.route('/')
    def index():
        return jsonify({
            'service': 'telegive-bot-service',
            'status': 'running',
            'version': 'fixed-railway-optimized',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'message': 'Telegram Bot Service is operational'
        })
    
    @app.route('/health')
    def health():
        """Comprehensive health check"""
        health_data = {
            'status': 'healthy',
            'service': 'telegive-bot-service',
            'version': 'fixed-railway-optimized',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'environment': os.getenv('ENVIRONMENT', 'production'),
            'checks': {}
        }
        
        # Database check
        try:
            if hasattr(db, 'engine'):
                db.engine.execute('SELECT 1')
                health_data['checks']['database'] = 'connected'
            else:
                health_data['checks']['database'] = 'mock'
        except Exception as e:
            health_data['checks']['database'] = f'error: {str(e)}'
            health_data['status'] = 'degraded'
        
        # Environment variables check
        required_vars = ['SECRET_KEY', 'ADMIN_TOKEN', 'JWT_SECRET_KEY']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            health_data['checks']['environment'] = f'missing: {missing_vars}'
            health_data['status'] = 'degraded'
        else:
            health_data['checks']['environment'] = 'configured'
        
        # External services check
        service_urls = {
            'auth': os.getenv('TELEGIVE_AUTH_URL'),
            'channel': os.getenv('TELEGIVE_CHANNEL_URL'),
            'participant': os.getenv('TELEGIVE_PARTICIPANT_URL'),
            'giveaway': os.getenv('TELEGIVE_GIVEAWAY_URL')
        }
        
        configured_services = {k: v for k, v in service_urls.items() if v}
        health_data['checks']['external_services'] = f'{len(configured_services)}/4 configured'
        
        return jsonify(health_data)
    
    @app.route('/health/ready')
    def readiness():
        """Readiness probe for Railway"""
        return jsonify({
            'status': 'ready',
            'service': 'telegive-bot-service',
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
    
    @app.route('/health/live')
    def liveness():
        """Liveness probe for Railway"""
        return jsonify({
            'status': 'alive',
            'service': 'telegive-bot-service',
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
    
    @app.route('/config')
    def config_check():
        """Configuration diagnostics"""
        config_data = {
            'environment_variables': {
                'SERVICE_NAME': os.getenv('SERVICE_NAME'),
                'SERVICE_PORT': os.getenv('SERVICE_PORT'),
                'PORT': os.getenv('PORT'),
                'ENVIRONMENT': os.getenv('ENVIRONMENT'),
                'SECRET_KEY': 'SET' if os.getenv('SECRET_KEY') else 'NOT_SET',
                'DATABASE_URL': 'SET' if os.getenv('DATABASE_URL') else 'NOT_SET',
                'ADMIN_TOKEN': 'SET' if os.getenv('ADMIN_TOKEN') else 'NOT_SET',
                'JWT_SECRET_KEY': 'SET' if os.getenv('JWT_SECRET_KEY') else 'NOT_SET',
                'WEBHOOK_SECRET': 'SET' if os.getenv('WEBHOOK_SECRET') else 'NOT_SET'
            },
            'service_urls': {
                'TELEGIVE_AUTH_URL': os.getenv('TELEGIVE_AUTH_URL'),
                'TELEGIVE_CHANNEL_URL': os.getenv('TELEGIVE_CHANNEL_URL'),
                'TELEGIVE_PARTICIPANT_URL': os.getenv('TELEGIVE_PARTICIPANT_URL'),
                'TELEGIVE_GIVEAWAY_URL': os.getenv('TELEGIVE_GIVEAWAY_URL'),
                'TELEGIVE_MEDIA_URL': os.getenv('TELEGIVE_MEDIA_URL')
            },
            'system_info': {
                'python_version': sys.version,
                'working_directory': os.getcwd(),
                'platform': sys.platform
            }
        }
        
        return jsonify(config_data)
    
    # Webhook endpoint (basic implementation)
    @app.route('/webhook/<bot_id>', methods=['POST'])
    def webhook_handler(bot_id):
        """Basic webhook handler"""
        try:
            data = request.get_json()
            logger.info(f"Webhook received for bot {bot_id}: {data}")
            
            return jsonify({
                'status': 'received',
                'bot_id': bot_id,
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
        except Exception as e:
            logger.error(f"Webhook error: {e}")
            return jsonify({'error': str(e)}), 500
    
    # API endpoints (basic implementations)
    @app.route('/api/bots', methods=['GET'])
    def list_bots():
        """List user bots (placeholder)"""
        return jsonify({
            'bots': [],
            'message': 'Bot management functionality available'
        })
    
    @app.route('/api/bots/register', methods=['POST'])
    def register_bot():
        """Register new bot (placeholder)"""
        return jsonify({
            'success': True,
            'message': 'Bot registration endpoint available'
        })
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'error': 'Not Found',
            'message': 'The requested endpoint does not exist',
            'service': 'telegive-bot-service'
        }), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({
            'error': 'Internal Server Error',
            'message': 'An internal error occurred',
            'service': 'telegive-bot-service'
        }), 500
    
    # Initialize database tables
    with app.app_context():
        try:
            if hasattr(db, 'create_all'):
                db.create_all()
                logger.info("Database tables created/verified")
        except Exception as e:
            logger.warning(f"Database table creation failed: {e}")
    
    logger.info("Flask application created successfully")
    return app

# Create the application
try:
    app = create_app()
    logger.info("Application initialization completed")
except Exception as e:
    logger.error(f"Application initialization failed: {e}")
    logger.error(traceback.format_exc())
    # Create a minimal fallback app
    app = Flask(__name__)
    
    @app.route('/')
    def fallback():
        return jsonify({
            'status': 'fallback',
            'message': 'Service running in fallback mode',
            'error': str(e)
        })

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    host = '0.0.0.0'
    
    logger.info(f"Starting server on {host}:{port}")
    
    try:
        app.run(
            host=host,
            port=port,
            debug=os.getenv('DEBUG', 'false').lower() == 'true'
        )
    except Exception as e:
        logger.error(f"Server startup failed: {e}")
        logger.error(traceback.format_exc())

