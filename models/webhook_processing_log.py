from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

db = SQLAlchemy()

class WebhookProcessingLog(db.Model):
    __tablename__ = 'webhook_processing_log'
    
    id = db.Column(db.BigInteger, primary_key=True)
    update_id = db.Column(db.BigInteger, nullable=False, unique=True)
    update_type = db.Column(db.String(50), nullable=False)  # message, callback_query, inline_query
    
    # Update details
    user_id = db.Column(db.BigInteger, nullable=True)
    chat_id = db.Column(db.BigInteger, nullable=True)
    message_text = db.Column(db.Text, nullable=True)
    callback_data = db.Column(db.Text, nullable=True)
    
    # Processing
    processing_status = db.Column(db.String(20), default='pending')  # pending, processed, failed
    processing_time_ms = db.Column(db.Integer, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    
    # Response
    response_sent = db.Column(db.Boolean, default=False)
    response_type = db.Column(db.String(50), nullable=True)  # text, inline_keyboard, edit_message
    
    # Timing
    received_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    processed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    
    def __repr__(self):
        return f'<WebhookProcessingLog {self.id}: {self.update_type} ({self.processing_status})>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'update_id': self.update_id,
            'update_type': self.update_type,
            'user_id': self.user_id,
            'chat_id': self.chat_id,
            'message_text': self.message_text,
            'callback_data': self.callback_data,
            'processing_status': self.processing_status,
            'processing_time_ms': self.processing_time_ms,
            'error_message': self.error_message,
            'response_sent': self.response_sent,
            'response_type': self.response_type,
            'received_at': self.received_at.isoformat() if self.received_at else None,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None
        }

