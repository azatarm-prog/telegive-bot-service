"""
Progressive diagnostic Flask app for Telegive Bot Service
Gradually adds complexity to identify the exact failure point
"""

import os
import sys
import logging
from flask import Flask, jsonify, request
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_progressive_app():
    """Create progressive Flask application for step-by-step diagnostics"""
    app = Flask(__name__)
    
    # Basic configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
    
    @app.route('/')
    def index():
        return jsonify({
            'service': 'telegive-bot-service',
            'status': 'running',
            'version': 'progressive-diagnostic',
            'timestamp': datetime.utcnow().isoformat(),
            'message': 'Progressive diagnostic version is working'
        })
    
    @app.route('/health')
    def health():
        return jsonify({
            'status': 'healthy',
            'service': 'telegive-bot-service',
            'version': 'progressive-diagnostic',
            'environment': os.getenv('ENVIRONMENT', 'production'),
            'timestamp': datetime.utcnow().isoformat()
        })
    
    @app.route('/step1/basic')
    def step1_basic():
        """Step 1: Basic Flask functionality"""
        try:
            return jsonify({
                'step': 1,
                'test': 'basic_flask',
                'status': 'success',
                'message': 'Basic Flask app is working'
            })
        except Exception as e:
            return jsonify({
                'step': 1,
                'test': 'basic_flask',
                'status': 'error',
                'error': str(e)
            }), 500
    
    @app.route('/step2/environment')
    def step2_environment():
        """Step 2: Environment variables check"""
        try:
            env_vars = {
                'SERVICE_NAME': os.getenv('SERVICE_NAME'),
                'SERVICE_PORT': os.getenv('SERVICE_PORT'),
                'SECRET_KEY': 'SET' if os.getenv('SECRET_KEY') else 'NOT_SET',
                'DATABASE_URL': 'SET' if os.getenv('DATABASE_URL') else 'NOT_SET',
                'ADMIN_TOKEN': 'SET' if os.getenv('ADMIN_TOKEN') else 'NOT_SET',
                'JWT_SECRET_KEY': 'SET' if os.getenv('JWT_SECRET_KEY') else 'NOT_SET',
                'WEBHOOK_SECRET': 'SET' if os.getenv('WEBHOOK_SECRET') else 'NOT_SET',
                'TELEGIVE_AUTH_URL': os.getenv('TELEGIVE_AUTH_URL'),
                'TELEGIVE_CHANNEL_URL': os.getenv('TELEGIVE_CHANNEL_URL'),
                'TELEGIVE_PARTICIPANT_URL': os.getenv('TELEGIVE_PARTICIPANT_URL'),
                'TELEGIVE_GIVEAWAY_URL': os.getenv('TELEGIVE_GIVEAWAY_URL'),
                'PORT': os.getenv('PORT'),
                'ENVIRONMENT': os.getenv('ENVIRONMENT')
            }
            
            missing_vars = [k for k, v in env_vars.items() if v is None or v == 'NOT_SET']
            
            return jsonify({
                'step': 2,
                'test': 'environment_variables',
                'status': 'success' if not missing_vars else 'warning',
                'environment_variables': env_vars,
                'missing_variables': missing_vars,
                'python_version': sys.version,
                'working_directory': os.getcwd()
            })
        except Exception as e:
            return jsonify({
                'step': 2,
                'test': 'environment_variables',
                'status': 'error',
                'error': str(e)
            }), 500
    
    @app.route('/step3/imports')
    def step3_imports():
        """Step 3: Test critical imports"""
        import_results = {}
        
        # Test basic imports
        try:
            import flask
            import_results['flask'] = {'status': 'success', 'version': flask.__version__}
        except Exception as e:
            import_results['flask'] = {'status': 'error', 'error': str(e)}
        
        try:
            import sqlalchemy
            import_results['sqlalchemy'] = {'status': 'success', 'version': sqlalchemy.__version__}
        except Exception as e:
            import_results['sqlalchemy'] = {'status': 'error', 'error': str(e)}
        
        try:
            import psycopg2
            import_results['psycopg2'] = {'status': 'success', 'version': psycopg2.__version__}
        except Exception as e:
            import_results['psycopg2'] = {'status': 'error', 'error': str(e)}
        
        try:
            import requests
            import_results['requests'] = {'status': 'success', 'version': requests.__version__}
        except Exception as e:
            import_results['requests'] = {'status': 'error', 'error': str(e)}
        
        # Test application imports
        try:
            from config.settings import Config
            import_results['config.settings'] = {'status': 'success'}
        except Exception as e:
            import_results['config.settings'] = {'status': 'error', 'error': str(e)}
        
        try:
            from models import db
            import_results['models'] = {'status': 'success'}
        except Exception as e:
            import_results['models'] = {'status': 'error', 'error': str(e)}
        
        errors = [k for k, v in import_results.items() if v['status'] == 'error']
        
        return jsonify({
            'step': 3,
            'test': 'imports',
            'status': 'success' if not errors else 'error',
            'import_results': import_results,
            'failed_imports': errors
        })
    
    @app.route('/step4/database')
    def step4_database():
        """Step 4: Test database connection"""
        try:
            database_url = os.getenv('DATABASE_URL')
            if not database_url:
                return jsonify({
                    'step': 4,
                    'test': 'database_connection',
                    'status': 'error',
                    'error': 'DATABASE_URL not set'
                }), 500
            
            # Test basic database connection
            import psycopg2
            from urllib.parse import urlparse
            
            parsed = urlparse(database_url)
            
            conn = psycopg2.connect(
                host=parsed.hostname,
                port=parsed.port,
                user=parsed.username,
                password=parsed.password,
                database=parsed.path[1:]  # Remove leading slash
            )
            
            cursor = conn.cursor()
            cursor.execute('SELECT version();')
            db_version = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            
            return jsonify({
                'step': 4,
                'test': 'database_connection',
                'status': 'success',
                'database_version': db_version,
                'connection_info': {
                    'host': parsed.hostname,
                    'port': parsed.port,
                    'database': parsed.path[1:],
                    'user': parsed.username
                }
            })
            
        except Exception as e:
            return jsonify({
                'step': 4,
                'test': 'database_connection',
                'status': 'error',
                'error': str(e)
            }), 500
    
    @app.route('/step5/services')
    def step5_services():
        """Step 5: Test external service connectivity"""
        import requests
        
        services = {
            'auth': os.getenv('TELEGIVE_AUTH_URL'),
            'channel': os.getenv('TELEGIVE_CHANNEL_URL'),
            'participant': os.getenv('TELEGIVE_PARTICIPANT_URL'),
            'giveaway': os.getenv('TELEGIVE_GIVEAWAY_URL')
        }
        
        service_results = {}
        
        for service_name, service_url in services.items():
            if not service_url:
                service_results[service_name] = {
                    'status': 'error',
                    'error': 'URL not configured'
                }
                continue
            
            try:
                # Test basic connectivity (with timeout)
                response = requests.get(f"{service_url}/health", timeout=5)
                service_results[service_name] = {
                    'status': 'success',
                    'url': service_url,
                    'response_code': response.status_code,
                    'response_time': response.elapsed.total_seconds()
                }
            except requests.exceptions.Timeout:
                service_results[service_name] = {
                    'status': 'timeout',
                    'url': service_url,
                    'error': 'Request timeout (5s)'
                }
            except Exception as e:
                service_results[service_name] = {
                    'status': 'error',
                    'url': service_url,
                    'error': str(e)
                }
        
        errors = [k for k, v in service_results.items() if v['status'] == 'error']
        
        return jsonify({
            'step': 5,
            'test': 'external_services',
            'status': 'success' if not errors else 'warning',
            'service_results': service_results,
            'failed_services': errors
        })
    
    @app.route('/diagnostic/full')
    def full_diagnostic():
        """Run all diagnostic steps"""
        try:
            # Import the step functions and run them
            from urllib.parse import urljoin
            import requests
            
            base_url = request.url_root
            steps = []
            
            for step in ['step1/basic', 'step2/environment', 'step3/imports', 'step4/database', 'step5/services']:
                try:
                    url = urljoin(base_url, step)
                    response = requests.get(url, timeout=10)
                    steps.append(response.json())
                except Exception as e:
                    steps.append({
                        'step': step,
                        'status': 'error',
                        'error': f'Failed to run step: {str(e)}'
                    })
            
            overall_status = 'success'
            if any(step.get('status') == 'error' for step in steps):
                overall_status = 'error'
            elif any(step.get('status') == 'warning' for step in steps):
                overall_status = 'warning'
            
            return jsonify({
                'diagnostic': 'full',
                'overall_status': overall_status,
                'timestamp': datetime.utcnow().isoformat(),
                'steps': steps
            })
            
        except Exception as e:
            return jsonify({
                'diagnostic': 'full',
                'overall_status': 'error',
                'error': str(e)
            }), 500
    
    logger.info("Progressive Flask app created successfully")
    return app

# Create the app
app = create_progressive_app()

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    logger.info(f"Starting progressive diagnostic app on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)

