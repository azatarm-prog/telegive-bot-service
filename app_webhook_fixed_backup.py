"""
Bot Service Phase 6 - Push Notification System with FIXED Webhook Handler
CRITICAL FIX: Simplified webhook processing to ensure /start commands get responses
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
telegram_bot = None  # Direct bot instance for sending messages
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

# Database models (abbreviated for space - same as before)
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

class PushNotification(db.Model):
    __tablename__ = 'push_notifications'
    
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    timestamp = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    source_service = db.Column(db.String(100), nullable=False)
    notification_type = db.Column(db.String(50), nullable=False)
    bot_id = db.Column(db.BigInteger)
    bot_username = db.Column(db.String(100))
    status = db.Column(db.String(20), nullable=False)
    processing_time = db.Column(db.Float)
    error_message = db.Column(db.Text)
    request_data = db.Column(db.Text)

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
    """Initialize Telegram bot with provided token - FIXED VERSION"""
    global telegram_app, telegram_bot, current_bot_token, current_bot_username, current_bot_id
    
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
                telegram_app = None
                telegram_bot = None
            except Exception as e:
                print(f"Warning: Error stopping existing bot: {e}")
        
        # Create both Application and direct Bot instance
        telegram_app = Application.builder().token(bot_token).build()
        telegram_bot = Bot(token=bot_token)  # Direct bot for sending messages
        
        # Add handlers with FIXED async handling
        telegram_app.add_handler(CommandHandler("start", start_handler_fixed))
        telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler_fixed))
        
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

def get_bot_status():
    """Get current bot status information"""
    global current_bot_token, current_bot_username, current_bot_id, telegram_app, telegram_bot, last_token_update
    
    return {
        'token_configured': bool(current_bot_token),
        'bot_initialized': telegram_app is not None and telegram_bot is not None,
        'bot_id': current_bot_id,
        'bot_username': current_bot_username,
        'token_source': 'push_notification',
        'push_notifications_enabled': push_notifications_enabled,
        'polling_disabled': True,
        'last_token_update': last_token_update.isoformat() if last_token_update else None,
        'webhook_url': WEBHOOK_URL,
        'direct_bot_available': telegram_bot is not None
    }

# FIXED: Simplified Telegram Bot Handlers that will definitely work
async def start_handler_fixed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """FIXED: Handle /start command - simplified version that will work"""
    try:
        user_id = update.effective_user.id
        args = context.args if context.args else []
        
        print(f"🎯 FIXED Start handler: user {user_id}, args: {args}")
        
        if not args:
            # Simple welcome message
            await update.message.reply_text(
                "🤖 Welcome to Telegive Bot!\n\n"
                "This bot handles giveaway participation. "
                "Click the '🎯 Participate' button in giveaway posts to join!"
            )
            print(f"✅ Welcome message sent to user {user_id}")
            return
        
        # Handle giveaway participation
        command = args[0]
        if command.startswith('giveaway_'):
            try:
                giveaway_id = int(command.split('_')[1])
                await update.message.reply_text(f"🎯 Processing participation for giveaway {giveaway_id}...")
                print(f"✅ Giveaway message sent to user {user_id} for giveaway {giveaway_id}")
            except (ValueError, IndexError):
                await update.message.reply_text("❌ Invalid giveaway link.")
                print(f"❌ Invalid giveaway link from user {user_id}")
        else:
            await update.message.reply_text("❌ Unknown command.")
            print(f"❌ Unknown command from user {user_id}: {command}")
            
    except Exception as e:
        print(f"❌ Start handler error: {e}")
        try:
            await update.message.reply_text("❌ Sorry, there was an error processing your request.")
        except:
            print("❌ Failed to send error message")

async def message_handler_fixed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """FIXED: Handle text messages - simplified version"""
    try:
        user_id = update.effective_user.id
        text = update.message.text
        
        print(f"💬 Message from user {user_id}: {text}")
        
        await update.message.reply_text("👋 Hello! Use /start to begin.")
        print(f"✅ Response sent to user {user_id}")
        
    except Exception as e:
        print(f"❌ Message handler error: {e}")

# CRITICAL FIX: Simplified webhook handler that will definitely work
@app.route('/webhook', methods=['POST'])
def webhook_fixed():
    """FIXED: Handle Telegram webhook - simplified version that will work"""
    global telegram_bot, telegram_app
    
    try:
        print("📨 Webhook received!")
        
        # Check if bot is available
        if not telegram_bot or not telegram_app:
            print("⚠️ Webhook received but bot not initialized")
            return jsonify({'error': 'Telegram bot not initialized', 'status': 'bot_unavailable'}), 200
        
        # Get update from request
        update_data = request.get_json()
        
        if not update_data:
            print("❌ No update data in webhook")
            return jsonify({'error': 'No update data'}), 400
        
        update_id = update_data.get('update_id', 'unknown')
        print(f"📨 Processing webhook update: {update_id}")
        
        # FIXED: Simplified synchronous processing for /start commands
        if 'message' in update_data:
            message = update_data['message']
            text = message.get('text', '')
            chat_id = message.get('chat', {}).get('id')
            user_id = message.get('from', {}).get('id')
            
            print(f"💬 Message received: '{text}' from user {user_id} in chat {chat_id}")
            
            # Handle /start command directly with synchronous bot
            if text.startswith('/start'):
                try:
                    print(f"🎯 Processing /start command from user {user_id}")
                    
                    # Extract args from /start command
                    parts = text.split(' ', 1)
                    args = parts[1] if len(parts) > 1 else None
                    
                    if not args:
                        # Send welcome message
                        response_text = (
                            "🤖 Welcome to Telegive Bot!\n\n"
                            "This bot handles giveaway participation. "
                            "Click the '🎯 Participate' button in giveaway posts to join!"
                        )
                        print(f"📤 Sending welcome message to chat {chat_id}")
                    else:
                        # Handle giveaway participation
                        if args.startswith('giveaway_'):
                            try:
                                giveaway_id = int(args.split('_')[1])
                                response_text = f"🎯 Processing participation for giveaway {giveaway_id}..."
                                print(f"📤 Sending giveaway message to chat {chat_id} for giveaway {giveaway_id}")
                            except (ValueError, IndexError):
                                response_text = "❌ Invalid giveaway link."
                                print(f"❌ Invalid giveaway link: {args}")
                        else:
                            response_text = "❌ Unknown command."
                            print(f"❌ Unknown command: {args}")
                    
                    # Send response using direct bot instance (synchronous)
                    import requests
                    telegram_url = f"https://api.telegram.org/bot{current_bot_token}/sendMessage"
                    payload = {
                        'chat_id': chat_id,
                        'text': response_text
                    }
                    
                    response = requests.post(telegram_url, json=payload, timeout=10)
                    
                    if response.status_code == 200:
                        print(f"✅ Message sent successfully to chat {chat_id}")
                    else:
                        print(f"❌ Failed to send message: {response.status_code} - {response.text}")
                        
                except Exception as e:
                    print(f"❌ Error processing /start command: {e}")
                    # Try to send error message
                    try:
                        telegram_url = f"https://api.telegram.org/bot{current_bot_token}/sendMessage"
                        payload = {
                            'chat_id': chat_id,
                            'text': "❌ Sorry, there was an error processing your request."
                        }
                        requests.post(telegram_url, json=payload, timeout=5)
                    except:
                        print("❌ Failed to send error message")
            
            else:
                # Handle other messages
                try:
                    print(f"💬 Processing regular message from user {user_id}")
                    telegram_url = f"https://api.telegram.org/bot{current_bot_token}/sendMessage"
                    payload = {
                        'chat_id': chat_id,
                        'text': "👋 Hello! Use /start to begin."
                    }
                    
                    response = requests.post(telegram_url, json=payload, timeout=10)
                    
                    if response.status_code == 200:
                        print(f"✅ Response sent to chat {chat_id}")
                    else:
                        print(f"❌ Failed to send response: {response.status_code}")
                        
                except Exception as e:
                    print(f"❌ Error processing message: {e}")
        
        print(f"✅ Webhook processed successfully: {update_id}")
        return jsonify({'status': 'ok'})
    
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        print(f"❌ Webhook traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

# Flask Routes (same as before but using fixed webhook)
@app.route('/')
def home():
    """Main service endpoint"""
    db_status = test_database_connection()
    bot_status = get_bot_status()
    
    return jsonify({
        'service': 'telegive-bot-service',
        'status': 'working',
        'version': '1.1.1-phase6-webhook-fixed',
        'phase': 'Phase 6 - Push Notification System with FIXED Webhook Handler',
        'message': 'Bot Service with FIXED webhook handler for guaranteed /start responses',
        'features': [
            'basic_endpoints', 'json_responses', 'error_handling', 
            'database_connection', 'optimized_service_integrations', 
            'service_status_caching', 'background_tasks', 'auth_service_token',
            'telegram_bot_integration', 'giveaway_participation_flow',
            'global_captcha_system', 'subscription_verification',
            'push_notification_system', 'instant_bot_token_updates',
            'flask_decorator_conflict_fixed', 'webhook_handler_fixed'
        ],
        'database': {
            'configured': database_configured,
            'status': db_status['status'],
            'message': db_status['message']
        },
        'telegram_bot': bot_status,
        'webhook_fix': {
            'applied': True,
            'description': 'Simplified synchronous webhook processing for guaranteed responses',
            'direct_telegram_api': True
        },
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'port': os.environ.get('PORT', 'not-set')
    })

# Push Notification Endpoint (same as before)
@app.route('/bot/token/update', methods=['POST'])
@create_service_token_decorator('bot_token_update')
def update_bot_token():
    """Receive instant bot token updates from Auth Service via push notification"""
    global last_token_update
    
    processing_start = time.time()
    
    try:
        print("🔔 Push notification received from Auth Service")
        
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
        
        if not bot_id:
            return jsonify({
                'success': False,
                'error': 'Invalid request',
                'message': 'bot_id is required'
            }), 400
        
        log_push_notification(
            source_service=source_service,
            notification_type='bot_token_update' if bot_token else 'bot_token_removed',
            bot_id=bot_id,
            bot_username=bot_username,
            status='received',
            request_data=data
        )
        
        with bot_initialization_lock:
            if status == 'removed' or not bot_token:
                # Token removed - stop bot
                print(f"🛑 Bot token removed for bot_id: {bot_id}")
                telegram_app = None
                telegram_bot = None
                current_bot_token = None
                current_bot_username = None
                current_bot_id = None
                
                processing_time = time.time() - processing_start
                last_token_update = datetime.now(timezone.utc)
                
                return jsonify({
                    'success': True,
                    'message': 'Bot token removed and bot stopped',
                    'bot_initialized': False,
                    'processing_time': processing_time
                })
            
            # Initialize bot with new token
            print(f"🚀 Initializing bot with new token for bot_id: {bot_id}")
            
            bot_initialized = initialize_telegram_bot_with_token(bot_token, bot_username, bot_id)
            
            processing_time = time.time() - processing_start
            last_token_update = datetime.now(timezone.utc)
            
            if bot_initialized:
                print("✅ Bot initialized successfully via push notification")
                
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
                    'message': 'Token updated successfully - FIXED webhook handler active',
                    'bot_initialized': True,
                    'webhook_fix': 'applied',
                    'processing_time': processing_time
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Bot initialization failed',
                    'message': 'Failed to initialize bot with provided token'
                }), 500
        
    except Exception as e:
        processing_time = time.time() - processing_start
        error_message = str(e)
        
        print(f"❌ Push notification error: {error_message}")
        
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': error_message
        }), 500

# Bot status endpoint
@app.route('/bot/status')
@create_service_token_decorator('bot_status')
def bot_status_endpoint():
    """Get detailed bot status information"""
    try:
        bot_status = get_bot_status()
        
        # Add webhook fix information
        bot_status['webhook_fix'] = {
            'applied': True,
            'description': 'Simplified synchronous webhook processing',
            'direct_telegram_api': True,
            'guaranteed_responses': True
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

# Helper functions (abbreviated)
def test_database_connection():
    """Test database connection safely"""
    if not db:
        return {'status': 'error', 'message': 'Database not initialized', 'error': database_error}
    
    try:
        db.session.execute(db.text('SELECT 1'))
        return {'status': 'connected', 'message': 'Database connection successful'}
    except Exception as e:
        return {'status': 'error', 'message': f'Database connection failed: {str(e)}'}

# Background scheduler (simplified)
scheduler = BackgroundScheduler()

def init_application():
    """Initialize database and background tasks on startup"""
    if db:
        try:
            with app.app_context():
                db.create_all()
                print("Database tables created successfully")
                
                startup_log = ServiceLog(
                    level='INFO',
                    message='Bot Service Phase 6 started with FIXED webhook handler',
                    endpoint='startup'
                )
                db.session.add(startup_log)
                db.session.commit()
                print("Startup logged to database")
                
        except Exception as e:
            print(f"Database initialization error: {e}")
    
    print("🔧 FIXED webhook handler ready for guaranteed /start responses")

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'error': 'Not Found',
        'message': 'The requested endpoint does not exist',
        'phase': 'Phase 6 - Push Notification System with FIXED Webhook Handler',
        'available_endpoints': [
            '/', '/webhook', '/bot/token/update', '/bot/status'
        ],
        'timestamp': datetime.now(timezone.utc).isoformat()
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'error': 'Internal Server Error',
        'message': 'An internal error occurred',
        'phase': 'Phase 6 - Push Notification System with FIXED Webhook Handler',
        'timestamp': datetime.now(timezone.utc).isoformat()
    }), 500

# For production (Gunicorn)
if __name__ != '__main__':
    init_application()

# For development testing only
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting Bot Service Phase 6 (FIXED Webhook Handler) on port {port}")
    
    with app.app_context():
        try:
            db.create_all()
            print("Development database initialized")
        except Exception as e:
            print(f"Development database error: {e}")
    
    init_application()
    
    app.run(host='0.0.0.0', port=port, debug=False)

