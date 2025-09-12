"""
Bot Service Phase 3 - Database Connection
Progressive rebuild with careful database integration
"""
import os
import json
import traceback
from datetime import datetime, timezone
from flask import Flask, jsonify
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

# Initialize database with error handling
db = None
database_error = None

try:
    db = SQLAlchemy(app)
    print("SQLAlchemy initialized successfully")
except Exception as e:
    database_error = str(e)
    print(f"SQLAlchemy initialization error: {e}")

# Simple models for testing
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

# Database helper functions
def test_database_connection():
    """Test database connection safely"""
    if not db:
        return {'status': 'error', 'message': 'Database not initialized', 'error': database_error}
    
    try:
        # Simple connection test
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

# Routes
@app.route('/')
def home():
    """Main service endpoint with database status"""
    db_status = test_database_connection()
    
    # Log this request
    log_to_database('INFO', 'Home endpoint accessed', '/')
    
    return jsonify({
        'service': 'telegive-bot-service',
        'status': 'working',
        'version': '1.0.4-phase3-database',
        'phase': 'Phase 3 - Database Connection',
        'message': 'Bot Service with database integration',
        'features': ['basic_endpoints', 'json_responses', 'error_handling', 'database_connection'],
        'database': {
            'configured': database_configured,
            'status': db_status['status'],
            'message': db_status['message']
        },
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'port': os.environ.get('PORT', 'not-set')
    })

@app.route('/health')
def health():
    """Health check endpoint with database status"""
    db_status = test_database_connection()
    
    # Count records if database is working
    record_counts = {}
    if db_status['status'] == 'connected':
        try:
            record_counts = {
                'health_checks': HealthCheck.query.count(),
                'service_logs': ServiceLog.query.count()
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
                    'record_counts': record_counts
                })
            )
            db.session.add(health_record)
            db.session.commit()
        except Exception as e:
            print(f"Health record creation error: {e}")
    
    overall_status = 'healthy' if db_status['status'] == 'connected' else 'degraded'
    
    return jsonify({
        'status': overall_status,
        'service': 'telegive-bot-service',
        'version': '1.0.4-phase3-database',
        'phase': 'Phase 3 - Database Connection',
        'database': {
            'configured': database_configured,
            'connection': db_status['status'],
            'message': db_status['message'],
            'records': record_counts
        },
        'environment': {
            'PORT': os.environ.get('PORT', 'not-set'),
            'RAILWAY_ENVIRONMENT': os.environ.get('RAILWAY_ENVIRONMENT', 'not-set'),
            'DATABASE_URL': 'set' if os.environ.get('DATABASE_URL') else 'not-set'
        },
        'checks': {
            'flask_app': 'working',
            'json_responses': 'working',
            'error_handling': 'implemented',
            'database_connection': db_status['status']
        },
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

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
                    message='Database test record',
                    endpoint='/database/test'
                )
                db.session.add(test_log)
                db.session.commit()
                results['insert'] = {'status': 'success', 'message': 'Test record inserted'}
                
                # Test 4: Query test
                try:
                    log_count = ServiceLog.query.count()
                    health_count = HealthCheck.query.count()
                    results['query'] = {
                        'status': 'success',
                        'service_logs': log_count,
                        'health_checks': health_count
                    }
                except Exception as e:
                    results['query'] = {'status': 'error', 'message': str(e)}
                    
            except Exception as e:
                results['insert'] = {'status': 'error', 'message': str(e)}
    
    return jsonify({
        'phase': 'Phase 3 - Database Connection',
        'database_tests': results,
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

@app.route('/database/status')
def database_status():
    """Detailed database status information"""
    db_status = test_database_connection()
    
    status_info = {
        'phase': 'Phase 3 - Database Connection',
        'database_url_configured': bool(os.environ.get('DATABASE_URL')),
        'sqlalchemy_initialized': db is not None,
        'connection_test': db_status,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }
    
    if db_status['status'] == 'connected':
        try:
            # Get table information
            tables_info = {}
            for table_name in ['health_checks', 'service_logs']:
                try:
                    if table_name == 'health_checks':
                        count = HealthCheck.query.count()
                    else:
                        count = ServiceLog.query.count()
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
            'phase': 'Phase 3 - Database Connection',
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

# Previous Phase 2 endpoints
@app.route('/test')
def test():
    """Test endpoint with database integration"""
    db_status = test_database_connection()
    
    return jsonify({
        'message': 'Bot Service Phase 3 test successful!',
        'phase': 'Phase 3 - Database Connection',
        'test_results': {
            'json_response': 'working',
            'datetime_handling': 'working',
            'environment_access': 'working',
            'database_connection': db_status['status']
        },
        'environment': {
            'PORT': os.environ.get('PORT'),
            'RAILWAY_ENVIRONMENT': os.environ.get('RAILWAY_ENVIRONMENT'),
            'DATABASE_URL': 'set' if os.environ.get('DATABASE_URL') else 'not-set'
        },
        'database': db_status,
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

@app.route('/status')
def status():
    """Service status endpoint with database info"""
    db_status = test_database_connection()
    
    return jsonify({
        'service': 'telegive-bot-service',
        'phase': 'Phase 3 - Database Connection',
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
            'Database logging'
        ],
        'database': {
            'status': db_status['status'],
            'models': ['HealthCheck', 'ServiceLog']
        },
        'next_phase': 'Phase 4 - Service Integrations',
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

@app.route('/api/info')
def api_info():
    """API information endpoint with database features"""
    return jsonify({
        'api': {
            'name': 'Telegive Bot Service API',
            'version': '1.0.4-phase3-database',
            'phase': 'Phase 3 - Database Connection'
        },
        'endpoints': {
            'GET /': 'Service information',
            'GET /health': 'Health check with database status',
            'GET /test': 'Test endpoint',
            'GET /status': 'Service status',
            'GET /api/info': 'API information',
            'GET /database/test': 'Database functionality test',
            'GET /database/status': 'Database status information',
            'GET /logs': 'Recent service logs from database'
        },
        'features': {
            'json_responses': 'implemented',
            'error_handling': 'implemented',
            'environment_checks': 'implemented',
            'timestamp_handling': 'implemented',
            'database_connection': 'implemented',
            'database_models': 'implemented',
            'database_logging': 'implemented'
        },
        'database': {
            'models': ['HealthCheck', 'ServiceLog'],
            'features': ['connection_testing', 'table_creation', 'logging', 'querying']
        },
        'next_features': {
            'service_integrations': 'phase 4',
            'background_tasks': 'phase 5',
            'telegram_bot': 'phase 6'
        },
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

# Error handlers with database logging
@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors with JSON response and database logging"""
    log_to_database('WARNING', f'404 error: {error}', 'unknown')
    
    return jsonify({
        'error': 'Not Found',
        'message': 'The requested endpoint does not exist',
        'phase': 'Phase 3 - Database Connection',
        'available_endpoints': [
            '/', '/health', '/test', '/status', '/api/info',
            '/database/test', '/database/status', '/logs'
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
        'phase': 'Phase 3 - Database Connection',
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
        'phase': 'Phase 3 - Database Connection',
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
                    message='Bot Service Phase 3 started successfully',
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
    print(f"Starting Bot Service Phase 3 on port {port}")
    
    # Initialize database for development
    with app.app_context():
        try:
            db.create_all()
            print("Development database initialized")
        except Exception as e:
            print(f"Development database error: {e}")
    
    app.run(host='0.0.0.0', port=port, debug=False)

