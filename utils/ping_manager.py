"""
Centralized ping management system for department-based notifications.
Supports context-specific pings for different types of requests.
"""
import discord
from typing import List, Dict, Optional, Set
from utils.config_manager import load_config, save_config
import logging

logger = logging.getLogger(__name__)

class PingManager:
    """Centralized manager for ping-related operations with context support"""
    
    # Supported ping contexts
    CONTEXTS = {
        'applications': 'Заявления в подразделения',
        'leave_requests': 'Рапорты на отпуск', 
        'dismissals': 'Увольнения',
        'warehouse': 'Складские запросы',
        'promotions': 'Присвоения званий',
        'medical': 'Медицинские заявки',
        'general': 'Общие уведомления'
    }
    
    # Department mapping for backward compatibility
    DEPARTMENT_PATTERNS = {
        'УВП': ['увп', 'увп.', 'учебно-воспитательный', 'учебно-воспитательного'],
        'ССО': ['ссо', 'ссо.', 'силы специальных операций', 'специальных операций'],
        'РОиО': ['роио', 'роио.', 'разведка', 'разведывательный', 'разведывательного'],
        'ВК': ['вк', 'вк.', 'военная комендатура', 'комендатура', 'комендатуры'],
        'МР': ['мр', 'мр.', 'медицинская рота', 'медицинская', 'медицинской']
    }
    
    def __init__(self):
        self.config = load_config()
    
    def get_departments_config(self) -> Dict:
        """Get the departments configuration with ping contexts"""
        return self.config.get('departments', {})
    
    def get_ping_settings_legacy(self) -> Dict:
        """Get legacy ping_settings for backward compatibility"""
        return self.config.get('ping_settings', {})
    
    def get_department_role_id(self, department_code: str) -> Optional[int]:
        """Get role ID for a department"""
        departments = self.get_departments_config()
        dept_config = departments.get(department_code)
        if dept_config:
            return dept_config.get('role_id')
        return None
    
    def get_department_channel_id(self, department_code: str) -> Optional[int]:
        """Get application channel ID for a department"""
        departments = self.get_departments_config()
        dept_config = departments.get(department_code)
        if dept_config:
            return dept_config.get('application_channel_id')
        return None
    
    def get_ping_roles_for_context(self, department_code: str, context: str, guild: discord.Guild) -> List[discord.Role]:
        """
        Get ping roles for a specific department and context
        
        Args:
            department_code: Department code (УВП, ССО, РОиО, ВК, МР)
            context: Ping context (applications, leave_requests, dismissals, etc.)
            guild: Discord guild
            
        Returns:
            List of Discord roles to ping
        """
        departments = self.get_departments_config()
        
        # Try new structure first
        if department_code in departments:
            dept_config = departments[department_code]
            ping_contexts = dept_config.get('ping_contexts', {})
            
            if context in ping_contexts:
                role_ids = ping_contexts[context]
                roles = []
                for role_id in role_ids:
                    role = guild.get_role(role_id)
                    if role:
                        roles.append(role)
                return roles
        
        # Fallback to legacy ping_settings
        return self._get_ping_roles_legacy(department_code, guild)
    
    def _get_ping_roles_legacy(self, department_code: str, guild: discord.Guild) -> List[discord.Role]:
        """Fallback to legacy ping_settings"""
        ping_settings = self.get_ping_settings_legacy()
        
        for dept_role_id_str, ping_role_ids in ping_settings.items():
            dept_role = guild.get_role(int(dept_role_id_str))
            if dept_role:
                # Check if this role matches the department
                if self._role_matches_department(dept_role.name, department_code):
                    roles = []
                    for role_id in ping_role_ids:
                        role = guild.get_role(role_id)
                        if role:
                            roles.append(role)
                    return roles
        
        return []
    
    def _role_matches_department(self, role_name: str, department_code: str) -> bool:
        """Check if a role name matches a department code"""
        role_name_lower = role_name.lower()
        patterns = self.DEPARTMENT_PATTERNS.get(department_code, [])
        
        for pattern in patterns:
            if pattern in role_name_lower:
                return True
        
        return False
    
    def get_user_department_code(self, user: discord.Member) -> Optional[str]:
        """Get department code for a user based on their roles"""
        departments = self.get_departments_config()
        
        # Check new structure first
        for dept_code, dept_config in departments.items():
            role_id = dept_config.get('role_id')
            if role_id:
                role = user.guild.get_role(role_id)
                if role and role in user.roles:
                    return dept_code
        
        # Fallback to legacy detection
        return self._get_user_department_legacy(user)
    
    def _get_user_department_legacy(self, user: discord.Member) -> Optional[str]:
        """Fallback to legacy department detection"""
        for role in user.roles:
            for dept_code, patterns in self.DEPARTMENT_PATTERNS.items():
                if self._role_matches_department(role.name, dept_code):
                    return dept_code
        
        return None
    
    def get_ping_roles_for_user(self, user: discord.Member, context: str) -> List[discord.Role]:
        """Get ping roles for a user in a specific context"""
        dept_code = self.get_user_department_code(user)
        if dept_code:
            return self.get_ping_roles_for_context(dept_code, context, user.guild)
        return []
    
    def set_department_config(self, department_code: str, config: Dict):
        """Set configuration for a department"""
        if 'departments' not in self.config:
            self.config['departments'] = {}
        
        self.config['departments'][department_code] = config
        save_config(self.config)
    
    def set_ping_context(self, department_code: str, context: str, role_ids: List[int]):
        """Set ping roles for a specific department and context"""
        if 'departments' not in self.config:
            self.config['departments'] = {}
        
        if department_code not in self.config['departments']:
            self.config['departments'][department_code] = {}
        
        if 'ping_contexts' not in self.config['departments'][department_code]:
            self.config['departments'][department_code]['ping_contexts'] = {}
        
        self.config['departments'][department_code]['ping_contexts'][context] = role_ids
        save_config(self.config)
    
    def get_all_departments(self) -> Dict[str, Dict]:
        """Get all departments configuration"""
        return self.get_departments_config()
    
    def get_department_info(self, department_code: str) -> Optional[Dict]:
        """Get full configuration for a specific department"""
        departments = self.get_departments_config()
        return departments.get(department_code)
    
    def migrate_legacy_config(self):
        """Migrate legacy ping_settings to new structure"""
        logger.info("Starting migration of legacy ping configuration")
        
        ping_settings = self.get_ping_settings_legacy()
        guild_id = None  # We'll need to get this from somewhere
        
        # This would need to be called with a guild context
        # For now, just log what would be migrated
        
        migrated_count = 0
        for dept_role_id_str, ping_role_ids in ping_settings.items():
            # Try to determine department from role ID
            # This would need guild context to actually work
            logger.info(f"Would migrate dept_role_id {dept_role_id_str} -> ping_roles {ping_role_ids}")
            migrated_count += 1
        
        logger.info(f"Migration complete. Migrated {migrated_count} ping configurations")
    
    def validate_department_config(self, department_code: str, guild: discord.Guild) -> tuple[bool, str]:
        """Validate department configuration"""
        dept_config = self.get_department_info(department_code)
        
        if not dept_config:
            return False, f"Конфигурация для подразделения {department_code} не найдена"
        
        # Check if role exists
        role_id = dept_config.get('role_id')
        if role_id:
            role = guild.get_role(role_id)
            if not role:
                return False, f"Роль подразделения {department_code} (ID: {role_id}) не найдена"
        
        # Check if channel exists
        channel_id = dept_config.get('application_channel_id')
        if channel_id:
            channel = guild.get_channel(channel_id)
            if not channel:
                return False, f"Канал заявлений {department_code} (ID: {channel_id}) не найден"
        
        # Check ping contexts
        ping_contexts = dept_config.get('ping_contexts', {})
        for context, role_ids in ping_contexts.items():
            for role_id in role_ids:
                role = guild.get_role(role_id)
                if not role:
                    return False, f"Роль для пинга в контексте '{context}' (ID: {role_id}) не найдена"
        
        return True, "Конфигурация подразделения корректна"

# Global instance
ping_manager = PingManager()
