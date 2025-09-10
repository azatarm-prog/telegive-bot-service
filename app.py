"""
Step 2: Add API endpoints and webhook functionality
"""
import os
import json
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

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
    bot_token_encrypted = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

class WebhookLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bot_id = db.Column(db.String(100), nullable=False)
    webhook_data = db.Column(db.Text, nullable=False)
    processed_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default='received')

# Basic routes
@app.route('/')
def hello():
    return jsonify({
        'status': 'working',
        'message': 'Step 2: Flask app with API endpoints and webhooks',
        'service': 'telegive-bot-service',
        'step': 2,
        'features': ['basic_flask', 'database_support', 'api_endpoints', 'webhook_handling']
    })

@app.route('/health')
def health():
    health_data = {
        'status': 'healthy',
        'service': 'telegive-bot-service',
        'step': 2,
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
        
        health_data['database'] = {
            'status': 'connected',
            'health_records': record_count,
            'registered_bots': bot_count,
            'webhook_logs': webhook_count,
            'url_configured': bool(os.environ.get('DATABASE_URL'))
        }
        
    except Exception as e:
        health_data['database'] = {
            'status': 'error',
            'error': str(e)
        }
        health_data['status'] = 'degraded'
    
    return jsonify(health_data)

# API Endpoints
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
                'is_active': bot.is_active
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

@app.route('/api/bots/register', methods=['POST'])
def register_bot():
    """Register a new bot"""
    try:
        data = request.get_json()
        
        if not data or 'bot_id' not in data or 'user_id' not in data:
            return jsonify({
                'status': 'error',
                'error': 'Missing required fields: bot_id, user_id'
            }), 400
        
        # Check if bot already exists
        existing_bot = BotRegistration.query.filter_by(bot_id=data['bot_id']).first()
        if existing_bot:
            return jsonify({
                'status': 'error',
                'error': 'Bot already registered'
            }), 409
        
        # Create new bot registration (token would be encrypted in production)
        new_bot = BotRegistration(
            bot_id=data['bot_id'],
            bot_token_encrypted='encrypted_token_placeholder',  # Would encrypt actual token
            user_id=data['user_id']
        )
        
        db.session.add(new_bot)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Bot registered successfully',
            'bot_id': data['bot_id'],
            'webhook_url': f"https://{request.host}/webhook/{data['bot_id']}"
        }), 201
        
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

# Webhook endpoints
@app.route('/webhook/<bot_id>', methods=['POST'])
def webhook_handler(bot_id):
    """Handle Telegram webhook for specific bot"""
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
        
        # Process webhook (placeholder for actual processing)
        response_data = {
            'status': 'processed',
            'bot_id': bot_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'message_type': webhook_data.get('message', {}).get('text', 'unknown')
        }
        
        # Update webhook log status
        webhook_log.status = 'processed'
        db.session.commit()
        
        return jsonify(response_data)
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

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

