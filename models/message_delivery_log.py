from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

db = SQLAlchemy()

class MessageDeliveryLog(db.Model):
    __tablename__ = 'message_delivery_log'
    
    id = db.Column(db.BigInteger, primary_key=True)
    giveaway_id = db.Column(db.BigInteger, nullable=False)
    user_id = db.Column(db.BigInteger, nullable=False)
    message_type = db.Column(db.String(50), nullable=False)  # winner, loser, participation_confirm, captcha
    
    # Delivery details
    telegram_message_id = db.Column(db.BigInteger, nullable=True)
    delivery_status = db.Column(db.String(20), default='pending')  # pending, sent, failed, blocked
    delivery_attempts = db.Column(db.Integer, default=0)
    max_attempts = db.Column(db.Integer, default=3)
    
    # Error handling
    error_code = db.Column(db.String(50), nullable=True)
    error_description = db.Column(db.Text, nullable=True)
    
    # Timing
    scheduled_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    delivered_at = db.Column(db.DateTime(timezone=True), nullable=True)
    last_attempt_at = db.Column(db.DateTime(timezone=True), nullable=True)
    
    def __repr__(self):
        return f'<MessageDeliveryLog {self.id}: {self.message_type} to {self.user_id} ({self.delivery_status})>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'giveaway_id': self.giveaway_id,
            'user_id': self.user_id,
            'message_type': self.message_type,
            'telegram_message_id': self.telegram_message_id,
            'delivery_status': self.delivery_status,
            'delivery_attempts': self.delivery_attempts,
            'max_attempts': self.max_attempts,
            'error_code': self.error_code,
            'error_description': self.error_description,
            'scheduled_at': self.scheduled_at.isoformat() if self.scheduled_at else None,
            'delivered_at': self.delivered_at.isoformat() if self.delivered_at else None,
            'last_attempt_at': self.last_attempt_at.isoformat() if self.last_attempt_at else None
        }

