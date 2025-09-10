"""
Step 4: Add service-to-service communication
"""
import os
import json
import requests
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
from urllib.parse import urljoin

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

class WebhookLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bot_id = db.Column(db.String(100), nullable=False)
    webhook_data = db.Column(db.Text, nullable=False)
    processed_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default='received')
    response_sent = db.Column(db.Text)

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

# Service Communication Helper
class ServiceClient:
    def __init__(self):
        self.timeout = 10
        self.headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Telegive-Bot-Service/1.0'
        }
    
    def call_service(self, service_name, endpoint, method='GET', data=None, user_id=None):
        """Make a call to another service"""
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
            
            # Update interaction log
            interaction.status_code = response.status_code
            interaction.response_data = response.text
            interaction.success = response.status_code < 400
            
            db.session.add(interaction)
            db.session.commit()
            
            if response.status_code < 400:
                try:
                    return {'success': True, 'data': response.json(), 'status_code': response.status_code}
                except:
                    return {'success': True, 'data': response.text, 'status_code': response.status_code}
            else:
                return {'success': False, 'error': f'HTTP {response.status_code}', 'response': response.text}
                
        except requests.exceptions.Timeout:
            interaction.success = False
            interaction.response_data = 'Timeout'
            db.session.add(interaction)
            db.session.commit()
            return {'success': False, 'error': 'Service timeout'}
        except Exception as e:
            interaction.success = False
            interaction.response_data = str(e)
            db.session.add(interaction)
            db.session.commit()
            return {'success': False, 'error': str(e)}

# Telegram API Helper Class
class TelegramBot:
    def __init__(self, bot_token):
        self.bot_token = bot_token
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
    
    def send_message(self, chat_id, text, reply_markup=None):
        """Send a message to a chat"""
        url = f"{self.base_url}/sendMessage"
        data = {
            'chat_id': chat_id,
            'text': text
        }
        if reply_markup:
            data['reply_markup'] = json.dumps(reply_markup)
        
        try:
            response = requests.post(url, json=data, timeout=10)
            return response.json()
        except Exception as e:
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

# Initialize service client
service_client = ServiceClient()

# Basic routes
@app.route('/')
def hello():
    return jsonify({
        'status': 'working',
        'message': 'Step 4: Flask app with service-to-service communication',
        'service': 'telegive-bot-service',
        'step': 4,
        'features': ['basic_flask', 'database_support', 'api_endpoints', 'webhook_handling', 'telegram_integration', 'service_communication'],
        'connected_services': list(SERVICE_URLS.keys())
    })

@app.route('/health')
def health():
    health_data = {
        'status': 'healthy',
        'service': 'telegive-bot-service',
        'step': 4,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }
    
    # Test database connection
    try:
        db.create_all()
        health_record = HealthCheck(status='healthy')
        db.session.add(health_record)
        db.session.commit()
        
        record_count = HealthCheck.query.count()
        bot_count = BotRegistration.query.count()
        webhook_count = WebhookLog.query.count()
        message_count = MessageLog.query.count()
        service_interaction_count = ServiceInteraction.query.count()
        
        health_data['database'] = {
            'status': 'connected',
            'health_records': record_count,
            'registered_bots': bot_count,
            'webhook_logs': webhook_count,
            'message_logs': message_count,
            'service_interactions': service_interaction_count,
            'url_configured': bool(os.environ.get('DATABASE_URL'))
        }
        
        # Test service connectivity
        health_data['services'] = {}
        for service_name, service_url in SERVICE_URLS.items():
            try:
                response = requests.get(f"{service_url}/health", timeout=5)
                health_data['services'][service_name] = {
                    'url': service_url,
                    'status': 'reachable' if response.status_code < 400 else 'error',
                    'response_time': response.elapsed.total_seconds()
                }
            except:
                health_data['services'][service_name] = {
                    'url': service_url,
                    'status': 'unreachable',
                    'response_time': None
                }
        
    except Exception as e:
        health_data['database'] = {
            'status': 'error',
            'error': str(e)
        }
        health_data['status'] = 'degraded'
    
    return jsonify(health_data)

# Service integration endpoints
@app.route('/api/services/test', methods=['POST'])
def test_service_communication():
    """Test communication with other services"""
    try:
        data = request.get_json() or {}
        service_name = data.get('service', 'auth')
        endpoint = data.get('endpoint', '/health')
        method = data.get('method', 'GET')
        payload = data.get('data')
        
        result = service_client.call_service(service_name, endpoint, method, payload)
        
        return jsonify({
            'status': 'success',
            'service': service_name,
            'endpoint': endpoint,
            'result': result
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@app.route('/api/services/interactions', methods=['GET'])
def get_service_interactions():
    """Get recent service interactions"""
    try:
        limit = request.args.get('limit', 20, type=int)
        interactions = ServiceInteraction.query.order_by(ServiceInteraction.created_at.desc()).limit(limit).all()
        
        interaction_list = []
        for interaction in interactions:
            interaction_list.append({
                'id': interaction.id,
                'service_name': interaction.service_name,
                'endpoint': interaction.endpoint,
                'status_code': interaction.status_code,
                'success': interaction.success,
                'created_at': interaction.created_at.isoformat(),
                'user_id': interaction.user_id
            })
        
        return jsonify({
            'status': 'success',
            'interactions': interaction_list,
            'total': len(interaction_list)
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

# Enhanced bot registration with service integration
@app.route('/api/bots/register', methods=['POST'])
def register_bot():
    """Register a new bot with Telegram token and service integration"""
    try:
        data = request.get_json()
        
        if not data or 'bot_token' not in data or 'user_id' not in data:
            return jsonify({
                'status': 'error',
                'error': 'Missing required fields: bot_token, user_id'
            }), 400
        
        user_id = data['user_id']
        
        # Validate user with auth service
        auth_result = service_client.call_service('auth', f'/api/users/{user_id}', 'GET', user_id=user_id)
        
        # Validate bot token by calling Telegram API
        telegram_bot = TelegramBot(data['bot_token'])
        bot_info = telegram_bot.get_me()
        
        if not bot_info.get('ok'):
            return jsonify({
                'status': 'error',
                'error': 'Invalid bot token'
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
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

# API Endpoints (existing ones)
@app.route('/api/bots', methods=['GET'])
def list_bots():
    """List registered bots"""
    try:
        bots = BotRegistration.query.filter_by(is_active=True).all()
        bot_list = []
        
        for bot in bots:
            bot_list.append({
                'bot_id': bot.bot_id,
                'user_id': bot.user_id,
                'created_at': bot.created_at.isoformat(),
                'is_active': bot.is_active,
                'webhook_set': bot.webhook_set
            })
        
        return jsonify({
            'status': 'success',
            'bots': bot_list,
            'total': len(bot_list)
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@app.route('/api/bots/<bot_id>', methods=['DELETE'])
def unregister_bot(bot_id):
    """Unregister a bot"""
    try:
        bot = BotRegistration.query.filter_by(bot_id=bot_id).first()
        
        if not bot:
            return jsonify({
                'status': 'error',
                'error': 'Bot not found'
            }), 404
        
        bot.is_active = False
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Bot unregistered successfully'
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

# Enhanced webhook handler with service integration
@app.route('/webhook/<bot_id>', methods=['POST'])
def webhook_handler(bot_id):
    """Handle Telegram webhook for specific bot with service integration"""
    try:
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
        
        # Process message with service integration
        response_data = process_telegram_message_with_services(bot, webhook_data, webhook_log)
        
        return jsonify(response_data)
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

def process_telegram_message_with_services(bot, webhook_data, webhook_log):
    """Process incoming Telegram message with service integration"""
    try:
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
            username=username
        )
        db.session.add(message_log)
        
        # Process commands with service integration
        response_text = None
        service_data = {}
        
        if text.startswith('/start'):
            response_text = f"Hello {username or 'there'}! Welcome to the Telegive Bot Service with full service integration!"
            
            # Check user with auth service
            auth_result = service_client.call_service('auth', f'/api/users/{user_id}', 'GET', user_id=str(user_id))
            service_data['auth_check'] = auth_result
            
        elif text.startswith('/help'):
            response_text = """Available commands:
/start - Start the bot
/help - Show this help
/status - Check bot status
/channels - List your channels
/participants - Check participants"""
            
        elif text.startswith('/status'):
            response_text = f"Bot Status: Active\nBot ID: {bot.bot_id}\nService: Telegive Bot Service Step 4\nServices: Connected"
            
        elif text.startswith('/channels'):
            # Get user channels from channel service
            channels_result = service_client.call_service('channel', f'/api/channels/user/{user_id}', 'GET', user_id=str(user_id))
            service_data['channels'] = channels_result
            
            if channels_result.get('success'):
                channels = channels_result.get('data', {}).get('channels', [])
                if channels:
                    response_text = f"Your channels ({len(channels)}):\n" + "\n".join([f"• {ch.get('name', 'Unknown')}" for ch in channels[:5]])
                else:
                    response_text = "You don't have any channels yet."
            else:
                response_text = "Unable to fetch channels at the moment."
                
        elif text.startswith('/participants'):
            # Get participants from participant service
            participants_result = service_client.call_service('participant', f'/api/participants/user/{user_id}', 'GET', user_id=str(user_id))
            service_data['participants'] = participants_result
            
            if participants_result.get('success'):
                participants = participants_result.get('data', {}).get('participants', [])
                response_text = f"Total participants: {len(participants)}"
            else:
                response_text = "Unable to fetch participants at the moment."
                
        else:
            response_text = f"You said: {text}\n\nThis is a test response from the Telegive Bot Service (Step 4) with service integration."
        
        # Send response
        if response_text:
            send_result = telegram_bot.send_message(chat_id, response_text)
            message_log.bot_response = json.dumps({
                'telegram_response': send_result,
                'service_data': service_data
            })
        
        # Update logs
        db.session.commit()
        webhook_log.status = 'processed'
        webhook_log.response_sent = response_text
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
        webhook_log.status = 'error'
        db.session.commit()
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

# Existing endpoints
@app.route('/api/webhooks/<bot_id>/logs', methods=['GET'])
def get_webhook_logs(bot_id):
    """Get webhook logs for a specific bot"""
    try:
        logs = WebhookLog.query.filter_by(bot_id=bot_id).order_by(WebhookLog.processed_at.desc()).limit(10).all()
        
        log_list = []
        for log in logs:
            log_list.append({
                'id': log.id,
                'processed_at': log.processed_at.isoformat(),
                'status': log.status,
                'response_sent': log.response_sent,
                'webhook_data': json.loads(log.webhook_data)
            })
        
        return jsonify({
            'status': 'success',
            'bot_id': bot_id,
            'logs': log_list,
            'total': len(log_list)
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@app.route('/api/messages/<bot_id>/logs', methods=['GET'])
def get_message_logs(bot_id):
    """Get message logs for a specific bot"""
    try:
        logs = MessageLog.query.filter_by(bot_id=bot_id).order_by(MessageLog.processed_at.desc()).limit(20).all()
        
        log_list = []
        for log in logs:
            log_list.append({
                'id': log.id,
                'chat_id': log.chat_id,
                'message_text': log.message_text,
                'message_type': log.message_type,
                'user_id': log.user_id,
                'username': log.username,
                'processed_at': log.processed_at.isoformat(),
                'bot_response': log.bot_response
            })
        
        return jsonify({
            'status': 'success',
            'bot_id': bot_id,
            'logs': log_list,
            'total': len(log_list)
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

# Database test endpoint
@app.route('/database/test')
def database_test():
    """Test database operations"""
    try:
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
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'database_url_set': bool(os.environ.get('DATABASE_URL'))
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    
    # Create tables on startup
    with app.app_context():
        try:
            db.create_all()
            print("Database tables created successfully")
        except Exception as e:
            print(f"Database initialization warning: {e}")
    
    app.run(host='0.0.0.0', port=port)

