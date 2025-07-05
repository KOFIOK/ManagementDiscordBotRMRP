#!/usr/bin/env python3
"""
Migration script for ping settings
Migrates legacy ping_settings to new departments.ping_contexts structure
"""

import asyncio
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from utils.config_manager import load_config, save_config
from utils.ping_manager import ping_manager


async def migrate_ping_settings():
    """Migrate legacy ping_settings to new structure"""
    print("🔄 Starting ping settings migration...")
    
    config = load_config()
    legacy_settings = config.get('ping_settings', {})
    
    if not legacy_settings:
        print("ℹ️ No legacy ping settings found. Migration not needed.")
        return
    
    print(f"📋 Found {len(legacy_settings)} legacy ping settings to migrate:")
    
    migrated_count = 0
    migration_log = []
    
    # Create departments section if it doesn't exist
    if 'departments' not in config:
        config['departments'] = {}
    
    # Migrate each legacy setting
    for dept_role_id_str, ping_role_ids in legacy_settings.items():
        print(f"   Processing role ID: {dept_role_id_str}")
        
        # Try to match role to department code
        department_code = _match_role_id_to_department(int(dept_role_id_str))
        
        if not department_code:
            migration_log.append(f"❌ Could not determine department for role ID {dept_role_id_str}")
            print(f"   ❌ Could not determine department for role ID {dept_role_id_str}")
            continue
        
        # Create department config if needed
        if department_code not in config['departments']:
            config['departments'][department_code] = {}
        
        # Set role_id if not already set
        if 'role_id' not in config['departments'][department_code]:
            config['departments'][department_code]['role_id'] = int(dept_role_id_str)
        
        # Create ping_contexts if needed
        if 'ping_contexts' not in config['departments'][department_code]:
            config['departments'][department_code]['ping_contexts'] = {}
        
        # Migrate to multiple contexts for backward compatibility
        contexts_to_migrate = ['general', 'dismissals', 'leave_requests']
        
        for context in contexts_to_migrate:
            config['departments'][department_code]['ping_contexts'][context] = ping_role_ids
        
        migrated_count += 1
        migration_log.append(f"✅ {department_code}: Role {dept_role_id_str} -> contexts: {', '.join(contexts_to_migrate)}")
        print(f"   ✅ Migrated to {department_code}: contexts {', '.join(contexts_to_migrate)}")
    
    if migrated_count > 0:
        # Clear legacy settings
        config['ping_settings'] = {}
        save_config(config)
        
        print(f"\n✅ Migration completed successfully!")
        print(f"   Migrated: {migrated_count} settings")
        print(f"   Legacy ping_settings cleared")
        
        print("\n📋 Migration log:")
        for log_entry in migration_log:
            print(f"   {log_entry}")
            
        print("\n📢 New ping contexts are now available:")
        for context_key, context_name in ping_manager.CONTEXTS.items():
            print(f"   • {context_name} ({context_key})")
            
        print("\n🔧 Next steps:")
        print("   1. Use /settings to configure context-specific pings")
        print("   2. Test notifications with new system")
        print("   3. Configure additional contexts as needed")
    else:
        print("\n⚠️ No settings were migrated.")
        
        if migration_log:
            print("\n📋 Issues encountered:")
            for log_entry in migration_log:
                print(f"   {log_entry}")


def _match_role_id_to_department(role_id: int) -> str:
    """
    Match a role ID to department code based on config or patterns.
    This is a simplified version - in real scenarios, you might need
    to check actual Discord role names or other patterns.
    """
    # You can customize this mapping based on your server's role structure
    # For now, we'll use a basic approach
    
    # Check if role is already assigned to a department
    config = load_config()
    departments = config.get('departments', {})
    
    for dept_code, dept_config in departments.items():
        if dept_config.get('role_id') == role_id:
            return dept_code
    
    # Fallback: return None to indicate manual intervention needed
    return None


if __name__ == "__main__":
    asyncio.run(migrate_ping_settings())
