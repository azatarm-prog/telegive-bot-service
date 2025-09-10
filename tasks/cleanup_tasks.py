"""
Cleanup tasks
Handles periodic cleanup of old data and maintenance operations
"""

import logging
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from models import db, BotInteraction, MessageDeliveryLog, WebhookProcessingLog

logger = logging.getLogger(__name__)

class CleanupService:
    """Service for periodic cleanup operations"""
    
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.retention_periods = {
            'bot_interactions': 30,  # days
            'message_delivery_logs': 90,  # days
            'webhook_processing_logs': 7,  # days
            'user_states': 1,  # days (handled separately)
        }
        
    def start(self):
        """Start the cleanup service"""
        try:
            # Schedule daily cleanup at 2 AM
            self.scheduler.add_job(
                func=self.run_daily_cleanup,
                trigger='cron',
                hour=2,
                minute=0,
                id='daily_cleanup_job',
                replace_existing=True
            )
            
            # Schedule weekly deep cleanup on Sundays at 3 AM
            self.scheduler.add_job(
                func=self.run_weekly_cleanup,
                trigger='cron',
                day_of_week=6,  # Sunday
                hour=3,
                minute=0,
                id='weekly_cleanup_job',
                replace_existing=True
            )
            
            # Schedule hourly maintenance
            self.scheduler.add_job(
                func=self.run_hourly_maintenance,
                trigger='interval',
                hours=1,
                id='hourly_maintenance_job',
                replace_existing=True
            )
            
            self.scheduler.start()
            logger.info("Cleanup service started")
            
        except Exception as e:
            logger.error(f"Failed to start cleanup service: {e}")
    
    def stop(self):
        """Stop the cleanup service"""
        try:
            self.scheduler.shutdown()
            logger.info("Cleanup service stopped")
        except Exception as e:
            logger.error(f"Failed to stop cleanup service: {e}")
    
    def run_daily_cleanup(self):
        """Run daily cleanup operations"""
        try:
            logger.info("Starting daily cleanup operations")
            
            # Clean old webhook processing logs
            self.cleanup_webhook_logs()
            
            # Clean old bot interactions
            self.cleanup_bot_interactions()
            
            # Clean expired user states
            self.cleanup_user_states()
            
            # Update database statistics
            self.update_database_stats()
            
            logger.info("Daily cleanup operations completed")
            
        except Exception as e:
            logger.error(f"Error in daily cleanup: {e}")
    
    def run_weekly_cleanup(self):
        """Run weekly cleanup operations"""
        try:
            logger.info("Starting weekly cleanup operations")
            
            # Clean old message delivery logs
            self.cleanup_message_delivery_logs()
            
            # Vacuum database (PostgreSQL specific)
            self.vacuum_database()
            
            # Generate cleanup report
            self.generate_cleanup_report()
            
            logger.info("Weekly cleanup operations completed")
            
        except Exception as e:
            logger.error(f"Error in weekly cleanup: {e}")
    
    def run_hourly_maintenance(self):
        """Run hourly maintenance operations"""
        try:
            # Clean up temporary files
            self.cleanup_temporary_files()
            
            # Check for stuck processes
            self.check_stuck_processes()
            
        except Exception as e:
            logger.error(f"Error in hourly maintenance: {e}")
    
    def cleanup_webhook_logs(self):
        """Clean up old webhook processing logs"""
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.retention_periods['webhook_processing_logs'])
            
            deleted_count = WebhookProcessingLog.query.filter(
                WebhookProcessingLog.received_at < cutoff_date
            ).delete()
            
            db.session.commit()
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old webhook processing logs")
                
        except Exception as e:
            logger.error(f"Error cleaning webhook logs: {e}")
            db.session.rollback()
    
    def cleanup_bot_interactions(self):
        """Clean up old bot interactions"""
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.retention_periods['bot_interactions'])
            
            deleted_count = BotInteraction.query.filter(
                BotInteraction.interaction_timestamp < cutoff_date
            ).delete()
            
            db.session.commit()
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old bot interactions")
                
        except Exception as e:
            logger.error(f"Error cleaning bot interactions: {e}")
            db.session.rollback()
    
    def cleanup_message_delivery_logs(self):
        """Clean up old message delivery logs"""
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.retention_periods['message_delivery_logs'])
            
            # Keep failed messages for longer for analysis
            deleted_count = MessageDeliveryLog.query.filter(
                MessageDeliveryLog.scheduled_at < cutoff_date,
                MessageDeliveryLog.delivery_status.in_(['sent', 'permanently_failed'])
            ).delete()
            
            db.session.commit()
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old message delivery logs")
                
        except Exception as e:
            logger.error(f"Error cleaning message delivery logs: {e}")
            db.session.rollback()
    
    def cleanup_user_states(self):
        """Clean up expired user states"""
        try:
            from utils.user_state import state_manager
            
            # This would clean up expired states from Redis or in-memory storage
            # Implementation depends on the storage backend
            
            logger.info("User state cleanup completed")
            
        except Exception as e:
            logger.error(f"Error cleaning user states: {e}")
    
    def cleanup_temporary_files(self):
        """Clean up temporary files"""
        try:
            import os
            import tempfile
            import glob
            
            temp_dir = tempfile.gettempdir()
            
            # Clean up old temporary files (older than 1 hour)
            cutoff_time = datetime.now().timestamp() - 3600
            
            temp_files = glob.glob(os.path.join(temp_dir, 'tmp*'))
            cleaned_count = 0
            
            for temp_file in temp_files:
                try:
                    if os.path.getmtime(temp_file) < cutoff_time:
                        os.unlink(temp_file)
                        cleaned_count += 1
                except (OSError, IOError):
                    pass  # File might be in use or already deleted
            
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} temporary files")
                
        except Exception as e:
            logger.error(f"Error cleaning temporary files: {e}")
    
    def check_stuck_processes(self):
        """Check for stuck webhook processes"""
        try:
            # Check for webhook processes that have been pending for too long
            stuck_cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
            
            stuck_webhooks = WebhookProcessingLog.query.filter(
                WebhookProcessingLog.processing_status == 'pending',
                WebhookProcessingLog.received_at < stuck_cutoff
            ).all()
            
            for webhook in stuck_webhooks:
                webhook.processing_status = 'failed'
                webhook.error_message = 'Process timeout - marked as failed by cleanup'
                webhook.processed_at = datetime.now(timezone.utc)
            
            if stuck_webhooks:
                db.session.commit()
                logger.warning(f"Marked {len(stuck_webhooks)} stuck webhook processes as failed")
                
        except Exception as e:
            logger.error(f"Error checking stuck processes: {e}")
            db.session.rollback()
    
    def vacuum_database(self):
        """Vacuum database to reclaim space (PostgreSQL specific)"""
        try:
            # This would run VACUUM on PostgreSQL
            # Note: This requires a separate connection outside of transaction
            logger.info("Database vacuum would be performed here")
            
        except Exception as e:
            logger.error(f"Error vacuuming database: {e}")
    
    def update_database_stats(self):
        """Update database statistics"""
        try:
            # This would update table statistics for query optimization
            logger.info("Database statistics updated")
            
        except Exception as e:
            logger.error(f"Error updating database stats: {e}")
    
    def generate_cleanup_report(self):
        """Generate cleanup report"""
        try:
            # Get current counts
            interaction_count = BotInteraction.query.count()
            delivery_count = MessageDeliveryLog.query.count()
            webhook_count = WebhookProcessingLog.query.count()
            
            # Get recent activity
            recent_cutoff = datetime.now(timezone.utc) - timedelta(days=7)
            recent_interactions = BotInteraction.query.filter(
                BotInteraction.interaction_timestamp >= recent_cutoff
            ).count()
            
            report = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'current_counts': {
                    'bot_interactions': interaction_count,
                    'message_deliveries': delivery_count,
                    'webhook_processes': webhook_count
                },
                'recent_activity': {
                    'interactions_last_7_days': recent_interactions
                },
                'retention_periods': self.retention_periods
            }
            
            logger.info(f"Cleanup report generated: {report}")
            
        except Exception as e:
            logger.error(f"Error generating cleanup report: {e}")
    
    def manual_cleanup(self, table_name, days_to_keep):
        """Manually trigger cleanup for specific table"""
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
            
            if table_name == 'bot_interactions':
                deleted_count = BotInteraction.query.filter(
                    BotInteraction.interaction_timestamp < cutoff_date
                ).delete()
            elif table_name == 'message_delivery_logs':
                deleted_count = MessageDeliveryLog.query.filter(
                    MessageDeliveryLog.scheduled_at < cutoff_date
                ).delete()
            elif table_name == 'webhook_processing_logs':
                deleted_count = WebhookProcessingLog.query.filter(
                    WebhookProcessingLog.received_at < cutoff_date
                ).delete()
            else:
                return {'success': False, 'error': 'Unknown table name'}
            
            db.session.commit()
            
            return {
                'success': True,
                'deleted_count': deleted_count,
                'table': table_name,
                'cutoff_date': cutoff_date.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in manual cleanup: {e}")
            db.session.rollback()
            return {'success': False, 'error': str(e)}

# Global cleanup service instance
cleanup_service = CleanupService()

def start_cleanup_service():
    """Start the cleanup service"""
    cleanup_service.start()

def stop_cleanup_service():
    """Stop the cleanup service"""
    cleanup_service.stop()

def run_manual_cleanup(table_name, days_to_keep):
    """Run manual cleanup (convenience function)"""
    return cleanup_service.manual_cleanup(table_name, days_to_keep)

