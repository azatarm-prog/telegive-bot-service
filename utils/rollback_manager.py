"""
Rollback Management System for Telegive Bot Service
Provides automated rollback capabilities, backup management, and recovery procedures
"""

import os
import json
import shutil
import subprocess
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import logging
from utils.logging_config import get_logger

logger = get_logger(__name__)

@dataclass
class DeploymentSnapshot:
    """Represents a deployment snapshot for rollback"""
    id: str
    timestamp: datetime
    version: str
    environment: str
    database_backup_path: Optional[str] = None
    config_backup_path: Optional[str] = None
    application_backup_path: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: str = "active"  # active, rolled_back, archived

@dataclass
class RollbackPlan:
    """Represents a rollback execution plan"""
    target_snapshot_id: str
    rollback_steps: List[Dict[str, Any]]
    estimated_duration: int  # seconds
    risk_level: str  # low, medium, high
    requires_downtime: bool
    validation_steps: List[str]

class BackupManager:
    """Manages backups for rollback purposes"""
    
    def __init__(self, backup_base_path: str = None):
        if backup_base_path is None:
            # Use /tmp for Railway deployment, /var/backups for local
            backup_base_path = os.getenv('BACKUP_BASE_PATH', '/tmp/telegive-bot-backups')
        
        self.backup_base_path = Path(backup_base_path)
        
        try:
            self.backup_base_path.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            # Fallback to /tmp if permission denied
            fallback_path = '/tmp/telegive-bot-backups'
            logger.warning(f"Permission denied for {backup_base_path}, using fallback: {fallback_path}")
            self.backup_base_path = Path(fallback_path)
            self.backup_base_path.mkdir(parents=True, exist_ok=True)
        
    def create_database_backup(self, snapshot_id: str) -> Optional[str]:
        """Create a database backup"""
        try:
            backup_dir = self.backup_base_path / snapshot_id
            backup_dir.mkdir(exist_ok=True)
            
            backup_file = backup_dir / f"database_{snapshot_id}.sql"
            
            # Get database URL from environment
            database_url = os.getenv('DATABASE_URL')
            if not database_url:
                logger.warning("No DATABASE_URL found, skipping database backup")
                return None
            
            # Extract connection details
            if database_url.startswith('postgresql://'):
                # PostgreSQL backup
                cmd = [
                    'pg_dump',
                    database_url,
                    '--no-password',
                    '--verbose',
                    '--clean',
                    '--no-acl',
                    '--no-owner',
                    '-f', str(backup_file)
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    logger.info(f"Database backup created: {backup_file}")
                    return str(backup_file)
                else:
                    logger.error(f"Database backup failed: {result.stderr}")
                    return None
                    
            elif database_url.startswith('sqlite://'):
                # SQLite backup
                sqlite_path = database_url.replace('sqlite:///', '')
                if os.path.exists(sqlite_path):
                    shutil.copy2(sqlite_path, backup_file.with_suffix('.db'))
                    logger.info(f"SQLite database backup created: {backup_file}")
                    return str(backup_file.with_suffix('.db'))
                else:
                    logger.warning(f"SQLite database not found: {sqlite_path}")
                    return None
            else:
                logger.warning(f"Unsupported database type: {database_url}")
                return None
                
        except Exception as e:
            logger.error(f"Database backup failed: {e}")
            return None
    
    def create_config_backup(self, snapshot_id: str) -> Optional[str]:
        """Create a configuration backup"""
        try:
            backup_dir = self.backup_base_path / snapshot_id
            backup_dir.mkdir(exist_ok=True)
            
            config_backup = backup_dir / f"config_{snapshot_id}.json"
            
            # Collect configuration
            config_data = {
                'environment_variables': {
                    key: value for key, value in os.environ.items()
                    if key.startswith(('TELEGIVE_', 'SERVICE_', 'DATABASE_', 'REDIS_'))
                    and 'SECRET' not in key and 'PASSWORD' not in key and 'TOKEN' not in key
                },
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'snapshot_id': snapshot_id
            }
            
            # Save configuration
            with open(config_backup, 'w') as f:
                json.dump(config_data, f, indent=2)
            
            logger.info(f"Configuration backup created: {config_backup}")
            return str(config_backup)
            
        except Exception as e:
            logger.error(f"Configuration backup failed: {e}")
            return None
    
    def create_application_backup(self, snapshot_id: str) -> Optional[str]:
        """Create an application code backup"""
        try:
            backup_dir = self.backup_base_path / snapshot_id
            backup_dir.mkdir(exist_ok=True)
            
            app_backup = backup_dir / f"application_{snapshot_id}.tar.gz"
            
            # Create tar archive of current application
            current_dir = os.getcwd()
            
            cmd = [
                'tar', '-czf', str(app_backup),
                '--exclude=__pycache__',
                '--exclude=*.pyc',
                '--exclude=.git',
                '--exclude=venv',
                '--exclude=.env',
                '--exclude=logs',
                '--exclude=backups',
                '-C', current_dir,
                '.'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info(f"Application backup created: {app_backup}")
                return str(app_backup)
            else:
                logger.error(f"Application backup failed: {result.stderr}")
                return None
                
        except Exception as e:
            logger.error(f"Application backup failed: {e}")
            return None
    
    def restore_database_backup(self, backup_path: str) -> bool:
        """Restore database from backup"""
        try:
            database_url = os.getenv('DATABASE_URL')
            if not database_url:
                logger.error("No DATABASE_URL found for restore")
                return False
            
            if database_url.startswith('postgresql://'):
                # PostgreSQL restore
                cmd = [
                    'psql',
                    database_url,
                    '-f', backup_path
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    logger.info(f"Database restored from: {backup_path}")
                    return True
                else:
                    logger.error(f"Database restore failed: {result.stderr}")
                    return False
                    
            elif database_url.startswith('sqlite://'):
                # SQLite restore
                sqlite_path = database_url.replace('sqlite:///', '')
                shutil.copy2(backup_path, sqlite_path)
                logger.info(f"SQLite database restored from: {backup_path}")
                return True
                
            else:
                logger.error(f"Unsupported database type for restore: {database_url}")
                return False
                
        except Exception as e:
            logger.error(f"Database restore failed: {e}")
            return False
    
    def cleanup_old_backups(self, retention_days: int = 30):
        """Clean up old backups"""
        try:
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            
            for backup_dir in self.backup_base_path.iterdir():
                if backup_dir.is_dir():
                    # Check if directory is older than retention period
                    dir_time = datetime.fromtimestamp(backup_dir.stat().st_mtime)
                    
                    if dir_time < cutoff_date:
                        shutil.rmtree(backup_dir)
                        logger.info(f"Cleaned up old backup: {backup_dir}")
                        
        except Exception as e:
            logger.error(f"Backup cleanup failed: {e}")

class RollbackManager:
    """Manages deployment rollbacks"""
    
    def __init__(self):
        self.backup_manager = BackupManager()
        self.snapshots_file = Path("/var/lib/telegive-bot/deployment_snapshots.json")
        self.snapshots_file.parent.mkdir(parents=True, exist_ok=True)
        self.snapshots: Dict[str, DeploymentSnapshot] = self._load_snapshots()
    
    def _load_snapshots(self) -> Dict[str, DeploymentSnapshot]:
        """Load deployment snapshots from storage"""
        try:
            if self.snapshots_file.exists():
                with open(self.snapshots_file, 'r') as f:
                    data = json.load(f)
                    
                snapshots = {}
                for snapshot_id, snapshot_data in data.items():
                    snapshot_data['timestamp'] = datetime.fromisoformat(snapshot_data['timestamp'])
                    snapshots[snapshot_id] = DeploymentSnapshot(**snapshot_data)
                
                return snapshots
            else:
                return {}
                
        except Exception as e:
            logger.error(f"Failed to load snapshots: {e}")
            return {}
    
    def _save_snapshots(self):
        """Save deployment snapshots to storage"""
        try:
            data = {}
            for snapshot_id, snapshot in self.snapshots.items():
                snapshot_data = {
                    'id': snapshot.id,
                    'timestamp': snapshot.timestamp.isoformat(),
                    'version': snapshot.version,
                    'environment': snapshot.environment,
                    'database_backup_path': snapshot.database_backup_path,
                    'config_backup_path': snapshot.config_backup_path,
                    'application_backup_path': snapshot.application_backup_path,
                    'metadata': snapshot.metadata,
                    'status': snapshot.status
                }
                data[snapshot_id] = snapshot_data
            
            with open(self.snapshots_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save snapshots: {e}")
    
    def create_deployment_snapshot(self, version: str, environment: str, 
                                 metadata: Dict[str, Any] = None) -> str:
        """Create a deployment snapshot"""
        snapshot_id = f"{environment}_{version}_{int(time.time())}"
        
        logger.info(f"Creating deployment snapshot: {snapshot_id}")
        
        # Create backups
        database_backup = self.backup_manager.create_database_backup(snapshot_id)
        config_backup = self.backup_manager.create_config_backup(snapshot_id)
        application_backup = self.backup_manager.create_application_backup(snapshot_id)
        
        # Create snapshot
        snapshot = DeploymentSnapshot(
            id=snapshot_id,
            timestamp=datetime.now(timezone.utc),
            version=version,
            environment=environment,
            database_backup_path=database_backup,
            config_backup_path=config_backup,
            application_backup_path=application_backup,
            metadata=metadata or {},
            status="active"
        )
        
        self.snapshots[snapshot_id] = snapshot
        self._save_snapshots()
        
        logger.info(f"Deployment snapshot created successfully: {snapshot_id}")
        return snapshot_id
    
    def get_rollback_candidates(self, environment: str) -> List[DeploymentSnapshot]:
        """Get available rollback candidates for an environment"""
        candidates = []
        
        for snapshot in self.snapshots.values():
            if (snapshot.environment == environment and 
                snapshot.status == "active" and
                snapshot.database_backup_path):  # Must have database backup
                candidates.append(snapshot)
        
        # Sort by timestamp (newest first)
        candidates.sort(key=lambda x: x.timestamp, reverse=True)
        
        return candidates
    
    def create_rollback_plan(self, target_snapshot_id: str) -> Optional[RollbackPlan]:
        """Create a rollback execution plan"""
        if target_snapshot_id not in self.snapshots:
            logger.error(f"Snapshot not found: {target_snapshot_id}")
            return None
        
        target_snapshot = self.snapshots[target_snapshot_id]
        
        # Define rollback steps
        rollback_steps = []
        
        # Step 1: Pre-rollback validation
        rollback_steps.append({
            'step': 'pre_validation',
            'description': 'Validate target snapshot and current state',
            'estimated_duration': 30,
            'critical': True
        })
        
        # Step 2: Create current state backup
        rollback_steps.append({
            'step': 'create_backup',
            'description': 'Create backup of current state',
            'estimated_duration': 120,
            'critical': True
        })
        
        # Step 3: Stop application (if required)
        rollback_steps.append({
            'step': 'stop_application',
            'description': 'Stop application services',
            'estimated_duration': 30,
            'critical': False
        })
        
        # Step 4: Restore database
        if target_snapshot.database_backup_path:
            rollback_steps.append({
                'step': 'restore_database',
                'description': 'Restore database from backup',
                'estimated_duration': 180,
                'critical': True
            })
        
        # Step 5: Restore application
        if target_snapshot.application_backup_path:
            rollback_steps.append({
                'step': 'restore_application',
                'description': 'Restore application code',
                'estimated_duration': 60,
                'critical': True
            })
        
        # Step 6: Start application
        rollback_steps.append({
            'step': 'start_application',
            'description': 'Start application services',
            'estimated_duration': 60,
            'critical': True
        })
        
        # Step 7: Post-rollback validation
        rollback_steps.append({
            'step': 'post_validation',
            'description': 'Validate rollback success',
            'estimated_duration': 120,
            'critical': True
        })
        
        # Calculate total duration
        total_duration = sum(step['estimated_duration'] for step in rollback_steps)
        
        # Determine risk level
        age_days = (datetime.now(timezone.utc) - target_snapshot.timestamp).days
        if age_days <= 1:
            risk_level = "low"
        elif age_days <= 7:
            risk_level = "medium"
        else:
            risk_level = "high"
        
        # Validation steps
        validation_steps = [
            "Check application health endpoints",
            "Verify database connectivity",
            "Test critical API endpoints",
            "Validate external service connections",
            "Check monitoring and logging"
        ]
        
        return RollbackPlan(
            target_snapshot_id=target_snapshot_id,
            rollback_steps=rollback_steps,
            estimated_duration=total_duration,
            risk_level=risk_level,
            requires_downtime=True,
            validation_steps=validation_steps
        )
    
    def execute_rollback(self, rollback_plan: RollbackPlan, 
                        dry_run: bool = False) -> Tuple[bool, List[str]]:
        """Execute a rollback plan"""
        if dry_run:
            logger.info(f"DRY RUN: Executing rollback to {rollback_plan.target_snapshot_id}")
        else:
            logger.info(f"Executing rollback to {rollback_plan.target_snapshot_id}")
        
        target_snapshot = self.snapshots[rollback_plan.target_snapshot_id]
        execution_log = []
        
        try:
            for step in rollback_plan.rollback_steps:
                step_name = step['step']
                step_desc = step['description']
                
                execution_log.append(f"Starting step: {step_name} - {step_desc}")
                logger.info(f"Rollback step: {step_name}")
                
                if dry_run:
                    execution_log.append(f"DRY RUN: Would execute {step_name}")
                    continue
                
                success = self._execute_rollback_step(step_name, target_snapshot)
                
                if success:
                    execution_log.append(f"✅ Step completed: {step_name}")
                else:
                    execution_log.append(f"❌ Step failed: {step_name}")
                    if step.get('critical', False):
                        execution_log.append("❌ Critical step failed, aborting rollback")
                        return False, execution_log
            
            if not dry_run:
                # Mark target snapshot as active
                target_snapshot.status = "active"
                self._save_snapshots()
            
            execution_log.append("✅ Rollback completed successfully")
            return True, execution_log
            
        except Exception as e:
            execution_log.append(f"❌ Rollback failed with exception: {e}")
            logger.error(f"Rollback execution failed: {e}")
            return False, execution_log
    
    def _execute_rollback_step(self, step_name: str, target_snapshot: DeploymentSnapshot) -> bool:
        """Execute a specific rollback step"""
        try:
            if step_name == 'pre_validation':
                return self._validate_rollback_preconditions(target_snapshot)
            
            elif step_name == 'create_backup':
                backup_id = self.create_deployment_snapshot(
                    version="pre_rollback_backup",
                    environment=target_snapshot.environment,
                    metadata={'rollback_target': target_snapshot.id}
                )
                return backup_id is not None
            
            elif step_name == 'stop_application':
                return self._stop_application()
            
            elif step_name == 'restore_database':
                if target_snapshot.database_backup_path:
                    return self.backup_manager.restore_database_backup(
                        target_snapshot.database_backup_path
                    )
                return True
            
            elif step_name == 'restore_application':
                return self._restore_application(target_snapshot)
            
            elif step_name == 'start_application':
                return self._start_application()
            
            elif step_name == 'post_validation':
                return self._validate_rollback_success()
            
            else:
                logger.warning(f"Unknown rollback step: {step_name}")
                return False
                
        except Exception as e:
            logger.error(f"Rollback step {step_name} failed: {e}")
            return False
    
    def _validate_rollback_preconditions(self, target_snapshot: DeploymentSnapshot) -> bool:
        """Validate preconditions for rollback"""
        # Check if backup files exist
        if target_snapshot.database_backup_path:
            if not os.path.exists(target_snapshot.database_backup_path):
                logger.error(f"Database backup not found: {target_snapshot.database_backup_path}")
                return False
        
        if target_snapshot.application_backup_path:
            if not os.path.exists(target_snapshot.application_backup_path):
                logger.error(f"Application backup not found: {target_snapshot.application_backup_path}")
                return False
        
        return True
    
    def _stop_application(self) -> bool:
        """Stop application services"""
        # This would typically stop the application server
        # For now, we'll just log the action
        logger.info("Application stop requested (implementation depends on deployment method)")
        return True
    
    def _start_application(self) -> bool:
        """Start application services"""
        # This would typically start the application server
        # For now, we'll just log the action
        logger.info("Application start requested (implementation depends on deployment method)")
        return True
    
    def _restore_application(self, target_snapshot: DeploymentSnapshot) -> bool:
        """Restore application from backup"""
        if not target_snapshot.application_backup_path:
            return True
        
        try:
            # Extract application backup
            cmd = [
                'tar', '-xzf', target_snapshot.application_backup_path,
                '-C', os.getcwd()
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("Application restored from backup")
                return True
            else:
                logger.error(f"Application restore failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Application restore failed: {e}")
            return False
    
    def _validate_rollback_success(self) -> bool:
        """Validate that rollback was successful"""
        # This would typically check:
        # - Application health endpoints
        # - Database connectivity
        # - Critical functionality
        
        logger.info("Rollback validation requested (implement specific checks)")
        return True
    
    def get_rollback_history(self, environment: str = None) -> List[Dict[str, Any]]:
        """Get rollback history"""
        history = []
        
        for snapshot in self.snapshots.values():
            if environment and snapshot.environment != environment:
                continue
            
            history.append({
                'snapshot_id': snapshot.id,
                'timestamp': snapshot.timestamp.isoformat(),
                'version': snapshot.version,
                'environment': snapshot.environment,
                'status': snapshot.status,
                'has_database_backup': snapshot.database_backup_path is not None,
                'has_application_backup': snapshot.application_backup_path is not None,
                'metadata': snapshot.metadata
            })
        
        # Sort by timestamp (newest first)
        history.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return history
    
    def cleanup_old_snapshots(self, retention_days: int = 30):
        """Clean up old snapshots"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
        
        snapshots_to_remove = []
        
        for snapshot_id, snapshot in self.snapshots.items():
            if snapshot.timestamp < cutoff_date and snapshot.status != "active":
                snapshots_to_remove.append(snapshot_id)
        
        for snapshot_id in snapshots_to_remove:
            snapshot = self.snapshots[snapshot_id]
            
            # Remove backup files
            if snapshot.database_backup_path and os.path.exists(snapshot.database_backup_path):
                os.remove(snapshot.database_backup_path)
            
            if snapshot.application_backup_path and os.path.exists(snapshot.application_backup_path):
                os.remove(snapshot.application_backup_path)
            
            if snapshot.config_backup_path and os.path.exists(snapshot.config_backup_path):
                os.remove(snapshot.config_backup_path)
            
            # Remove snapshot record
            del self.snapshots[snapshot_id]
            logger.info(f"Cleaned up old snapshot: {snapshot_id}")
        
        self._save_snapshots()
        
        # Clean up old backup directories
        self.backup_manager.cleanup_old_backups(retention_days)

# Global rollback manager instance
rollback_manager = RollbackManager()

# Convenience functions
def create_deployment_snapshot(version: str, environment: str, metadata: Dict[str, Any] = None) -> str:
    """Create a deployment snapshot"""
    return rollback_manager.create_deployment_snapshot(version, environment, metadata)

def get_rollback_candidates(environment: str) -> List[DeploymentSnapshot]:
    """Get rollback candidates"""
    return rollback_manager.get_rollback_candidates(environment)

def create_rollback_plan(target_snapshot_id: str) -> Optional[RollbackPlan]:
    """Create rollback plan"""
    return rollback_manager.create_rollback_plan(target_snapshot_id)

def execute_rollback(rollback_plan: RollbackPlan, dry_run: bool = False) -> Tuple[bool, List[str]]:
    """Execute rollback"""
    return rollback_manager.execute_rollback(rollback_plan, dry_run)

