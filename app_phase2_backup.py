"""
Bot Service Phase 2 - JSON Responses & Basic Structure
Progressive rebuild after 502 error fix
"""
import os
import json
from datetime import datetime, timezone
from flask import Flask, jsonify

# Create Flask app
app = Flask(__name__)

# Basic configuration
app.config['DEBUG'] = False
app.config['TESTING'] = False

@app.route('/')
def home():
    """Main service endpoint with JSON response"""
    return jsonify({
        'service': 'telegive-bot-service',
        'status': 'working',
        'version': '1.0.3-phase2-json',
        'phase': 'Phase 2 - JSON Responses',
        'message': 'Bot Service with proper JSON responses',
        'features': ['basic_endpoints', 'json_responses', 'error_handling'],
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'port': os.environ.get('PORT', 'not-set')
    })

@app.route('/health')
def health():
    """Health check endpoint with detailed JSON response"""
    return jsonify({
        'status': 'healthy',
        'service': 'telegive-bot-service',
        'version': '1.0.3-phase2-json',
        'phase': 'Phase 2 - JSON Responses',
        'environment': {
            'PORT': os.environ.get('PORT', 'not-set'),
            'RAILWAY_ENVIRONMENT': os.environ.get('RAILWAY_ENVIRONMENT', 'not-set'),
            'DATABASE_URL': 'set' if os.environ.get('DATABASE_URL') else 'not-set'
        },
        'checks': {
            'flask_app': 'working',
            'json_responses': 'working',
            'error_handling': 'implemented'
        },
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

@app.route('/test')
def test():
    """Test endpoint for verification"""
    return jsonify({
        'message': 'Bot Service Phase 2 test successful!',
        'phase': 'Phase 2 - JSON Responses',
        'test_results': {
            'json_response': 'working',
            'datetime_handling': 'working',
            'environment_access': 'working'
        },
        'environment': {
            'PORT': os.environ.get('PORT'),
            'RAILWAY_ENVIRONMENT': os.environ.get('RAILWAY_ENVIRONMENT')
        },
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

@app.route('/status')
def status():
    """Service status endpoint"""
    return jsonify({
        'service': 'telegive-bot-service',
        'phase': 'Phase 2 - JSON Responses',
        'status': 'operational',
        'uptime': 'running',
        'features_implemented': [
            'Basic Flask endpoints',
            'JSON responses',
            'Error handling',
            'Environment variable access',
            'Timestamp handling'
        ],
        'next_phase': 'Phase 3 - Database Connection',
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

@app.route('/env-check')
def env_check():
    """Environment variables diagnostic endpoint"""
    env_vars = {}
    
    # Check critical environment variables
    critical_vars = [
        'PORT',
        'DATABASE_URL', 
        'RAILWAY_ENVIRONMENT',
        'AUTH_SERVICE_URL',
        'CHANNEL_SERVICE_URL',
        'PARTICIPANT_SERVICE_URL'
    ]
    
    for var in critical_vars:
        value = os.environ.get(var)
        if value:
            # Don't expose sensitive values, just confirm they exist
            if 'URL' in var or 'DATABASE' in var:
                env_vars[var] = f"set ({len(value)} chars)"
            else:
                env_vars[var] = value
        else:
            env_vars[var] = "NOT SET"
    
    return jsonify({
        'phase': 'Phase 2 - JSON Responses',
        'environment_variables': env_vars,
        'critical_vars_status': {
            'PORT': 'set' if os.environ.get('PORT') else 'not-set',
            'DATABASE_URL': 'set' if os.environ.get('DATABASE_URL') else 'not-set',
            'RAILWAY_ENVIRONMENT': 'set' if os.environ.get('RAILWAY_ENVIRONMENT') else 'not-set'
        },
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

@app.route('/api/info')
def api_info():
    """API information endpoint"""
    return jsonify({
        'api': {
            'name': 'Telegive Bot Service API',
            'version': '1.0.3-phase2-json',
            'phase': 'Phase 2 - JSON Responses'
        },
        'endpoints': {
            'GET /': 'Service information',
            'GET /health': 'Health check',
            'GET /test': 'Test endpoint',
            'GET /status': 'Service status',
            'GET /env-check': 'Environment variables check',
            'GET /api/info': 'API information'
        },
        'features': {
            'json_responses': 'implemented',
            'error_handling': 'implemented',
            'environment_checks': 'implemented',
            'timestamp_handling': 'implemented'
        },
        'next_features': {
            'database_connection': 'phase 3',
            'service_integrations': 'phase 4',
            'background_tasks': 'phase 5'
        },
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

# Error handlers
@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors with JSON response"""
    return jsonify({
        'error': 'Not Found',
        'message': 'The requested endpoint does not exist',
        'phase': 'Phase 2 - JSON Responses',
        'available_endpoints': [
            '/',
            '/health',
            '/test',
            '/status',
            '/env-check',
            '/api/info'
        ],
        'timestamp': datetime.now(timezone.utc).isoformat()
    }), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors with JSON response"""
    return jsonify({
        'error': 'Internal Server Error',
        'message': 'An internal error occurred',
        'phase': 'Phase 2 - JSON Responses',
        'timestamp': datetime.now(timezone.utc).isoformat()
    }), 500

@app.errorhandler(Exception)
def handle_exception(error):
    """Handle all other exceptions with JSON response"""
    return jsonify({
        'error': type(error).__name__,
        'message': str(error),
        'phase': 'Phase 2 - JSON Responses',
        'timestamp': datetime.now(timezone.utc).isoformat()
    }), 500

# For development testing only
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting Bot Service Phase 2 on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)

