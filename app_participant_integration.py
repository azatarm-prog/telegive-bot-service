"""
Bot Service Phase 6 - Complete Participant Service Integration
Implements all 6 API endpoints for full giveaway participation functionality
"""
import os
import json
import time
import threading
import traceback
import requests
import asyncio
import logging
import random
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError
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

# User session management for captcha and participation
user_sessions = {}
session_lock = threading.Lock()

# Initialize database with error handling
db = None
database_error = None

try:
    db = SQLAlchemy(app)
    print("SQLAlchemy initialized successfully")
except Exception as e:
    database_error = str(e)
    print(f"SQLAlchemy initialization error: {e}")

# Database models (same as before plus new ones for participant integration)
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

class ParticipantInteraction(db.Model):
    __tablename__ = 'participant_interactions'
    
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    timestamp = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    user_id = db.Column(db.BigInteger, nullable=False)
    giveaway_id = db.Column(db.BigInteger)
    interaction_type = db.Column(db.String(50), nullable=False)  # register, captcha, result_check
    api_endpoint = db.Column(db.String(200))
    request_data = db.Column(db.Text)
    response_data = db.Column(db.Text)
    success = db.Column(db.Boolean, nullable=False)
    processing_time = db.Column(db.Float)
    error_message = db.Column(db.Text)

# PARTICIPANT SERVICE INTEGRATION FUNCTIONS

def make_participant_api_call(endpoint, method='GET', data=None, timeout=10):
    """Make API call to Participant Service with error handling"""
    url = f"{SERVICE_URLS['participant']}{endpoint}"
    
    try:
        headers = {'Content-Type': 'application/json'}
        
        if method == 'GET':
            response = requests.get(url, timeout=timeout)
        elif method == 'POST':
            response = requests.post(url, json=data, headers=headers, timeout=timeout)
        elif method == 'PUT':
            response = requests.put(url, json=data, headers=headers, timeout=timeout)
        
        return response.json()
    except requests.exceptions.RequestException as e:
        return {'success': False, 'error': f'API call failed: {str(e)}'}

def participant_api_call_with_retry(endpoint, method='GET', data=None, max_retries=3):
    """API call with exponential backoff retry"""
    for attempt in range(max_retries):
        try:
            response = make_participant_api_call(endpoint, method, data)
            
            if response.get('success') or response.get('error_code') in ['USER_NOT_FOUND', 'DUPLICATE_PARTICIPATION']:
                # Don't retry for these errors
                return response
            
            if attempt < max_retries - 1:
                # Exponential backoff with jitter
                delay = (2 ** attempt) + random.uniform(0, 1)
                time.sleep(delay)
                continue
            
            return response
            
        except Exception as e:
            if attempt < max_retries - 1:
                delay = (2 ** attempt) + random.uniform(0, 1)
                time.sleep(delay)
                continue
            
            return {'success': False, 'error': f'Max retries exceeded: {str(e)}'}

def log_participant_interaction(user_id, giveaway_id, interaction_type, api_endpoint, request_data, response_data, success, processing_time, error_message=None):
    """Log participant service interaction to database"""
    if not db:
        return
    
    try:
        with app.app_context():
            interaction = ParticipantInteraction(
                user_id=user_id,
                giveaway_id=giveaway_id,
                interaction_type=interaction_type,
                api_endpoint=api_endpoint,
                request_data=json.dumps(request_data) if request_data else None,
                response_data=json.dumps(response_data) if response_data else None,
                success=success,
                processing_time=processing_time,
                error_message=error_message
            )
            db.session.add(interaction)
            db.session.commit()
    except Exception as e:
        print(f"Participant interaction logging error: {e}")

# 1. PARTICIPATION REGISTRATION
def register_user_participation(user_id, giveaway_id, user_info):
    """Register user participation in giveaway"""
    start_time = time.time()
    
    data = {
        'giveaway_id': giveaway_id,
        'user_id': user_id,
        'username': user_info.get('username'),
        'first_name': user_info.get('first_name'),
        'last_name': user_info.get('last_name')
    }
    
    response = participant_api_call_with_retry('/api/participants/register', 'POST', data)
    processing_time = time.time() - start_time
    
    log_participant_interaction(
        user_id=user_id,
        giveaway_id=giveaway_id,
        interaction_type='register',
        api_endpoint='/api/participants/register',
        request_data=data,
        response_data=response,
        success=response.get('success', False),
        processing_time=processing_time,
        error_message=response.get('error') if not response.get('success') else None
    )
    
    if response.get('success'):
        if response.get('requires_captcha'):
            # New user - show captcha
            return {
                'action': 'show_captcha',
                'question': response['captcha_question'],
                'session_id': response['session_id']
            }
        else:
            # Returning user - participation confirmed
            return {
                'action': 'confirm_participation',
                'participant_id': response['participant_id']
            }
    else:
        return {
            'action': 'show_error',
            'error': response.get('error', 'Registration failed')
        }

# 2. CAPTCHA STATUS CHECK
def check_user_captcha_status(user_id):
    """Check if user has completed captcha globally"""
    start_time = time.time()
    
    response = participant_api_call_with_retry(f'/api/participants/captcha-status/{user_id}')
    processing_time = time.time() - start_time
    
    log_participant_interaction(
        user_id=user_id,
        giveaway_id=None,
        interaction_type='captcha_status',
        api_endpoint=f'/api/participants/captcha-status/{user_id}',
        request_data=None,
        response_data=response,
        success=response.get('success', False),
        processing_time=processing_time,
        error_message=response.get('error') if not response.get('success') else None
    )
    
    if response.get('success'):
        return {
            'completed': response['captcha_completed'],
            'total_participations': response.get('total_participations', 0),
            'total_wins': response.get('total_wins', 0)
        }
    else:
        # Assume new user if API fails
        return {'completed': False}

# 3. CAPTCHA VALIDATION
def validate_captcha_answer(user_id, giveaway_id, answer):
    """Validate user's captcha answer"""
    start_time = time.time()
    
    data = {
        'user_id': user_id,
        'giveaway_id': giveaway_id,
        'answer': int(answer)  # Ensure integer
    }
    
    response = participant_api_call_with_retry('/api/participants/validate-captcha', 'POST', data)
    processing_time = time.time() - start_time
    
    log_participant_interaction(
        user_id=user_id,
        giveaway_id=giveaway_id,
        interaction_type='captcha_validation',
        api_endpoint='/api/participants/validate-captcha',
        request_data=data,
        response_data=response,
        success=response.get('success', False),
        processing_time=processing_time,
        error_message=response.get('error') if not response.get('success') else None
    )
    
    if response.get('success'):
        if response.get('captcha_completed'):
            return {
                'action': 'confirm_participation',
                'participant_id': response['participant_id'],
                'global_completion': True
            }
        else:
            return {
                'action': 'retry_captcha',
                'attempts_remaining': response['attempts_remaining'],
                'new_question': response.get('new_question')
            }
    else:
        return {
            'action': 'show_error',
            'error': response.get('error', 'Captcha validation failed')
        }

# 4. WINNER STATUS CHECK
def check_winner_status(user_id, giveaway_id):
    """Check if user won the giveaway"""
    start_time = time.time()
    
    response = participant_api_call_with_retry(f'/api/participants/winner-status/{user_id}/{giveaway_id}')
    processing_time = time.time() - start_time
    
    log_participant_interaction(
        user_id=user_id,
        giveaway_id=giveaway_id,
        interaction_type='winner_check',
        api_endpoint=f'/api/participants/winner-status/{user_id}/{giveaway_id}',
        request_data=None,
        response_data=response,
        success=response.get('success', False),
        processing_time=processing_time,
        error_message=response.get('error') if not response.get('success') else None
    )
    
    if response.get('success'):
        return {
            'participated': response['participated'],
            'is_winner': response['is_winner'],
            'winner_selected_at': response.get('winner_selected_at'),
            'total_winners': response.get('total_winners')
        }
    else:
        return {
            'participated': False,
            'is_winner': False,
            'error': response.get('error', 'Winner status check failed')
        }

# 5. SUBSCRIPTION VERIFICATION
def verify_user_subscription(user_id, account_id):
    """Verify user is subscribed to channel"""
    start_time = time.time()
    
    data = {
        'user_id': user_id,
        'account_id': account_id
    }
    
    response = participant_api_call_with_retry('/api/participants/verify-subscription', 'POST', data)
    processing_time = time.time() - start_time
    
    log_participant_interaction(
        user_id=user_id,
        giveaway_id=None,
        interaction_type='subscription_verification',
        api_endpoint='/api/participants/verify-subscription',
        request_data=data,
        response_data=response,
        success=response.get('success', False),
        processing_time=processing_time,
        error_message=response.get('error') if not response.get('success') else None
    )
    
    if response.get('success'):
        return {
            'is_subscribed': response['is_subscribed'],
            'channel_info': response.get('channel_info', {}),
            'verified_at': response.get('verified_at')
        }
    else:
        return {
            'is_subscribed': False,
            'error': response.get('error', 'Subscription verification failed')
        }

# 6. DELIVERY STATUS UPDATES
def update_message_delivery_status(delivery_results):
    """Update delivery status for sent messages"""
    successful_deliveries = []
    failed_deliveries = []
    
    for result in delivery_results:
        if result['success']:
            successful_deliveries.append(result['participant_id'])
        else:
            failed_deliveries.append({
                'participant_id': result['participant_id'],
                'error': result['error']
            })
    
    # Update successful deliveries
    if successful_deliveries:
        data = {
            'participant_ids': successful_deliveries,
            'delivered': True,
            'delivery_timestamp': datetime.utcnow().isoformat()
        }
        
        response = participant_api_call_with_retry('/api/participants/update-delivery-status', 'PUT', data)
        
        if response.get('success'):
            print(f"Updated delivery status for {len(successful_deliveries)} participants")
        else:
            print(f"Failed to update delivery status: {response.get('error')}")

# ERROR HANDLING
def handle_participant_service_errors(response):
    """Handle common Participant Service errors"""
    if not response.get('success'):
        error_code = response.get('error_code', 'UNKNOWN_ERROR')
        
        error_handlers = {
            'USER_NOT_FOUND': lambda: "User not found in system",
            'GIVEAWAY_NOT_FOUND': lambda: "Giveaway not found or expired",
            'DUPLICATE_PARTICIPATION': lambda: "You're already participating in this giveaway",
            'CAPTCHA_EXPIRED': lambda: "Captcha session expired, please try again",
            'INVALID_CAPTCHA_ANSWER': lambda: "Invalid answer format",
            'USER_NOT_SUBSCRIBED': lambda: "You must subscribe to the channel first",
            'GIVEAWAY_NOT_ACTIVE': lambda: "This giveaway is no longer active",
            'SERVICE_UNAVAILABLE': lambda: "Service temporarily unavailable, please try again"
        }
        
        return error_handlers.get(error_code, lambda: response.get('error', 'Unknown error'))()
    
    return None

# USER SESSION MANAGEMENT
def store_user_session(user_id, session_data):
    """Store user session data for captcha and participation"""
    with session_lock:
        user_sessions[user_id] = {
            **session_data,
            'timestamp': datetime.now(timezone.utc)
        }

def get_user_session(user_id):
    """Get user session data"""
    with session_lock:
        return user_sessions.get(user_id)

def clear_user_session(user_id):
    """Clear user session data"""
    with session_lock:
        user_sessions.pop(user_id, None)

# TELEGRAM MESSAGE HELPERS
def send_telegram_message(chat_id, text, reply_markup=None):
    """Send message via Telegram API"""
    if not current_bot_token:
        return {'success': False, 'error': 'Bot token not configured'}
    
    try:
        telegram_url = f"https://api.telegram.org/bot{current_bot_token}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'HTML'
        }
        
        if reply_markup:
            payload['reply_markup'] = reply_markup
        
        response = requests.post(telegram_url, json=payload, timeout=10)
        
        if response.status_code == 200:
            return {'success': True, 'message_id': response.json().get('result', {}).get('message_id')}
        else:
            return {'success': False, 'error': f'Telegram API error: {response.status_code}'}
            
    except Exception as e:
        return {'success': False, 'error': f'Message sending failed: {str(e)}'}

# TELEGRAM BOT HANDLERS WITH PARTICIPANT SERVICE INTEGRATION

async def start_handler_with_participant_integration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command with full participant service integration"""
    try:
        user_id = update.effective_user.id
        user_info = {
            'username': update.effective_user.username,
            'first_name': update.effective_user.first_name,
            'last_name': update.effective_user.last_name
        }
        args = context.args if context.args else []
        
        print(f"🎯 Start handler with participant integration: user {user_id}, args: {args}")
        
        if not args:
            # Simple welcome message
            await update.message.reply_text(
                "🤖 <b>Welcome to Telegive Bot!</b>\n\n"
                "This bot handles giveaway participation with:\n"
                "• 🎯 One-click participation\n"
                "• 🧮 Global captcha system\n"
                "• 📊 Subscription verification\n"
                "• 🏆 Result checking\n\n"
                "Click the '🎯 Participate' button in giveaway posts to join!",
                parse_mode='HTML'
            )
            print(f"✅ Welcome message sent to user {user_id}")
            return
        
        # Handle giveaway participation
        command = args[0]
        if command.startswith('giveaway_'):
            try:
                giveaway_id = int(command.split('_')[1])
                await handle_giveaway_participation(update, user_id, giveaway_id, user_info)
            except (ValueError, IndexError):
                await update.message.reply_text("❌ Invalid giveaway link.")
                print(f"❌ Invalid giveaway link from user {user_id}")
        
        elif command.startswith('result_'):
            try:
                result_token = command.split('_', 1)[1]
                await handle_result_check(update, user_id, result_token)
            except IndexError:
                await update.message.reply_text("❌ Invalid result link.")
                print(f"❌ Invalid result link from user {user_id}")
        
        else:
            await update.message.reply_text("❌ Unknown command.")
            print(f"❌ Unknown command from user {user_id}: {command}")
            
    except Exception as e:
        print(f"❌ Start handler error: {e}")
        try:
            await update.message.reply_text("❌ Sorry, there was an error processing your request.")
        except:
            print("❌ Failed to send error message")

async def handle_giveaway_participation(update, user_id, giveaway_id, user_info):
    """Handle giveaway participation with full participant service integration"""
    try:
        print(f"🎯 Processing giveaway participation: user {user_id}, giveaway {giveaway_id}")
        
        # Step 1: Check captcha status for optimization
        captcha_status = check_user_captcha_status(user_id)
        print(f"📊 Captcha status for user {user_id}: {captcha_status}")
        
        # Step 2: Register participation
        result = register_user_participation(user_id, giveaway_id, user_info)
        print(f"📝 Registration result: {result}")
        
        if result['action'] == 'show_captcha':
            # Store captcha session
            store_user_session(user_id, {
                'type': 'captcha',
                'giveaway_id': giveaway_id,
                'session_id': result['session_id'],
                'question': result['question']
            })
            
            await update.message.reply_text(
                f"🧮 <b>Captcha Required</b>\n\n"
                f"To participate in giveaways, please solve this simple math problem:\n\n"
                f"<b>{result['question']}</b>\n\n"
                f"Please reply with just the number.",
                parse_mode='HTML'
            )
            print(f"🧮 Captcha sent to user {user_id}")
            
        elif result['action'] == 'confirm_participation':
            await update.message.reply_text(
                "🎉 <b>Participation Confirmed!</b>\n\n"
                "You're now participating in this giveaway. "
                "Good luck! 🍀\n\n"
                "You'll be notified when results are available.",
                parse_mode='HTML'
            )
            print(f"✅ Participation confirmed for user {user_id}")
            
        else:
            error_message = handle_participant_service_errors({'success': False, 'error': result.get('error')})
            await update.message.reply_text(f"❌ {error_message}")
            print(f"❌ Participation error for user {user_id}: {error_message}")
            
    except Exception as e:
        print(f"❌ Giveaway participation error: {e}")
        await update.message.reply_text("❌ Sorry, there was an error processing your participation.")

async def handle_result_check(update, user_id, result_token):
    """Handle result checking with participant service integration"""
    try:
        print(f"🏆 Processing result check: user {user_id}, token {result_token}")
        
        # TODO: Get giveaway info from result token (would need Giveaway Service integration)
        # For now, extract giveaway_id from token format
        try:
            giveaway_id = int(result_token.split('_')[0])
        except (ValueError, IndexError):
            await update.message.reply_text("❌ Invalid result token.")
            return
        
        # Check winner status
        winner_status = check_winner_status(user_id, giveaway_id)
        print(f"🏆 Winner status: {winner_status}")
        
        if not winner_status['participated']:
            await update.message.reply_text(
                "❌ <b>Not Participated</b>\n\n"
                "You didn't participate in this giveaway.",
                parse_mode='HTML'
            )
        elif winner_status['is_winner']:
            await update.message.reply_text(
                "🎉 <b>Congratulations!</b>\n\n"
                "You won this giveaway! 🏆\n\n"
                "Check your DMs for prize details.",
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text(
                "😔 <b>Better Luck Next Time</b>\n\n"
                "You didn't win this giveaway, but don't give up!\n\n"
                "Keep participating for more chances to win! 🍀",
                parse_mode='HTML'
            )
            
    except Exception as e:
        print(f"❌ Result check error: {e}")
        await update.message.reply_text("❌ Sorry, there was an error checking your results.")

async def message_handler_with_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages with captcha processing"""
    try:
        user_id = update.effective_user.id
        text = update.message.text.strip()
        
        print(f"💬 Message from user {user_id}: {text}")
        
        # Check if user has active captcha session
        session = get_user_session(user_id)
        
        if session and session.get('type') == 'captcha':
            # Process captcha answer
            try:
                answer = int(text)
                giveaway_id = session['giveaway_id']
                
                print(f"🧮 Processing captcha answer: {answer} for giveaway {giveaway_id}")
                
                result = validate_captcha_answer(user_id, giveaway_id, answer)
                print(f"🧮 Captcha validation result: {result}")
                
                if result['action'] == 'confirm_participation':
                    clear_user_session(user_id)
                    await update.message.reply_text(
                        "✅ <b>Correct!</b>\n\n"
                        "🎉 <b>Participation Confirmed!</b>\n\n"
                        "You're now participating in this giveaway. "
                        "Good luck! 🍀\n\n"
                        "You'll be notified when results are available.",
                        parse_mode='HTML'
                    )
                    print(f"✅ Captcha completed and participation confirmed for user {user_id}")
                    
                elif result['action'] == 'retry_captcha':
                    if result.get('new_question'):
                        # Update session with new question
                        session['question'] = result['new_question']
                        store_user_session(user_id, session)
                        
                        await update.message.reply_text(
                            f"❌ <b>Incorrect Answer</b>\n\n"
                            f"New question:\n\n"
                            f"<b>{result['new_question']}</b>\n\n"
                            f"Please reply with just the number.",
                            parse_mode='HTML'
                        )
                    else:
                        await update.message.reply_text(
                            f"❌ <b>Incorrect Answer</b>\n\n"
                            f"You have {result['attempts_remaining']} attempts remaining.\n\n"
                            f"Please try again with the same question:\n"
                            f"<b>{session['question']}</b>",
                            parse_mode='HTML'
                        )
                    print(f"❌ Incorrect captcha answer from user {user_id}")
                    
                else:
                    clear_user_session(user_id)
                    error_message = handle_participant_service_errors({'success': False, 'error': result.get('error')})
                    await update.message.reply_text(f"❌ {error_message}")
                    print(f"❌ Captcha error for user {user_id}: {error_message}")
                    
            except ValueError:
                await update.message.reply_text(
                    "❌ <b>Invalid Format</b>\n\n"
                    "Please reply with just the number.\n\n"
                    f"Question: <b>{session['question']}</b>",
                    parse_mode='HTML'
                )
                print(f"❌ Invalid captcha format from user {user_id}")
        else:
            # Regular message handling
            await update.message.reply_text(
                "👋 Hello! Use /start to begin or click a giveaway participation link."
            )
            print(f"✅ Regular response sent to user {user_id}")
        
    except Exception as e:
        print(f"❌ Message handler error: {e}")

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

def initialize_telegram_bot_with_token(bot_token, bot_username=None, bot_id=None):
    """Initialize Telegram bot with provided token"""
    global telegram_app, telegram_bot, current_bot_token, current_bot_username, current_bot_id
    
    if not bot_token:
        print("❌ No bot token provided for initialization")
        return False
    
    try:
        print(f"🤖 Initializing Telegram bot with participant service integration...")
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
        
        # Add handlers with participant service integration
        telegram_app.add_handler(CommandHandler("start", start_handler_with_participant_integration))
        telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler_with_captcha))
        
        # Update global state
        current_bot_token = bot_token
        current_bot_username = bot_username
        current_bot_id = bot_id
        
        print(f"✅ Telegram bot initialized with participant service integration!")
        print(f"🎉 Bot @{bot_username} is ready for full giveaway participation!")
        
        return True
    
    except Exception as e:
        print(f"❌ Telegram bot initialization error: {e}")
        return False

# FIXED: Simplified webhook handler with participant service integration
@app.route('/webhook', methods=['POST'])
def webhook_with_participant_integration():
    """Handle Telegram webhook with participant service integration"""
    global telegram_bot, telegram_app
    
    try:
        print("📨 Webhook received with participant integration!")
        
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
        print(f"📨 Processing webhook update with participant integration: {update_id}")
        
        # Process message with participant service integration
        if 'message' in update_data:
            message = update_data['message']
            text = message.get('text', '')
            chat_id = message.get('chat', {}).get('id')
            user_id = message.get('from', {}).get('id')
            username = message.get('from', {}).get('username')
            first_name = message.get('from', {}).get('first_name')
            last_name = message.get('from', {}).get('last_name')
            
            user_info = {
                'username': username,
                'first_name': first_name,
                'last_name': last_name
            }
            
            print(f"💬 Message received: '{text}' from user {user_id} (@{username})")
            
            # Handle /start command with participant integration
            if text.startswith('/start'):
                try:
                    print(f"🎯 Processing /start command with participant integration from user {user_id}")
                    
                    # Extract args from /start command
                    parts = text.split(' ', 1)
                    args = parts[1] if len(parts) > 1 else None
                    
                    if not args:
                        # Send welcome message
                        response_text = (
                            "🤖 <b>Welcome to Telegive Bot!</b>\n\n"
                            "This bot handles giveaway participation with:\n"
                            "• 🎯 One-click participation\n"
                            "• 🧮 Global captcha system\n"
                            "• 📊 Subscription verification\n"
                            "• 🏆 Result checking\n\n"
                            "Click the '🎯 Participate' button in giveaway posts to join!"
                        )
                        print(f"📤 Sending welcome message to chat {chat_id}")
                        
                    elif args.startswith('giveaway_'):
                        # Handle giveaway participation
                        try:
                            giveaway_id = int(args.split('_')[1])
                            print(f"🎯 Processing giveaway participation: giveaway {giveaway_id}")
                            
                            # Check captcha status first
                            captcha_status = check_user_captcha_status(user_id)
                            
                            # Register participation
                            result = register_user_participation(user_id, giveaway_id, user_info)
                            
                            if result['action'] == 'show_captcha':
                                # Store captcha session
                                store_user_session(user_id, {
                                    'type': 'captcha',
                                    'giveaway_id': giveaway_id,
                                    'session_id': result['session_id'],
                                    'question': result['question']
                                })
                                
                                response_text = (
                                    f"🧮 <b>Captcha Required</b>\n\n"
                                    f"To participate in giveaways, please solve this simple math problem:\n\n"
                                    f"<b>{result['question']}</b>\n\n"
                                    f"Please reply with just the number."
                                )
                                
                            elif result['action'] == 'confirm_participation':
                                response_text = (
                                    "🎉 <b>Participation Confirmed!</b>\n\n"
                                    "You're now participating in this giveaway. "
                                    "Good luck! 🍀\n\n"
                                    "You'll be notified when results are available."
                                )
                                
                            else:
                                error_message = handle_participant_service_errors({'success': False, 'error': result.get('error')})
                                response_text = f"❌ {error_message}"
                                
                        except (ValueError, IndexError):
                            response_text = "❌ Invalid giveaway link."
                            
                    elif args.startswith('result_'):
                        # Handle result checking
                        try:
                            result_token = args.split('_', 1)[1]
                            giveaway_id = int(result_token.split('_')[0])
                            
                            winner_status = check_winner_status(user_id, giveaway_id)
                            
                            if not winner_status['participated']:
                                response_text = (
                                    "❌ <b>Not Participated</b>\n\n"
                                    "You didn't participate in this giveaway."
                                )
                            elif winner_status['is_winner']:
                                response_text = (
                                    "🎉 <b>Congratulations!</b>\n\n"
                                    "You won this giveaway! 🏆\n\n"
                                    "Check your DMs for prize details."
                                )
                            else:
                                response_text = (
                                    "😔 <b>Better Luck Next Time</b>\n\n"
                                    "You didn't win this giveaway, but don't give up!\n\n"
                                    "Keep participating for more chances to win! 🍀"
                                )
                                
                        except (ValueError, IndexError):
                            response_text = "❌ Invalid result link."
                            
                    else:
                        response_text = "❌ Unknown command."
                    
                    # Send response using direct bot instance
                    telegram_url = f"https://api.telegram.org/bot{current_bot_token}/sendMessage"
                    payload = {
                        'chat_id': chat_id,
                        'text': response_text,
                        'parse_mode': 'HTML'
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
                # Handle regular messages (captcha answers)
                try:
                    print(f"💬 Processing regular message from user {user_id}")
                    
                    # Check if user has active captcha session
                    session = get_user_session(user_id)
                    
                    if session and session.get('type') == 'captcha':
                        # Process captcha answer
                        try:
                            answer = int(text)
                            giveaway_id = session['giveaway_id']
                            
                            result = validate_captcha_answer(user_id, giveaway_id, answer)
                            
                            if result['action'] == 'confirm_participation':
                                clear_user_session(user_id)
                                response_text = (
                                    "✅ <b>Correct!</b>\n\n"
                                    "🎉 <b>Participation Confirmed!</b>\n\n"
                                    "You're now participating in this giveaway. "
                                    "Good luck! 🍀\n\n"
                                    "You'll be notified when results are available."
                                )
                                
                            elif result['action'] == 'retry_captcha':
                                if result.get('new_question'):
                                    # Update session with new question
                                    session['question'] = result['new_question']
                                    store_user_session(user_id, session)
                                    
                                    response_text = (
                                        f"❌ <b>Incorrect Answer</b>\n\n"
                                        f"New question:\n\n"
                                        f"<b>{result['new_question']}</b>\n\n"
                                        f"Please reply with just the number."
                                    )
                                else:
                                    response_text = (
                                        f"❌ <b>Incorrect Answer</b>\n\n"
                                        f"You have {result['attempts_remaining']} attempts remaining.\n\n"
                                        f"Please try again with the same question:\n"
                                        f"<b>{session['question']}</b>"
                                    )
                                    
                            else:
                                clear_user_session(user_id)
                                error_message = handle_participant_service_errors({'success': False, 'error': result.get('error')})
                                response_text = f"❌ {error_message}"
                                
                        except ValueError:
                            response_text = (
                                "❌ <b>Invalid Format</b>\n\n"
                                "Please reply with just the number.\n\n"
                                f"Question: <b>{session['question']}</b>"
                            )
                    else:
                        # Regular message
                        response_text = "👋 Hello! Use /start to begin or click a giveaway participation link."
                    
                    # Send response
                    telegram_url = f"https://api.telegram.org/bot{current_bot_token}/sendMessage"
                    payload = {
                        'chat_id': chat_id,
                        'text': response_text,
                        'parse_mode': 'HTML'
                    }
                    
                    response = requests.post(telegram_url, json=payload, timeout=10)
                    
                    if response.status_code == 200:
                        print(f"✅ Response sent to chat {chat_id}")
                    else:
                        print(f"❌ Failed to send response: {response.status_code}")
                        
                except Exception as e:
                    print(f"❌ Error processing message: {e}")
        
        print(f"✅ Webhook processed successfully with participant integration: {update_id}")
        return jsonify({'status': 'ok'})
    
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        print(f"❌ Webhook traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

# Flask Routes (same as before but with participant integration info)
@app.route('/')
def home():
    """Main service endpoint"""
    db_status = test_database_connection()
    bot_status = get_bot_status()
    
    return jsonify({
        'service': 'telegive-bot-service',
        'status': 'working',
        'version': '1.2.0-phase6-participant-integration',
        'phase': 'Phase 6 - Complete Participant Service Integration',
        'message': 'Bot Service with full participant service integration for giveaway participation',
        'features': [
            'basic_endpoints', 'json_responses', 'error_handling', 
            'database_connection', 'optimized_service_integrations', 
            'service_status_caching', 'background_tasks', 'auth_service_token',
            'telegram_bot_integration', 'giveaway_participation_flow',
            'global_captcha_system', 'subscription_verification',
            'push_notification_system', 'instant_bot_token_updates',
            'flask_decorator_conflict_fixed', 'webhook_handler_fixed',
            'participant_service_integration', 'captcha_processing',
            'winner_status_checking', 'delivery_status_tracking'
        ],
        'participant_integration': {
            'api_endpoints': 6,
            'features': [
                'participation_registration',
                'captcha_status_check',
                'captcha_validation',
                'winner_status_check',
                'subscription_verification',
                'delivery_status_updates'
            ],
            'error_handling': 'comprehensive',
            'retry_logic': 'exponential_backoff',
            'session_management': 'thread_safe'
        },
        'database': {
            'configured': database_configured,
            'status': db_status['status'],
            'message': db_status['message']
        },
        'telegram_bot': bot_status,
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
            print(f"🚀 Initializing bot with participant integration for bot_id: {bot_id}")
            
            bot_initialized = initialize_telegram_bot_with_token(bot_token, bot_username, bot_id)
            
            processing_time = time.time() - processing_start
            last_token_update = datetime.now(timezone.utc)
            
            if bot_initialized:
                print("✅ Bot initialized successfully with participant service integration")
                
                return jsonify({
                    'success': True,
                    'message': 'Token updated successfully - Participant service integration active',
                    'bot_initialized': True,
                    'participant_integration': 'enabled',
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
        'direct_bot_available': telegram_bot is not None,
        'participant_integration': {
            'enabled': True,
            'api_endpoints': 6,
            'session_management': 'active',
            'active_sessions': len(user_sessions)
        }
    }

# Bot status endpoint
@app.route('/bot/status')
@create_service_token_decorator('bot_status')
def bot_status_endpoint():
    """Get detailed bot status information"""
    try:
        bot_status = get_bot_status()
        
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

# Participant integration stats endpoint
@app.route('/participant/stats')
@create_service_token_decorator('participant_stats')
def participant_stats():
    """Get participant service integration statistics"""
    try:
        with app.app_context():
            if db:
                # Get interaction statistics
                total_interactions = db.session.query(ParticipantInteraction).count()
                successful_interactions = db.session.query(ParticipantInteraction).filter_by(success=True).count()
                
                # Get interaction types
                interaction_types = db.session.query(
                    ParticipantInteraction.interaction_type,
                    db.func.count(ParticipantInteraction.id)
                ).group_by(ParticipantInteraction.interaction_type).all()
                
                # Get recent interactions (last 24 hours)
                recent_cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
                recent_interactions = db.session.query(ParticipantInteraction).filter(
                    ParticipantInteraction.timestamp >= recent_cutoff
                ).count()
                
                stats = {
                    'total_interactions': total_interactions,
                    'successful_interactions': successful_interactions,
                    'success_rate': (successful_interactions / total_interactions * 100) if total_interactions > 0 else 0,
                    'recent_interactions_24h': recent_interactions,
                    'interaction_types': {itype: count for itype, count in interaction_types},
                    'active_sessions': len(user_sessions),
                    'api_endpoints_available': 6
                }
            else:
                stats = {
                    'database_unavailable': True,
                    'active_sessions': len(user_sessions),
                    'api_endpoints_available': 6
                }
        
        return jsonify({
            'participant_integration_stats': stats,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
    
    except Exception as e:
        return jsonify({
            'error': 'Failed to get participant stats',
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

def init_application():
    """Initialize database and background tasks on startup"""
    if db:
        try:
            with app.app_context():
                db.create_all()
                print("Database tables created successfully")
                
                startup_log = ServiceLog(
                    level='INFO',
                    message='Bot Service Phase 6 started with complete participant service integration',
                    endpoint='startup'
                )
                db.session.add(startup_log)
                db.session.commit()
                print("Startup logged to database")
                
        except Exception as e:
            print(f"Database initialization error: {e}")
    
    print("🎯 Complete participant service integration ready!")
    print("📊 6 API endpoints available for giveaway participation")

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'error': 'Not Found',
        'message': 'The requested endpoint does not exist',
        'phase': 'Phase 6 - Complete Participant Service Integration',
        'available_endpoints': [
            '/', '/webhook', '/bot/token/update', '/bot/status', '/participant/stats'
        ],
        'timestamp': datetime.now(timezone.utc).isoformat()
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'error': 'Internal Server Error',
        'message': 'An internal error occurred',
        'phase': 'Phase 6 - Complete Participant Service Integration',
        'timestamp': datetime.now(timezone.utc).isoformat()
    }), 500

# For production (Gunicorn)
if __name__ != '__main__':
    init_application()

# For development testing only
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting Bot Service Phase 6 (Complete Participant Integration) on port {port}")
    
    with app.app_context():
        try:
            db.create_all()
            print("Development database initialized")
        except Exception as e:
            print(f"Development database error: {e}")
    
    init_application()
    
    app.run(host='0.0.0.0', port=port, debug=False)

