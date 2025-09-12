"""
Minimal Bot Service Test - 502 Error Diagnosis
Ultra-minimal version to isolate startup issues
"""
import os
import json
from flask import Flask, jsonify
from datetime import datetime, timezone

# Create minimal Flask app
app = Flask(__name__)

# Minimal configuration
app.config['DEBUG'] = False
app.config['TESTING'] = False

@app.route('/')
def home():
    """Minimal home endpoint"""
    return jsonify({
        'status': 'working',
        'service': 'telegive-bot-service-minimal',
        'version': '1.0.2-minimal-test',
        'message': 'Minimal bot service for 502 diagnosis',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'port': os.environ.get('PORT', 'not-set')
    })

@app.route('/health')
def health():
    """Minimal health check"""
    return jsonify({
        'status': 'healthy',
        'service': 'telegive-bot-service-minimal',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'environment': {
            'PORT': os.environ.get('PORT', 'not-set'),
            'DATABASE_URL': 'set' if os.environ.get('DATABASE_URL') else 'not-set',
            'RAILWAY_ENVIRONMENT': os.environ.get('RAILWAY_ENVIRONMENT', 'not-set')
        }
    })

@app.route('/test')
def test():
    """Test endpoint for verification"""
    return jsonify({
        'message': 'Bot Service minimal test is working!',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'environment_check': {
            'PORT': os.environ.get('PORT'),
            'RAILWAY_ENVIRONMENT': os.environ.get('RAILWAY_ENVIRONMENT'),
            'DATABASE_URL_EXISTS': bool(os.environ.get('DATABASE_URL'))
        }
    })

@app.route('/env-check')
def env_check():
    """Environment variables check"""
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
        'environment_variables': env_vars,
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

# Error handler
@app.errorhandler(Exception)
def handle_error(error):
    """Catch any errors and return them as JSON"""
    return jsonify({
        'error': str(error),
        'type': type(error).__name__,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }), 500

# For development testing only
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting minimal bot service on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)

