"""
Health check routes
Provides health and status information for the service
"""

import logging
import requests
from flask import Blueprint, jsonify
from datetime import datetime, timezone
from models import db
from config.settings import Config

logger = logging.getLogger(__name__)

health_bp = Blueprint('health', __name__)

@health_bp.route('/health', methods=['GET'])
def health_check():
    """Main health check endpoint"""
    try:
        health_status = {
            'status': 'healthy',
            'service': 'bot-service',
            'version': '1.0.0',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        # Check database connection
        try:
            db.session.execute('SELECT 1')
            health_status['database'] = 'connected'
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            health_status['database'] = 'disconnected'
            health_status['status'] = 'unhealthy'
        
        # Check Telegram API accessibility
        try:
            response = requests.get(f"{Config.TELEGRAM_API_BASE}/bot123456:test/getMe", timeout=5)
            # We expect this to fail with 401, but if we get a response, API is accessible
            health_status['telegram_api'] = 'accessible'
        except requests.exceptions.RequestException as e:
            logger.warning(f"Telegram API health check failed: {e}")
            health_status['telegram_api'] = 'inaccessible'
            # Don't mark as unhealthy since this is expected without valid token
        
        # Check webhook status (basic check)
        webhook_base = Config.WEBHOOK_BASE_URL
        if webhook_base and webhook_base != 'https://telegive-bot.railway.app':
            health_status['webhook_status'] = 'configured'
        else:
            health_status['webhook_status'] = 'default_config'
        
        # Check external services
        external_services = check_external_services()
        health_status['external_services'] = external_services
        
        # Determine overall status
        if health_status['database'] == 'disconnected':
            health_status['status'] = 'unhealthy'
        elif any(status == 'inaccessible' for status in external_services.values()):
            health_status['status'] = 'degraded'
        
        status_code = 200 if health_status['status'] in ['healthy', 'degraded'] else 503
        return jsonify(health_status), status_code
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify({
            'status': 'unhealthy',
            'service': 'bot-service',
            'error': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 503

@health_bp.route('/health/database', methods=['GET'])
def database_health():
    """Database-specific health check"""
    try:
        # Test database connection
        db.session.execute('SELECT 1')
        
        # Get some basic stats
        from models import BotInteraction, MessageDeliveryLog, WebhookProcessingLog
        
        interaction_count = BotInteraction.query.count()
        delivery_count = MessageDeliveryLog.query.count()
        webhook_count = WebhookProcessingLog.query.count()
        
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'statistics': {
                'bot_interactions': interaction_count,
                'message_deliveries': delivery_count,
                'webhook_processes': webhook_count
            },
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'database': 'disconnected',
            'error': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 503

@health_bp.route('/health/services', methods=['GET'])
def services_health():
    """External services health check"""
    try:
        services_status = check_external_services()
        
        overall_status = 'healthy'
        if any(status == 'inaccessible' for status in services_status.values()):
            overall_status = 'degraded'
        
        return jsonify({
            'status': overall_status,
            'services': services_status,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Services health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 503

@health_bp.route('/health/telegram', methods=['GET'])
def telegram_health():
    """Telegram API health check"""
    try:
        # Test Telegram API accessibility
        response = requests.get(f"{Config.TELEGRAM_API_BASE}/bot123456:test/getMe", timeout=10)
        
        # We expect 401 Unauthorized, which means API is accessible
        if response.status_code == 401:
            api_status = 'accessible'
        else:
            api_status = 'unexpected_response'
        
        return jsonify({
            'status': 'healthy' if api_status == 'accessible' else 'degraded',
            'telegram_api': api_status,
            'api_base': Config.TELEGRAM_API_BASE,
            'response_code': response.status_code,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Telegram API health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'telegram_api': 'inaccessible',
            'error': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 503

@health_bp.route('/status', methods=['GET'])
def service_status():
    """Detailed service status information"""
    try:
        from models import BotInteraction, MessageDeliveryLog, WebhookProcessingLog
        
        # Get recent statistics
        recent_interactions = BotInteraction.query.filter(
            BotInteraction.interaction_timestamp >= datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)
        ).count()
        
        recent_deliveries = MessageDeliveryLog.query.filter(
            MessageDeliveryLog.scheduled_at >= datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)
        ).count()
        
        recent_webhooks = WebhookProcessingLog.query.filter(
            WebhookProcessingLog.received_at >= datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)
        ).count()
        
        # Get error rates
        failed_interactions = BotInteraction.query.filter(
            BotInteraction.interaction_timestamp >= datetime.now(timezone.utc).replace(hour=0, minute=0, second=0),
            BotInteraction.success == False
        ).count()
        
        failed_deliveries = MessageDeliveryLog.query.filter(
            MessageDeliveryLog.scheduled_at >= datetime.now(timezone.utc).replace(hour=0, minute=0, second=0),
            MessageDeliveryLog.delivery_status == 'failed'
        ).count()
        
        return jsonify({
            'service': 'bot-service',
            'version': '1.0.0',
            'uptime': 'N/A',  # Would need to track service start time
            'configuration': {
                'service_port': Config.SERVICE_PORT,
                'webhook_base_url': Config.WEBHOOK_BASE_URL,
                'max_message_length': Config.MAX_MESSAGE_LENGTH,
                'bulk_message_batch_size': Config.BULK_MESSAGE_BATCH_SIZE,
                'message_retry_attempts': Config.MESSAGE_RETRY_ATTEMPTS
            },
            'statistics': {
                'today': {
                    'interactions': recent_interactions,
                    'message_deliveries': recent_deliveries,
                    'webhook_processes': recent_webhooks,
                    'failed_interactions': failed_interactions,
                    'failed_deliveries': failed_deliveries
                },
                'error_rates': {
                    'interaction_error_rate': (failed_interactions / max(recent_interactions, 1)) * 100,
                    'delivery_error_rate': (failed_deliveries / max(recent_deliveries, 1)) * 100
                }
            },
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        return jsonify({
            'service': 'bot-service',
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 500

def check_external_services():
    """Check accessibility of external services"""
    services = {
        'auth_service': Config.TELEGIVE_AUTH_URL,
        'channel_service': Config.TELEGIVE_CHANNEL_URL,
        'telegive_service': Config.TELEGIVE_GIVEAWAY_URL,
        'participant_service': Config.TELEGIVE_PARTICIPANT_URL,
        'media_service': Config.TELEGIVE_MEDIA_URL
    }
    
    service_status = {}
    
    for service_name, service_url in services.items():
        try:
            # Try to reach the health endpoint
            health_url = f"{service_url}/health"
            response = requests.get(health_url, timeout=5)
            
            if response.status_code == 200:
                service_status[service_name] = 'accessible'
            else:
                service_status[service_name] = 'degraded'
                
        except requests.exceptions.RequestException:
            service_status[service_name] = 'inaccessible'
    
    return service_status

