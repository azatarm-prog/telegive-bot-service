"""
Admin routes for Telegive Bot Service
Provides administrative endpoints for database management, monitoring, and rollback operations
"""

from flask import Blueprint, request, jsonify
from datetime import datetime, timezone
import logging
import os
from functools import wraps

from utils.database_manager import db_manager as database_manager
from utils.rollback_manager import rollback_manager
from utils.monitoring import monitoring_manager
from config.environment import env_manager

admin_bp = Blueprint('admin', __name__)
logger = logging.getLogger(__name__)

def require_admin_token(f):
    """Decorator to require admin authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            return jsonify({'error': 'Authorization header required'}), 401
        
        try:
            token_type, token = auth_header.split(' ', 1)
            if token_type.lower() != 'bearer':
                return jsonify({'error': 'Bearer token required'}), 401
        except ValueError:
            return jsonify({'error': 'Invalid authorization header format'}), 401
        
        # Check against admin token
        admin_token = env_manager.get('ADMIN_TOKEN')
        if not admin_token or token != admin_token:
            return jsonify({'error': 'Invalid admin token'}), 403
        
        return f(*args, **kwargs)
    
    return decorated_function

# Database Management Endpoints

@admin_bp.route('/db-status', methods=['GET'])
@require_admin_token
def get_database_status():
    """Get database status and statistics"""
    try:
        status = database_manager.get_database_status()
        return jsonify({
            'success': True,
            'data': status,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
    except Exception as e:
        logger.error(f"Failed to get database status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin_bp.route('/db-backup', methods=['POST'])
@require_admin_token
def create_database_backup():
    """Create a database backup"""
    try:
        data = request.get_json() or {}
        backup_name = data.get('backup_name')
        
        backup_path = database_manager.create_backup(backup_name)
        
        if backup_path:
            return jsonify({
                'success': True,
                'backup_path': backup_path,
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to create backup'
            }), 500
            
    except Exception as e:
        logger.error(f"Failed to create database backup: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin_bp.route('/db-restore', methods=['POST'])
@require_admin_token
def restore_database():
    """Restore database from backup"""
    try:
        data = request.get_json()
        if not data or 'backup_path' not in data:
            return jsonify({
                'success': False,
                'error': 'backup_path is required'
            }), 400
        
        backup_path = data['backup_path']
        success = database_manager.restore_backup(backup_path)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Database restored successfully',
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to restore database'
            }), 500
            
    except Exception as e:
        logger.error(f"Failed to restore database: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin_bp.route('/db-cleanup', methods=['POST'])
@require_admin_token
def cleanup_database():
    """Clean up old database records"""
    try:
        data = request.get_json() or {}
        retention_days = data.get('retention_days', 30)
        
        cleanup_results = database_manager.cleanup_old_records(retention_days)
        
        return jsonify({
            'success': True,
            'cleanup_results': cleanup_results,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to cleanup database: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Rollback Management Endpoints

@admin_bp.route('/snapshots', methods=['GET'])
@require_admin_token
def list_deployment_snapshots():
    """List deployment snapshots"""
    try:
        environment = request.args.get('environment')
        snapshots = rollback_manager.get_rollback_history(environment)
        
        return jsonify({
            'success': True,
            'snapshots': snapshots,
            'count': len(snapshots),
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to list snapshots: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin_bp.route('/snapshots', methods=['POST'])
@require_admin_token
def create_deployment_snapshot():
    """Create a deployment snapshot"""
    try:
        data = request.get_json()
        if not data or 'version' not in data or 'environment' not in data:
            return jsonify({
                'success': False,
                'error': 'version and environment are required'
            }), 400
        
        version = data['version']
        environment = data['environment']
        metadata = data.get('metadata', {})
        
        snapshot_id = rollback_manager.create_deployment_snapshot(version, environment, metadata)
        
        return jsonify({
            'success': True,
            'snapshot_id': snapshot_id,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to create snapshot: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin_bp.route('/rollback-candidates/<environment>', methods=['GET'])
@require_admin_token
def get_rollback_candidates(environment):
    """Get rollback candidates for an environment"""
    try:
        candidates = rollback_manager.get_rollback_candidates(environment)
        
        candidate_data = []
        for candidate in candidates:
            candidate_data.append({
                'snapshot_id': candidate.id,
                'version': candidate.version,
                'timestamp': candidate.timestamp.isoformat(),
                'age_days': (datetime.now(timezone.utc) - candidate.timestamp).days,
                'has_database_backup': candidate.database_backup_path is not None,
                'has_application_backup': candidate.application_backup_path is not None,
                'metadata': candidate.metadata
            })
        
        return jsonify({
            'success': True,
            'environment': environment,
            'candidates': candidate_data,
            'count': len(candidate_data),
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to get rollback candidates: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin_bp.route('/rollback-plan/<snapshot_id>', methods=['GET'])
@require_admin_token
def create_rollback_plan(snapshot_id):
    """Create a rollback plan"""
    try:
        plan = rollback_manager.create_rollback_plan(snapshot_id)
        
        if not plan:
            return jsonify({
                'success': False,
                'error': f'Cannot create rollback plan for snapshot: {snapshot_id}'
            }), 404
        
        return jsonify({
            'success': True,
            'plan': {
                'target_snapshot_id': plan.target_snapshot_id,
                'estimated_duration': plan.estimated_duration,
                'risk_level': plan.risk_level,
                'requires_downtime': plan.requires_downtime,
                'rollback_steps': plan.rollback_steps,
                'validation_steps': plan.validation_steps
            },
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to create rollback plan: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin_bp.route('/rollback/<snapshot_id>', methods=['POST'])
@require_admin_token
def execute_rollback(snapshot_id):
    """Execute a rollback"""
    try:
        data = request.get_json() or {}
        dry_run = data.get('dry_run', False)
        
        # Create rollback plan
        plan = rollback_manager.create_rollback_plan(snapshot_id)
        if not plan:
            return jsonify({
                'success': False,
                'error': f'Cannot create rollback plan for snapshot: {snapshot_id}'
            }), 404
        
        # Execute rollback
        success, execution_log = rollback_manager.execute_rollback(plan, dry_run)
        
        return jsonify({
            'success': success,
            'dry_run': dry_run,
            'snapshot_id': snapshot_id,
            'execution_log': execution_log,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to execute rollback: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin_bp.route('/snapshots/cleanup', methods=['POST'])
@require_admin_token
def cleanup_old_snapshots():
    """Clean up old snapshots"""
    try:
        data = request.get_json() or {}
        retention_days = data.get('retention_days', 30)
        
        rollback_manager.cleanup_old_snapshots(retention_days)
        
        return jsonify({
            'success': True,
            'message': f'Cleaned up snapshots older than {retention_days} days',
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to cleanup snapshots: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Monitoring and Metrics Endpoints

@admin_bp.route('/metrics-summary', methods=['GET'])
@require_admin_token
def get_metrics_summary():
    """Get metrics summary"""
    try:
        summary = monitoring_manager.get_metrics_summary()
        
        return jsonify({
            'success': True,
            'metrics': summary,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to get metrics summary: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin_bp.route('/system-info', methods=['GET'])
@require_admin_token
def get_system_info():
    """Get system information"""
    try:
        import psutil
        import platform
        
        system_info = {
            'platform': {
                'system': platform.system(),
                'release': platform.release(),
                'version': platform.version(),
                'machine': platform.machine(),
                'processor': platform.processor()
            },
            'cpu': {
                'count': psutil.cpu_count(),
                'usage_percent': psutil.cpu_percent(interval=1)
            },
            'memory': {
                'total': psutil.virtual_memory().total,
                'available': psutil.virtual_memory().available,
                'used': psutil.virtual_memory().used,
                'percent': psutil.virtual_memory().percent
            },
            'disk': {
                'total': psutil.disk_usage('/').total,
                'free': psutil.disk_usage('/').free,
                'used': psutil.disk_usage('/').used,
                'percent': (psutil.disk_usage('/').used / psutil.disk_usage('/').total) * 100
            },
            'network': psutil.net_io_counters()._asdict(),
            'boot_time': datetime.fromtimestamp(psutil.boot_time()).isoformat()
        }
        
        return jsonify({
            'success': True,
            'system_info': system_info,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to get system info: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Configuration Management

@admin_bp.route('/config', methods=['GET'])
@require_admin_token
def get_configuration():
    """Get current configuration"""
    try:
        config = {
            'environment': env_manager.env.value,
            'service_name': env_manager.get('SERVICE_NAME'),
            'service_port': env_manager.get('SERVICE_PORT'),
            'external_services': {
                'configured': list(env_manager.get_all_service_urls().keys()),
                'required': env_manager.get_required_services(),
                'optional': env_manager.get_optional_services()
            },
            'features': {
                'monitoring_enabled': True,
                'logging_enabled': True,
                'rollback_enabled': True,
                'backup_enabled': True
            }
        }
        
        return jsonify({
            'success': True,
            'configuration': config,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to get configuration: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin_bp.route('/config/validate', methods=['POST'])
@require_admin_token
def validate_configuration():
    """Validate current configuration"""
    try:
        issues = env_manager.validate_runtime_config()
        
        return jsonify({
            'success': True,
            'valid': len(issues) == 0,
            'issues': issues,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to validate configuration: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Emergency Operations

@admin_bp.route('/emergency/stop', methods=['POST'])
@require_admin_token
def emergency_stop():
    """Emergency stop of non-critical services"""
    try:
        # Stop monitoring
        monitoring_manager.stop_monitoring()
        
        # Log emergency stop
        logger.critical("Emergency stop initiated via admin API")
        
        return jsonify({
            'success': True,
            'message': 'Emergency stop completed',
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Emergency stop failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin_bp.route('/emergency/restart', methods=['POST'])
@require_admin_token
def emergency_restart():
    """Emergency restart of services"""
    try:
        # Restart monitoring
        monitoring_manager.stop_monitoring()
        monitoring_manager.start_monitoring()
        
        # Log emergency restart
        logger.warning("Emergency restart initiated via admin API")
        
        return jsonify({
            'success': True,
            'message': 'Emergency restart completed',
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Emergency restart failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Logs Management

@admin_bp.route('/logs', methods=['GET'])
@require_admin_token
def get_logs():
    """Get recent application logs"""
    try:
        lines = request.args.get('lines', 100, type=int)
        level = request.args.get('level', 'INFO').upper()
        
        # Limit lines to prevent memory issues
        lines = min(lines, 1000)
        
        log_entries = []
        
        # Try to read from log file if it exists
        log_file = '/var/log/telegive-bot.log'
        if not os.path.exists(log_file):
            log_file = '/tmp/telegive-bot.log'
        
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                all_lines = f.readlines()
                recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
                
                for line in recent_lines:
                    if level in line or level == 'ALL':
                        log_entries.append(line.strip())
        else:
            log_entries = [f"Log file not found at {log_file}"]
        
        return jsonify({
            'success': True,
            'logs': log_entries,
            'count': len(log_entries),
            'level_filter': level,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting logs: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

