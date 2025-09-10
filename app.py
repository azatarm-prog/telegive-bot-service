#!/usr/bin/env python3
"""
Bot Service - Main Flask Application
Handles Telegram bot operations, message handling, and user interactions
"""

import os
from flask import Flask
from flask_cors import CORS
from config.settings import Config
from models import db

def create_app(config_class=Config):
    """Create and configure Flask application"""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Enable CORS for all routes
    CORS(app, origins="*")
    
    # Initialize database
    db.init_app(app)
    
    # Register blueprints
    from routes.webhook import webhook_bp
    from routes.bot_api import bot_api_bp
    from routes.health import health_bp
    
    app.register_blueprint(webhook_bp)
    app.register_blueprint(bot_api_bp, url_prefix='/api/bot')
    app.register_blueprint(health_bp)
    
    # Create tables if they don't exist
    with app.app_context():
        db.create_all()
    
    return app

# Create the Flask app
app = create_app()

@app.before_first_request
def initialize_app():
    """Initialize application on first request"""
    print(f"🤖 Bot Service starting on port {app.config['SERVICE_PORT']}")
    print(f"📊 Database: {app.config['SQLALCHEMY_DATABASE_URI'][:50]}...")
    print(f"🔗 Webhook base URL: {app.config['WEBHOOK_BASE_URL']}")

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return {
        'success': False,
        'error': 'Endpoint not found',
        'error_code': 'NOT_FOUND'
    }, 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    db.session.rollback()
    return {
        'success': False,
        'error': 'Internal server error',
        'error_code': 'INTERNAL_ERROR'
    }, 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', app.config['SERVICE_PORT']))
    app.run(host='0.0.0.0', port=port, debug=False)

