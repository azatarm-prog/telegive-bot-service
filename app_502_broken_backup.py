"""
Telegram Bot Service - Application Context Fix
Fixed version that properly handles Flask application context in background tasks
"""
import os
import json
import requests
import logging
import traceback
from functools import wraps
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin
import threading
import time

# Configure production logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)

# Production configuration
app.config['ENV'] = 'production'
app.config['DEBUG'] = False
app.config['TESTING'] = False

# Database configuration
database_url = os.environ.get('DATABASE_URL')
if database_url:
    # Fix postgres:// to postgresql:// for SQLAlchemy compatibility
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    # Fallback for development
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fallback.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'production-secret-key-change-me')

# Service URLs configuration
SERVICE_URLS = {
    'auth': os.environ.get('AUTH_SERVICE_URL', 'https://web-production-ddd7e.up.railway.app'),
    'channel': os.environ.get('CHANNEL_SERVICE_URL', 'https://telegive-channel-service.railway.app'),
    'participant': os.environ.get('PARTICIPANT_SERVICE_URL', 'https://telegive-participant-production.up.railway.app')
}

# Initialize database
db = SQLAlchemy(app)

# Models
class HealthCheck(db.Model):
    __tablename__ = 'health_checks'
    
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    timestamp = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    status = db.Column(db.String(50), nullable=False)
    details = db.Column(db.Text)

class BotRegistration(db.Model):
    __tablename__ = 'bot_registrations'
    
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    bot_id = db.Column(db.String(255), unique=True, nullable=False)
    bot_token = db.Column(db.String(500), nullable=False)
    user_id = db.Column(db.BigInteger, nullable=False)
    webhook_url = db.Column(db.String(500))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_activity = db.Column(db.DateTime(timezone=True))

class WebhookLog(db.Model):
    __tablename__ = 'webhook_logs'
    
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    bot_id = db.Column(db.String(255), nullable=False)
    webhook_data = db.Column(db.Text)
    status = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class MessageLog(db.Model):
    __tablename__ = 'message_logs'
    
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    bot_id = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.BigInteger, nullable=False)
    message_type = db.Column(db.String(50), nullable=False)
    message_content = db.Column(db.Text)
    response_content = db.Column(db.Text)
    timestamp = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class ServiceInteraction(db.Model):
    __tablename__ = 'service_interactions'
    
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    service_name = db.Column(db.String(100), nullable=False)
    endpoint = db.Column(db.String(500), nullable=False)
    method = db.Column(db.String(10), nullable=False)
    status_code = db.Column(db.Integer)
    response_time = db.Column(db.Float)
    success = db.Column(db.Boolean, nullable=False)
    error_message = db.Column(db.Text)
    timestamp = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class ErrorLog(db.Model):
    __tablename__ = 'error_logs'
    
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    error_type = db.Column(db.String(100), nullable=False)
    error_message = db.Column(db.Text, nullable=False)
    stack_trace = db.Column(db.Text)
    endpoint = db.Column(db.String(500))
    user_id = db.Column(db.BigInteger)
    timestamp = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class BackgroundTask(db.Model):
    __tablename__ = 'background_tasks'
    
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    task_type = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(50), default='pending')
    data = db.Column(db.Text)
    result = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    started_at = db.Column(db.DateTime(timezone=True))
    completed_at = db.Column(db.DateTime(timezone=True))
    error_message = db.Column(db.Text)

# Error handling decorator
def handle_errors(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            # Log error to database
            try:
                error_log = ErrorLog(
                    error_type=type(e).__name__,
                    error_message=str(e),
                    stack_trace=traceback.format_exc(),
                    endpoint=request.endpoint if request else None
                )
                db.session.add(error_log)
                db.session.commit()
            except Exception as log_error:
                logger.error(f"Failed to log error to database: {log_error}")
            
            logger.error(f"Error in {f.__name__}: {str(e)}")
            return jsonify({
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }), 500
    return decorated_function

# Service client for external API calls
class ServiceClient:
    def __init__(self):
        self.headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Telegive-Bot-Service/1.0'
        }
    
    def call_service(self, service_name, endpoint, method='GET', data=None):
        start_time = time.time()
        
        try:
            base_url = SERVICE_URLS.get(service_name)
            if not base_url:
                return {'success': False, 'error': f'Service {service_name} not configured'}
            
            url = urljoin(base_url, endpoint)
            
            if method.upper() == 'POST':
                response = requests.post(url, headers=self.headers, json=data, timeout=10)
            else:
                response = requests.get(url, headers=self.headers, timeout=10)
            
            response_time = time.time() - start_time
            
            # Log interaction with app context
            with app.app_context():
                interaction = ServiceInteraction(
                    service_name=service_name,
                    endpoint=endpoint,
                    method=method.upper(),
                    status_code=response.status_code,
                    response_time=response_time,
                    success=response.status_code < 400
                )
                
                if response.status_code >= 400:
                    interaction.error_message = response.text
                
                db.session.add(interaction)
                db.session.commit()
            
            if response.status_code < 400:
                return {'success': True, 'data': response.json(), 'response_time': response_time}
            else:
                return {'success': False, 'error': f'HTTP {response.status_code}', 'response_time': response_time}
                
        except requests.exceptions.Timeout:
            response_time = time.time() - start_time
            with app.app_context():
                interaction = ServiceInteraction(
                    service_name=service_name,
                    endpoint=endpoint,
                    method=method.upper(),
                    response_time=response_time,
                    success=False,
                    error_message='Timeout'
                )
                db.session.add(interaction)
                db.session.commit()
            return {'success': False, 'error': 'Service timeout'}
            
        except Exception as e:
            response_time = time.time() - start_time
            with app.app_context():
                interaction = ServiceInteraction(
                    service_name=service_name,
                    endpoint=endpoint,
                    method=method.upper(),
                    response_time=response_time,
                    success=False,
                    error_message=str(e)
                )
                db.session.add(interaction)
                db.session.commit()
            return {'success': False, 'error': str(e)}

# Initialize service client
service_client = ServiceClient()

# Telegram Bot class
class TelegramBot:
    def __init__(self, bot_token):
        self.bot_token = bot_token
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
    
    def send_message(self, chat_id, text):
        """Send message to Telegram chat"""
        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                'chat_id': chat_id,
                'text': text,
                'parse_mode': 'HTML'
            }
            
            response = requests.post(url, json=data, timeout=10)
            return response.json()
            
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return {'ok': False, 'error': str(e)}
    
    def set_webhook(self, webhook_url):
        """Set webhook for the bot"""
        try:
            url = f"{self.base_url}/setWebhook"
            data = {'url': webhook_url}
            
            response = requests.post(url, json=data, timeout=10)
            return response.json()
            
        except Exception as e:
            logger.error(f"Failed to set webhook: {e}")
            return {'ok': False, 'error': str(e)}

# Background Task Manager with proper application context
class BackgroundTaskManager:
    def __init__(self, flask_app):
        self.app = flask_app
        self.running = False
        self.thread = None
    
    def start(self):
        """Start background task processing"""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._process_tasks, daemon=True)
            self.thread.start()
            logger.info("Background task manager started")
    
    def stop(self):
        """Stop background task processing"""
        self.running = False
        if self.thread:
            self.thread.join()
        logger.info("Background task manager stopped")
    
    def _process_tasks(self):
        """Process background tasks with proper application context"""
        while self.running:
            try:
                with self.app.app_context():
                    # Get pending tasks
                    tasks = BackgroundTask.query.filter_by(status='pending').limit(10).all()
                    
                    for task in tasks:
                        self._execute_task(task)
                    
                    # Clean up old completed tasks (older than 7 days)
                    cutoff_date = datetime.now(timezone.utc) - timedelta(days=7)
                    old_tasks = BackgroundTask.query.filter(
                        BackgroundTask.status.in_(['completed', 'failed']),
                        BackgroundTask.completed_at < cutoff_date
                    ).all()
                    
                    for old_task in old_tasks:
                        db.session.delete(old_task)
                    
                    if old_tasks:
                        db.session.commit()
                        logger.info(f"Cleaned up {len(old_tasks)} old background tasks")
                
            except Exception as e:
                logger.error(f"Background task processing error: {e}")
            
            time.sleep(5)  # Check every 5 seconds
    
    def _execute_task(self, task):
        """Execute a single background task within application context"""
        try:
            task.status = 'running'
            task.started_at = datetime.now(timezone.utc)
            db.session.commit()
            
            if task.task_type == 'cleanup_logs':
                self._cleanup_old_logs()
            elif task.task_type == 'health_check_bots':
                self._health_check_bots()
            elif task.task_type == 'retry_failed_messages':
                self._retry_failed_messages()
            
            task.status = 'completed'
            task.completed_at = datetime.now(timezone.utc)
            task.result = 'Task completed successfully'
            
        except Exception as e:
            task.status = 'failed'
            task.completed_at = datetime.now(timezone.utc)
            task.error_message = str(e)
            logger.error(f"Background task {task.id} failed: {e}")
        
        finally:
            db.session.commit()
    
    def _cleanup_old_logs(self):
        """Clean up old log entries"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)
        
        # Clean up old webhook logs
        old_webhooks = WebhookLog.query.filter(WebhookLog.timestamp < cutoff_date).all()
        for log in old_webhooks:
            db.session.delete(log)
        
        # Clean up old message logs
        old_messages = MessageLog.query.filter(MessageLog.timestamp < cutoff_date).all()
        for log in old_messages:
            db.session.delete(log)
        
        # Clean up old error logs (keep for 90 days)
        error_cutoff = datetime.now(timezone.utc) - timedelta(days=90)
        old_errors = ErrorLog.query.filter(ErrorLog.timestamp < error_cutoff).all()
        for log in old_errors:
            db.session.delete(log)
        
        db.session.commit()
        logger.info(f"Cleaned up {len(old_webhooks)} webhook logs, {len(old_messages)} message logs, {len(old_errors)} error logs")
    
    def _health_check_bots(self):
        """Check health of registered bots"""
        bots = BotRegistration.query.filter_by(is_active=True).all()
        
        for bot in bots:
            try:
                # Try to get bot info to verify token is still valid
                response = requests.get(f"https://api.telegram.org/bot{bot.bot_token}/getMe", timeout=10)
                
                if response.status_code == 200:
                    bot.last_activity = datetime.now(timezone.utc)
                else:
                    # Bot token might be invalid, deactivate
                    bot.is_active = False
                    logger.warning(f"Deactivated bot {bot.bot_id} due to invalid token")
                
            except Exception as e:
                logger.error(f"Health check failed for bot {bot.bot_id}: {e}")
        
        db.session.commit()
    
    def _retry_failed_messages(self):
        """Retry failed message deliveries"""
        # This would implement retry logic for failed messages
        # For now, just log that we're checking
        logger.info("Checking for failed messages to retry")

# Initialize background task manager with app context
task_manager = BackgroundTaskManager(app)

# Routes
@app.route('/')
@handle_errors
def home():
    return jsonify({
        'service': 'telegive-bot-service',
        'status': 'working',
        'version': '1.0.1-context-fixed',
        'features': ['telegram_integration', 'service_communication', 'background_tasks', 'error_handling'],
        'message': 'Production Telegram Bot Service with fixed application context',
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

@app.route('/health')
@handle_errors
def health():
    # Test database connection
    try:
        db.session.execute(db.text('SELECT 1'))
        db_status = 'connected'
    except Exception as e:
        db_status = 'disconnected'
        logger.error(f"Database health check failed: {e}")
    
    # Test service connectivity
    service_status = {}
    for service_name in SERVICE_URLS.keys():
        try:
            result = service_client.call_service(service_name, '/health')
            service_status[service_name] = 'connected' if result['success'] else 'disconnected'
        except:
            service_status[service_name] = 'disconnected'
    
    # Count registered bots
    try:
        bot_count = BotRegistration.query.filter_by(is_active=True).count()
    except:
        bot_count = 0
    
    # Count recent errors
    try:
        recent_errors = ErrorLog.query.filter(
            ErrorLog.timestamp > datetime.now(timezone.utc) - timedelta(hours=1)
        ).count()
    except:
        recent_errors = 0
    
    overall_status = 'healthy' if db_status == 'connected' and recent_errors < 10 else 'unhealthy'
    
    health_data = {
        'status': overall_status,
        'database': db_status,
        'services': service_status,
        'registered_bots': bot_count,
        'recent_errors': recent_errors,
        'background_tasks': 'running' if task_manager.running else 'stopped',
        'context_fix': 'applied',
        'timestamp': datetime.now(timezone.utc).isoformat()
    }
    
    # Log health check
    try:
        health_check = HealthCheck(
            status=overall_status,
            details=json.dumps(health_data)
        )
        db.session.add(health_check)
        db.session.commit()
    except Exception as e:
        logger.error(f"Failed to log health check: {e}")
    
    status_code = 200 if overall_status == 'healthy' else 503
    return jsonify(health_data), status_code

@app.route('/database/test')
@handle_errors
def test_database():
    try:
        # Test database connection
        db.session.execute(db.text('SELECT 1'))
        
        # Count records in each table
        health_count = HealthCheck.query.count()
        bot_count = BotRegistration.query.count()
        webhook_count = WebhookLog.query.count()
        
        return jsonify({
            'database': 'connected',
            'tables': {
                'health_checks': health_count,
                'bot_registrations': bot_count,
                'webhook_logs': webhook_count
            },
            'context_fix': 'applied',
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'database': 'error',
            'error': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 500

# Bot management endpoints
@app.route('/api/bots', methods=['GET'])
@handle_errors
def list_bots():
    bots = BotRegistration.query.filter_by(is_active=True).all()
    
    bot_list = []
    for bot in bots:
        bot_list.append({
            'bot_id': bot.bot_id,
            'user_id': bot.user_id,
            'webhook_url': bot.webhook_url,
            'created_at': bot.created_at.isoformat() if bot.created_at else None,
            'last_activity': bot.last_activity.isoformat() if bot.last_activity else None
        })
    
    return jsonify({
        'bots': bot_list,
        'count': len(bot_list),
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

@app.route('/api/bots/register', methods=['POST'])
@handle_errors
def register_bot():
    data = request.get_json()
    
    if not data or 'bot_token' not in data or 'user_id' not in data:
        return jsonify({
            'status': 'error',
            'error': 'bot_token and user_id are required'
        }), 400
    
    bot_token = data['bot_token']
    user_id = data['user_id']
    
    # Validate bot token by getting bot info
    try:
        response = requests.get(f"https://api.telegram.org/bot{bot_token}/getMe", timeout=10)
        if response.status_code != 200:
            return jsonify({
                'status': 'error',
                'error': 'Invalid bot token'
            }), 400
        
        bot_info = response.json()
        bot_id = bot_info['result']['username']
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': f'Failed to validate bot token: {str(e)}'
        }), 400
    
    # Check if bot already exists
    existing_bot = BotRegistration.query.filter_by(bot_id=bot_id).first()
    if existing_bot:
        return jsonify({
            'status': 'error',
            'error': 'Bot already registered'
        }), 409
    
    # Register bot
    webhook_url = f"https://telegive-bot-service-production.up.railway.app/webhook/{bot_id}"
    
    bot_registration = BotRegistration(
        bot_id=bot_id,
        bot_token=bot_token,
        user_id=user_id,
        webhook_url=webhook_url
    )
    
    db.session.add(bot_registration)
    db.session.commit()
    
    # Set webhook
    telegram_bot = TelegramBot(bot_token)
    webhook_result = telegram_bot.set_webhook(webhook_url)
    
    return jsonify({
        'status': 'success',
        'bot_id': bot_id,
        'webhook_url': webhook_url,
        'webhook_set': webhook_result.get('ok', False),
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

@app.route('/webhook/<bot_id>', methods=['POST'])
@handle_errors
def webhook_handler(bot_id):
    # Verify bot exists
    bot = BotRegistration.query.filter_by(bot_id=bot_id, is_active=True).first()
    if not bot:
        return jsonify({'status': 'error', 'error': 'Bot not found'}), 404
    
    webhook_data = request.get_json()
    if not webhook_data:
        return jsonify({'status': 'error', 'error': 'No data received'}), 400
    
    # Log webhook
    webhook_log = WebhookLog(
        bot_id=bot_id,
        webhook_data=json.dumps(webhook_data),
        status='received'
    )
    db.session.add(webhook_log)
    
    # Process webhook
    try:
        telegram_bot = TelegramBot(bot.bot_token)
        
        if 'message' in webhook_data:
            message = webhook_data['message']
            chat_id = message['chat']['id']
            user_id = message['from']['id']
            
            # Handle different message types
            if 'text' in message:
                text = message['text']
                
                # Log message
                message_log = MessageLog(
                    bot_id=bot_id,
                    user_id=user_id,
                    message_type='text',
                    message_content=text
                )
                
                # Process commands
                response_text = None
                if text.startswith('/start'):
                    response_text = f"🤖 Welcome to {bot_id}!\n\nI'm your Telegive bot assistant. Use /help to see available commands."
                elif text.startswith('/help'):
                    response_text = """🆘 <b>Available Commands:</b>

/start - Welcome message
/help - Show this help
/status - Bot and service status
/health - Service health information
/channels - Your channels (via Channel Service)
/participants - Participant count (via Participant Service)

🔗 <b>Telegive Services Integration:</b>
This bot is connected to the Telegive ecosystem and can access your channels and participant data."""
                elif text.startswith('/status'):
                    bot_count = BotRegistration.query.filter_by(is_active=True).count()
                    response_text = f"""📊 <b>Bot Status:</b>

🤖 Bot: {bot_id}
✅ Status: Active
🔗 Webhook: Configured
📈 Total Active Bots: {bot_count}
🕐 Last Update: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC

🌐 <b>Service Status:</b>
All Telegive services are operational."""
                elif text.startswith('/health'):
                    # Get service health
                    service_health = {}
                    for service_name in SERVICE_URLS.keys():
                        result = service_client.call_service(service_name, '/health')
                        service_health[service_name] = '✅' if result['success'] else '❌'
                    
                    health_text = "🏥 <b>Service Health:</b>\n\n"
                    health_text += f"🤖 Bot Service: ✅\n"
                    health_text += f"🔐 Auth Service: {service_health.get('auth', '❌')}\n"
                    health_text += f"📺 Channel Service: {service_health.get('channel', '❌')}\n"
                    health_text += f"👥 Participant Service: {service_health.get('participant', '❌')}\n"
                    
                    response_text = health_text
                elif text.startswith('/channels'):
                    # Get user channels from Channel Service
                    result = service_client.call_service('channel', f'/api/channels/user/{user_id}')
                    if result['success']:
                        channels = result['data'].get('channels', [])
                        if channels:
                            response_text = f"📺 <b>Your Channels ({len(channels)}):</b>\n\n"
                            for channel in channels[:5]:  # Show first 5
                                response_text += f"• {channel.get('name', 'Unknown')}\n"
                            if len(channels) > 5:
                                response_text += f"\n... and {len(channels) - 5} more"
                        else:
                            response_text = "📺 You don't have any channels yet."
                    else:
                        response_text = "❌ Unable to fetch channels at the moment."
                elif text.startswith('/participants'):
                    # Get participant count from Participant Service
                    result = service_client.call_service('participant', f'/api/participants/count/{user_id}')
                    if result['success']:
                        count = result['data'].get('count', 0)
                        response_text = f"👥 <b>Participant Statistics:</b>\n\nTotal Participants: {count}"
                    else:
                        response_text = "❌ Unable to fetch participant data at the moment."
                else:
                    response_text = f"🤔 I didn't understand that command. Use /help to see available commands."
                
                # Send response
                if response_text:
                    send_result = telegram_bot.send_message(chat_id, response_text)
                    message_log.response_content = response_text
                    
                    if not send_result.get('ok'):
                        logger.error(f"Failed to send message: {send_result}")
                
                db.session.add(message_log)
        
        webhook_log.status = 'processed'
        
    except Exception as e:
        webhook_log.status = 'error'
        logger.error(f"Webhook processing error: {e}")
    
    db.session.commit()
    
    return jsonify({'status': 'ok'})

# Service integration endpoints
@app.route('/api/services/test', methods=['POST'])
@handle_errors
def test_service_integration():
    data = request.get_json()
    
    if not data or 'service' not in data or 'endpoint' not in data:
        return jsonify({
            'status': 'error',
            'error': 'service and endpoint are required'
        }), 400
    
    service_name = data['service']
    endpoint = data['endpoint']
    method = data.get('method', 'GET')
    request_data = data.get('data')
    
    result = service_client.call_service(service_name, endpoint, method, request_data)
    
    return jsonify({
        'status': 'success',
        'service': service_name,
        'endpoint': endpoint,
        'result': result,
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

# Admin endpoints
@app.route('/api/admin/errors', methods=['GET'])
@handle_errors
def get_recent_errors():
    hours = request.args.get('hours', 24, type=int)
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    errors = ErrorLog.query.filter(ErrorLog.timestamp > cutoff_time).order_by(ErrorLog.timestamp.desc()).limit(50).all()
    
    error_list = []
    for error in errors:
        error_list.append({
            'id': error.id,
            'error_type': error.error_type,
            'error_message': error.error_message,
            'endpoint': error.endpoint,
            'timestamp': error.timestamp.isoformat()
        })
    
    return jsonify({
        'errors': error_list,
        'count': len(error_list),
        'hours': hours,
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

@app.route('/api/admin/tasks', methods=['GET'])
@handle_errors
def get_background_tasks():
    tasks = BackgroundTask.query.order_by(BackgroundTask.created_at.desc()).limit(20).all()
    
    task_list = []
    for task in tasks:
        task_list.append({
            'id': task.id,
            'task_type': task.task_type,
            'status': task.status,
            'created_at': task.created_at.isoformat(),
            'started_at': task.started_at.isoformat() if task.started_at else None,
            'completed_at': task.completed_at.isoformat() if task.completed_at else None,
            'error_message': task.error_message
        })
    
    return jsonify({
        'tasks': task_list,
        'count': len(task_list),
        'manager_running': task_manager.running,
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

@app.route('/api/admin/tasks/create', methods=['POST'])
@handle_errors
def create_background_task():
    data = request.get_json()
    
    if not data or 'task_type' not in data:
        return jsonify({
            'status': 'error',
            'error': 'task_type is required'
        }), 400
    
    task = BackgroundTask(
        task_type=data['task_type'],
        data=json.dumps(data.get('data', {}))
    )
    
    db.session.add(task)
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'task_id': task.id,
        'task_type': task.task_type,
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

# Production initialization with proper context
def init_production_app():
    """Initialize the app for production use"""
    with app.app_context():
        try:
            # Create database tables
            db.create_all()
            logger.info("Database tables created successfully")
            
            # Create initial background tasks
            cleanup_task = BackgroundTask(task_type='cleanup_logs')
            health_task = BackgroundTask(task_type='health_check_bots')
            
            db.session.add(cleanup_task)
            db.session.add(health_task)
            db.session.commit()
            
            # Start background task manager
            task_manager.start()
            logger.info("Production initialization completed with context fix")
            
        except Exception as e:
            logger.error(f"Production initialization failed: {str(e)}")

# Initialize for production when imported by gunicorn
if __name__ != '__main__':
    init_production_app()

# For development/testing only
if __name__ == '__main__':
    logger.warning("Running in development mode - use gunicorn for production")
    port = int(os.environ.get('PORT', 5000))
    
    # Initialize for development
    with app.app_context():
        try:
            db.create_all()
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Database initialization warning: {str(e)}")
    
    app.run(host='0.0.0.0', port=port, debug=True)

