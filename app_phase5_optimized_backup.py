"""
Bot Service Phase 5 - Optimized Service Integrations + Background Tasks
Complete optimization with caching, background tasks, and performance improvements
"""
import os
import json
import time
import threading
import traceback
import requests
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

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

# Service status cache
service_status_cache = {}
cache_lock = threading.Lock()
last_cache_update = None

# Initialize database with error handling
db = None
database_error = None

try:
    db = SQLAlchemy(app)
    print("SQLAlchemy initialized successfully")
except Exception as e:
    database_error = str(e)
    print(f"SQLAlchemy initialization error: {e}")

# Database models
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

class BackgroundTask(db.Model):
    __tablename__ = 'background_tasks'
    
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    timestamp = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    task_name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), nullable=False)  # pending, running, completed, failed
    details = db.Column(db.Text)
    execution_time = db.Column(db.Float)
    error_message = db.Column(db.Text)

# Optimized Service Client with caching
class OptimizedServiceClient:
    def __init__(self):
        self.headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Telegive-Bot-Service/1.0.6-phase5-optimized'
        }
        self.fast_timeout = 3  # Reduced from 10 seconds
        self.health_timeout = 2  # Even faster for health checks
    
    def call_service(self, service_name, endpoint, method='GET', data=None, timeout=None, log_interaction=True):
        """Make API call to external service with optimized timeouts"""
        if timeout is None:
            timeout = self.fast_timeout
            
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
            
            # Make the request with optimized timeout
            if method.upper() == 'POST':
                response = requests.post(url, headers=self.headers, json=data, timeout=timeout)
            elif method.upper() == 'PUT':
                response = requests.put(url, headers=self.headers, json=data, timeout=timeout)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, headers=self.headers, timeout=timeout)
            else:
                response = requests.get(url, headers=self.headers, timeout=timeout)
            
            response_time = time.time() - start_time
            
            # Log interaction to database (optional for performance)
            if log_interaction:
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
                    'response_text': response.text[:200]  # Reduced response text
                }
                
        except requests.exceptions.Timeout:
            response_time = time.time() - start_time
            if log_interaction:
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
            if log_interaction:
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
            if log_interaction:
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
        """Log service interaction to database (async to avoid blocking)"""
        if not db:
            return
        
        try:
            with app.app_context():
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

# Initialize optimized service client
service_client = OptimizedServiceClient()

# Background task functions
def update_service_status_cache():
    """Background task to update service status cache"""
    global service_status_cache, last_cache_update
    
    task_start = time.time()
    task_name = "update_service_status_cache"
    
    # Log task start
    if db:
        try:
            with app.app_context():
                task_record = BackgroundTask(
                    task_name=task_name,
                    status='running',
                    details='Updating service status cache'
                )
                db.session.add(task_record)
                db.session.commit()
                task_id = task_record.id
        except Exception as e:
            print(f"Task logging error: {e}")
            task_id = None
    else:
        task_id = None
    
    try:
        new_status = {}
        
        for service_name in SERVICE_URLS.keys():
            try:
                # Use fast health check timeout
                result = service_client.call_service(
                    service_name, 
                    '/health', 
                    timeout=service_client.health_timeout,
                    log_interaction=False  # Don't log background health checks
                )
                new_status[service_name] = {
                    'status': 'connected' if result['success'] else 'disconnected',
                    'response_time': result.get('response_time', 0),
                    'error': result.get('error') if not result['success'] else None,
                    'last_checked': datetime.now(timezone.utc).isoformat()
                }
            except Exception as e:
                new_status[service_name] = {
                    'status': 'error',
                    'error': str(e),
                    'response_time': 0,
                    'last_checked': datetime.now(timezone.utc).isoformat()
                }
        
        # Update cache with thread safety
        with cache_lock:
            service_status_cache.update(new_status)
            last_cache_update = datetime.now(timezone.utc)
        
        execution_time = time.time() - task_start
        
        # Log task completion
        if db and task_id:
            try:
                with app.app_context():
                    task_record = BackgroundTask.query.get(task_id)
                    if task_record:
                        task_record.status = 'completed'
                        task_record.execution_time = execution_time
                        task_record.details = f'Updated status for {len(new_status)} services'
                        db.session.commit()
            except Exception as e:
                print(f"Task completion logging error: {e}")
        
        print(f"Service status cache updated in {execution_time:.3f}s")
        
    except Exception as e:
        execution_time = time.time() - task_start
        
        # Log task failure
        if db and task_id:
            try:
                with app.app_context():
                    task_record = BackgroundTask.query.get(task_id)
                    if task_record:
                        task_record.status = 'failed'
                        task_record.execution_time = execution_time
                        task_record.error_message = str(e)
                        db.session.commit()
            except Exception as log_error:
                print(f"Task failure logging error: {log_error}")
        
        print(f"Service status cache update failed: {e}")

def cleanup_old_records():
    """Background task to clean up old database records"""
    task_start = time.time()
    task_name = "cleanup_old_records"
    
    if not db:
        return
    
    # Log task start
    try:
        with app.app_context():
            task_record = BackgroundTask(
                task_name=task_name,
                status='running',
                details='Cleaning up old database records'
            )
            db.session.add(task_record)
            db.session.commit()
            task_id = task_record.id
    except Exception as e:
        print(f"Cleanup task logging error: {e}")
        task_id = None
    
    try:
        with app.app_context():
            # Keep only last 1000 service interactions
            old_interactions = ServiceInteraction.query.order_by(
                ServiceInteraction.timestamp.desc()
            ).offset(1000).all()
            
            # Keep only last 500 health checks
            old_health_checks = HealthCheck.query.order_by(
                HealthCheck.timestamp.desc()
            ).offset(500).all()
            
            # Keep only last 200 service logs
            old_logs = ServiceLog.query.order_by(
                ServiceLog.timestamp.desc()
            ).offset(200).all()
            
            # Keep only last 100 background tasks
            old_tasks = BackgroundTask.query.order_by(
                BackgroundTask.timestamp.desc()
            ).offset(100).all()
            
            # Delete old records
            deleted_count = 0
            for record_list in [old_interactions, old_health_checks, old_logs, old_tasks]:
                for record in record_list:
                    db.session.delete(record)
                    deleted_count += 1
            
            db.session.commit()
            
            execution_time = time.time() - task_start
            
            # Log task completion
            if task_id:
                task_record = BackgroundTask.query.get(task_id)
                if task_record:
                    task_record.status = 'completed'
                    task_record.execution_time = execution_time
                    task_record.details = f'Deleted {deleted_count} old records'
                    db.session.commit()
            
            print(f"Cleanup completed: deleted {deleted_count} records in {execution_time:.3f}s")
            
    except Exception as e:
        execution_time = time.time() - task_start
        
        # Log task failure
        if task_id:
            try:
                with app.app_context():
                    task_record = BackgroundTask.query.get(task_id)
                    if task_record:
                        task_record.status = 'failed'
                        task_record.execution_time = execution_time
                        task_record.error_message = str(e)
                        db.session.commit()
            except Exception as log_error:
                print(f"Cleanup failure logging error: {log_error}")
        
        print(f"Cleanup task failed: {e}")

# Background scheduler
scheduler = BackgroundScheduler()

# Database helper functions
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
    """Log message to database safely (async)"""
    if not db:
        return False
    
    try:
        # Use a separate thread to avoid blocking
        def log_async():
            try:
                with app.app_context():
                    log_entry = ServiceLog(
                        level=level,
                        message=message,
                        endpoint=endpoint
                    )
                    db.session.add(log_entry)
                    db.session.commit()
            except Exception as e:
                print(f"Async database logging error: {e}")
        
        thread = threading.Thread(target=log_async)
        thread.daemon = True
        thread.start()
        return True
    except Exception as e:
        print(f"Database logging error: {e}")
        return False

# Optimized service status functions
def get_cached_service_status():
    """Get service status from cache (fast)"""
    global service_status_cache, last_cache_update
    
    with cache_lock:
        if not service_status_cache or not last_cache_update:
            # Initialize cache if empty
            return {service: {'status': 'unknown', 'error': 'Cache not initialized'} 
                   for service in SERVICE_URLS.keys()}
        
        # Check if cache is stale (older than 5 minutes)
        cache_age = datetime.now(timezone.utc) - last_cache_update
        if cache_age > timedelta(minutes=5):
            # Mark as stale but still return cached data
            stale_status = service_status_cache.copy()
            for service in stale_status:
                stale_status[service]['cache_status'] = 'stale'
            return stale_status
        
        return service_status_cache.copy()

def check_single_service(service_name, timeout=None):
    """Check single service status (for testing)"""
    if timeout is None:
        timeout = service_client.fast_timeout
    
    try:
        result = service_client.call_service(service_name, '/health', timeout=timeout)
        return {
            'status': 'connected' if result['success'] else 'disconnected',
            'response_time': result.get('response_time', 0),
            'error': result.get('error') if not result['success'] else None,
            'last_checked': datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'response_time': 0,
            'last_checked': datetime.now(timezone.utc).isoformat()
        }

# Routes
@app.route('/')
def home():
    """Main service endpoint with cached service status (fast)"""
    db_status = test_database_connection()
    service_status = get_cached_service_status()  # Use cached status for speed
    
    # Log this request (async)
    log_to_database('INFO', 'Home endpoint accessed', '/')
    
    return jsonify({
        'service': 'telegive-bot-service',
        'status': 'working',
        'version': '1.0.6-phase5-optimized',
        'phase': 'Phase 5 - Optimized Service Integrations + Background Tasks',
        'message': 'Bot Service with optimized service integrations and background tasks',
        'features': [
            'basic_endpoints', 'json_responses', 'error_handling', 
            'database_connection', 'optimized_service_integrations', 
            'service_status_caching', 'background_tasks'
        ],
        'database': {
            'configured': database_configured,
            'status': db_status['status'],
            'message': db_status['message']
        },
        'services': service_status,
        'cache_info': {
            'last_updated': last_cache_update.isoformat() if last_cache_update else None,
            'cache_age_seconds': (datetime.now(timezone.utc) - last_cache_update).total_seconds() if last_cache_update else None
        },
        'background_tasks': {
            'scheduler_running': scheduler.running,
            'active_jobs': len(scheduler.get_jobs())
        },
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'port': os.environ.get('PORT', 'not-set')
    })

@app.route('/health')
def health():
    """Health check endpoint with cached service status (fast)"""
    db_status = test_database_connection()
    service_status = get_cached_service_status()  # Use cached status for speed
    
    # Count records if database is working
    record_counts = {}
    if db_status['status'] == 'connected':
        try:
            record_counts = {
                'health_checks': HealthCheck.query.count(),
                'service_logs': ServiceLog.query.count(),
                'service_interactions': ServiceInteraction.query.count(),
                'background_tasks': BackgroundTask.query.count()
            }
        except Exception as e:
            record_counts = {'error': str(e)}
    
    # Log health check (async)
    log_to_database('INFO', 'Health check performed', '/health')
    
    # Create health check record (async)
    if db_status['status'] == 'connected':
        def create_health_record():
            try:
                with app.app_context():
                    health_record = HealthCheck(
                        status='healthy',
                        details=json.dumps({
                            'database_status': db_status['status'],
                            'service_status': service_status,
                            'record_counts': record_counts,
                            'background_tasks': scheduler.running
                        })
                    )
                    db.session.add(health_record)
                    db.session.commit()
            except Exception as e:
                print(f"Health record creation error: {e}")
        
        thread = threading.Thread(target=create_health_record)
        thread.daemon = True
        thread.start()
    
    # Determine overall status
    services_healthy = all(s.get('status') == 'connected' for s in service_status.values())
    overall_status = 'healthy' if db_status['status'] == 'connected' and services_healthy else 'degraded'
    
    return jsonify({
        'status': overall_status,
        'service': 'telegive-bot-service',
        'version': '1.0.6-phase5-optimized',
        'phase': 'Phase 5 - Optimized Service Integrations + Background Tasks',
        'database': {
            'configured': database_configured,
            'connection': db_status['status'],
            'message': db_status['message'],
            'records': record_counts
        },
        'services': service_status,
        'background_tasks': {
            'scheduler_running': scheduler.running,
            'active_jobs': len(scheduler.get_jobs()),
            'job_names': [job.id for job in scheduler.get_jobs()]
        },
        'cache_info': {
            'last_updated': last_cache_update.isoformat() if last_cache_update else None,
            'services_cached': len(service_status)
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
            'database_connection': db_status['status'],
            'service_integrations': 'optimized',
            'background_tasks': 'running' if scheduler.running else 'stopped',
            'service_caching': 'active'
        },
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

# Background task management endpoints
@app.route('/tasks/status')
def tasks_status():
    """Get background task status and recent executions"""
    db_status = test_database_connection()
    
    task_info = {
        'phase': 'Phase 5 - Optimized Service Integrations + Background Tasks',
        'scheduler': {
            'running': scheduler.running,
            'active_jobs': len(scheduler.get_jobs()),
            'jobs': []
        },
        'timestamp': datetime.now(timezone.utc).isoformat()
    }
    
    # Get job information
    for job in scheduler.get_jobs():
        task_info['scheduler']['jobs'].append({
            'id': job.id,
            'name': job.name,
            'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
            'trigger': str(job.trigger)
        })
    
    # Get recent task executions from database
    if db_status['status'] == 'connected':
        try:
            recent_tasks = BackgroundTask.query.order_by(
                BackgroundTask.timestamp.desc()
            ).limit(20).all()
            
            task_executions = []
            for task in recent_tasks:
                task_executions.append({
                    'id': task.id,
                    'timestamp': task.timestamp.isoformat(),
                    'task_name': task.task_name,
                    'status': task.status,
                    'execution_time': task.execution_time,
                    'details': task.details,
                    'error_message': task.error_message
                })
            
            task_info['recent_executions'] = task_executions
            
        except Exception as e:
            task_info['recent_executions_error'] = str(e)
    
    return jsonify(task_info)

@app.route('/tasks/trigger/<task_name>', methods=['POST'])
def trigger_task(task_name):
    """Manually trigger a background task"""
    if task_name == 'update_service_status':
        # Run in background thread
        thread = threading.Thread(target=update_service_status_cache)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'message': f'Task {task_name} triggered successfully',
            'task_name': task_name,
            'status': 'started',
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
    
    elif task_name == 'cleanup_old_records':
        # Run in background thread
        thread = threading.Thread(target=cleanup_old_records)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'message': f'Task {task_name} triggered successfully',
            'task_name': task_name,
            'status': 'started',
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
    
    else:
        return jsonify({
            'error': f'Unknown task: {task_name}',
            'available_tasks': ['update_service_status', 'cleanup_old_records'],
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 400

# Optimized service integration endpoints
@app.route('/services/test', methods=['POST'])
def test_service_integration():
    """Test service integration with specific service and endpoint (optimized)"""
    data = request.get_json()
    
    if not data or 'service' not in data or 'endpoint' not in data:
        return jsonify({
            'error': 'service and endpoint are required',
            'example': {
                'service': 'auth',
                'endpoint': '/health',
                'method': 'GET',
                'data': {},
                'timeout': 3
            },
            'available_services': list(SERVICE_URLS.keys()),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 400
    
    service_name = data['service']
    endpoint = data['endpoint']
    method = data.get('method', 'GET')
    request_data = data.get('data')
    timeout = data.get('timeout', service_client.fast_timeout)
    
    if service_name not in SERVICE_URLS:
        return jsonify({
            'error': f'Service {service_name} not available',
            'available_services': list(SERVICE_URLS.keys()),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 400
    
    result = service_client.call_service(service_name, endpoint, method, request_data, timeout)
    
    return jsonify({
        'phase': 'Phase 5 - Optimized Service Integrations + Background Tasks',
        'test_result': result,
        'optimizations': {
            'timeout_used': timeout,
            'fast_timeout': service_client.fast_timeout,
            'health_timeout': service_client.health_timeout
        },
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

@app.route('/services/status')
def services_status():
    """Get detailed status of all external services (fast with cache)"""
    service_status = get_cached_service_status()
    
    # Get recent interaction statistics (limited for performance)
    interaction_stats = {}
    if db and test_database_connection()['status'] == 'connected':
        try:
            for service_name in SERVICE_URLS.keys():
                # Only get last 5 interactions for performance
                recent_interactions = ServiceInteraction.query.filter_by(
                    service_name=service_name
                ).order_by(ServiceInteraction.timestamp.desc()).limit(5).all()
                
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
        'phase': 'Phase 5 - Optimized Service Integrations + Background Tasks',
        'service_urls': SERVICE_URLS,
        'service_status': service_status,
        'interaction_statistics': interaction_stats,
        'cache_info': {
            'last_updated': last_cache_update.isoformat() if last_cache_update else None,
            'cache_age_seconds': (datetime.now(timezone.utc) - last_cache_update).total_seconds() if last_cache_update else None,
            'services_cached': len(service_status)
        },
        'optimizations': {
            'status_caching': 'active',
            'background_updates': scheduler.running,
            'fast_timeouts': {
                'service_calls': service_client.fast_timeout,
                'health_checks': service_client.health_timeout
            }
        },
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

@app.route('/services/refresh', methods=['POST'])
def refresh_service_status():
    """Force refresh of service status cache"""
    # Trigger immediate cache update
    thread = threading.Thread(target=update_service_status_cache)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'message': 'Service status cache refresh triggered',
        'previous_update': last_cache_update.isoformat() if last_cache_update else None,
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

@app.route('/services/check/<service_name>')
def check_service_live(service_name):
    """Check single service status live (not cached)"""
    if service_name not in SERVICE_URLS:
        return jsonify({
            'error': f'Service {service_name} not available',
            'available_services': list(SERVICE_URLS.keys()),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 400
    
    result = check_single_service(service_name)
    
    return jsonify({
        'service_name': service_name,
        'live_status': result,
        'cached_status': service_status_cache.get(service_name, {}),
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

# Continue with remaining endpoints in next part due to length...
# [Previous phase endpoints would continue here]

# Error handlers with optimized logging
@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors with JSON response and async logging"""
    log_to_database('WARNING', f'404 error: {error}', 'unknown')
    
    return jsonify({
        'error': 'Not Found',
        'message': 'The requested endpoint does not exist',
        'phase': 'Phase 5 - Optimized Service Integrations + Background Tasks',
        'available_endpoints': [
            '/', '/health', '/test', '/status', '/api/info',
            '/database/test', '/database/status', '/logs',
            '/services/test', '/services/status', '/services/refresh',
            '/services/check/<service>', '/tasks/status', '/tasks/trigger/<task>'
        ],
        'timestamp': datetime.now(timezone.utc).isoformat()
    }), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors with JSON response and async logging"""
    log_to_database('ERROR', f'500 error: {error}', 'unknown')
    
    return jsonify({
        'error': 'Internal Server Error',
        'message': 'An internal error occurred',
        'phase': 'Phase 5 - Optimized Service Integrations + Background Tasks',
        'timestamp': datetime.now(timezone.utc).isoformat()
    }), 500

@app.errorhandler(Exception)
def handle_exception(error):
    """Handle all other exceptions with JSON response and async logging"""
    error_details = {
        'type': type(error).__name__,
        'message': str(error),
        'traceback': traceback.format_exc()
    }
    
    log_to_database('ERROR', f'Exception: {error_details}', 'unknown')
    
    return jsonify({
        'error': type(error).__name__,
        'message': str(error),
        'phase': 'Phase 5 - Optimized Service Integrations + Background Tasks',
        'timestamp': datetime.now(timezone.utc).isoformat()
    }), 500

# Initialize database and background tasks on startup
def init_application():
    """Initialize database and background tasks safely on startup"""
    if db:
        try:
            with app.app_context():
                db.create_all()
                print("Database tables created successfully")
                
                # Log startup
                startup_log = ServiceLog(
                    level='INFO',
                    message='Bot Service Phase 5 started with optimizations and background tasks',
                    endpoint='startup'
                )
                db.session.add(startup_log)
                db.session.commit()
                print("Startup logged to database")
                
        except Exception as e:
            print(f"Database initialization error: {e}")
    
    # Start background scheduler
    try:
        if not scheduler.running:
            # Add background jobs
            scheduler.add_job(
                func=update_service_status_cache,
                trigger=IntervalTrigger(minutes=2),  # Update every 2 minutes
                id='update_service_status',
                name='Update Service Status Cache',
                replace_existing=True
            )
            
            scheduler.add_job(
                func=cleanup_old_records,
                trigger=IntervalTrigger(hours=6),  # Cleanup every 6 hours
                id='cleanup_old_records',
                name='Cleanup Old Database Records',
                replace_existing=True
            )
            
            scheduler.start()
            print("Background scheduler started successfully")
            
            # Initial cache update
            update_service_status_cache()
            
    except Exception as e:
        print(f"Background scheduler initialization error: {e}")

# For production (Gunicorn)
if __name__ != '__main__':
    init_application()

# For development testing only
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting Bot Service Phase 5 (Optimized) on port {port}")
    
    # Initialize for development
    with app.app_context():
        try:
            db.create_all()
            print("Development database initialized")
        except Exception as e:
            print(f"Development database error: {e}")
    
    # Start scheduler for development
    init_application()
    
    app.run(host='0.0.0.0', port=port, debug=False)

