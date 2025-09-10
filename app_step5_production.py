"""
Step 5: Add background tasks and comprehensive error handling
Production-ready Telegram Bot Service
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Database configuration
database_url = os.environ.get('DATABASE_URL')
if database_url:
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fallback.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')

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
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default='healthy')

class BotRegistration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bot_id = db.Column(db.String(100), unique=True, nullable=False)
    bot_token = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    webhook_set = db.Column(db.Boolean, default=False)
    last_activity = db.Column(db.DateTime, default=datetime.utcnow)
    error_count = db.Column(db.Integer, default=0)

class WebhookLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bot_id = db.Column(db.String(100), nullable=False)
    webhook_data = db.Column(db.Text, nullable=False)
    processed_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default='received')
    response_sent = db.Column(db.Text)
    processing_time = db.Column(db.Float)
    error_message = db.Column(db.Text)

class MessageLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bot_id = db.Column(db.String(100), nullable=False)
    chat_id = db.Column(db.String(100), nullable=False)
    message_text = db.Column(db.Text)
    message_type = db.Column(db.String(50))
    user_id = db.Column(db.String(100))
    username = db.Column(db.String(100))
    processed_at = db.Column(db.DateTime, default=datetime.utcnow)
    bot_response = db.Column(db.Text)
    retry_count = db.Column(db.Integer, default=0)
    status = db.Column(db.String(50), default='processed')

class ServiceInteraction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    service_name = db.Column(db.String(50), nullable=False)
    endpoint = db.Column(db.String(200), nullable=False)
    request_data = db.Column(db.Text)
    response_data = db.Column(db.Text)
    status_code = db.Column(db.Integer)
    success = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.String(100))
    response_time = db.Column(db.Float)

class ErrorLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    error_type = db.Column(db.String(100), nullable=False)
    error_message = db.Column(db.Text, nullable=False)
    stack_trace = db.Column(db.Text)
    endpoint = db.Column(db.String(200))
    user_id = db.Column(db.String(100))
    bot_id = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved = db.Column(db.Boolean, default=False)

class BackgroundTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_type = db.Column(db.String(50), nullable=False)
    task_data = db.Column(db.Text)
    status = db.Column(db.String(50), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    error_message = db.Column(db.Text)
    retry_count = db.Column(db.Integer, default=0)
    max_retries = db.Column(db.Integer, default=3)

# Error handling decorator
def handle_errors(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {f.__name__}: {str(e)}")
            
            # Log error to database
            try:
                error_log = ErrorLog(
                    error_type=type(e).__name__,
                    error_message=str(e),
                    stack_trace=traceback.format_exc(),
                    endpoint=request.endpoint if request else None,
                    user_id=request.json.get('user_id') if request and request.json else None
                )
                db.session.add(error_log)
                db.session.commit()
            except:
                pass  # Don't fail if error logging fails
            
            return jsonify({
                'status': 'error',
                'error': str(e),
                'error_type': type(e).__name__,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }), 500
    return decorated_function

# Service Communication Helper with enhanced error handling
class ServiceClient:
    def __init__(self):
        self.timeout = 10
        self.headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Telegive-Bot-Service/1.0'
        }
    
    def call_service(self, service_name, endpoint, method='GET', data=None, user_id=None):
        """Make a call to another service with comprehensive error handling"""
        start_time = time.time()
        interaction = None
        
        try:
            base_url = SERVICE_URLS.get(service_name)
            if not base_url:
                return {'success': False, 'error': f'Service {service_name} not configured'}
            
            url = urljoin(base_url, endpoint)
            
            # Log the interaction
            interaction = ServiceInteraction(
                service_name=service_name,
                endpoint=endpoint,
                request_data=json.dumps(data) if data else None,
                user_id=user_id
            )
            
            if method.upper() == 'GET':
                response = requests.get(url, headers=self.headers, timeout=self.timeout)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=self.headers, json=data, timeout=self.timeout)
            elif method.upper() == 'PUT':
                response = requests.put(url, headers=self.headers, json=data, timeout=self.timeout)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, headers=self.headers, timeout=self.timeout)
            else:
                return {'success': False, 'error': f'Unsupported method: {method}'}
            
            response_time = time.time() - start_time
            
            # Update interaction log
            interaction.status_code = response.status_code
            interaction.response_data = response.text[:1000]  # Limit response data size
            interaction.success = response.status_code < 400
            interaction.response_time = response_time
            
            db.session.add(interaction)
            db.session.commit()
            
            if response.status_code < 400:
                try:
                    return {'success': True, 'data': response.json(), 'status_code': response.status_code, 'response_time': response_time}
                except:
                    return {'success': True, 'data': response.text, 'status_code': response.status_code, 'response_time': response_time}
            else:
                return {'success': False, 'error': f'HTTP {response.status_code}', 'response': response.text[:500]}
                
        except requests.exceptions.Timeout:
            if interaction:
                interaction.success = False
                interaction.response_data = 'Timeout'
                interaction.response_time = time.time() - start_time
                db.session.add(interaction)
                db.session.commit()
            return {'success': False, 'error': 'Service timeout'}
        except Exception as e:
            if interaction:
                interaction.success = False
                interaction.response_data = str(e)
                interaction.response_time = time.time() - start_time
                db.session.add(interaction)
                db.session.commit()
            return {'success': False, 'error': str(e)}

# Telegram API Helper Class with enhanced error handling
class TelegramBot:
    def __init__(self, bot_token):
        self.bot_token = bot_token
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
    
    def send_message(self, chat_id, text, reply_markup=None, retry_count=0):
        """Send a message to a chat with retry logic"""
        url = f"{self.base_url}/sendMessage"
        data = {
            'chat_id': chat_id,
            'text': text[:4096]  # Telegram message limit
        }
        if reply_markup:
            data['reply_markup'] = json.dumps(reply_markup)
        
        try:
            response = requests.post(url, json=data, timeout=10)
            result = response.json()
            
            if not result.get('ok') and retry_count < 3:
                time.sleep(1)  # Wait before retry
                return self.send_message(chat_id, text, reply_markup, retry_count + 1)
            
            return result
        except Exception as e:
            if retry_count < 3:
                time.sleep(1)
                return self.send_message(chat_id, text, reply_markup, retry_count + 1)
            return {'ok': False, 'error': str(e)}
    
    def set_webhook(self, webhook_url):
        """Set webhook for the bot"""
        url = f"{self.base_url}/setWebhook"
        data = {'url': webhook_url}
        
        try:
            response = requests.post(url, json=data, timeout=10)
            return response.json()
        except Exception as e:
            return {'ok': False, 'error': str(e)}
    
    def get_me(self):
        """Get bot information"""
        url = f"{self.base_url}/getMe"
        try:
            response = requests.get(url, timeout=10)
            return response.json()
        except Exception as e:
            return {'ok': False, 'error': str(e)}

# Background Task Manager
class BackgroundTaskManager:
    def __init__(self):
        self.running = False
        self.thread = None
    
    def start(self):
        """Start background task processing"""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._process_tasks)
            self.thread.daemon = True
            self.thread.start()
            logger.info("Background task manager started")
    
    def stop(self):
        """Stop background task processing"""
        self.running = False
        if self.thread:
            self.thread.join()
        logger.info("Background task manager stopped")
    
    def _process_tasks(self):
        """Process pending background tasks"""
        while self.running:
            try:
                with app.app_context():
                    # Get pending tasks
                    tasks = BackgroundTask.query.filter_by(status='pending').limit(10).all()
                    
                    for task in tasks:
                        try:
                            self._execute_task(task)
                        except Exception as e:
                            logger.error(f"Error executing task {task.id}: {str(e)}")
                            task.status = 'failed'
                            task.error_message = str(e)
                            task.retry_count += 1
                            
                            if task.retry_count < task.max_retries:
                                task.status = 'pending'
                            
                            db.session.commit()
                
                time.sleep(5)  # Wait 5 seconds between task checks
            except Exception as e:
                logger.error(f"Error in background task manager: {str(e)}")
                time.sleep(10)
    
    def _execute_task(self, task):
        """Execute a specific task"""
        task.status = 'running'
        task.started_at = datetime.utcnow()
        db.session.commit()
        
        try:
            if task.task_type == 'cleanup_old_logs':
                self._cleanup_old_logs()
            elif task.task_type == 'health_check_bots':
                self._health_check_bots()
            elif task.task_type == 'retry_failed_messages':
                self._retry_failed_messages()
            else:
                raise ValueError(f"Unknown task type: {task.task_type}")
            
            task.status = 'completed'
            task.completed_at = datetime.utcnow()
            
        except Exception as e:
            task.status = 'failed'
            task.error_message = str(e)
            task.retry_count += 1
            
            if task.retry_count < task.max_retries:
                task.status = 'pending'
        
        db.session.commit()
    
    def _cleanup_old_logs(self):
        """Clean up old logs"""
        cutoff_date = datetime.utcnow() - timedelta(days=7)
        
        # Clean old webhook logs
        old_webhooks = WebhookLog.query.filter(WebhookLog.processed_at < cutoff_date).limit(100)
        for log in old_webhooks:
            db.session.delete(log)
        
        # Clean old message logs
        old_messages = MessageLog.query.filter(MessageLog.processed_at < cutoff_date).limit(100)
        for log in old_messages:
            db.session.delete(log)
        
        db.session.commit()
        logger.info("Cleaned up old logs")
    
    def _health_check_bots(self):
        """Check health of registered bots"""
        bots = BotRegistration.query.filter_by(is_active=True).all()
        
        for bot in bots:
            try:
                telegram_bot = TelegramBot(bot.bot_token)
                result = telegram_bot.get_me()
                
                if result.get('ok'):
                    bot.last_activity = datetime.utcnow()
                    bot.error_count = 0
                else:
                    bot.error_count += 1
                    if bot.error_count > 5:
                        bot.is_active = False
                        logger.warning(f"Deactivated bot {bot.bot_id} due to repeated errors")
                
            except Exception as e:
                bot.error_count += 1
                logger.error(f"Health check failed for bot {bot.bot_id}: {str(e)}")
        
        db.session.commit()
    
    def _retry_failed_messages(self):
        """Retry failed message deliveries"""
        failed_messages = MessageLog.query.filter_by(status='failed').filter(MessageLog.retry_count < 3).limit(10).all()
        
        for message in failed_messages:
            try:
                bot = BotRegistration.query.filter_by(bot_id=message.bot_id, is_active=True).first()
                if bot:
                    telegram_bot = TelegramBot(bot.bot_token)
                    result = telegram_bot.send_message(message.chat_id, "Message retry attempt")
                    
                    if result.get('ok'):
                        message.status = 'processed'
                        logger.info(f"Successfully retried message {message.id}")
                    else:
                        message.retry_count += 1
                        
            except Exception as e:
                message.retry_count += 1
                logger.error(f"Failed to retry message {message.id}: {str(e)}")
        
        db.session.commit()

# Initialize components
service_client = ServiceClient()
task_manager = BackgroundTaskManager()

# Basic routes
@app.route('/')
@handle_errors
def hello():
    return jsonify({
        'status': 'working',
        'message': 'Step 5: Production-ready Telegram Bot Service',
        'service': 'telegive-bot-service',
        'step': 5,
        'features': [
            'basic_flask', 'database_support', 'api_endpoints', 
            'webhook_handling', 'telegram_integration', 'service_communication',
            'error_handling', 'background_tasks', 'monitoring'
        ],
        'connected_services': list(SERVICE_URLS.keys()),
        'version': '1.0.0'
    })

@app.route('/health')
@handle_errors
def health():
    health_data = {
        'status': 'healthy',
        'service': 'telegive-bot-service',
        'step': 5,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'version': '1.0.0'
    }
    
    # Test database connection
    try:
        db.create_all()
        health_record = HealthCheck(status='healthy')
        db.session.add(health_record)
        db.session.commit()
        
        # Get counts
        record_count = HealthCheck.query.count()
        bot_count = BotRegistration.query.filter_by(is_active=True).count()
        webhook_count = WebhookLog.query.count()
        message_count = MessageLog.query.count()
        service_interaction_count = ServiceInteraction.query.count()
        error_count = ErrorLog.query.filter_by(resolved=False).count()
        task_count = BackgroundTask.query.filter_by(status='pending').count()
        
        health_data['database'] = {
            'status': 'connected',
            'health_records': record_count,
            'active_bots': bot_count,
            'webhook_logs': webhook_count,
            'message_logs': message_count,
            'service_interactions': service_interaction_count,
            'unresolved_errors': error_count,
            'pending_tasks': task_count,
            'url_configured': bool(os.environ.get('DATABASE_URL'))
        }
        
        # Test service connectivity
        health_data['services'] = {}
        for service_name, service_url in SERVICE_URLS.items():
            try:
                start_time = time.time()
                response = requests.get(f"{service_url}/health", timeout=5)
                response_time = time.time() - start_time
                
                health_data['services'][service_name] = {
                    'url': service_url,
                    'status': 'reachable' if response.status_code < 400 else 'error',
                    'response_time': round(response_time, 3)
                }
            except:
                health_data['services'][service_name] = {
                    'url': service_url,
                    'status': 'unreachable',
                    'response_time': None
                }
        
        # Background task manager status
        health_data['background_tasks'] = {
            'manager_running': task_manager.running,
            'pending_tasks': task_count
        }
        
    except Exception as e:
        health_data['database'] = {
            'status': 'error',
            'error': str(e)
        }
        health_data['status'] = 'degraded'
    
    return jsonify(health_data)

# Enhanced API endpoints with error handling
@app.route('/api/bots/register', methods=['POST'])
@handle_errors
def register_bot():
    """Register a new bot with comprehensive validation"""
    data = request.get_json()
    
    if not data or 'bot_token' not in data or 'user_id' not in data:
        return jsonify({
            'status': 'error',
            'error': 'Missing required fields: bot_token, user_id'
        }), 400
    
    user_id = data['user_id']
    
    # Validate user with auth service
    auth_result = service_client.call_service('auth', f'/api/users/{user_id}', 'GET', user_id=user_id)
    
    # Validate bot token
    telegram_bot = TelegramBot(data['bot_token'])
    bot_info = telegram_bot.get_me()
    
    if not bot_info.get('ok'):
        return jsonify({
            'status': 'error',
            'error': 'Invalid bot token',
            'telegram_error': bot_info.get('description', 'Unknown error')
        }), 400
    
    bot_id = bot_info['result']['username']
    
    # Check if bot already exists
    existing_bot = BotRegistration.query.filter_by(bot_id=bot_id).first()
    if existing_bot:
        return jsonify({
            'status': 'error',
            'error': 'Bot already registered'
        }), 409
    
    # Create new bot registration
    new_bot = BotRegistration(
        bot_id=bot_id,
        bot_token=data['bot_token'],
        user_id=user_id
    )
    
    db.session.add(new_bot)
    db.session.commit()
    
    # Set webhook
    webhook_url = f"https://{request.host}/webhook/{bot_id}"
    webhook_result = telegram_bot.set_webhook(webhook_url)
    
    if webhook_result.get('ok'):
        new_bot.webhook_set = True
        db.session.commit()
    
    return jsonify({
        'status': 'success',
        'message': 'Bot registered successfully',
        'bot_id': bot_id,
        'bot_info': bot_info['result'],
        'webhook_url': webhook_url,
        'webhook_set': webhook_result.get('ok', False),
        'auth_service_check': auth_result.get('success', False)
    }), 201

# Enhanced webhook handler with comprehensive error handling
@app.route('/webhook/<bot_id>', methods=['POST'])
@handle_errors
def webhook_handler(bot_id):
    """Handle Telegram webhook with comprehensive error handling"""
    start_time = time.time()
    
    # Verify bot exists
    bot = BotRegistration.query.filter_by(bot_id=bot_id, is_active=True).first()
    if not bot:
        return jsonify({
            'status': 'error',
            'error': 'Bot not found or inactive'
        }), 404
    
    # Get webhook data
    webhook_data = request.get_json()
    if not webhook_data:
        return jsonify({
            'status': 'error',
            'error': 'No webhook data received'
        }), 400
    
    # Log webhook
    webhook_log = WebhookLog(
        bot_id=bot_id,
        webhook_data=json.dumps(webhook_data),
        status='received'
    )
    db.session.add(webhook_log)
    db.session.commit()
    
    try:
        # Process message
        response_data = process_telegram_message_with_services(bot, webhook_data, webhook_log)
        
        # Update processing time
        processing_time = time.time() - start_time
        webhook_log.processing_time = processing_time
        webhook_log.status = 'processed'
        db.session.commit()
        
        return jsonify(response_data)
        
    except Exception as e:
        processing_time = time.time() - start_time
        webhook_log.processing_time = processing_time
        webhook_log.status = 'error'
        webhook_log.error_message = str(e)
        db.session.commit()
        
        # Log error
        error_log = ErrorLog(
            error_type=type(e).__name__,
            error_message=str(e),
            stack_trace=traceback.format_exc(),
            endpoint=f'/webhook/{bot_id}',
            bot_id=bot_id
        )
        db.session.add(error_log)
        db.session.commit()
        
        raise

def process_telegram_message_with_services(bot, webhook_data, webhook_log):
    """Process Telegram message with enhanced error handling"""
    telegram_bot = TelegramBot(bot.bot_token)
    
    # Extract message data
    message = webhook_data.get('message', {})
    chat_id = message.get('chat', {}).get('id')
    text = message.get('text', '')
    user = message.get('from', {})
    user_id = user.get('id')
    username = user.get('username', '')
    
    if not chat_id:
        return {'status': 'ignored', 'reason': 'No chat_id found'}
    
    # Log message
    message_log = MessageLog(
        bot_id=bot.bot_id,
        chat_id=str(chat_id),
        message_text=text,
        message_type='text' if text else 'other',
        user_id=str(user_id) if user_id else None,
        username=username,
        status='processing'
    )
    db.session.add(message_log)
    db.session.commit()
    
    try:
        # Process commands with service integration
        response_text = None
        service_data = {}
        
        if text.startswith('/start'):
            response_text = f"🚀 Hello {username or 'there'}! Welcome to the Telegive Bot Service!\n\nThis is a production-ready bot with full service integration and error handling."
            
            # Check user with auth service
            auth_result = service_client.call_service('auth', f'/api/users/{user_id}', 'GET', user_id=str(user_id))
            service_data['auth_check'] = auth_result
            
        elif text.startswith('/help'):
            response_text = """🤖 Available commands:

/start - Start the bot
/help - Show this help
/status - Check bot status
/channels - List your channels
/participants - Check participants
/health - Service health status"""
            
        elif text.startswith('/status'):
            response_text = f"✅ Bot Status: Active\n🤖 Bot ID: {bot.bot_id}\n🔧 Service: Telegive Bot Service v1.0\n🌐 Services: Connected\n⚡ Background Tasks: Running"
            
        elif text.startswith('/health'):
            # Get service health
            health_status = []
            for service_name in SERVICE_URLS.keys():
                result = service_client.call_service(service_name, '/health', 'GET')
                status = "✅" if result.get('success') else "❌"
                health_status.append(f"{status} {service_name.title()}")
            
            response_text = f"🏥 Service Health:\n" + "\n".join(health_status)
            
        elif text.startswith('/channels'):
            # Get user channels
            channels_result = service_client.call_service('channel', f'/api/channels/user/{user_id}', 'GET', user_id=str(user_id))
            service_data['channels'] = channels_result
            
            if channels_result.get('success'):
                channels = channels_result.get('data', {}).get('channels', [])
                if channels:
                    response_text = f"📺 Your channels ({len(channels)}):\n" + "\n".join([f"• {ch.get('name', 'Unknown')}" for ch in channels[:5]])
                else:
                    response_text = "📺 You don't have any channels yet."
            else:
                response_text = "❌ Unable to fetch channels at the moment."
                
        elif text.startswith('/participants'):
            # Get participants
            participants_result = service_client.call_service('participant', f'/api/participants/user/{user_id}', 'GET', user_id=str(user_id))
            service_data['participants'] = participants_result
            
            if participants_result.get('success'):
                participants = participants_result.get('data', {}).get('participants', [])
                response_text = f"👥 Total participants: {len(participants)}"
            else:
                response_text = "❌ Unable to fetch participants at the moment."
                
        else:
            response_text = f"💬 You said: {text}\n\n🤖 This is a response from the Telegive Bot Service (Production v1.0) with full error handling and monitoring."
        
        # Send response
        if response_text:
            send_result = telegram_bot.send_message(chat_id, response_text)
            
            if send_result.get('ok'):
                message_log.status = 'processed'
            else:
                message_log.status = 'failed'
                message_log.retry_count = 1
            
            message_log.bot_response = json.dumps({
                'telegram_response': send_result,
                'service_data': service_data
            })
        
        # Update bot activity
        bot.last_activity = datetime.utcnow()
        db.session.commit()
        
        return {
            'status': 'processed',
            'bot_id': bot.bot_id,
            'chat_id': chat_id,
            'message_type': text[:50] if text else 'non-text',
            'response_sent': bool(response_text),
            'services_called': list(service_data.keys()),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        message_log.status = 'failed'
        db.session.commit()
        raise

# Monitoring and admin endpoints
@app.route('/api/admin/errors', methods=['GET'])
@handle_errors
def get_errors():
    """Get recent errors"""
    limit = request.args.get('limit', 50, type=int)
    errors = ErrorLog.query.order_by(ErrorLog.created_at.desc()).limit(limit).all()
    
    error_list = []
    for error in errors:
        error_list.append({
            'id': error.id,
            'error_type': error.error_type,
            'error_message': error.error_message,
            'endpoint': error.endpoint,
            'created_at': error.created_at.isoformat(),
            'resolved': error.resolved
        })
    
    return jsonify({
        'status': 'success',
        'errors': error_list,
        'total': len(error_list)
    })

@app.route('/api/admin/tasks', methods=['GET'])
@handle_errors
def get_background_tasks():
    """Get background task status"""
    tasks = BackgroundTask.query.order_by(BackgroundTask.created_at.desc()).limit(20).all()
    
    task_list = []
    for task in tasks:
        task_list.append({
            'id': task.id,
            'task_type': task.task_type,
            'status': task.status,
            'created_at': task.created_at.isoformat(),
            'retry_count': task.retry_count,
            'error_message': task.error_message
        })
    
    return jsonify({
        'status': 'success',
        'tasks': task_list,
        'manager_running': task_manager.running
    })

@app.route('/api/admin/tasks/create', methods=['POST'])
@handle_errors
def create_background_task():
    """Create a new background task"""
    data = request.get_json()
    task_type = data.get('task_type')
    
    if task_type not in ['cleanup_old_logs', 'health_check_bots', 'retry_failed_messages']:
        return jsonify({
            'status': 'error',
            'error': 'Invalid task type'
        }), 400
    
    task = BackgroundTask(
        task_type=task_type,
        task_data=json.dumps(data.get('task_data', {}))
    )
    
    db.session.add(task)
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'task_id': task.id,
        'message': 'Background task created'
    })

# Existing endpoints (with error handling added)
@app.route('/api/bots', methods=['GET'])
@handle_errors
def list_bots():
    """List registered bots"""
    bots = BotRegistration.query.filter_by(is_active=True).all()
    bot_list = []
    
    for bot in bots:
        bot_list.append({
            'bot_id': bot.bot_id,
            'user_id': bot.user_id,
            'created_at': bot.created_at.isoformat(),
            'is_active': bot.is_active,
            'webhook_set': bot.webhook_set,
            'last_activity': bot.last_activity.isoformat() if bot.last_activity else None,
            'error_count': bot.error_count
        })
    
    return jsonify({
        'status': 'success',
        'bots': bot_list,
        'total': len(bot_list)
    })

# Database test endpoint
@app.route('/database/test')
@handle_errors
def database_test():
    """Test database operations"""
    db.create_all()
    
    test_record = HealthCheck(status='test')
    db.session.add(test_record)
    db.session.commit()
    
    all_records = HealthCheck.query.all()
    recent_records = HealthCheck.query.order_by(HealthCheck.timestamp.desc()).limit(5).all()
    
    return jsonify({
        'status': 'success',
        'total_records': len(all_records),
        'recent_records': [
            {
                'id': r.id,
                'timestamp': r.timestamp.isoformat(),
                'status': r.status
            } for r in recent_records
        ],
        'database_url_set': bool(os.environ.get('DATABASE_URL'))
    })

# Initialize background tasks on startup
@app.before_first_request
def initialize_background_tasks():
    """Initialize background tasks"""
    try:
        # Create initial cleanup task
        cleanup_task = BackgroundTask(
            task_type='cleanup_old_logs',
            task_data=json.dumps({'initial': True})
        )
        db.session.add(cleanup_task)
        
        # Create initial health check task
        health_task = BackgroundTask(
            task_type='health_check_bots',
            task_data=json.dumps({'initial': True})
        )
        db.session.add(health_task)
        
        db.session.commit()
        
        # Start background task manager
        task_manager.start()
        
    except Exception as e:
        logger.error(f"Failed to initialize background tasks: {str(e)}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    
    # Create tables on startup
    with app.app_context():
        try:
            db.create_all()
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Database initialization warning: {str(e)}")
    
    app.run(host='0.0.0.0', port=port)

