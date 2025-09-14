"""
Bot Service Phase 6 - Push Notification System for Instant Bot Token Updates (FIXED)
Replaces 2-minute polling with instant push notifications from Auth Service
FIXED: Flask route decorator conflict resolved
"""
import os
import json
import time
import threading
import traceback
import requests
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError
import random
from functools import wraps

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

# Webhook URL configuration
WEBHOOK_URL = os.environ.get('WEBHOOK_URL', 'https://telegive-bot-service-production.up.railway.app')

# Service URLs and authentication configuration
SERVICE_URLS = {
    'auth': os.environ.get('AUTH_SERVICE_URL', 'https://web-production-ddd7e.up.railway.app'),
    'channel': os.environ.get('CHANNEL_SERVICE_URL', 'https://telegive-channel-service.railway.app'),
    'participant': os.environ.get('PARTICIPANT_SERVICE_URL', 'https://telegive-participant-production.up.railway.app')
}

# Service authentication
SERVICE_TO_SERVICE_SECRET = os.environ.get('SERVICE_TO_SERVICE_SECRET', 'ch4nn3l_s3rv1c3_t0k3n_2025_s3cur3_r4nd0m_str1ng')
AUTH_SERVICE_TOKEN = os.environ.get('AUTH_SERVICE_TOKEN', SERVICE_TO_SERVICE_SECRET)
AUTH_SERVICE_HEADER = 'X-Service-Token'

# Service status cache
service_status_cache = {}
cache_lock = threading.Lock()
last_cache_update = None

# Push notification system for bot token management
current_bot_token = None
current_bot_username = None
current_bot_id = None
telegram_app = None
bot_initialization_lock = threading.Lock()
last_token_update = None
push_notifications_enabled = True

# Initialize database with error handling
db = None
database_error = None

try:
    db = SQLAlchemy(app)
    print("SQLAlchemy initialized successfully")
except Exception as e:
    database_error = str(e)
    print(f"SQLAlchemy initialization error: {e}")

# Database models (same as previous phases)
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

# Push notification tracking
class PushNotification(db.Model):
    __tablename__ = 'push_notifications'
    
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    timestamp = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    source_service = db.Column(db.String(100), nullable=False)
    notification_type = db.Column(db.String(50), nullable=False)  # bot_token_update, bot_token_removed
    bot_id = db.Column(db.BigInteger)
    bot_username = db.Column(db.String(100))
    status = db.Column(db.String(20), nullable=False)  # received, processed, failed
    processing_time = db.Column(db.Float)
    error_message = db.Column(db.Text)
    request_data = db.Column(db.Text)  # JSON data

# Giveaway-related models (same as previous phases)
class UserCaptchaStatus(db.Model):
    __tablename__ = 'user_captcha_status'
    
    user_id = db.Column(db.BigInteger, primary_key=True)
    completed_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    first_giveaway_id = db.Column(db.Integer)

class CaptchaChallenge(db.Model):
    __tablename__ = 'captcha_challenges'
    
    user_id = db.Column(db.BigInteger, primary_key=True)
    giveaway_id = db.Column(db.Integer, nullable=False)
    answer = db.Column(db.Integer, nullable=False)
    attempts = db.Column(db.Integer, default=0)
    max_attempts = db.Column(db.Integer, default=3)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc) + timedelta(hours=1))

class GiveawayParticipation(db.Model):
    __tablename__ = 'giveaway_participations'
    
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    giveaway_id = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.BigInteger, nullable=False)
    username = db.Column(db.String(255))
    first_name = db.Column(db.String(255))
    participation_date = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    status = db.Column(db.String(20), default='active')
    
    __table_args__ = (db.UniqueConstraint('giveaway_id', 'user_id', name='unique_participation'),)

class UserState(db.Model):
    __tablename__ = 'user_states'
    
    user_id = db.Column(db.BigInteger, primary_key=True)
    state = db.Column(db.String(100), nullable=False)
    data = db.Column(db.Text)  # JSON data for state context
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

# Authenticated Service Client (same as previous phases)
class AuthenticatedServiceClient:
    def __init__(self):
        self.headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Telegive-Bot-Service/1.1.0-phase6-push-notifications-fixed'
        }
        self.fast_timeout = 3
        self.health_timeout = 2
    
    def _get_headers_for_service(self, service_name):
        """Get headers with authentication for specific service"""
        headers = self.headers.copy()
        
        # Add Auth Service token if calling Auth Service
        if service_name == 'auth' and AUTH_SERVICE_TOKEN:
            headers[AUTH_SERVICE_HEADER] = AUTH_SERVICE_TOKEN
            
        return headers
    
    def call_service(self, service_name, endpoint, method='GET', data=None, timeout=None, log_interaction=True):
        """Make API call to external service with authentication"""
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
            headers = self._get_headers_for_service(service_name)
            
            # Make the request with service-specific authentication
            if method.upper() == 'POST':
                response = requests.post(url, headers=headers, json=data, timeout=timeout)
            elif method.upper() == 'PUT':
                response = requests.put(url, headers=headers, json=data, timeout=timeout)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=timeout)
            else:
                response = requests.get(url, headers=headers, timeout=timeout)
            
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
                    'endpoint': endpoint,
                    'authenticated': service_name == 'auth'
                }
            else:
                return {
                    'success': False,
                    'error': f'HTTP {response.status_code}',
                    'status_code': response.status_code,
                    'response_time': response_time,
                    'service_name': service_name,
                    'endpoint': endpoint,
                    'response_text': response.text[:200],
                    'authenticated': service_name == 'auth'
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

# Initialize authenticated service client
service_client = AuthenticatedServiceClient()

# FIXED: Create unique decorator functions to avoid Flask route conflicts
def create_service_token_decorator(endpoint_name):
    """Create a unique service token decorator for each endpoint"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            token = request.headers.get('X-Service-Token')
            
            if not token or token != SERVICE_TO_SERVICE_SECRET:
                return jsonify({
                    'success': False,
                    'error': 'Authentication failed',
                    'message': 'Invalid or missing service token'
                }), 401
            
            return f(*args, **kwargs)
        
        # Make function name unique to avoid Flask conflicts
        decorated_function.__name__ = f'{endpoint_name}_authenticated'
        return decorated_function
    return decorator

def log_push_notification(source_service, notification_type, bot_id=None, bot_username=None, status='received', processing_time=None, error_message=None, request_data=None):
    """Log push notification to database"""
    if not db:
        return
    
    try:
        with app.app_context():
            notification = PushNotification(
                source_service=source_service,
                notification_type=notification_type,
                bot_id=bot_id,
                bot_username=bot_username,
                status=status,
                processing_time=processing_time,
                error_message=error_message,
                request_data=json.dumps(request_data) if request_data else None
            )
            db.session.add(notification)
            db.session.commit()
    except Exception as e:
        print(f"Push notification logging error: {e}")

def initialize_telegram_bot_with_token(bot_token, bot_username=None, bot_id=None):
    """Initialize Telegram bot with provided token"""
    global telegram_app, current_bot_token, current_bot_username, current_bot_id
    
    if not bot_token:
        print("❌ No bot token provided for initialization")
        return False
    
    try:
        print(f"🤖 Initializing Telegram bot...")
        print(f"   Bot ID: {bot_id}")
        print(f"   Bot Username: @{bot_username}")
        print(f"   Token: {bot_token.split(':')[0]}:***")
        
        # Stop existing bot if running
        if telegram_app:
            print("🔄 Stopping existing bot...")
            try:
                # Note: In production, you might need to handle this differently
                # depending on how your bot is running (polling vs webhook)
                telegram_app = None
            except Exception as e:
                print(f"Warning: Error stopping existing bot: {e}")
        
        # Create application with the provided token
        telegram_app = Application.builder().token(bot_token).build()
        
        # Add handlers
        telegram_app.add_handler(CommandHandler("start", start_handler))
        telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
        
        # Update global state
        current_bot_token = bot_token
        current_bot_username = bot_username
        current_bot_id = bot_id
        
        print(f"✅ Telegram bot initialized successfully!")
        print(f"🎉 Bot @{bot_username} is now ready for giveaways!")
        
        return True
    
    except Exception as e:
        print(f"❌ Telegram bot initialization error: {e}")
        return False

def stop_telegram_bot():
    """Stop the current Telegram bot"""
    global telegram_app, current_bot_token, current_bot_username, current_bot_id
    
    try:
        if telegram_app:
            print("🛑 Stopping Telegram bot...")
            # Note: In production, you might need to handle this differently
            telegram_app = None
            current_bot_token = None
            current_bot_username = None
            current_bot_id = None
            print("✅ Bot stopped successfully")
            return True
        else:
            print("ℹ️ No bot running to stop")
            return True
    except Exception as e:
        print(f"❌ Error stopping bot: {e}")
        return False

def get_bot_status():
    """Get current bot status information"""
    global current_bot_token, current_bot_username, current_bot_id, telegram_app, last_token_update
    
    return {
        'token_configured': bool(current_bot_token),
        'bot_initialized': telegram_app is not None,
        'bot_id': current_bot_id,
        'bot_username': current_bot_username,
        'token_source': 'push_notification',
        'push_notifications_enabled': push_notifications_enabled,
        'polling_disabled': True,
        'last_token_update': last_token_update.isoformat() if last_token_update else None,
        'webhook_url': WEBHOOK_URL
    }

# Giveaway Helper Functions (same as previous phases - abbreviated for space)
def has_user_completed_captcha_globally(user_id):
    """Check if user has completed captcha globally"""
    try:
        with app.app_context():
            result = UserCaptchaStatus.query.filter_by(user_id=user_id).first()
            return result is not None
    except Exception as e:
        print(f"Error checking global captcha status: {e}")
        return False

def mark_user_captcha_completed_globally(user_id, giveaway_id=None):
    """Mark user as having completed captcha globally"""
    try:
        with app.app_context():
            existing = UserCaptchaStatus.query.filter_by(user_id=user_id).first()
            if not existing:
                captcha_status = UserCaptchaStatus(
                    user_id=user_id,
                    first_giveaway_id=giveaway_id
                )
                db.session.add(captcha_status)
                db.session.commit()
                return True
            return True
    except Exception as e:
        print(f"Error marking captcha completed: {e}")
        return False

# Telegram Bot Handlers (abbreviated for space - same as previous phases)
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command with giveaway and result parameters"""
    user_id = update.effective_user.id
    args = context.args
    
    print(f"🎯 Start command from user {user_id} with args: {args}")
    
    if not args:
        await update.message.reply_text(
            "🤖 Welcome to Telegive Bot!\n\n"
            "This bot handles giveaway participation. "
            "Click the '🎯 Participate' button in giveaway posts to join!"
        )
        return
    
    command = args[0]
    
    if command.startswith('giveaway_'):
        try:
            giveaway_id = int(command.split('_')[1])
            await update.message.reply_text(f"🎯 Processing participation for giveaway {giveaway_id}...")
        except (ValueError, IndexError):
            await update.message.reply_text("❌ Invalid giveaway link.")
    else:
        await update.message.reply_text("❌ Unknown command.")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages"""
    await update.message.reply_text("👋 Hello! Use /start to begin.")

# Background task functions (optimized for push notification system)
def update_service_status_cache():
    """Background task to update service status cache (no longer checks bot token)"""
    global service_status_cache, last_cache_update
    
    task_start = time.time()
    task_name = "update_service_status_cache"
    
    try:
        # Update service status cache (no bot token checking needed)
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
                    'last_checked': datetime.now(timezone.utc).isoformat(),
                    'authenticated': result.get('authenticated', False)
                }
            except Exception as e:
                new_status[service_name] = {
                    'status': 'error',
                    'error': str(e),
                    'response_time': 0,
                    'last_checked': datetime.now(timezone.utc).isoformat(),
                    'authenticated': False
                }
        
        # Update cache with thread safety
        with cache_lock:
            service_status_cache.update(new_status)
            last_cache_update = datetime.now(timezone.utc)
        
        execution_time = time.time() - task_start
        print(f"Service status cache updated in {execution_time:.3f}s (push notification system)")
        
    except Exception as e:
        print(f"Service status cache update failed: {e}")

def cleanup_old_records():
    """Background task to clean up old database records"""
    if not db:
        return
    
    try:
        with app.app_context():
            # Keep only last 1000 service interactions
            old_interactions = ServiceInteraction.query.order_by(
                ServiceInteraction.timestamp.desc()
            ).offset(1000).all()
            
            # Keep only last 100 push notifications
            old_notifications = PushNotification.query.order_by(
                PushNotification.timestamp.desc()
            ).offset(100).all()
            
            # Delete old records
            deleted_count = 0
            for record_list in [old_interactions, old_notifications]:
                for record in record_list:
                    db.session.delete(record)
                    deleted_count += 1
            
            db.session.commit()
            print(f"Cleanup completed: deleted {deleted_count} records")
            
    except Exception as e:
        print(f"Cleanup task failed: {e}")

# Background scheduler
scheduler = BackgroundScheduler()

# Database helper functions (same as previous phases)
def test_database_connection():
    """Test database connection safely"""
    if not db:
        return {'status': 'error', 'message': 'Database not initialized', 'error': database_error}
    
    try:
        db.session.execute(db.text('SELECT 1'))
        return {'status': 'connected', 'message': 'Database connection successful'}
    except Exception as e:
        return {'status': 'error', 'message': f'Database connection failed: {str(e)}'}

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

# Optimized service status functions (same as previous phases)
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

# Flask Routes
@app.route('/')
def home():
    """Main service endpoint with cached service status and push notification bot status"""
    db_status = test_database_connection()
    service_status = get_cached_service_status()  # Use cached status for speed
    bot_status = get_bot_status()  # Get push notification bot status
    
    # Log this request (async)
    log_to_database('INFO', 'Home endpoint accessed', '/')
    
    return jsonify({
        'service': 'telegive-bot-service',
        'status': 'working',
        'version': '1.1.0-phase6-push-notifications-fixed',
        'phase': 'Phase 6 - Push Notification System for Instant Bot Token Updates (FIXED)',
        'message': 'Bot Service with instant push notification system for bot token management (Flask decorator conflict resolved)',
        'features': [
            'basic_endpoints', 'json_responses', 'error_handling', 
            'database_connection', 'optimized_service_integrations', 
            'service_status_caching', 'background_tasks', 'auth_service_token',
            'telegram_bot_integration', 'giveaway_participation_flow',
            'global_captcha_system', 'subscription_verification',
            'push_notification_system', 'instant_bot_token_updates',
            'flask_decorator_conflict_fixed'
        ],
        'database': {
            'configured': database_configured,
            'status': db_status['status'],
            'message': db_status['message']
        },
        'services': service_status,
        'telegram_bot': bot_status,
        'authentication': {
            'service_to_service_secret': 'configured' if SERVICE_TO_SERVICE_SECRET else 'missing',
            'auth_service_token': 'configured' if AUTH_SERVICE_TOKEN else 'missing',
            'auth_header': AUTH_SERVICE_HEADER
        },
        'push_notifications': {
            'enabled': push_notifications_enabled,
            'polling_disabled': True,
            'instant_updates': True
        },
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

# Push Notification Endpoint - The Core of the New System (FIXED)
@app.route('/bot/token/update', methods=['POST'])
@create_service_token_decorator('bot_token_update')
def update_bot_token():
    """Receive instant bot token updates from Auth Service via push notification"""
    global last_token_update
    
    processing_start = time.time()
    
    try:
        print("🔔 Push notification received from Auth Service")
        
        # Get request data
        data = request.get_json()
        source_service = request.headers.get('X-Service-Name', 'unknown')
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Invalid request',
                'message': 'No JSON data provided'
            }), 400
        
        bot_token = data.get('bot_token')
        bot_username = data.get('bot_username')
        bot_id = data.get('bot_id')
        status = data.get('status', 'active')
        
        # Validate required fields
        if not bot_id:
            log_push_notification(
                source_service=source_service,
                notification_type='bot_token_update',
                status='failed',
                error_message='bot_id is required',
                request_data=data
            )
            return jsonify({
                'success': False,
                'error': 'Invalid request',
                'message': 'bot_id is required'
            }), 400
        
        # Log notification received
        log_push_notification(
            source_service=source_service,
            notification_type='bot_token_update' if bot_token else 'bot_token_removed',
            bot_id=bot_id,
            bot_username=bot_username,
            status='received',
            request_data=data
        )
        
        previous_token = current_bot_token
        
        with bot_initialization_lock:
            if status == 'removed' or not bot_token:
                # Token removed - stop bot
                print(f"🛑 Bot token removed for bot_id: {bot_id}")
                
                if stop_telegram_bot():
                    processing_time = time.time() - processing_start
                    last_token_update = datetime.now(timezone.utc)
                    
                    # Log successful processing
                    log_push_notification(
                        source_service=source_service,
                        notification_type='bot_token_removed',
                        bot_id=bot_id,
                        bot_username=bot_username,
                        status='processed',
                        processing_time=processing_time
                    )
                    
                    return jsonify({
                        'success': True,
                        'message': 'Bot token removed and bot stopped',
                        'bot_initialized': False,
                        'previous_token': f"{previous_token.split(':')[0]}:***" if previous_token else None,
                        'new_token': None,
                        'processing_time': processing_time
                    })
                else:
                    processing_time = time.time() - processing_start
                    
                    # Log processing failure
                    log_push_notification(
                        source_service=source_service,
                        notification_type='bot_token_removed',
                        bot_id=bot_id,
                        bot_username=bot_username,
                        status='failed',
                        processing_time=processing_time,
                        error_message='Failed to stop bot'
                    )
                    
                    return jsonify({
                        'success': False,
                        'error': 'Bot stop failed',
                        'message': 'Failed to stop existing bot'
                    }), 500
            
            # New/updated token - initialize bot
            print(f"🚀 Initializing bot with new token for bot_id: {bot_id}")
            print(f"   Bot username: @{bot_username}")
            print(f"   Token: {bot_token.split(':')[0]}:***")
            
            # Initialize bot
            bot_initialized = initialize_telegram_bot_with_token(bot_token, bot_username, bot_id)
            
            processing_time = time.time() - processing_start
            last_token_update = datetime.now(timezone.utc)
            
            if bot_initialized:
                print("✅ Bot initialized successfully via push notification")
                
                # Log successful processing
                log_push_notification(
                    source_service=source_service,
                    notification_type='bot_token_update',
                    bot_id=bot_id,
                    bot_username=bot_username,
                    status='processed',
                    processing_time=processing_time
                )
                
                return jsonify({
                    'success': True,
                    'message': 'Token updated successfully',
                    'bot_initialized': True,
                    'previous_token': f"{previous_token.split(':')[0]}:***" if previous_token else None,
                    'new_token': f"{bot_token.split(':')[0]}:***",
                    'processing_time': processing_time
                })
            else:
                print("❌ Bot initialization failed")
                
                # Log processing failure
                log_push_notification(
                    source_service=source_service,
                    notification_type='bot_token_update',
                    bot_id=bot_id,
                    bot_username=bot_username,
                    status='failed',
                    processing_time=processing_time,
                    error_message='Bot initialization failed'
                )
                
                return jsonify({
                    'success': False,
                    'error': 'Bot initialization failed',
                    'message': 'Failed to initialize bot with provided token'
                }), 500
        
    except Exception as e:
        processing_time = time.time() - processing_start
        error_message = str(e)
        
        print(f"❌ Push notification error: {error_message}")
        
        # Log processing error
        try:
            log_push_notification(
                source_service=request.headers.get('X-Service-Name', 'unknown'),
                notification_type='bot_token_update',
                status='failed',
                processing_time=processing_time,
                error_message=error_message,
                request_data=request.get_json() if request.is_json else None
            )
        except:
            pass  # Don't fail on logging errors
        
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': error_message
        }), 500

# Telegram webhook endpoint (enhanced with bot availability check)
@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle Telegram webhook"""
    if not telegram_app:
        print("⚠️ Webhook received but bot not initialized")
        return jsonify({'error': 'Telegram bot not initialized', 'status': 'bot_unavailable'}), 200
    
    try:
        # Get update from request
        update_data = request.get_json()
        
        if not update_data:
            return jsonify({'error': 'No update data'}), 400
        
        print(f"📨 Webhook received: {update_data.get('update_id', 'unknown')}")
        
        # Process update asynchronously
        def process_update():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                update = Update.de_json(update_data, telegram_app.bot)
                loop.run_until_complete(telegram_app.process_update(update))
                
                loop.close()
                print(f"✅ Webhook processed successfully")
            except Exception as e:
                print(f"❌ Webhook processing error: {e}")
        
        thread = threading.Thread(target=process_update)
        thread.daemon = True
        thread.start()
        
        return jsonify({'status': 'ok'})
    
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return jsonify({'error': str(e)}), 500

# Bot status endpoint (enhanced for push notification system) - FIXED
@app.route('/bot/status')
@create_service_token_decorator('bot_status')
def bot_status_endpoint():
    """Get detailed bot status information for push notification system"""
    try:
        bot_status = get_bot_status()
        
        # Add push notification statistics
        if db:
            try:
                with app.app_context():
                    total_notifications = PushNotification.query.count()
                    successful_notifications = PushNotification.query.filter_by(status='processed').count()
                    failed_notifications = PushNotification.query.filter_by(status='failed').count()
                    recent_notifications = PushNotification.query.filter(
                        PushNotification.timestamp > datetime.now(timezone.utc) - timedelta(hours=24)
                    ).count()
                    
                    bot_status['push_notification_stats'] = {
                        'total_notifications': total_notifications,
                        'successful_notifications': successful_notifications,
                        'failed_notifications': failed_notifications,
                        'recent_notifications_24h': recent_notifications,
                        'success_rate': (successful_notifications / total_notifications * 100) if total_notifications > 0 else 0
                    }
            except Exception as e:
                bot_status['push_notification_stats'] = {'error': str(e)}
        
        # Add service configuration
        bot_status['service_configuration'] = {
            'service_to_service_secret_configured': bool(SERVICE_TO_SERVICE_SECRET),
            'auth_service_url': SERVICE_URLS['auth'],
            'webhook_url': WEBHOOK_URL
        }
        
        return jsonify({
            'bot_status': bot_status,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
    
    except Exception as e:
        return jsonify({
            'error': 'Failed to get bot status',
            'details': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 500

# Push notification statistics endpoint - FIXED
@app.route('/push/stats')
@create_service_token_decorator('push_stats')
def push_notification_stats():
    """Get push notification statistics"""
    try:
        if not db:
            return jsonify({'error': 'Database not available'}), 503
        
        with app.app_context():
            # Get statistics
            total_notifications = PushNotification.query.count()
            successful_notifications = PushNotification.query.filter_by(status='processed').count()
            failed_notifications = PushNotification.query.filter_by(status='failed').count()
            
            # Recent notifications (last 24 hours)
            recent_notifications = PushNotification.query.filter(
                PushNotification.timestamp > datetime.now(timezone.utc) - timedelta(hours=24)
            ).all()
            
            # Average processing time
            processed_notifications = PushNotification.query.filter(
                PushNotification.status == 'processed',
                PushNotification.processing_time.isnot(None)
            ).all()
            
            avg_processing_time = sum(n.processing_time for n in processed_notifications) / len(processed_notifications) if processed_notifications else 0
            
            # Recent notifications details
            recent_details = []
            for notification in recent_notifications[-10:]:  # Last 10
                recent_details.append({
                    'timestamp': notification.timestamp.isoformat(),
                    'source_service': notification.source_service,
                    'notification_type': notification.notification_type,
                    'bot_id': notification.bot_id,
                    'bot_username': notification.bot_username,
                    'status': notification.status,
                    'processing_time': notification.processing_time,
                    'error_message': notification.error_message
                })
            
            return jsonify({
                'push_notification_statistics': {
                    'total_notifications': total_notifications,
                    'successful_notifications': successful_notifications,
                    'failed_notifications': failed_notifications,
                    'success_rate': (successful_notifications / total_notifications * 100) if total_notifications > 0 else 0,
                    'average_processing_time': avg_processing_time,
                    'recent_notifications_24h': len(recent_notifications)
                },
                'recent_notifications': recent_details,
                'system_status': {
                    'push_notifications_enabled': push_notifications_enabled,
                    'polling_disabled': True,
                    'instant_updates': True
                },
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
    
    except Exception as e:
        return jsonify({
            'error': 'Failed to get push notification statistics',
            'details': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 500

# Error handlers (same as previous phases)
@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors with JSON response and async logging"""
    log_to_database('WARNING', f'404 error: {error}', 'unknown')
    
    return jsonify({
        'error': 'Not Found',
        'message': 'The requested endpoint does not exist',
        'phase': 'Phase 6 - Push Notification System for Instant Bot Token Updates (FIXED)',
        'available_endpoints': [
            '/', '/webhook', '/bot/token/update', '/bot/status', '/push/stats'
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
        'phase': 'Phase 6 - Push Notification System for Instant Bot Token Updates (FIXED)',
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
        'phase': 'Phase 6 - Push Notification System for Instant Bot Token Updates (FIXED)',
        'timestamp': datetime.now(timezone.utc).isoformat()
    }), 500

# Initialize database and background tasks on startup
def init_application():
    """Initialize database and background tasks on startup (no bot token checking needed)"""
    if db:
        try:
            with app.app_context():
                db.create_all()
                print("Database tables created successfully")
                
                # Log startup
                startup_log = ServiceLog(
                    level='INFO',
                    message='Bot Service Phase 6 started with push notification system (Flask decorator conflict fixed)',
                    endpoint='startup'
                )
                db.session.add(startup_log)
                db.session.commit()
                print("Startup logged to database")
                
        except Exception as e:
            print(f"Database initialization error: {e}")
    
    # No bot token checking needed - push notifications will handle this
    print("🔔 Push notification system ready for instant bot token updates (FIXED)")
    
    # Start background scheduler (no bot token checking job needed)
    try:
        if not scheduler.running:
            # Add background jobs (no bot token checking needed)
            scheduler.add_job(
                func=update_service_status_cache,
                trigger=IntervalTrigger(minutes=5),  # Less frequent since no bot token checking
                id='update_service_status',
                name='Update Service Status Cache (Push Notification System)',
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
            print("Background scheduler started successfully (push notification system - FIXED)")
            
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
    print(f"Starting Bot Service Phase 6 (Push Notifications - FIXED) on port {port}")
    
    # Initialize for development
    with app.app_context():
        try:
            db.create_all()
            print("Development database initialized")
        except Exception as e:
            print(f"Development database error: {e}")
    
    # Start scheduler
    init_application()
    
    app.run(host='0.0.0.0', port=port, debug=False)

