"""
Ping System Adapter - Provides backward compatibility for existing ping systems
"""
import discord
from typing import List, Optional
from utils.config_manager import load_config
from utils.ping_manager import ping_manager
import logging

logger = logging.getLogger(__name__)

class PingSystemAdapter:
    """Adapter to maintain backward compatibility with existing ping systems"""
    
    @staticmethod
    def get_ping_roles_for_user_legacy(user: discord.Member) -> List[discord.Role]:
        """
        Get ping roles for user using legacy ping_settings
        This is for backward compatibility with existing systems
        """
        config = load_config()
        ping_settings = config.get('ping_settings', {})
        
        ping_roles = []
        user_role_ids = [role.id for role in user.roles]
        
        # Check each ping setting
        for role_id_str, ping_role_ids in ping_settings.items():
            role_id = int(role_id_str)
            
            # If user has this role, add corresponding ping roles
            if role_id in user_role_ids:
                for ping_role_id in ping_role_ids:
                    ping_role = user.guild.get_role(ping_role_id)
                    if ping_role and ping_role not in ping_roles:
                        ping_roles.append(ping_role)
        
        return ping_roles
    
    @staticmethod
    def get_ping_roles_for_leave_requests(user: discord.Member) -> List[discord.Role]:
        """Get ping roles for leave requests - tries new system first, then legacy"""
        # Try new system first
        dept_code = ping_manager.get_user_department_code(user)
        if dept_code:
            ping_roles = ping_manager.get_ping_roles_for_context(dept_code, 'leave_requests', user.guild)
            if ping_roles:
                return ping_roles
        
        # Fallback to legacy system
        return PingSystemAdapter._get_ping_roles_legacy_leave_requests(user)
    
    @staticmethod
    def _get_ping_roles_legacy_leave_requests(user: discord.Member) -> List[discord.Role]:
        """Legacy leave request ping logic"""
        from forms.leave_requests.utils import LeaveRequestUtils
        
        # Get department from user roles
        department = LeaveRequestUtils.get_department_from_roles(user.roles)
        
        # Get ping roles for this department
        return LeaveRequestUtils.get_ping_roles(department, user.guild)
    
    @staticmethod
    def get_ping_roles_for_dismissals(user: discord.Member) -> List[discord.Role]:
        """Get ping roles for dismissals - tries new system first, then legacy"""
        # Try new system first
        dept_code = ping_manager.get_user_department_code(user)
        if dept_code:
            ping_roles = ping_manager.get_ping_roles_for_context(dept_code, 'dismissals', user.guild)
            if ping_roles:
                return ping_roles
        
        # Fallback to legacy system
        return PingSystemAdapter.get_ping_roles_for_user_legacy(user)
    
    @staticmethod
    def get_ping_roles_for_warehouse(user: discord.Member) -> List[discord.Role]:
        """Get ping roles for warehouse requests - tries new system first, then legacy"""
        # Try new system first
        dept_code = ping_manager.get_user_department_code(user)
        if dept_code:
            ping_roles = ping_manager.get_ping_roles_for_context(dept_code, 'warehouse', user.guild)
            if ping_roles:
                return ping_roles
        
        # Fallback to legacy warehouse manager logic
        return PingSystemAdapter._get_ping_roles_legacy_warehouse(user)
    
    @staticmethod
    def _get_ping_roles_legacy_warehouse(user: discord.Member) -> List[discord.Role]:
        """Legacy warehouse ping logic"""
        from utils.warehouse_manager import WarehouseManager
        
        warehouse_manager = WarehouseManager()
        return warehouse_manager.get_ping_roles_for_warehouse_request(user, "")
    
    @staticmethod
    def get_ping_roles_for_role_assignments(user: discord.Member, role_type: str) -> List[discord.Role]:
        """Get ping roles for role assignments using legacy config"""
        config = load_config()
        
        # Use legacy role assignment ping settings
        ping_role_ids = []
        
        if role_type == "military":
            ping_role_ids = config.get('military_role_assignment_ping_roles', [])
        elif role_type == "civilian":
            ping_role_ids = config.get('civilian_role_assignment_ping_roles', [])
        elif role_type == "supplier":
            ping_role_ids = config.get('supplier_role_assignment_ping_roles', [])
        
        ping_roles = []
        for role_id in ping_role_ids:
            role = user.guild.get_role(role_id)
            if role:
                ping_roles.append(role)
        
        return ping_roles
    
    @staticmethod
    def migrate_legacy_pings_to_new_system(guild: discord.Guild):
        """Migrate legacy ping settings to new department-based system"""
        logger.info("Starting migration of legacy ping settings to new system")
        
        config = load_config()
        ping_settings = config.get('ping_settings', {})
        
        if not ping_settings:
            logger.info("No legacy ping settings to migrate")
            return
        
        migrated_count = 0
        
        for dept_role_id_str, ping_role_ids in ping_settings.items():
            try:
                dept_role_id = int(dept_role_id_str)
                dept_role = guild.get_role(dept_role_id)
                
                if not dept_role:
                    logger.warning(f"Department role {dept_role_id} not found, skipping")
                    continue
                
                # Try to match role to department
                dept_code = PingSystemAdapter._match_role_to_department(dept_role.name)
                
                if dept_code:
                    # Migrate to new system
                    logger.info(f"Migrating {dept_role.name} -> {dept_code}")
                    
                    # Set for general context (backward compatibility)
                    ping_manager.set_ping_context(dept_code, 'general', ping_role_ids)
                    
                    # Also set for specific contexts
                    ping_manager.set_ping_context(dept_code, 'leave_requests', ping_role_ids)
                    ping_manager.set_ping_context(dept_code, 'dismissals', ping_role_ids)
                    
                    migrated_count += 1
                else:
                    logger.warning(f"Could not match role {dept_role.name} to department")
                    
            except Exception as e:
                logger.error(f"Error migrating ping setting {dept_role_id_str}: {e}")
        
        logger.info(f"Migration complete. Migrated {migrated_count} ping configurations")
    
    @staticmethod
    def _match_role_to_department(role_name: str) -> Optional[str]:
        """Match role name to department code"""
        role_name_lower = role_name.lower()
        
        # Use patterns from ping_manager
        for dept_code, patterns in ping_manager.DEPARTMENT_PATTERNS.items():
            for pattern in patterns:
                if pattern in role_name_lower:
                    return dept_code
        
        return None
    
    @staticmethod
    def validate_ping_system_compatibility(guild: discord.Guild) -> tuple[bool, List[str]]:
        """Validate that existing systems can work with new ping system"""
        issues = []
        
        # Check if any legacy ping_settings exist that aren't migrated
        config = load_config()
        ping_settings = config.get('ping_settings', {})
        departments = config.get('departments', {})
        
        if ping_settings and not departments:
            issues.append("Существуют legacy ping_settings, но новая система подразделений не настроена")
        
        # Check each department configuration
        for dept_code in ['УВП', 'ССО', 'РОиО', 'ВК', 'МР']:
            is_valid, status = ping_manager.validate_department_config(dept_code, guild)
            if not is_valid:
                issues.append(f"Подразделение {dept_code}: {status}")
        
        return len(issues) == 0, issues

# Global adapter instance
ping_adapter = PingSystemAdapter()
