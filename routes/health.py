"""
Standardized health check routes for Telegive Bot Service
Implements comprehensive health monitoring and service discovery
"""

from flask import Blueprint, jsonify, request
from sqlalchemy import text
import logging
import os
import time
import psutil
import requests
from datetime import datetime, timezone
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

health_bp = Blueprint('health', __name__)

# These will be set by the app after initialization
db = None

def get_service_info() -> Dict[str, Any]:
    """Get basic service information"""
    return {
        'service': os.getenv('SERVICE_NAME', 'telegive-bot-service'),
        'version': '1.0.0',
        'environment': os.getenv('ENVIRONMENT', 'development'),
        'timestamp': datetime.now(timezone.utc).isoformat()
    }

def check_database_health() -> Dict[str, Any]:
    """Check database connectivity and performance"""
    try:
        start_time = time.time()
        
        # Test basic connectivity
        db.session.execute(text('SELECT 1'))
        db.session.commit()
        
        response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        # Get database statistics
        try:
            from models import BotInteraction, MessageDeliveryLog, WebhookProcessingLog
            
            stats = {
                'bot_interactions': BotInteraction.query.count(),
                'message_deliveries': MessageDeliveryLog.query.count(),
                'webhook_processes': WebhookProcessingLog.query.count()
            }
        except Exception as e:
            logger.warning(f"Could not get database statistics: {e}")
            stats = {'error': 'Statistics unavailable'}
        
        return {
            'status': 'healthy',
            'response_time_ms': round(response_time, 2),
            'statistics': stats
        }
        
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            'status': 'unhealthy',
            'error': str(e)
        }

def check_external_services() -> Dict[str, Any]:
    """Check external service connectivity"""
    services = {
        'auth': os.getenv('TELEGIVE_AUTH_URL'),
        'channel': os.getenv('TELEGIVE_CHANNEL_URL'),
        'giveaway': os.getenv('TELEGIVE_GIVEAWAY_URL'),
        'participant': os.getenv('TELEGIVE_PARTICIPANT_URL'),
        'media': os.getenv('TELEGIVE_MEDIA_URL')
    }
    
    service_status = {}
    
    for service_name, service_url in services.items():
        if not service_url:
            service_status[service_name] = {
                'status': 'not_configured',
                'url': None
            }
            continue
        
        try:
            start_time = time.time()
            response = requests.get(f"{service_url}/health", timeout=5)
            response_time = (time.time() - start_time) * 1000
            
            service_status[service_name] = {
                'status': 'healthy' if response.status_code == 200 else 'unhealthy',
                'url': service_url,
                'response_time_ms': round(response_time, 2),
                'http_status': response.status_code
            }
            
        except requests.exceptions.Timeout:
            service_status[service_name] = {
                'status': 'timeout',
                'url': service_url,
                'error': 'Request timed out'
            }
        except Exception as e:
            service_status[service_name] = {
                'status': 'error',
                'url': service_url,
                'error': str(e)
            }
    
    return service_status

def check_system_resources() -> Dict[str, Any]:
    """Check system resource usage"""
    try:
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # Memory usage
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_available_mb = memory.available / (1024 * 1024)
        
        # Disk usage
        disk = psutil.disk_usage('/')
        disk_percent = (disk.used / disk.total) * 100
        disk_free_gb = disk.free / (1024 * 1024 * 1024)
        
        return {
            'cpu_percent': round(cpu_percent, 1),
            'memory_percent': round(memory_percent, 1),
            'memory_available_mb': round(memory_available_mb, 1),
            'disk_percent': round(disk_percent, 1),
            'disk_free_gb': round(disk_free_gb, 2)
        }
        
    except Exception as e:
        logger.warning(f"Could not get system resources: {e}")
        return {'error': 'Resource monitoring unavailable'}

@health_bp.route('/health', methods=['GET'])
def health_check():
    """
    Comprehensive health check endpoint
    Returns overall service health status
    """
    try:
        service_info = get_service_info()
        
        # Check database
        db_health = check_database_health()
        
        # Check external services
        external_services = check_external_services()
        
        # Check system resources
        system_resources = check_system_resources()
        
        # Determine overall health
        overall_healthy = (
            db_health['status'] == 'healthy' and
            all(
                service['status'] in ['healthy', 'not_configured'] 
                for service in external_services.values()
            )
        )
        
        response = {
            **service_info,
            'status': 'healthy' if overall_healthy else 'unhealthy',
            'database': db_health,
            'external_services': external_services,
            'system_resources': system_resources
        }
        
        status_code = 200 if overall_healthy else 503
        return jsonify(response), status_code
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            **get_service_info(),
            'status': 'error',
            'error': str(e)
        }), 503

@health_bp.route('/health/live', methods=['GET'])
def liveness_check():
    """
    Kubernetes-style liveness probe
    Simple check to verify the service is running
    """
    return jsonify({
        'alive': True,
        'status': 'alive',
        'service': os.getenv('SERVICE_NAME', 'telegive-bot-service'),
        'timestamp': datetime.now(timezone.utc).isoformat()
    }), 200

@health_bp.route('/health/ready', methods=['GET'])
def readiness_check():
    """
    Kubernetes-style readiness probe
    Checks if service is ready to handle requests
    """
    try:
        # Check database connectivity
        db.session.execute(text('SELECT 1'))
        db.session.commit()
        
        # Check critical external services
        critical_services = ['auth']  # Only auth service is critical for bot operation
        auth_url = os.getenv('TELEGIVE_AUTH_URL')
        
        if auth_url:
            try:
                response = requests.get(f"{auth_url}/health", timeout=3)
                if response.status_code != 200:
                    raise Exception(f"Auth service unhealthy: {response.status_code}")
            except Exception as e:
                return jsonify({
                    'ready': False,
                    'status': 'not_ready',
                    'reason': f"Auth service unavailable: {e}"
                }), 503
        
        return jsonify({
            'ready': True,
            'status': 'ready',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return jsonify({
            'ready': False,
            'status': 'not_ready',
            'error': str(e)
        }), 503

@health_bp.route('/health/database', methods=['GET'])
def database_health():
    """Detailed database health check"""
    db_health = check_database_health()
    
    status_code = 200 if db_health['status'] == 'healthy' else 503
    return jsonify({
        **get_service_info(),
        'database': db_health
    }), status_code

@health_bp.route('/health/services', methods=['GET'])
def services_health():
    """External services health check"""
    external_services = check_external_services()
    
    # Determine if any critical services are down
    critical_services = ['auth']
    critical_down = any(
        external_services.get(service, {}).get('status') not in ['healthy', 'not_configured']
        for service in critical_services
    )
    
    overall_status = 'unhealthy' if critical_down else 'healthy'
    status_code = 503 if critical_down else 200
    
    return jsonify({
        **get_service_info(),
        'status': overall_status,
        'services': external_services
    }), status_code

@health_bp.route('/health/telegram', methods=['GET'])
def telegram_health():
    """Telegram API health check"""
    try:
        # Test Telegram API accessibility
        response = requests.get('https://api.telegram.org/bot123:test/getMe', timeout=5)
        
        # We expect 401 (Unauthorized) which means API is accessible
        telegram_accessible = response.status_code == 401
        
        return jsonify({
            **get_service_info(),
            'telegram_api': 'accessible' if telegram_accessible else 'inaccessible',
            'api_base': 'https://api.telegram.org',
            'response_code': response.status_code
        }), 200 if telegram_accessible else 503
        
    except Exception as e:
        logger.error(f"Telegram API check failed: {e}")
        return jsonify({
            **get_service_info(),
            'telegram_api': 'error',
            'error': str(e)
        }), 503

@health_bp.route('/status', methods=['GET'])
def service_status():
    """
    Detailed service status endpoint
    Provides comprehensive information about service state
    """
    try:
        service_info = get_service_info()
        
        # Get uptime (approximate)
        try:
            boot_time = psutil.boot_time()
            uptime_seconds = time.time() - boot_time
            uptime_hours = uptime_seconds / 3600
            uptime_str = f"{int(uptime_hours // 24)} days, {int(uptime_hours % 24)} hours"
        except:
            uptime_str = "unknown"
        
        # Configuration info
        config_info = {
            'service_port': int(os.getenv('SERVICE_PORT', 5000)),
            'webhook_base_url': os.getenv('WEBHOOK_BASE_URL', 'not_configured'),
            'environment': os.getenv('ENVIRONMENT', 'development'),
            'debug_mode': os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
        }
        
        # Get today's statistics
        try:
            from models import BotInteraction, MessageDeliveryLog, WebhookProcessingLog
            from datetime import date
            
            today = date.today()
            
            today_stats = {
                'interactions': BotInteraction.query.filter(
                    BotInteraction.interaction_timestamp >= today
                ).count(),
                'message_deliveries': MessageDeliveryLog.query.filter(
                    MessageDeliveryLog.scheduled_at >= today
                ).count(),
                'webhook_processes': WebhookProcessingLog.query.filter(
                    WebhookProcessingLog.received_at >= today
                ).count(),
                'failed_interactions': BotInteraction.query.filter(
                    BotInteraction.interaction_timestamp >= today,
                    BotInteraction.success == False
                ).count(),
                'failed_deliveries': MessageDeliveryLog.query.filter(
                    MessageDeliveryLog.scheduled_at >= today,
                    MessageDeliveryLog.delivery_status == 'failed'
                ).count()
            }
            
            # Calculate error rates
            error_rates = {
                'interaction_error_rate': (
                    (today_stats['failed_interactions'] / today_stats['interactions'] * 100)
                    if today_stats['interactions'] > 0 else 0
                ),
                'delivery_error_rate': (
                    (today_stats['failed_deliveries'] / today_stats['message_deliveries'] * 100)
                    if today_stats['message_deliveries'] > 0 else 0
                )
            }
            
        except Exception as e:
            logger.warning(f"Could not get statistics: {e}")
            today_stats = {'error': 'Statistics unavailable'}
            error_rates = {'error': 'Error rates unavailable'}
        
        return jsonify({
            **service_info,
            'uptime': uptime_str,
            'configuration': config_info,
            'statistics': {
                'today': today_stats,
                'error_rates': error_rates
            },
            'system_resources': check_system_resources()
        }), 200
        
    except Exception as e:
        logger.error(f"Status endpoint failed: {e}")
        return jsonify({
            **get_service_info(),
            'status': 'error',
            'error': str(e)
        }), 500

@health_bp.route('/health/metrics', methods=['GET'])
def metrics():
    """
    Prometheus-style metrics endpoint
    Returns metrics in a format suitable for monitoring systems
    """
    try:
        # Get basic metrics
        db_health = check_database_health()
        system_resources = check_system_resources()
        external_services = check_external_services()
        
        # Format metrics
        metrics_lines = [
            f"# HELP telegive_bot_service_up Service availability",
            f"# TYPE telegive_bot_service_up gauge",
            f"telegive_bot_service_up 1",
            f"",
            f"# HELP telegive_bot_database_response_time_ms Database response time in milliseconds",
            f"# TYPE telegive_bot_database_response_time_ms gauge",
            f"telegive_bot_database_response_time_ms {db_health.get('response_time_ms', 0)}",
            f"",
            f"# HELP telegive_bot_database_healthy Database health status",
            f"# TYPE telegive_bot_database_healthy gauge",
            f"telegive_bot_database_healthy {1 if db_health['status'] == 'healthy' else 0}",
        ]
        
        # Add system resource metrics
        if 'error' not in system_resources:
            metrics_lines.extend([
                f"",
                f"# HELP telegive_bot_cpu_percent CPU usage percentage",
                f"# TYPE telegive_bot_cpu_percent gauge",
                f"telegive_bot_cpu_percent {system_resources['cpu_percent']}",
                f"",
                f"# HELP telegive_bot_memory_percent Memory usage percentage",
                f"# TYPE telegive_bot_memory_percent gauge",
                f"telegive_bot_memory_percent {system_resources['memory_percent']}",
            ])
        
        # Add external service metrics
        for service_name, service_info in external_services.items():
            if service_info['status'] == 'healthy':
                metrics_lines.extend([
                    f"",
                    f"# HELP telegive_bot_service_{service_name}_healthy External service health",
                    f"# TYPE telegive_bot_service_{service_name}_healthy gauge",
                    f"telegive_bot_service_{service_name}_healthy 1",
                ])
                
                if 'response_time_ms' in service_info:
                    metrics_lines.extend([
                        f"",
                        f"# HELP telegive_bot_service_{service_name}_response_time_ms Service response time",
                        f"# TYPE telegive_bot_service_{service_name}_response_time_ms gauge",
                        f"telegive_bot_service_{service_name}_response_time_ms {service_info['response_time_ms']}",
                    ])
            else:
                metrics_lines.extend([
                    f"",
                    f"# HELP telegive_bot_service_{service_name}_healthy External service health",
                    f"# TYPE telegive_bot_service_{service_name}_healthy gauge",
                    f"telegive_bot_service_{service_name}_healthy 0",
                ])
        
        return '\n'.join(metrics_lines), 200, {'Content-Type': 'text/plain; charset=utf-8'}
        
    except Exception as e:
        logger.error(f"Metrics endpoint failed: {e}")
        return f"# Error generating metrics: {e}", 500, {'Content-Type': 'text/plain; charset=utf-8'}

