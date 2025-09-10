#!/usr/bin/env python3
"""
Rollback Execution Script for Telegive Bot Service
Provides command-line interface for rollback operations
"""

import sys
import os
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.rollback_manager import rollback_manager, RollbackPlan
from utils.logging_config import configure_logging, get_logger

# Configure logging
configure_logging()
logger = get_logger(__name__)

def list_snapshots(environment: str = None):
    """List available deployment snapshots"""
    print("📸 Available Deployment Snapshots")
    print("=" * 50)
    
    history = rollback_manager.get_rollback_history(environment)
    
    if not history:
        print("No snapshots found.")
        return
    
    for snapshot in history:
        status_icon = "✅" if snapshot['status'] == 'active' else "📦"
        backup_info = []
        
        if snapshot['has_database_backup']:
            backup_info.append("DB")
        if snapshot['has_application_backup']:
            backup_info.append("APP")
        
        backup_str = f"[{', '.join(backup_info)}]" if backup_info else "[NO BACKUPS]"
        
        print(f"{status_icon} {snapshot['snapshot_id']}")
        print(f"   Version: {snapshot['version']}")
        print(f"   Environment: {snapshot['environment']}")
        print(f"   Created: {snapshot['timestamp']}")
        print(f"   Backups: {backup_str}")
        print(f"   Status: {snapshot['status']}")
        
        if snapshot['metadata']:
            print(f"   Metadata: {json.dumps(snapshot['metadata'], indent=2)}")
        
        print()

def show_rollback_candidates(environment: str):
    """Show rollback candidates for an environment"""
    print(f"🔄 Rollback Candidates for {environment}")
    print("=" * 50)
    
    candidates = rollback_manager.get_rollback_candidates(environment)
    
    if not candidates:
        print(f"No rollback candidates found for environment: {environment}")
        return
    
    for i, candidate in enumerate(candidates, 1):
        age_days = (datetime.now(timezone.utc) - candidate.timestamp).days
        
        print(f"{i}. {candidate.id}")
        print(f"   Version: {candidate.version}")
        print(f"   Created: {candidate.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"   Age: {age_days} days")
        print(f"   Database Backup: {'✅' if candidate.database_backup_path else '❌'}")
        print(f"   Application Backup: {'✅' if candidate.application_backup_path else '❌'}")
        print()

def create_rollback_plan_interactive(target_snapshot_id: str):
    """Create and display rollback plan"""
    print(f"📋 Creating Rollback Plan for {target_snapshot_id}")
    print("=" * 50)
    
    plan = rollback_manager.create_rollback_plan(target_snapshot_id)
    
    if not plan:
        print(f"❌ Failed to create rollback plan for {target_snapshot_id}")
        return None
    
    print(f"Target Snapshot: {plan.target_snapshot_id}")
    print(f"Estimated Duration: {plan.estimated_duration // 60} minutes {plan.estimated_duration % 60} seconds")
    print(f"Risk Level: {plan.risk_level.upper()}")
    print(f"Requires Downtime: {'Yes' if plan.requires_downtime else 'No'}")
    print()
    
    print("📝 Rollback Steps:")
    for i, step in enumerate(plan.rollback_steps, 1):
        critical_marker = "🔴" if step.get('critical', False) else "🟡"
        duration_min = step['estimated_duration'] // 60
        duration_sec = step['estimated_duration'] % 60
        
        print(f"  {i}. {critical_marker} {step['description']}")
        print(f"     Duration: {duration_min}m {duration_sec}s")
        print()
    
    print("✅ Validation Steps:")
    for i, validation in enumerate(plan.validation_steps, 1):
        print(f"  {i}. {validation}")
    print()
    
    return plan

def execute_rollback_interactive(plan: RollbackPlan, dry_run: bool = False):
    """Execute rollback with user confirmation"""
    if dry_run:
        print("🧪 DRY RUN MODE - No actual changes will be made")
    else:
        print("⚠️  PRODUCTION ROLLBACK - This will make actual changes!")
    
    print(f"Target: {plan.target_snapshot_id}")
    print(f"Risk Level: {plan.risk_level.upper()}")
    print(f"Estimated Duration: {plan.estimated_duration // 60} minutes")
    
    if plan.requires_downtime:
        print("⚠️  This rollback requires application downtime!")
    
    if not dry_run:
        confirmation = input("\nDo you want to proceed? (type 'ROLLBACK' to confirm): ")
        if confirmation != 'ROLLBACK':
            print("❌ Rollback cancelled by user")
            return False
    
    print("\n🚀 Starting rollback execution...")
    print("=" * 50)
    
    success, execution_log = rollback_manager.execute_rollback(plan, dry_run)
    
    # Display execution log
    for log_entry in execution_log:
        print(log_entry)
    
    if success:
        if dry_run:
            print("\n✅ Dry run completed successfully")
        else:
            print("\n✅ Rollback completed successfully")
        return True
    else:
        print("\n❌ Rollback failed")
        return False

def create_snapshot_interactive():
    """Create a deployment snapshot interactively"""
    print("📸 Create Deployment Snapshot")
    print("=" * 30)
    
    version = input("Version (e.g., v1.2.3): ").strip()
    if not version:
        print("❌ Version is required")
        return
    
    environment = input("Environment (e.g., production, staging): ").strip()
    if not environment:
        print("❌ Environment is required")
        return
    
    description = input("Description (optional): ").strip()
    
    metadata = {}
    if description:
        metadata['description'] = description
    
    print(f"\nCreating snapshot for {version} in {environment}...")
    
    try:
        snapshot_id = rollback_manager.create_deployment_snapshot(version, environment, metadata)
        print(f"✅ Snapshot created successfully: {snapshot_id}")
    except Exception as e:
        print(f"❌ Failed to create snapshot: {e}")

def cleanup_old_snapshots(retention_days: int):
    """Clean up old snapshots"""
    print(f"🧹 Cleaning up snapshots older than {retention_days} days")
    
    try:
        rollback_manager.cleanup_old_snapshots(retention_days)
        print("✅ Cleanup completed")
    except Exception as e:
        print(f"❌ Cleanup failed: {e}")

def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(description="Telegive Bot Service Rollback Manager")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # List snapshots command
    list_parser = subparsers.add_parser('list', help='List deployment snapshots')
    list_parser.add_argument('--environment', '-e', help='Filter by environment')
    
    # Show candidates command
    candidates_parser = subparsers.add_parser('candidates', help='Show rollback candidates')
    candidates_parser.add_argument('environment', help='Environment name')
    
    # Create plan command
    plan_parser = subparsers.add_parser('plan', help='Create rollback plan')
    plan_parser.add_argument('snapshot_id', help='Target snapshot ID')
    
    # Execute rollback command
    rollback_parser = subparsers.add_parser('rollback', help='Execute rollback')
    rollback_parser.add_argument('snapshot_id', help='Target snapshot ID')
    rollback_parser.add_argument('--dry-run', action='store_true', help='Perform dry run')
    rollback_parser.add_argument('--auto-confirm', action='store_true', help='Skip confirmation')
    
    # Create snapshot command
    snapshot_parser = subparsers.add_parser('snapshot', help='Create deployment snapshot')
    snapshot_parser.add_argument('--version', '-v', help='Version string')
    snapshot_parser.add_argument('--environment', '-e', help='Environment name')
    snapshot_parser.add_argument('--description', '-d', help='Description')
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser('cleanup', help='Clean up old snapshots')
    cleanup_parser.add_argument('--retention-days', type=int, default=30, 
                               help='Retention period in days (default: 30)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        if args.command == 'list':
            list_snapshots(args.environment)
        
        elif args.command == 'candidates':
            show_rollback_candidates(args.environment)
        
        elif args.command == 'plan':
            create_rollback_plan_interactive(args.snapshot_id)
        
        elif args.command == 'rollback':
            plan = rollback_manager.create_rollback_plan(args.snapshot_id)
            if plan:
                if args.auto_confirm:
                    success, _ = rollback_manager.execute_rollback(plan, args.dry_run)
                    if success:
                        print("✅ Rollback completed successfully")
                    else:
                        print("❌ Rollback failed")
                        sys.exit(1)
                else:
                    success = execute_rollback_interactive(plan, args.dry_run)
                    if not success:
                        sys.exit(1)
            else:
                print(f"❌ Failed to create rollback plan for {args.snapshot_id}")
                sys.exit(1)
        
        elif args.command == 'snapshot':
            if args.version and args.environment:
                metadata = {}
                if args.description:
                    metadata['description'] = args.description
                
                snapshot_id = rollback_manager.create_deployment_snapshot(
                    args.version, args.environment, metadata
                )
                print(f"✅ Snapshot created: {snapshot_id}")
            else:
                create_snapshot_interactive()
        
        elif args.command == 'cleanup':
            cleanup_old_snapshots(args.retention_days)
    
    except KeyboardInterrupt:
        print("\n❌ Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Command failed: {e}")
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()

