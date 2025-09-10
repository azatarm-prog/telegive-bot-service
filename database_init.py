#!/usr/bin/env python3
"""
Database initialization script for Bot Service
Creates all tables and indexes as specified in the documentation
"""

import os
import sys
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config.settings import Config

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import db, BotInteraction, MessageDeliveryLog, WebhookProcessingLog

def create_app():
    """Create Flask app for database initialization"""
    app = Flask(__name__)
    app.config.from_object(Config)
    
    db.init_app(app)
    
    return app

def create_indexes(db_session):
    """Create indexes as specified in the documentation"""
    indexes = [
        # Bot interactions indexes
        "CREATE INDEX IF NOT EXISTS idx_bot_interactions_user_id ON bot_interactions(user_id);",
        "CREATE INDEX IF NOT EXISTS idx_bot_interactions_giveaway_id ON bot_interactions(giveaway_id);",
        "CREATE INDEX IF NOT EXISTS idx_bot_interactions_type ON bot_interactions(interaction_type);",
        
        # Message delivery log indexes
        "CREATE INDEX IF NOT EXISTS idx_message_delivery_log_giveaway_user ON message_delivery_log(giveaway_id, user_id);",
        "CREATE INDEX IF NOT EXISTS idx_message_delivery_log_status ON message_delivery_log(delivery_status);",
        
        # Webhook processing log indexes
        "CREATE INDEX IF NOT EXISTS idx_webhook_processing_log_update_id ON webhook_processing_log(update_id);",
        "CREATE INDEX IF NOT EXISTS idx_webhook_processing_log_status ON webhook_processing_log(processing_status);"
    ]
    
    for index_sql in indexes:
        try:
            db_session.execute(index_sql)
            print(f"✓ Created index: {index_sql.split('idx_')[1].split(' ')[0] if 'idx_' in index_sql else 'unknown'}")
        except Exception as e:
            print(f"✗ Failed to create index: {e}")

def init_database():
    """Initialize database with tables and indexes"""
    app = create_app()
    
    with app.app_context():
        try:
            # Create all tables
            print("Creating database tables...")
            db.create_all()
            print("✓ All tables created successfully")
            
            # Create indexes
            print("Creating database indexes...")
            create_indexes(db.session)
            db.session.commit()
            print("✓ All indexes created successfully")
            
            print("\n🎉 Database initialization completed successfully!")
            
        except Exception as e:
            print(f"✗ Database initialization failed: {e}")
            db.session.rollback()
            return False
    
    return True

if __name__ == "__main__":
    success = init_database()
    sys.exit(0 if success else 1)

