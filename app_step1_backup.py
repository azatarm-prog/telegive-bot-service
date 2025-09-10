"""
Step 1: Add database support to the working Flask app
"""
import os
from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

app = Flask(__name__)

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
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')

# Initialize database
db = SQLAlchemy(app)

# Simple test model
class HealthCheck(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default='healthy')

@app.route('/')
def hello():
    return jsonify({
        'status': 'working',
        'message': 'Step 1: Flask app with database support',
        'service': 'telegive-bot-service',
        'step': 1,
        'features': ['basic_flask', 'database_support']
    })

@app.route('/health')
def health():
    health_data = {
        'status': 'healthy',
        'service': 'telegive-bot-service',
        'step': 1,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }
    
    # Test database connection
    try:
        # Try to create tables if they don't exist
        db.create_all()
        
        # Test database write/read
        health_record = HealthCheck(status='healthy')
        db.session.add(health_record)
        db.session.commit()
        
        # Count records
        record_count = HealthCheck.query.count()
        
        health_data['database'] = {
            'status': 'connected',
            'records': record_count,
            'url_configured': bool(os.environ.get('DATABASE_URL'))
        }
        
    except Exception as e:
        health_data['database'] = {
            'status': 'error',
            'error': str(e)
        }
        health_data['status'] = 'degraded'
    
    return jsonify(health_data)

@app.route('/database/test')
def database_test():
    """Test database operations"""
    try:
        # Create tables
        db.create_all()
        
        # Add test record
        test_record = HealthCheck(status='test')
        db.session.add(test_record)
        db.session.commit()
        
        # Query records
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

