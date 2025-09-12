"""
Bot Service Phase 4 - Service Integrations
Progressive rebuild with external service API calls
"""
import os
import json
import time
import traceback
import requests
from datetime import datetime, timezone
from urllib.parse import urljoin
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy

# Create Flask app
app = Flask(__name__)

# Basic configuration
app.config['DEBUG'] = False
app.config['TESTING'] = False

# Database configuration with careful error handling
try:
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        # Fix postgres:// to postgresql:// for SQLAlchemy compatibility
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        database_configured = True
    else:
        # Fallback for development/testing
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fallback.db'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        database_configured = False
except Exception as e:
    print(f"Database configuration error: {e}")
    database_configured = False

# Service URLs configuration
SERVICE_URLS = {
    'auth': os.environ.get('AUTH_SERVICE_URL', 'https://web-production-ddd7e.up.railway.app'),
    'channel': os.environ.get('CHANNEL_SERVICE_URL', 'https://telegive-channel-service.railway.app'),
    'participant': os.environ.get('PARTICIPANT_SERVICE_URL', 'https://telegive-participant-production.up.railway.app')
}

# Initialize database with error handling
db = None
database_error = None

try:
    db = SQLAlchemy(app)
    print("SQLAlchemy initialized successfully")
except Exception as e:
    database_error = str(e)
    print(f"SQLAlchemy initialization error: {e}")

# Database models (from Phase 3)
class HealthCheck(db.Model):
    __tablename__ = 'health_checks'
    
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    timestamp = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    status = db.Column(db.String(50), nullable=False)
    details = db.Column(db.Text)

class ServiceLog(db.Model):
    __tablename__ = 'service_logs'
    
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    timestamp = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    level = db.Column(db.String(20), nullable=False)
    message = db.Column(db.Text, nullable=False)
    endpoint = db.Column(db.String(100))

# New model for service interactions
class ServiceInteraction(db.Model):
    __tablename__ = 'service_interactions'
    
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    timestamp = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    service_name = db.Column(db.String(100), nullable=False)
    endpoint = db.Column(db.String(500), nullable=False)
    method = db.Column(db.String(10), nullable=False)
    status_code = db.Column(db.Integer)
    response_time = db.Column(db.Float)
    success = db.Column(db.Boolean, nullable=False)
    error_message = db.Column(db.Text)

# Service Client for external API calls
class ServiceClient:
    def __init__(self):
        self.headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Telegive-Bot-Service/1.0.5-phase4'
        }
    
    def call_service(self, service_name, endpoint, method='GET', data=None, timeout=10):
        """Make API call to external service with comprehensive logging"""
        start_time = time.time()
        
        try:
            base_url = SERVICE_URLS.get(service_name)
            if not base_url:
                return {
                    'success': False, 
                    'error': f'Service {service_name} not configured',
                    'service_name': service_name,
                    'endpoint': endpoint
                }
            
            url = urljoin(base_url, endpoint)
            
            # Make the request
            if method.upper() == 'POST':
                response = requests.post(url, headers=self.headers, json=data, timeout=timeout)
            elif method.upper() == 'PUT':
                response = requests.put(url, headers=self.headers, json=data, timeout=timeout)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, headers=self.headers, timeout=timeout)
            else:
                response = requests.get(url, headers=self.headers, timeout=timeout)
            
            response_time = time.time() - start_time
            
            # Log interaction to database
            self._log_interaction(
                service_name=service_name,
                endpoint=endpoint,
                method=method.upper(),
                status_code=response.status_code,
                response_time=response_time,
                success=response.status_code < 400
            )
            
            if response.status_code < 400:
                try:
                    response_data = response.json()
                except:
                    response_data = response.text
                
                return {
                    'success': True,
                    'data': response_data,
                    'status_code': response.status_code,
                    'response_time': response_time,
                    'service_name': service_name,
                    'endpoint': endpoint
                }
            else:
                return {
                    'success': False,
                    'error': f'HTTP {response.status_code}',
                    'status_code': response.status_code,
                    'response_time': response_time,
                    'service_name': service_name,
                    'endpoint': endpoint,
                    'response_text': response.text[:500]  # Limit response text
                }
                
        except requests.exceptions.Timeout:
            response_time = time.time() - start_time
            self._log_interaction(
                service_name=service_name,
                endpoint=endpoint,
                method=method.upper(),
                response_time=response_time,
                success=False,
                error_message='Timeout'
            )
            return {
                'success': False,
                'error': 'Service timeout',
                'response_time': response_time,
                'service_name': service_name,
                'endpoint': endpoint
            }
            
        except requests.exceptions.ConnectionError:
            response_time = time.time() - start_time
            self._log_interaction(
                service_name=service_name,
                endpoint=endpoint,
                method=method.upper(),
                response_time=response_time,
                success=False,
                error_message='Connection Error'
            )
            return {
                'success': False,
                'error': 'Connection error',
                'response_time': response_time,
                'service_name': service_name,
                'endpoint': endpoint
            }
            
        except Exception as e:
            response_time = time.time() - start_time
            self._log_interaction(
                service_name=service_name,
                endpoint=endpoint,
                method=method.upper(),
                response_time=response_time,
                success=False,
                error_message=str(e)
            )
            return {
                'success': False,
                'error': str(e),
                'response_time': response_time,
                'service_name': service_name,
                'endpoint': endpoint
            }
    
    def _log_interaction(self, service_name, endpoint, method, status_code=None, response_time=None, success=False, error_message=None):
        """Log service interaction to database"""
        if not db:
            return
        
        try:
            interaction = ServiceInteraction(
                service_name=service_name,
                endpoint=endpoint,
                method=method,
                status_code=status_code,
                response_time=response_time,
                success=success,
                error_message=error_message
            )
            db.session.add(interaction)
            db.session.commit()
        except Exception as e:
            print(f"Service interaction logging error: {e}")

# Initialize service client
service_client = ServiceClient()

# Database helper functions (from Phase 3)
def test_database_connection():
    """Test database connection safely"""
    if not db:
        return {'status': 'error', 'message': 'Database not initialized', 'error': database_error}
    
    try:
        db.session.execute(db.text('SELECT 1'))
        return {'status': 'connected', 'message': 'Database connection successful'}
    except Exception as e:
        return {'status': 'error', 'message': f'Database connection failed: {str(e)}'}

def create_tables_safely():
    """Create database tables with error handling"""
    if not db:
        return {'status': 'error', 'message': 'Database not initialized'}
    
    try:
        db.create_all()
        return {'status': 'success', 'message': 'Database tables created successfully'}
    except Exception as e:
        return {'status': 'error', 'message': f'Table creation failed: {str(e)}'}

def log_to_database(level, message, endpoint=None):
    """Log message to database safely"""
    if not db:
        return False
    
    try:
        log_entry = ServiceLog(
            level=level,
            message=message,
            endpoint=endpoint
        )
        db.session.add(log_entry)
        db.session.commit()
        return True
    except Exception as e:
        print(f"Database logging error: {e}")
        return False

# Service health checking
def check_all_services():
    """Check health of all external services"""
    service_status = {}
    
    for service_name in SERVICE_URLS.keys():
        try:
            result = service_client.call_service(service_name, '/health', timeout=5)
            service_status[service_name] = {
                'status': 'connected' if result['success'] else 'disconnected',
                'response_time': result.get('response_time', 0),
                'error': result.get('error') if not result['success'] else None
            }
        except Exception as e:
            service_status[service_name] = {
                'status': 'error',
                'error': str(e),
                'response_time': 0
            }
    
    return service_status

# Routes
@app.route('/')
def home():
    """Main service endpoint with database and service status"""
    db_status = test_database_connection()
    service_status = check_all_services()
    
    # Log this request
    log_to_database('INFO', 'Home endpoint accessed', '/')
    
    return jsonify({
        'service': 'telegive-bot-service',
        'status': 'working',
        'version': '1.0.5-phase4-services',
        'phase': 'Phase 4 - Service Integrations',
        'message': 'Bot Service with external service integrations',
        'features': ['basic_endpoints', 'json_responses', 'error_handling', 'database_connection', 'service_integrations'],
        'database': {
            'configured': database_configured,
            'status': db_status['status'],
            'message': db_status['message']
        },
        'services': service_status,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'port': os.environ.get('PORT', 'not-set')
    })

@app.route('/health')
def health():
    """Health check endpoint with database and service status"""
    db_status = test_database_connection()
    service_status = check_all_services()
    
    # Count records if database is working
    record_counts = {}
    if db_status['status'] == 'connected':
        try:
            record_counts = {
                'health_checks': HealthCheck.query.count(),
                'service_logs': ServiceLog.query.count(),
                'service_interactions': ServiceInteraction.query.count()
            }
        except Exception as e:
            record_counts = {'error': str(e)}
    
    # Log health check
    log_to_database('INFO', 'Health check performed', '/health')
    
    # Create health check record
    if db_status['status'] == 'connected':
        try:
            health_record = HealthCheck(
                status='healthy',
                details=json.dumps({
                    'database_status': db_status['status'],
                    'service_status': service_status,
                    'record_counts': record_counts
                })
            )
            db.session.add(health_record)
            db.session.commit()
        except Exception as e:
            print(f"Health record creation error: {e}")
    
    # Determine overall status
    services_healthy = all(s['status'] == 'connected' for s in service_status.values())
    overall_status = 'healthy' if db_status['status'] == 'connected' and services_healthy else 'degraded'
    
    return jsonify({
        'status': overall_status,
        'service': 'telegive-bot-service',
        'version': '1.0.5-phase4-services',
        'phase': 'Phase 4 - Service Integrations',
        'database': {
            'configured': database_configured,
            'connection': db_status['status'],
            'message': db_status['message'],
            'records': record_counts
        },
        'services': service_status,
        'environment': {
            'PORT': os.environ.get('PORT', 'not-set'),
            'RAILWAY_ENVIRONMENT': os.environ.get('RAILWAY_ENVIRONMENT', 'not-set'),
            'DATABASE_URL': 'set' if os.environ.get('DATABASE_URL') else 'not-set'
        },
        'checks': {
            'flask_app': 'working',
            'json_responses': 'working',
            'error_handling': 'implemented',
            'database_connection': db_status['status'],
            'service_integrations': 'connected' if services_healthy else 'degraded'
        },
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

# Service integration endpoints
@app.route('/services/test', methods=['POST'])
def test_service_integration():
    """Test service integration with specific service and endpoint"""
    data = request.get_json()
    
    if not data or 'service' not in data or 'endpoint' not in data:
        return jsonify({
            'error': 'service and endpoint are required',
            'example': {
                'service': 'auth',
                'endpoint': '/health',
                'method': 'GET',
                'data': {}
            },
            'available_services': list(SERVICE_URLS.keys()),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 400
    
    service_name = data['service']
    endpoint = data['endpoint']
    method = data.get('method', 'GET')
    request_data = data.get('data')
    
    if service_name not in SERVICE_URLS:
        return jsonify({
            'error': f'Service {service_name} not available',
            'available_services': list(SERVICE_URLS.keys()),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 400
    
    result = service_client.call_service(service_name, endpoint, method, request_data)
    
    return jsonify({
        'phase': 'Phase 4 - Service Integrations',
        'test_result': result,
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

@app.route('/services/status')
def services_status():
    """Get detailed status of all external services"""
    service_status = check_all_services()
    
    # Get recent interaction statistics
    interaction_stats = {}
    if db and test_database_connection()['status'] == 'connected':
        try:
            for service_name in SERVICE_URLS.keys():
                recent_interactions = ServiceInteraction.query.filter_by(
                    service_name=service_name
                ).order_by(ServiceInteraction.timestamp.desc()).limit(10).all()
                
                if recent_interactions:
                    success_count = sum(1 for i in recent_interactions if i.success)
                    avg_response_time = sum(i.response_time or 0 for i in recent_interactions) / len(recent_interactions)
                    
                    interaction_stats[service_name] = {
                        'recent_interactions': len(recent_interactions),
                        'success_rate': f"{(success_count / len(recent_interactions) * 100):.1f}%",
                        'avg_response_time': f"{avg_response_time:.3f}s"
                    }
                else:
                    interaction_stats[service_name] = {
                        'recent_interactions': 0,
                        'success_rate': 'N/A',
                        'avg_response_time': 'N/A'
                    }
        except Exception as e:
            interaction_stats = {'error': str(e)}
    
    return jsonify({
        'phase': 'Phase 4 - Service Integrations',
        'service_urls': SERVICE_URLS,
        'service_status': service_status,
        'interaction_statistics': interaction_stats,
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

@app.route('/services/interactions')
def service_interactions():
    """Get recent service interactions from database"""
    db_status = test_database_connection()
    
    if db_status['status'] != 'connected':
        return jsonify({
            'error': 'Database not available',
            'database_status': db_status,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 503
    
    try:
        # Get recent interactions
        interactions = ServiceInteraction.query.order_by(
            ServiceInteraction.timestamp.desc()
        ).limit(50).all()
        
        interaction_list = []
        for interaction in interactions:
            interaction_list.append({
                'id': interaction.id,
                'timestamp': interaction.timestamp.isoformat(),
                'service_name': interaction.service_name,
                'endpoint': interaction.endpoint,
                'method': interaction.method,
                'status_code': interaction.status_code,
                'response_time': interaction.response_time,
                'success': interaction.success,
                'error_message': interaction.error_message
            })
        
        return jsonify({
            'phase': 'Phase 4 - Service Integrations',
            'interactions': interaction_list,
            'count': len(interaction_list),
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'error': 'Failed to retrieve service interactions',
            'message': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 500

# Previous phase endpoints (Phase 3 database endpoints)
@app.route('/database/test')
def database_test():
    """Database connection and functionality test"""
    results = {}
    
    # Test 1: Connection
    connection_test = test_database_connection()
    results['connection'] = connection_test
    
    # Test 2: Table creation
    if connection_test['status'] == 'connected':
        table_test = create_tables_safely()
        results['tables'] = table_test
        
        # Test 3: Insert test record
        if table_test['status'] == 'success':
            try:
                test_log = ServiceLog(
                    level='TEST',
                    message='Database test record from Phase 4',
                    endpoint='/database/test'
                )
                db.session.add(test_log)
                db.session.commit()
                results['insert'] = {'status': 'success', 'message': 'Test record inserted'}
                
                # Test 4: Query test
                try:
                    log_count = ServiceLog.query.count()
                    health_count = HealthCheck.query.count()
                    interaction_count = ServiceInteraction.query.count()
                    results['query'] = {
                        'status': 'success',
                        'service_logs': log_count,
                        'health_checks': health_count,
                        'service_interactions': interaction_count
                    }
                except Exception as e:
                    results['query'] = {'status': 'error', 'message': str(e)}
                    
            except Exception as e:
                results['insert'] = {'status': 'error', 'message': str(e)}
    
    return jsonify({
        'phase': 'Phase 4 - Service Integrations',
        'database_tests': results,
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

@app.route('/database/status')
def database_status():
    """Detailed database status information"""
    db_status = test_database_connection()
    
    status_info = {
        'phase': 'Phase 4 - Service Integrations',
        'database_url_configured': bool(os.environ.get('DATABASE_URL')),
        'sqlalchemy_initialized': db is not None,
        'connection_test': db_status,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }
    
    if db_status['status'] == 'connected':
        try:
            # Get table information
            tables_info = {}
            table_models = {
                'health_checks': HealthCheck,
                'service_logs': ServiceLog,
                'service_interactions': ServiceInteraction
            }
            
            for table_name, model in table_models.items():
                try:
                    count = model.query.count()
                    tables_info[table_name] = {'exists': True, 'record_count': count}
                except Exception as e:
                    tables_info[table_name] = {'exists': False, 'error': str(e)}
            
            status_info['tables'] = tables_info
            
        except Exception as e:
            status_info['tables_error'] = str(e)
    
    return jsonify(status_info)

@app.route('/logs')
def get_logs():
    """Get recent service logs from database"""
    db_status = test_database_connection()
    
    if db_status['status'] != 'connected':
        return jsonify({
            'error': 'Database not available',
            'database_status': db_status,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 503
    
    try:
        # Get recent logs
        logs = ServiceLog.query.order_by(ServiceLog.timestamp.desc()).limit(20).all()
        
        log_list = []
        for log in logs:
            log_list.append({
                'id': log.id,
                'timestamp': log.timestamp.isoformat(),
                'level': log.level,
                'message': log.message,
                'endpoint': log.endpoint
            })
        
        return jsonify({
            'phase': 'Phase 4 - Service Integrations',
            'logs': log_list,
            'count': len(log_list),
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'error': 'Failed to retrieve logs',
            'message': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 500

# Previous phase endpoints (Phase 2 endpoints)
@app.route('/test')
def test():
    """Test endpoint with database and service integration"""
    db_status = test_database_connection()
    service_status = check_all_services()
    
    return jsonify({
        'message': 'Bot Service Phase 4 test successful!',
        'phase': 'Phase 4 - Service Integrations',
        'test_results': {
            'json_response': 'working',
            'datetime_handling': 'working',
            'environment_access': 'working',
            'database_connection': db_status['status'],
            'service_integrations': 'working'
        },
        'environment': {
            'PORT': os.environ.get('PORT'),
            'RAILWAY_ENVIRONMENT': os.environ.get('RAILWAY_ENVIRONMENT'),
            'DATABASE_URL': 'set' if os.environ.get('DATABASE_URL') else 'not-set'
        },
        'database': db_status,
        'services': service_status,
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

@app.route('/status')
def status():
    """Service status endpoint with all features"""
    db_status = test_database_connection()
    service_status = check_all_services()
    
    return jsonify({
        'service': 'telegive-bot-service',
        'phase': 'Phase 4 - Service Integrations',
        'status': 'operational',
        'uptime': 'running',
        'features_implemented': [
            'Basic Flask endpoints',
            'JSON responses',
            'Error handling',
            'Environment variable access',
            'Timestamp handling',
            'Database connection',
            'Database models',
            'Database logging',
            'Service integrations',
            'Service health monitoring',
            'Service interaction logging'
        ],
        'database': {
            'status': db_status['status'],
            'models': ['HealthCheck', 'ServiceLog', 'ServiceInteraction']
        },
        'services': {
            'configured': list(SERVICE_URLS.keys()),
            'status': service_status
        },
        'next_phase': 'Phase 5 - Background Tasks',
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

@app.route('/api/info')
def api_info():
    """API information endpoint with all features"""
    return jsonify({
        'api': {
            'name': 'Telegive Bot Service API',
            'version': '1.0.5-phase4-services',
            'phase': 'Phase 4 - Service Integrations'
        },
        'endpoints': {
            'GET /': 'Service information',
            'GET /health': 'Health check with database and service status',
            'GET /test': 'Test endpoint',
            'GET /status': 'Service status',
            'GET /api/info': 'API information',
            'GET /database/test': 'Database functionality test',
            'GET /database/status': 'Database status information',
            'GET /logs': 'Recent service logs from database',
            'POST /services/test': 'Test service integration',
            'GET /services/status': 'External services status',
            'GET /services/interactions': 'Recent service interactions'
        },
        'features': {
            'json_responses': 'implemented',
            'error_handling': 'implemented',
            'environment_checks': 'implemented',
            'timestamp_handling': 'implemented',
            'database_connection': 'implemented',
            'database_models': 'implemented',
            'database_logging': 'implemented',
            'service_integrations': 'implemented',
            'service_health_monitoring': 'implemented',
            'service_interaction_logging': 'implemented'
        },
        'database': {
            'models': ['HealthCheck', 'ServiceLog', 'ServiceInteraction'],
            'features': ['connection_testing', 'table_creation', 'logging', 'querying']
        },
        'services': {
            'configured': SERVICE_URLS,
            'features': ['health_checking', 'api_calls', 'interaction_logging', 'timeout_handling']
        },
        'next_features': {
            'background_tasks': 'phase 5',
            'telegram_bot': 'phase 6',
            'webhook_handling': 'phase 6'
        },
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

# Error handlers with database and service logging
@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors with JSON response and database logging"""
    log_to_database('WARNING', f'404 error: {error}', 'unknown')
    
    return jsonify({
        'error': 'Not Found',
        'message': 'The requested endpoint does not exist',
        'phase': 'Phase 4 - Service Integrations',
        'available_endpoints': [
            '/', '/health', '/test', '/status', '/api/info',
            '/database/test', '/database/status', '/logs',
            '/services/test', '/services/status', '/services/interactions'
        ],
        'timestamp': datetime.now(timezone.utc).isoformat()
    }), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors with JSON response and database logging"""
    log_to_database('ERROR', f'500 error: {error}', 'unknown')
    
    return jsonify({
        'error': 'Internal Server Error',
        'message': 'An internal error occurred',
        'phase': 'Phase 4 - Service Integrations',
        'timestamp': datetime.now(timezone.utc).isoformat()
    }), 500

@app.errorhandler(Exception)
def handle_exception(error):
    """Handle all other exceptions with JSON response and database logging"""
    error_details = {
        'type': type(error).__name__,
        'message': str(error),
        'traceback': traceback.format_exc()
    }
    
    log_to_database('ERROR', f'Exception: {error_details}', 'unknown')
    
    return jsonify({
        'error': type(error).__name__,
        'message': str(error),
        'phase': 'Phase 4 - Service Integrations',
        'timestamp': datetime.now(timezone.utc).isoformat()
    }), 500

# Initialize database on startup (for production)
def init_database():
    """Initialize database safely on startup"""
    if db:
        try:
            with app.app_context():
                db.create_all()
                print("Database tables created successfully")
                
                # Log startup
                startup_log = ServiceLog(
                    level='INFO',
                    message='Bot Service Phase 4 started successfully with service integrations',
                    endpoint='startup'
                )
                db.session.add(startup_log)
                db.session.commit()
                print("Startup logged to database")
                
        except Exception as e:
            print(f"Database initialization error: {e}")

# For production (Gunicorn)
if __name__ != '__main__':
    init_database()

# For development testing only
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting Bot Service Phase 4 on port {port}")
    
    # Initialize database for development
    with app.app_context():
        try:
            db.create_all()
            print("Development database initialized")
        except Exception as e:
            print(f"Development database error: {e}")
    
    app.run(host='0.0.0.0', port=port, debug=False)

