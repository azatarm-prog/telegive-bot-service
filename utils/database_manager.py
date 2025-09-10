"""
Database management automation for Telegive Bot Service
Provides automated database operations, migrations, backups, and health monitoring
"""

import os
import logging
import json
import subprocess
import shutil
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy import text, inspect, MetaData, Table
from sqlalchemy.exc import SQLAlchemyError
from flask import current_app
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Comprehensive database management utilities"""
    
    def __init__(self, db):
        self.db = db
        self.backup_dir = os.getenv('DB_BACKUP_DIR', '/tmp/db_backups')
        self.max_backup_age_days = int(os.getenv('DB_BACKUP_RETENTION_DAYS', 7))
        
        # Ensure backup directory exists
        os.makedirs(self.backup_dir, exist_ok=True)
    
    def check_database_health(self) -> Dict[str, Any]:
        """Comprehensive database health check"""
        health_info = {
            'status': 'unknown',
            'connection': False,
            'tables': {},
            'statistics': {},
            'performance': {},
            'issues': []
        }
        
        try:
            # Test basic connectivity
            start_time = datetime.now()
            self.db.session.execute(text('SELECT 1'))
            connection_time = (datetime.now() - start_time).total_seconds()
            
            health_info['connection'] = True
            health_info['performance']['connection_time_ms'] = round(connection_time * 1000, 2)
            
            # Check table existence and row counts
            inspector = inspect(self.db.engine)
            table_names = inspector.get_table_names()
            
            for table_name in table_names:
                try:
                    result = self.db.session.execute(text(f'SELECT COUNT(*) FROM {table_name}'))
                    count = result.scalar()
                    health_info['tables'][table_name] = {
                        'exists': True,
                        'row_count': count
                    }
                except Exception as e:
                    health_info['tables'][table_name] = {
                        'exists': True,
                        'row_count': None,
                        'error': str(e)
                    }
                    health_info['issues'].append(f"Cannot count rows in {table_name}: {e}")
            
            # Get database statistics
            try:
                db_stats = self._get_database_statistics()
                health_info['statistics'] = db_stats
            except Exception as e:
                health_info['issues'].append(f"Cannot get database statistics: {e}")
            
            # Check for long-running queries
            try:
                long_queries = self._get_long_running_queries()
                if long_queries:
                    health_info['issues'].extend([
                        f"Long-running query: {query}" for query in long_queries
                    ])
            except Exception as e:
                health_info['issues'].append(f"Cannot check long-running queries: {e}")
            
            # Determine overall status
            if health_info['issues']:
                health_info['status'] = 'degraded'
            else:
                health_info['status'] = 'healthy'
            
            self.db.session.commit()
            
        except Exception as e:
            health_info['status'] = 'unhealthy'
            health_info['connection'] = False
            health_info['issues'].append(f"Database connection failed: {e}")
            logger.error(f"Database health check failed: {e}")
        
        return health_info
    
    def _get_database_statistics(self) -> Dict[str, Any]:
        """Get database performance statistics"""
        stats = {}
        
        try:
            # For PostgreSQL
            if 'postgresql' in str(self.db.engine.url):
                # Database size
                result = self.db.session.execute(text(
                    "SELECT pg_size_pretty(pg_database_size(current_database()))"
                ))
                stats['database_size'] = result.scalar()
                
                # Connection count
                result = self.db.session.execute(text(
                    "SELECT count(*) FROM pg_stat_activity WHERE state = 'active'"
                ))
                stats['active_connections'] = result.scalar()
                
                # Cache hit ratio
                result = self.db.session.execute(text("""
                    SELECT round(
                        100 * sum(blks_hit) / (sum(blks_hit) + sum(blks_read)), 2
                    ) as cache_hit_ratio
                    FROM pg_stat_database
                    WHERE datname = current_database()
                """))
                stats['cache_hit_ratio'] = result.scalar()
                
            # For SQLite
            elif 'sqlite' in str(self.db.engine.url):
                # Database file size
                db_path = str(self.db.engine.url).replace('sqlite:///', '')
                if os.path.exists(db_path):
                    size_bytes = os.path.getsize(db_path)
                    stats['database_size'] = f"{size_bytes / 1024 / 1024:.2f} MB"
                
                # Page count
                result = self.db.session.execute(text("PRAGMA page_count"))
                stats['page_count'] = result.scalar()
                
                # Page size
                result = self.db.session.execute(text("PRAGMA page_size"))
                stats['page_size'] = result.scalar()
        
        except Exception as e:
            logger.warning(f"Could not get database statistics: {e}")
        
        return stats
    
    def _get_long_running_queries(self, threshold_seconds: int = 30) -> List[str]:
        """Get list of long-running queries"""
        long_queries = []
        
        try:
            if 'postgresql' in str(self.db.engine.url):
                result = self.db.session.execute(text(f"""
                    SELECT query, now() - query_start as duration
                    FROM pg_stat_activity
                    WHERE state = 'active'
                    AND now() - query_start > interval '{threshold_seconds} seconds'
                    AND query NOT LIKE '%pg_stat_activity%'
                """))
                
                for row in result:
                    long_queries.append(f"{row.query[:100]}... (duration: {row.duration})")
        
        except Exception as e:
            logger.warning(f"Could not check long-running queries: {e}")
        
        return long_queries
    
    def create_backup(self, backup_name: Optional[str] = None) -> Dict[str, Any]:
        """Create database backup"""
        if not backup_name:
            backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        backup_info = {
            'name': backup_name,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'status': 'unknown',
            'file_path': None,
            'size_bytes': 0,
            'error': None
        }
        
        try:
            db_url = str(self.db.engine.url)
            
            if 'postgresql' in db_url:
                backup_info = self._create_postgresql_backup(backup_name, backup_info)
            elif 'sqlite' in db_url:
                backup_info = self._create_sqlite_backup(backup_name, backup_info)
            else:
                backup_info['status'] = 'unsupported'
                backup_info['error'] = f"Backup not supported for database type: {db_url}"
            
        except Exception as e:
            backup_info['status'] = 'failed'
            backup_info['error'] = str(e)
            logger.error(f"Database backup failed: {e}")
        
        return backup_info
    
    def _create_postgresql_backup(self, backup_name: str, backup_info: Dict) -> Dict[str, Any]:
        """Create PostgreSQL backup using pg_dump"""
        db_url = str(self.db.engine.url)
        backup_file = os.path.join(self.backup_dir, f"{backup_name}.sql")
        
        # Parse database URL
        import urllib.parse
        parsed = urllib.parse.urlparse(db_url)
        
        env = os.environ.copy()
        if parsed.password:
            env['PGPASSWORD'] = parsed.password
        
        cmd = [
            'pg_dump',
            '-h', parsed.hostname or 'localhost',
            '-p', str(parsed.port or 5432),
            '-U', parsed.username or 'postgres',
            '-d', parsed.path.lstrip('/'),
            '-f', backup_file,
            '--verbose'
        ]
        
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        if result.returncode == 0:
            backup_info['status'] = 'success'
            backup_info['file_path'] = backup_file
            backup_info['size_bytes'] = os.path.getsize(backup_file)
            logger.info(f"PostgreSQL backup created: {backup_file}")
        else:
            backup_info['status'] = 'failed'
            backup_info['error'] = result.stderr
            logger.error(f"PostgreSQL backup failed: {result.stderr}")
        
        return backup_info
    
    def _create_sqlite_backup(self, backup_name: str, backup_info: Dict) -> Dict[str, Any]:
        """Create SQLite backup by copying the database file"""
        db_url = str(self.db.engine.url)
        source_path = db_url.replace('sqlite:///', '')
        backup_file = os.path.join(self.backup_dir, f"{backup_name}.db")
        
        if os.path.exists(source_path):
            shutil.copy2(source_path, backup_file)
            backup_info['status'] = 'success'
            backup_info['file_path'] = backup_file
            backup_info['size_bytes'] = os.path.getsize(backup_file)
            logger.info(f"SQLite backup created: {backup_file}")
        else:
            backup_info['status'] = 'failed'
            backup_info['error'] = f"Source database file not found: {source_path}"
        
        return backup_info
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """List all available backups"""
        backups = []
        
        try:
            for filename in os.listdir(self.backup_dir):
                file_path = os.path.join(self.backup_dir, filename)
                if os.path.isfile(file_path):
                    stat = os.stat(file_path)
                    backups.append({
                        'name': filename,
                        'file_path': file_path,
                        'size_bytes': stat.st_size,
                        'created_at': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                        'age_days': (datetime.now() - datetime.fromtimestamp(stat.st_ctime)).days
                    })
            
            # Sort by creation time (newest first)
            backups.sort(key=lambda x: x['created_at'], reverse=True)
            
        except Exception as e:
            logger.error(f"Error listing backups: {e}")
        
        return backups
    
    def cleanup_old_backups(self) -> Dict[str, Any]:
        """Remove old backups based on retention policy"""
        cleanup_info = {
            'removed_count': 0,
            'removed_files': [],
            'freed_bytes': 0,
            'errors': []
        }
        
        try:
            cutoff_date = datetime.now() - timedelta(days=self.max_backup_age_days)
            
            for backup in self.list_backups():
                backup_date = datetime.fromisoformat(backup['created_at'])
                
                if backup_date < cutoff_date:
                    try:
                        os.remove(backup['file_path'])
                        cleanup_info['removed_count'] += 1
                        cleanup_info['removed_files'].append(backup['name'])
                        cleanup_info['freed_bytes'] += backup['size_bytes']
                        logger.info(f"Removed old backup: {backup['name']}")
                    except Exception as e:
                        cleanup_info['errors'].append(f"Failed to remove {backup['name']}: {e}")
            
        except Exception as e:
            cleanup_info['errors'].append(f"Cleanup failed: {e}")
            logger.error(f"Backup cleanup failed: {e}")
        
        return cleanup_info
    
    def restore_backup(self, backup_name: str) -> Dict[str, Any]:
        """Restore database from backup"""
        restore_info = {
            'backup_name': backup_name,
            'status': 'unknown',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'error': None
        }
        
        try:
            backup_file = os.path.join(self.backup_dir, backup_name)
            
            if not os.path.exists(backup_file):
                restore_info['status'] = 'failed'
                restore_info['error'] = f"Backup file not found: {backup_name}"
                return restore_info
            
            db_url = str(self.db.engine.url)
            
            if 'postgresql' in db_url and backup_name.endswith('.sql'):
                restore_info = self._restore_postgresql_backup(backup_file, restore_info)
            elif 'sqlite' in db_url and backup_name.endswith('.db'):
                restore_info = self._restore_sqlite_backup(backup_file, restore_info)
            else:
                restore_info['status'] = 'failed'
                restore_info['error'] = "Backup format not compatible with current database"
            
        except Exception as e:
            restore_info['status'] = 'failed'
            restore_info['error'] = str(e)
            logger.error(f"Database restore failed: {e}")
        
        return restore_info
    
    def _restore_postgresql_backup(self, backup_file: str, restore_info: Dict) -> Dict[str, Any]:
        """Restore PostgreSQL backup using psql"""
        db_url = str(self.db.engine.url)
        
        # Parse database URL
        import urllib.parse
        parsed = urllib.parse.urlparse(db_url)
        
        env = os.environ.copy()
        if parsed.password:
            env['PGPASSWORD'] = parsed.password
        
        cmd = [
            'psql',
            '-h', parsed.hostname or 'localhost',
            '-p', str(parsed.port or 5432),
            '-U', parsed.username or 'postgres',
            '-d', parsed.path.lstrip('/'),
            '-f', backup_file
        ]
        
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        if result.returncode == 0:
            restore_info['status'] = 'success'
            logger.info(f"PostgreSQL restore completed: {backup_file}")
        else:
            restore_info['status'] = 'failed'
            restore_info['error'] = result.stderr
            logger.error(f"PostgreSQL restore failed: {result.stderr}")
        
        return restore_info
    
    def _restore_sqlite_backup(self, backup_file: str, restore_info: Dict) -> Dict[str, Any]:
        """Restore SQLite backup by replacing the database file"""
        db_url = str(self.db.engine.url)
        target_path = db_url.replace('sqlite:///', '')
        
        # Create backup of current database
        current_backup = f"{target_path}.pre_restore_{int(datetime.now().timestamp())}"
        if os.path.exists(target_path):
            shutil.copy2(target_path, current_backup)
        
        try:
            shutil.copy2(backup_file, target_path)
            restore_info['status'] = 'success'
            logger.info(f"SQLite restore completed: {backup_file}")
        except Exception as e:
            # Restore original file if restore failed
            if os.path.exists(current_backup):
                shutil.copy2(current_backup, target_path)
            restore_info['status'] = 'failed'
            restore_info['error'] = str(e)
        finally:
            # Clean up temporary backup
            if os.path.exists(current_backup):
                os.remove(current_backup)
        
        return restore_info
    
    def optimize_database(self) -> Dict[str, Any]:
        """Optimize database performance"""
        optimization_info = {
            'status': 'unknown',
            'operations': [],
            'errors': []
        }
        
        try:
            db_url = str(self.db.engine.url)
            
            if 'postgresql' in db_url:
                optimization_info = self._optimize_postgresql(optimization_info)
            elif 'sqlite' in db_url:
                optimization_info = self._optimize_sqlite(optimization_info)
            
            if not optimization_info['errors']:
                optimization_info['status'] = 'success'
            else:
                optimization_info['status'] = 'partial'
            
        except Exception as e:
            optimization_info['status'] = 'failed'
            optimization_info['errors'].append(str(e))
            logger.error(f"Database optimization failed: {e}")
        
        return optimization_info
    
    def _optimize_postgresql(self, optimization_info: Dict) -> Dict[str, Any]:
        """Optimize PostgreSQL database"""
        try:
            # Analyze tables
            self.db.session.execute(text('ANALYZE'))
            optimization_info['operations'].append('ANALYZE completed')
            
            # Vacuum (if not in transaction)
            self.db.session.commit()
            self.db.session.execute(text('VACUUM'))
            optimization_info['operations'].append('VACUUM completed')
            
        except Exception as e:
            optimization_info['errors'].append(f"PostgreSQL optimization error: {e}")
        
        return optimization_info
    
    def _optimize_sqlite(self, optimization_info: Dict) -> Dict[str, Any]:
        """Optimize SQLite database"""
        try:
            # Analyze
            self.db.session.execute(text('ANALYZE'))
            optimization_info['operations'].append('ANALYZE completed')
            
            # Vacuum
            self.db.session.execute(text('VACUUM'))
            optimization_info['operations'].append('VACUUM completed')
            
            # Reindex
            self.db.session.execute(text('REINDEX'))
            optimization_info['operations'].append('REINDEX completed')
            
        except Exception as e:
            optimization_info['errors'].append(f"SQLite optimization error: {e}")
        
        return optimization_info
    
    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """Get detailed information about a specific table"""
        table_info = {
            'name': table_name,
            'exists': False,
            'columns': [],
            'indexes': [],
            'row_count': 0,
            'size_info': {}
        }
        
        try:
            inspector = inspect(self.db.engine)
            
            if table_name in inspector.get_table_names():
                table_info['exists'] = True
                
                # Get columns
                columns = inspector.get_columns(table_name)
                table_info['columns'] = [
                    {
                        'name': col['name'],
                        'type': str(col['type']),
                        'nullable': col['nullable'],
                        'default': col.get('default')
                    }
                    for col in columns
                ]
                
                # Get indexes
                indexes = inspector.get_indexes(table_name)
                table_info['indexes'] = [
                    {
                        'name': idx['name'],
                        'columns': idx['column_names'],
                        'unique': idx['unique']
                    }
                    for idx in indexes
                ]
                
                # Get row count
                result = self.db.session.execute(text(f'SELECT COUNT(*) FROM {table_name}'))
                table_info['row_count'] = result.scalar()
                
                # Get size information (PostgreSQL only)
                if 'postgresql' in str(self.db.engine.url):
                    result = self.db.session.execute(text(f"""
                        SELECT pg_size_pretty(pg_total_relation_size('{table_name}'))
                    """))
                    table_info['size_info']['total_size'] = result.scalar()
            
        except Exception as e:
            logger.error(f"Error getting table info for {table_name}: {e}")
        
        return table_info
    
    def export_schema(self) -> Dict[str, Any]:
        """Export database schema information"""
        schema_info = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'database_url': str(self.db.engine.url).split('@')[0] + '@***',  # Hide credentials
            'tables': {}
        }
        
        try:
            inspector = inspect(self.db.engine)
            
            for table_name in inspector.get_table_names():
                schema_info['tables'][table_name] = self.get_table_info(table_name)
            
        except Exception as e:
            logger.error(f"Error exporting schema: {e}")
            schema_info['error'] = str(e)
        
        return schema_info

# Global database manager instance (will be initialized with app)
db_manager = None

def init_database_manager(db):
    """Initialize global database manager"""
    global db_manager
    db_manager = DatabaseManager(db)
    return db_manager

