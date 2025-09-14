"""
Bot Service Phase 6 - Dynamic Bot Token Retrieval from Auth Service
Telegram bot integration with dynamic token retrieval and giveaway participation flow
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

# Auth Service authentication
AUTH_SERVICE_TOKEN = os.environ.get('AUTH_SERVICE_TOKEN', 'ch4nn3l_s3rv1c3_t0k3n_2025_s3cur3_r4nd0m_str1ng')
AUTH_SERVICE_HEADER = 'X-Service-Token'

# Service status cache
service_status_cache = {}
cache_lock = threading.Lock()
last_cache_update = None

# Dynamic bot token and application
current_bot_token = None
telegram_app = None
bot_token_last_check = None
bot_initialization_lock = threading.Lock()

# Initialize database with error handling
db = None
database_error = None

try:
    db = SQLAlchemy(app)
    print("SQLAlchemy initialized successfully")
except Exception as e:
    database_error = str(e)
    print(f"SQLAlchemy initialization error: {e}")

# Database models (same as Phase 6)
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

# Giveaway-related models
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

# Authenticated Service Client
class AuthenticatedServiceClient:
    def __init__(self):
        self.headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Telegive-Bot-Service/1.0.9-phase6-dynamic-token'
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

# Dynamic Bot Token Management
def get_bot_token_from_auth_service():
    """Retrieve bot token from Auth Service"""
    try:
        # Call Auth Service to get the current bot token
        result = service_client.call_service(
            'auth', 
            '/api/bot/token',  # Endpoint to get current bot token
            timeout=5,
            log_interaction=False  # Don't log frequent token checks
        )
        
        if result['success'] and result['data']:
            token = result['data'].get('bot_token')
            if token:
                print(f"✅ Bot token retrieved from Auth Service")
                return token
            else:
                print("⚠️ No bot token found in Auth Service response")
                return None
        else:
            print(f"❌ Failed to retrieve bot token: {result.get('error', 'Unknown error')}")
            return None
            
    except Exception as e:
        print(f"❌ Error retrieving bot token from Auth Service: {e}")
        return None

def initialize_telegram_bot_with_token(bot_token):
    """Initialize Telegram bot with provided token"""
    global telegram_app
    
    if not bot_token:
        print("❌ No bot token provided for initialization")
        return None
    
    try:
        # Create application with the retrieved token
        telegram_app = Application.builder().token(bot_token).build()
        
        # Add handlers
        telegram_app.add_handler(CommandHandler("start", start_handler))
        telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
        
        print(f"✅ Telegram bot initialized successfully with token: {bot_token[:10]}...")
        return telegram_app
    
    except Exception as e:
        print(f"❌ Telegram bot initialization error: {e}")
        return None

def check_and_update_bot_token():
    """Check for bot token updates and reinitialize if needed"""
    global current_bot_token, telegram_app, bot_token_last_check
    
    with bot_initialization_lock:
        try:
            # Get current bot token from Auth Service
            new_token = get_bot_token_from_auth_service()
            
            # Update last check time
            bot_token_last_check = datetime.now(timezone.utc)
            
            # Check if token has changed
            if new_token != current_bot_token:
                print(f"🔄 Bot token changed, reinitializing bot...")
                
                # Update current token
                current_bot_token = new_token
                
                if new_token:
                    # Initialize bot with new token
                    telegram_app = initialize_telegram_bot_with_token(new_token)
                    if telegram_app:
                        print("✅ Bot reinitialized with new token")
                        return True
                    else:
                        print("❌ Failed to reinitialize bot with new token")
                        telegram_app = None
                        return False
                else:
                    # No token available
                    print("⚠️ No bot token available, bot disabled")
                    telegram_app = None
                    return False
            else:
                # Token unchanged
                if new_token:
                    print("✅ Bot token unchanged, bot operational")
                    return True
                else:
                    print("⚠️ No bot token available")
                    return False
                    
        except Exception as e:
            print(f"❌ Error checking bot token: {e}")
            return False

def get_bot_status():
    """Get current bot status information"""
    global current_bot_token, telegram_app, bot_token_last_check
    
    return {
        'token_configured': bool(current_bot_token),
        'bot_initialized': telegram_app is not None,
        'token_source': 'auth_service',
        'last_token_check': bot_token_last_check.isoformat() if bot_token_last_check else None,
        'webhook_url': WEBHOOK_URL
    }

# Giveaway Helper Functions (same as Phase 6)
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

def store_captcha_challenge(user_id, challenge_data):
    """Store captcha challenge for user"""
    try:
        with app.app_context():
            # Remove existing challenge
            CaptchaChallenge.query.filter_by(user_id=user_id).delete()
            
            # Create new challenge
            challenge = CaptchaChallenge(
                user_id=user_id,
                giveaway_id=challenge_data['giveaway_id'],
                answer=challenge_data['answer'],
                attempts=challenge_data.get('attempts', 0),
                max_attempts=challenge_data.get('max_attempts', 3)
            )
            db.session.add(challenge)
            db.session.commit()
            return True
    except Exception as e:
        print(f"Error storing captcha challenge: {e}")
        return False

def get_captcha_challenge(user_id):
    """Get current captcha challenge for user"""
    try:
        with app.app_context():
            challenge = CaptchaChallenge.query.filter_by(user_id=user_id).filter(
                CaptchaChallenge.expires_at > datetime.now(timezone.utc)
            ).first()
            
            if challenge:
                return {
                    'giveaway_id': challenge.giveaway_id,
                    'answer': challenge.answer,
                    'attempts': challenge.attempts,
                    'max_attempts': challenge.max_attempts
                }
            return None
    except Exception as e:
        print(f"Error getting captcha challenge: {e}")
        return None

def update_captcha_challenge(user_id, updates):
    """Update captcha challenge for user"""
    try:
        with app.app_context():
            challenge = CaptchaChallenge.query.filter_by(user_id=user_id).first()
            if challenge:
                for key, value in updates.items():
                    if hasattr(challenge, key):
                        setattr(challenge, key, value)
                db.session.commit()
                return True
            return False
    except Exception as e:
        print(f"Error updating captcha challenge: {e}")
        return False

def clear_captcha_challenge(user_id):
    """Clear captcha challenge for user"""
    try:
        with app.app_context():
            CaptchaChallenge.query.filter_by(user_id=user_id).delete()
            db.session.commit()
            return True
    except Exception as e:
        print(f"Error clearing captcha challenge: {e}")
        return False

def set_user_state(user_id, state, data=None):
    """Set user state"""
    try:
        with app.app_context():
            existing = UserState.query.filter_by(user_id=user_id).first()
            if existing:
                existing.state = state
                existing.data = json.dumps(data) if data else None
                existing.updated_at = datetime.now(timezone.utc)
            else:
                user_state = UserState(
                    user_id=user_id,
                    state=state,
                    data=json.dumps(data) if data else None
                )
                db.session.add(user_state)
            db.session.commit()
            return True
    except Exception as e:
        print(f"Error setting user state: {e}")
        return False

def get_user_state(user_id):
    """Get user state"""
    try:
        with app.app_context():
            user_state = UserState.query.filter_by(user_id=user_id).first()
            if user_state:
                return {
                    'state': user_state.state,
                    'data': json.loads(user_state.data) if user_state.data else None
                }
            return None
    except Exception as e:
        print(f"Error getting user state: {e}")
        return None

def clear_user_state(user_id):
    """Clear user state"""
    try:
        with app.app_context():
            UserState.query.filter_by(user_id=user_id).delete()
            db.session.commit()
            return True
    except Exception as e:
        print(f"Error clearing user state: {e}")
        return False

def check_user_participation(giveaway_id, user_id):
    """Check if user already participated in giveaway"""
    try:
        with app.app_context():
            participation = GiveawayParticipation.query.filter_by(
                giveaway_id=giveaway_id,
                user_id=user_id
            ).first()
            return participation is not None
    except Exception as e:
        print(f"Error checking user participation: {e}")
        return False

def register_user_participation(participation_data):
    """Register user participation in giveaway"""
    try:
        with app.app_context():
            participation = GiveawayParticipation(
                giveaway_id=participation_data['giveaway_id'],
                user_id=participation_data['user_id'],
                username=participation_data.get('username'),
                first_name=participation_data.get('first_name'),
                status=participation_data.get('status', 'active')
            )
            db.session.add(participation)
            db.session.commit()
            return True
    except Exception as e:
        print(f"Error registering participation: {e}")
        return False

def get_participant_count(giveaway_id):
    """Get participant count for giveaway"""
    try:
        with app.app_context():
            count = GiveawayParticipation.query.filter_by(
                giveaway_id=giveaway_id,
                status='active'
            ).count()
            return count
    except Exception as e:
        print(f"Error getting participant count: {e}")
        return 0

# Telegram Bot Handlers (same as Phase 6, but with bot availability check)
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command with giveaway and result parameters"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    args = context.args
    
    print(f"🎯 Start command from user {user_id} with args: {args}")
    
    if not args:
        # Regular start command
        await update.message.reply_text(
            "🤖 Welcome to Telegive Bot!\n\n"
            "This bot handles giveaway participation. "
            "Click the '🎯 Participate' button in giveaway posts to join!"
        )
        return
    
    command = args[0]
    
    # Handle giveaway participation: /start giveaway_123
    if command.startswith('giveaway_'):
        try:
            giveaway_id = int(command.split('_')[1])
            await handle_giveaway_participation(update, context, giveaway_id)
        except (ValueError, IndexError):
            await update.message.reply_text("❌ Invalid giveaway link.")
    
    # Handle result checking: /start result_123
    elif command.startswith('result_'):
        try:
            giveaway_id = int(command.split('_')[1])
            await handle_result_check(update, context, giveaway_id)
        except (ValueError, IndexError):
            await update.message.reply_text("❌ Invalid result link.")
    
    else:
        await update.message.reply_text("❌ Unknown command.")

async def handle_giveaway_participation(update: Update, context: ContextTypes.DEFAULT_TYPE, giveaway_id: int):
    """Handle giveaway participation flow"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    print(f"🎯 Participation attempt: user {user_id}, giveaway {giveaway_id}")
    
    try:
        # 1. Get giveaway information from Channel Service
        giveaway_result = service_client.call_service('channel', f'/api/giveaways/{giveaway_id}')
        
        if not giveaway_result['success']:
            await update.message.reply_text("❌ This giveaway is no longer available.")
            return
        
        giveaway = giveaway_result['data']
        
        if giveaway.get('status') != 'active':
            await update.message.reply_text("❌ This giveaway is no longer active.")
            return
        
        # 2. Check if user already participated
        if check_user_participation(giveaway_id, user_id):
            await update.message.reply_text(f"✅ You're already participating in \"{giveaway.get('title', 'this giveaway')}\"!")
            return
        
        # 3. Check subscription requirement
        await check_subscription_requirement(update, context, giveaway)
        
    except Exception as e:
        print(f"❌ Participation error: {e}")
        await update.message.reply_text("❌ Error processing participation. Please try again.")

async def check_subscription_requirement(update: Update, context: ContextTypes.DEFAULT_TYPE, giveaway):
    """Check if user is subscribed to required channel"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    giveaway_id = giveaway['id']
    
    print(f"📺 Checking subscription requirement for user {user_id}")
    
    try:
        # Get channel configuration from Channel Service
        channel_result = service_client.call_service('channel', f'/api/giveaways/{giveaway_id}/channel')
        
        if not channel_result['success']:
            await update.message.reply_text("❌ Unable to verify channel requirements.")
            return
        
        channel_config = channel_result['data']
        channel_username = channel_config.get('channel_username')
        
        if not channel_username:
            # No channel requirement, proceed to captcha
            await check_captcha_requirement(update, context, giveaway)
            return
        
        # Check user membership using bot
        try:
            member = await context.bot.get_chat_member(channel_username, user_id)
            
            if member.status in ['member', 'administrator', 'creator']:
                # User is subscribed, proceed to captcha
                print(f"✅ User {user_id} is subscribed to {channel_username}")
                await check_captcha_requirement(update, context, giveaway)
            else:
                # User not subscribed
                keyboard = [[InlineKeyboardButton(
                    "📺 Subscribe to Channel",
                    url=f"https://t.me/{channel_username.replace('@', '')}"
                )]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    f"📺 To participate in this giveaway, you must be subscribed to {channel_username}.\n\n"
                    "Please subscribe to the channel and then click the \"🎯 Participate\" button in the giveaway post again.",
                    reply_markup=reply_markup
                )
        
        except TelegramError as e:
            print(f"❌ Telegram API error checking membership: {e}")
            await update.message.reply_text("❌ Unable to verify subscription. Please try again.")
    
    except Exception as e:
        print(f"❌ Subscription check error: {e}")
        await update.message.reply_text("❌ Unable to verify subscription. Please try again.")

async def check_captcha_requirement(update: Update, context: ContextTypes.DEFAULT_TYPE, giveaway):
    """Check if user needs to complete captcha"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    giveaway_id = giveaway['id']
    
    print(f"🧮 Checking captcha requirement for user {user_id}")
    
    try:
        # Check if user has completed captcha globally
        if has_user_completed_captcha_globally(user_id):
            # User has completed captcha before, proceed to participation
            print(f"✅ User {user_id} has completed captcha globally")
            await confirm_participation(update, context, giveaway)
        else:
            # First-time user, present captcha
            print(f"🧮 First-time user {user_id}, presenting captcha")
            await present_first_time_captcha(update, context, giveaway)
    
    except Exception as e:
        print(f"❌ Captcha check error: {e}")
        await update.message.reply_text("❌ Error checking verification status. Please try again.")

async def present_first_time_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE, giveaway):
    """Present captcha challenge to first-time user"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    giveaway_id = giveaway['id']
    
    # Generate simple math question
    num1 = random.randint(1, 10)
    num2 = random.randint(1, 10)
    answer = num1 + num2
    
    # Store captcha challenge
    challenge_data = {
        'giveaway_id': giveaway_id,
        'answer': answer,
        'attempts': 0,
        'max_attempts': 3
    }
    
    if store_captcha_challenge(user_id, challenge_data):
        # Set user state
        set_user_state(user_id, 'captcha_pending', {'giveaway_id': giveaway_id})
        
        # Send captcha question
        await update.message.reply_text(
            f"🧮 First-time participation requires verification. Please solve: {num1} + {num2} = ?\n\n"
            "Reply with just the number.",
            reply_markup=ForceReply(selective=True)
        )
    else:
        await update.message.reply_text("❌ Error setting up verification. Please try again.")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages for captcha processing"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Get user state
    user_state = get_user_state(user_id)
    
    if user_state and user_state['state'] == 'captcha_pending':
        await process_captcha_answer(update, context, update.message.text)

async def process_captcha_answer(update: Update, context: ContextTypes.DEFAULT_TYPE, user_input: str):
    """Process captcha answer from user"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    try:
        captcha_data = get_captcha_challenge(user_id)
        
        if not captcha_data:
            await update.message.reply_text(
                "❌ Captcha session expired. Please click the \"🎯 Participate\" button again."
            )
            clear_user_state(user_id)
            return
        
        # Parse user answer
        try:
            user_answer = int(user_input.strip())
        except ValueError:
            await update.message.reply_text(
                "Please reply with just the number. What is the answer? Reply with just the number."
            )
            return
        
        # Check if answer is correct
        if user_answer == captcha_data['answer']:
            # Correct answer - mark user as globally verified
            mark_user_captcha_completed_globally(user_id, captcha_data['giveaway_id'])
            clear_user_state(user_id)
            clear_captcha_challenge(user_id)
            
            await update.message.reply_text(
                "✅ Verification complete! You can now participate in giveaways. "
                "Please click the \"🎯 Participate\" button in the giveaway post again."
            )
        
        else:
            # Incorrect answer
            new_attempts = captcha_data['attempts'] + 1
            
            if new_attempts >= captcha_data['max_attempts']:
                # Max attempts reached - generate new question
                num1 = random.randint(1, 10)
                num2 = random.randint(1, 10)
                new_answer = num1 + num2
                
                update_captcha_challenge(user_id, {
                    'answer': new_answer,
                    'attempts': 0
                })
                
                await update.message.reply_text(
                    f"❌ Maximum attempts reached. New question: {num1} + {num2} = ?\n\n"
                    "Reply with just the number."
                )
            
            else:
                # Still have attempts left
                update_captcha_challenge(user_id, {'attempts': new_attempts})
                remaining_attempts = captcha_data['max_attempts'] - new_attempts
                
                await update.message.reply_text(
                    f"❌ Incorrect. {remaining_attempts} attempts remaining. "
                    "What is the answer? Reply with just the number."
                )
    
    except Exception as e:
        print(f"❌ Captcha processing error: {e}")
        await update.message.reply_text("❌ Error processing answer. Please try again.")

async def confirm_participation(update: Update, context: ContextTypes.DEFAULT_TYPE, giveaway):
    """Confirm user participation in giveaway"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    giveaway_id = giveaway['id']
    
    print(f"🎉 Confirming participation for user {user_id} in giveaway {giveaway_id}")
    
    try:
        # Register user participation
        participation_data = {
            'giveaway_id': giveaway_id,
            'user_id': user_id,
            'username': update.effective_user.username,
            'first_name': update.effective_user.first_name,
            'status': 'active'
        }
        
        if register_user_participation(participation_data):
            # Get current participant count
            participant_count = get_participant_count(giveaway_id)
            
            # Send success confirmation
            await update.message.reply_text(
                f"🎉 Participation confirmed!\n\n"
                f"📊 Current participants: {participant_count}\n\n"
                "⏳ Waiting for admin to finish the giveaway. "
                "You'll receive a direct message with results when it's completed."
            )
            
            print(f"✅ Participation confirmed for user {user_id}")
        
        else:
            await update.message.reply_text("❌ Error confirming participation. Please try again.")
    
    except Exception as e:
        print(f"❌ Participation confirmation error: {e}")
        await update.message.reply_text("❌ Error confirming participation. Please try again.")

async def handle_result_check(update: Update, context: ContextTypes.DEFAULT_TYPE, giveaway_id: int):
    """Handle result checking from channel announcement"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    print(f"🔍 Result check request: user {user_id}, giveaway {giveaway_id}")
    
    try:
        # Check if user participated
        if not check_user_participation(giveaway_id, user_id):
            await update.message.reply_text("❌ You did not participate in this giveaway.")
            return
        
        # Get giveaway results from Channel Service
        results_result = service_client.call_service('channel', f'/api/giveaways/{giveaway_id}/results')
        
        if not results_result['success']:
            await update.message.reply_text("❌ Results not available yet.")
            return
        
        giveaway_results = results_result['data']
        winner_ids = giveaway_results.get('winner_ids', [])
        
        # Send personalized result message
        is_winner = user_id in winner_ids
        
        if is_winner:
            message = giveaway_results.get('winner_message', '🎉 Congratulations! You won!')
        else:
            message = giveaway_results.get('loser_message', '😔 Better luck next time!')
        
        await update.message.reply_text(message)
    
    except Exception as e:
        print(f"❌ Result check error: {e}")
        await update.message.reply_text("❌ Error checking results. Please try again.")

# Background task functions (enhanced with bot token checking)
def update_service_status_cache():
    """Background task to update service status cache and check bot token"""
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
                    details='Updating service status cache and checking bot token'
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
        # Check and update bot token
        bot_token_updated = check_and_update_bot_token()
        
        # Update service status cache
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
        
        # Log task completion
        if db and task_id:
            try:
                with app.app_context():
                    task_record = BackgroundTask.query.get(task_id)
                    if task_record:
                        task_record.status = 'completed'
                        task_record.execution_time = execution_time
                        task_record.details = f'Updated status for {len(new_status)} services, bot token: {"updated" if bot_token_updated else "unchanged"}'
                        db.session.commit()
            except Exception as e:
                print(f"Task completion logging error: {e}")
        
        print(f"Service status cache updated in {execution_time:.3f}s (bot token: {'updated' if bot_token_updated else 'unchanged'})")
        
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
            
            # Clean up expired captcha challenges
            expired_captchas = CaptchaChallenge.query.filter(
                CaptchaChallenge.expires_at < datetime.now(timezone.utc)
            ).all()
            
            # Clean up old user states (older than 24 hours)
            old_states = UserState.query.filter(
                UserState.updated_at < datetime.now(timezone.utc) - timedelta(hours=24)
            ).all()
            
            # Delete old records
            deleted_count = 0
            for record_list in [old_interactions, old_health_checks, old_logs, old_tasks, expired_captchas, old_states]:
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

# Database helper functions (same as Phase 6)
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

# Optimized service status functions (same as Phase 6)
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
    """Main service endpoint with cached service status and dynamic bot status"""
    db_status = test_database_connection()
    service_status = get_cached_service_status()  # Use cached status for speed
    bot_status = get_bot_status()  # Get dynamic bot status
    
    # Log this request (async)
    log_to_database('INFO', 'Home endpoint accessed', '/')
    
    return jsonify({
        'service': 'telegive-bot-service',
        'status': 'working',
        'version': '1.0.9-phase6-dynamic-token',
        'phase': 'Phase 6 - Dynamic Bot Token from Auth Service',
        'message': 'Bot Service with dynamic Telegram bot token retrieval from Auth Service',
        'features': [
            'basic_endpoints', 'json_responses', 'error_handling', 
            'database_connection', 'optimized_service_integrations', 
            'service_status_caching', 'background_tasks', 'auth_service_token',
            'telegram_bot_integration', 'giveaway_participation_flow',
            'global_captcha_system', 'subscription_verification',
            'dynamic_bot_token_retrieval'
        ],
        'database': {
            'configured': database_configured,
            'status': db_status['status'],
            'message': db_status['message']
        },
        'services': service_status,
        'telegram_bot': bot_status,
        'authentication': {
            'auth_service_token': 'configured' if AUTH_SERVICE_TOKEN else 'missing',
            'auth_header': AUTH_SERVICE_HEADER
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

# Bot token management endpoints
@app.route('/bot/token/refresh', methods=['POST'])
def refresh_bot_token():
    """Manually refresh bot token from Auth Service"""
    try:
        success = check_and_update_bot_token()
        bot_status = get_bot_status()
        
        return jsonify({
            'message': 'Bot token refresh completed',
            'success': success,
            'bot_status': bot_status,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
    
    except Exception as e:
        return jsonify({
            'error': 'Failed to refresh bot token',
            'details': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 500

@app.route('/bot/status')
def bot_status_endpoint():
    """Get detailed bot status information"""
    try:
        bot_status = get_bot_status()
        
        # Add additional status information
        bot_status['auth_service_url'] = SERVICE_URLS['auth']
        bot_status['auth_service_token_configured'] = bool(AUTH_SERVICE_TOKEN)
        
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

# Giveaway management endpoints (same as Phase 6)
@app.route('/giveaway/stats')
def giveaway_stats():
    """Get giveaway participation statistics"""
    try:
        with app.app_context():
            total_participations = GiveawayParticipation.query.count()
            active_participations = GiveawayParticipation.query.filter_by(status='active').count()
            unique_participants = db.session.query(GiveawayParticipation.user_id).distinct().count()
            captcha_completions = UserCaptchaStatus.query.count()
            
            return jsonify({
                'giveaway_statistics': {
                    'total_participations': total_participations,
                    'active_participations': active_participations,
                    'unique_participants': unique_participants,
                    'captcha_completions': captcha_completions
                },
                'telegram_bot': get_bot_status(),
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
    
    except Exception as e:
        return jsonify({
            'error': 'Failed to get statistics',
            'details': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 500

@app.route('/giveaway/<int:giveaway_id>/participants')
def get_giveaway_participants(giveaway_id):
    """Get participants for specific giveaway"""
    try:
        with app.app_context():
            participants = GiveawayParticipation.query.filter_by(
                giveaway_id=giveaway_id,
                status='active'
            ).all()
            
            participant_list = []
            for p in participants:
                participant_list.append({
                    'user_id': p.user_id,
                    'username': p.username,
                    'first_name': p.first_name,
                    'participation_date': p.participation_date.isoformat()
                })
            
            return jsonify({
                'giveaway_id': giveaway_id,
                'participant_count': len(participant_list),
                'participants': participant_list,
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
    
    except Exception as e:
        return jsonify({
            'error': 'Failed to get participants',
            'giveaway_id': giveaway_id,
            'details': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 500

@app.route('/giveaway/<int:giveaway_id>/distribute-results', methods=['POST'])
def distribute_giveaway_results(giveaway_id):
    """Distribute giveaway results to all participants"""
    if not telegram_app:
        return jsonify({'error': 'Telegram bot not available for result distribution'}), 503
    
    try:
        data = request.get_json()
        
        if not data or 'winner_ids' not in data:
            return jsonify({'error': 'winner_ids required'}), 400
        
        winner_ids = data['winner_ids']
        winner_message = data.get('winner_message', '🎉 Congratulations! You won!')
        loser_message = data.get('loser_message', '😔 Better luck next time!')
        
        # Get all participants
        with app.app_context():
            participants = GiveawayParticipation.query.filter_by(
                giveaway_id=giveaway_id,
                status='active'
            ).all()
        
        # Distribute results asynchronously
        def distribute_results():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                async def send_results():
                    sent_count = 0
                    failed_count = 0
                    
                    for participant in participants:
                        try:
                            is_winner = participant.user_id in winner_ids
                            message = winner_message if is_winner else loser_message
                            
                            await telegram_app.bot.send_message(
                                chat_id=participant.user_id,
                                text=message
                            )
                            
                            sent_count += 1
                            print(f"✅ Result sent to user {participant.user_id} ({'winner' if is_winner else 'loser'})")
                        
                        except Exception as e:
                            failed_count += 1
                            print(f"❌ Failed to send result to user {participant.user_id}: {e}")
                    
                    print(f"✅ Result distribution completed: {sent_count} sent, {failed_count} failed")
                
                loop.run_until_complete(send_results())
                loop.close()
            
            except Exception as e:
                print(f"❌ Result distribution error: {e}")
        
        thread = threading.Thread(target=distribute_results)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'message': 'Result distribution started',
            'giveaway_id': giveaway_id,
            'participant_count': len(participants),
            'winner_count': len(winner_ids),
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
    
    except Exception as e:
        return jsonify({
            'error': 'Failed to distribute results',
            'giveaway_id': giveaway_id,
            'details': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 500

# Error handlers (same as Phase 6)
@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors with JSON response and async logging"""
    log_to_database('WARNING', f'404 error: {error}', 'unknown')
    
    return jsonify({
        'error': 'Not Found',
        'message': 'The requested endpoint does not exist',
        'phase': 'Phase 6 - Dynamic Bot Token from Auth Service',
        'available_endpoints': [
            '/', '/webhook', '/bot/token/refresh', '/bot/status',
            '/giveaway/stats', '/giveaway/<id>/participants', 
            '/giveaway/<id>/distribute-results'
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
        'phase': 'Phase 6 - Dynamic Bot Token from Auth Service',
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
        'phase': 'Phase 6 - Dynamic Bot Token from Auth Service',
        'timestamp': datetime.now(timezone.utc).isoformat()
    }), 500

# Initialize database and background tasks on startup
def init_application():
    """Initialize database, background tasks, and check for bot token on startup"""
    if db:
        try:
            with app.app_context():
                db.create_all()
                print("Database tables created successfully")
                
                # Log startup
                startup_log = ServiceLog(
                    level='INFO',
                    message='Bot Service Phase 6 started with dynamic bot token retrieval from Auth Service',
                    endpoint='startup'
                )
                db.session.add(startup_log)
                db.session.commit()
                print("Startup logged to database")
                
        except Exception as e:
            print(f"Database initialization error: {e}")
    
    # Check for bot token from Auth Service
    print("🔍 Checking for bot token from Auth Service...")
    check_and_update_bot_token()
    
    # Start background scheduler
    try:
        if not scheduler.running:
            # Add background jobs (enhanced with bot token checking)
            scheduler.add_job(
                func=update_service_status_cache,
                trigger=IntervalTrigger(minutes=2),  # Update every 2 minutes
                id='update_service_status',
                name='Update Service Status Cache and Check Bot Token',
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
    print(f"Starting Bot Service Phase 6 (Dynamic Token) on port {port}")
    
    # Initialize for development
    with app.app_context():
        try:
            db.create_all()
            print("Development database initialized")
        except Exception as e:
            print(f"Development database error: {e}")
    
    # Start scheduler and check for bot token
    init_application()
    
    app.run(host='0.0.0.0', port=port, debug=False)

