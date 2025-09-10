#!/usr/bin/env python3
"""
Automated database maintenance script for Telegive Bot Service
Performs regular database maintenance tasks including backups, optimization, and cleanup
"""

import os
import sys
import logging
import argparse
from datetime import datetime, timezone
from typing import Dict, Any

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from utils.database_manager import init_database_manager
from models import db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DatabaseMaintenanceRunner:
    """Automated database maintenance operations"""
    
    def __init__(self):
        self.app = create_app()
        self.db_manager = None
        
        with self.app.app_context():
            self.db_manager = init_database_manager(db)
    
    def run_health_check(self) -> Dict[str, Any]:
        """Run comprehensive database health check"""
        logger.info("Running database health check...")
        
        with self.app.app_context():
            health_info = self.db_manager.check_database_health()
            
            if health_info['status'] == 'healthy':
                logger.info("✅ Database health check passed")
            elif health_info['status'] == 'degraded':
                logger.warning(f"⚠️ Database health check shows degraded performance: {health_info['issues']}")
            else:
                logger.error(f"❌ Database health check failed: {health_info['issues']}")
            
            return health_info
    
    def create_backup(self, backup_name: str = None) -> Dict[str, Any]:
        """Create database backup"""
        logger.info("Creating database backup...")
        
        with self.app.app_context():
            backup_info = self.db_manager.create_backup(backup_name)
            
            if backup_info['status'] == 'success':
                size_mb = backup_info['size_bytes'] / (1024 * 1024)
                logger.info(f"✅ Backup created successfully: {backup_info['name']} ({size_mb:.2f} MB)")
            else:
                logger.error(f"❌ Backup failed: {backup_info.get('error')}")
            
            return backup_info
    
    def cleanup_old_backups(self) -> Dict[str, Any]:
        """Clean up old backups"""
        logger.info("Cleaning up old backups...")
        
        with self.app.app_context():
            cleanup_info = self.db_manager.cleanup_old_backups()
            
            if cleanup_info['removed_count'] > 0:
                freed_mb = cleanup_info['freed_bytes'] / (1024 * 1024)
                logger.info(f"✅ Cleaned up {cleanup_info['removed_count']} old backups, freed {freed_mb:.2f} MB")
            else:
                logger.info("ℹ️ No old backups to clean up")
            
            if cleanup_info['errors']:
                logger.warning(f"⚠️ Cleanup errors: {cleanup_info['errors']}")
            
            return cleanup_info
    
    def optimize_database(self) -> Dict[str, Any]:
        """Optimize database performance"""
        logger.info("Optimizing database...")
        
        with self.app.app_context():
            optimization_info = self.db_manager.optimize_database()
            
            if optimization_info['status'] == 'success':
                logger.info(f"✅ Database optimization completed: {optimization_info['operations']}")
            elif optimization_info['status'] == 'partial':
                logger.warning(f"⚠️ Database optimization partially completed: {optimization_info['operations']}")
                logger.warning(f"Errors: {optimization_info['errors']}")
            else:
                logger.error(f"❌ Database optimization failed: {optimization_info['errors']}")
            
            return optimization_info
    
    def run_full_maintenance(self) -> Dict[str, Any]:
        """Run complete maintenance routine"""
        logger.info("🔧 Starting full database maintenance routine...")
        
        maintenance_report = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'operations': {},
            'overall_status': 'unknown'
        }
        
        try:
            # 1. Health check
            health_info = self.run_health_check()
            maintenance_report['operations']['health_check'] = health_info
            
            # 2. Create backup
            backup_info = self.create_backup()
            maintenance_report['operations']['backup'] = backup_info
            
            # 3. Optimize database (only if healthy)
            if health_info['status'] in ['healthy', 'degraded']:
                optimization_info = self.optimize_database()
                maintenance_report['operations']['optimization'] = optimization_info
            else:
                logger.warning("Skipping optimization due to unhealthy database")
                maintenance_report['operations']['optimization'] = {'status': 'skipped', 'reason': 'unhealthy_database'}
            
            # 4. Cleanup old backups
            cleanup_info = self.cleanup_old_backups()
            maintenance_report['operations']['cleanup'] = cleanup_info
            
            # Determine overall status
            failed_operations = [
                op for op, info in maintenance_report['operations'].items()
                if info.get('status') == 'failed'
            ]
            
            if not failed_operations:
                maintenance_report['overall_status'] = 'success'
                logger.info("🎉 Full maintenance routine completed successfully")
            else:
                maintenance_report['overall_status'] = 'partial'
                logger.warning(f"⚠️ Maintenance completed with some failures: {failed_operations}")
            
        except Exception as e:
            maintenance_report['overall_status'] = 'failed'
            maintenance_report['error'] = str(e)
            logger.error(f"❌ Maintenance routine failed: {e}")
        
        return maintenance_report
    
    def list_backups(self):
        """List all available backups"""
        logger.info("Listing available backups...")
        
        with self.app.app_context():
            backups = self.db_manager.list_backups()
            
            if backups:
                logger.info(f"Found {len(backups)} backups:")
                for backup in backups:
                    size_mb = backup['size_bytes'] / (1024 * 1024)
                    logger.info(f"  - {backup['name']} ({size_mb:.2f} MB, {backup['age_days']} days old)")
            else:
                logger.info("No backups found")
            
            return backups
    
    def export_schema(self):
        """Export database schema"""
        logger.info("Exporting database schema...")
        
        with self.app.app_context():
            schema_info = self.db_manager.export_schema()
            
            # Save schema to file
            schema_file = f"schema_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            import json
            with open(schema_file, 'w') as f:
                json.dump(schema_info, f, indent=2, default=str)
            
            logger.info(f"✅ Schema exported to {schema_file}")
            
            # Print summary
            table_count = len(schema_info.get('tables', {}))
            logger.info(f"Database contains {table_count} tables")
            
            return schema_info

def main():
    """Main function with command line interface"""
    parser = argparse.ArgumentParser(description='Database maintenance for Telegive Bot Service')
    parser.add_argument('operation', choices=[
        'health-check', 'backup', 'cleanup', 'optimize', 'full-maintenance',
        'list-backups', 'export-schema'
    ], help='Maintenance operation to perform')
    parser.add_argument('--backup-name', help='Custom backup name')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize maintenance runner
    runner = DatabaseMaintenanceRunner()
    
    # Execute requested operation
    try:
        if args.operation == 'health-check':
            result = runner.run_health_check()
            
        elif args.operation == 'backup':
            result = runner.create_backup(args.backup_name)
            
        elif args.operation == 'cleanup':
            result = runner.cleanup_old_backups()
            
        elif args.operation == 'optimize':
            result = runner.optimize_database()
            
        elif args.operation == 'full-maintenance':
            result = runner.run_full_maintenance()
            
        elif args.operation == 'list-backups':
            result = runner.list_backups()
            
        elif args.operation == 'export-schema':
            result = runner.export_schema()
        
        # Print result summary
        if args.verbose:
            import json
            print("\n" + "="*50)
            print("OPERATION RESULT:")
            print("="*50)
            print(json.dumps(result, indent=2, default=str))
        
        # Exit with appropriate code
        if isinstance(result, dict):
            status = result.get('status') or result.get('overall_status', 'unknown')
            if status in ['success', 'healthy']:
                sys.exit(0)
            elif status in ['partial', 'degraded']:
                sys.exit(1)
            else:
                sys.exit(2)
        else:
            sys.exit(0)
            
    except Exception as e:
        logger.error(f"Operation failed: {e}")
        sys.exit(3)

if __name__ == '__main__':
    main()

