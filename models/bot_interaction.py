from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

db = SQLAlchemy()

class BotInteraction(db.Model):
    __tablename__ = 'bot_interactions'
    
    id = db.Column(db.BigInteger, primary_key=True)
    user_id = db.Column(db.BigInteger, nullable=False)
    interaction_type = db.Column(db.String(50), nullable=False)  # participate, check_result, captcha, subscription
    giveaway_id = db.Column(db.BigInteger, nullable=True)
    
    # Interaction details
    message_text = db.Column(db.Text, nullable=True)
    callback_data = db.Column(db.Text, nullable=True)
    response_sent = db.Column(db.Text, nullable=True)
    success = db.Column(db.Boolean, default=True)
    error_message = db.Column(db.Text, nullable=True)
    
    # Context
    chat_id = db.Column(db.BigInteger, nullable=True)
    message_id = db.Column(db.BigInteger, nullable=True)
    from_channel = db.Column(db.Boolean, default=False)
    
    # Timing
    interaction_timestamp = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    response_timestamp = db.Column(db.DateTime(timezone=True), nullable=True)
    processing_time_ms = db.Column(db.Integer, nullable=True)
    
    def __repr__(self):
        return f'<BotInteraction {self.id}: {self.interaction_type} by {self.user_id}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'interaction_type': self.interaction_type,
            'giveaway_id': self.giveaway_id,
            'message_text': self.message_text,
            'callback_data': self.callback_data,
            'response_sent': self.response_sent,
            'success': self.success,
            'error_message': self.error_message,
            'chat_id': self.chat_id,
            'message_id': self.message_id,
            'from_channel': self.from_channel,
            'interaction_timestamp': self.interaction_timestamp.isoformat() if self.interaction_timestamp else None,
            'response_timestamp': self.response_timestamp.isoformat() if self.response_timestamp else None,
            'processing_time_ms': self.processing_time_ms
        }

