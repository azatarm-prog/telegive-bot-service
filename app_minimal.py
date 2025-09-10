"""
Minimal diagnostic Flask app for Telegive Bot Service
This simplified version helps identify startup issues
"""

import os
import logging
from flask import Flask, jsonify

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_minimal_app():
    """Create minimal Flask application for diagnostics"""
    app = Flask(__name__)
    
    # Basic configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
    
    @app.route('/')
    def index():
        return jsonify({
            'service': 'telegive-bot-service',
            'status': 'running',
            'message': 'Minimal diagnostic version is working'
        })
    
    @app.route('/health')
    def health():
        return jsonify({
            'status': 'healthy',
            'service': 'telegive-bot-service',
            'version': 'minimal-diagnostic',
            'environment': os.getenv('ENVIRONMENT', 'unknown')
        })
    
    @app.route('/env-check')
    def env_check():
        """Check environment variables"""
        env_vars = {
            'SERVICE_NAME': os.getenv('SERVICE_NAME'),
            'SERVICE_PORT': os.getenv('SERVICE_PORT'),
            'DATABASE_URL': 'SET' if os.getenv('DATABASE_URL') else 'NOT_SET',
            'SECRET_KEY': 'SET' if os.getenv('SECRET_KEY') else 'NOT_SET',
            'ENVIRONMENT': os.getenv('ENVIRONMENT'),
            'PORT': os.getenv('PORT')  # Railway sets this automatically
        }
        
        return jsonify({
            'environment_variables': env_vars,
            'python_version': os.sys.version,
            'working_directory': os.getcwd()
        })
    
    logger.info("Minimal Flask app created successfully")
    return app

# Create the app
app = create_minimal_app()

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    logger.info(f"Starting minimal app on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)

