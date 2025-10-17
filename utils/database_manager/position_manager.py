"""
Position Management System for Discord Bot
Simple version: positions with Discord roles only
"""

import discord
from typing import Optional, Dict, List, Any, Tuple
from utils.postgresql_pool import get_db_cursor

class PositionManager:
    """Simple position manager - just positions and roles"""
    
    def __init__(self):
        self._position_roles_cache = None
        self._cache_timestamp = 0
        self._cache_ttl = 300  # 5 minutes cache
        self._cache_stats = {
            'hits': 0,
            'misses': 0,
            'refreshes': 0
        }
    
    def _get_position_roles_cached(self):
        """Get position roles with caching"""
        import time
        current_time = time.time()
        
        if (self._position_roles_cache is None or 
            current_time - self._cache_timestamp > self._cache_ttl):
            
            try:
                with get_db_cursor() as cursor:
                    cursor.execute("SELECT id, role_id FROM positions WHERE role_id IS NOT NULL")
                    position_roles = cursor.fetchall()
                    
                    # Создаем два маппинга для быстрого поиска
                    role_to_position = {int(row['role_id']): row['id'] for row in position_roles}
                    position_to_role = {row['id']: int(row['role_id']) for row in position_roles}
                    
                    self._position_roles_cache = {
                        'role_to_position': role_to_position,  # {role_id: position_id}
                        'position_to_role': position_to_role   # {position_id: role_id}
                    }
                    self._cache_timestamp = current_time
                    self._cache_stats['refreshes'] += 1
                    print(f"🔄 Refreshed position roles cache: {len(role_to_position)} roles")
            except Exception as e:
                print(f"⚠️ Failed to refresh position roles cache: {e}")
                if self._position_roles_cache is None:
                    self._position_roles_cache = {
                        'role_to_position': {},
                        'position_to_role': {}
                    }
        else:
            self._cache_stats['hits'] += 1
        
        return self._position_roles_cache
    
    def invalidate_position_cache(self):
        """Invalidate position roles cache (when positions are added/updated)"""
        self._position_roles_cache = None
        self._cache_timestamp = 0
        print("🗑️ Position roles cache invalidated")
    
    def get_cache_stats(self):
        """Get cache statistics"""
        return {
            'hits': self._cache_stats['hits'],
            'refreshes': self._cache_stats['refreshes'],
            'ttl_seconds': self._cache_ttl,
            'is_cached': self._position_roles_cache is not None
        }
    
    def add_position_to_database(self, position_name: str, role_id: Optional[int] = None) -> Tuple[bool, str]:
        """
        Add position to database with optional Discord role
        
        Args:
            position_name: Position name
            role_id: Discord role ID (optional)
            
        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            with get_db_cursor() as cursor:
                # Check if role_id already exists (if provided)
                if role_id:
                    cursor.execute("SELECT id, name FROM positions WHERE role_id = %s", (role_id,))
                    existing_position = cursor.fetchone()
                    
                    if existing_position:
                        return False, f"Должность '{existing_position['name']}' уже использует эту роль Discord"
                
                # Get next available ID
                cursor.execute("SELECT MAX(id) FROM positions")
                max_id_result = cursor.fetchone()
                max_id = max_id_result['max'] if max_id_result and max_id_result['max'] else 0
                next_id = max_id + 1
                
                # Add position to positions table
                cursor.execute(
                    "INSERT INTO positions (id, name, role_id) VALUES (%s, %s, %s)",
                    (next_id, position_name, role_id)
                )
                
                # Invalidate cache since we added a new position
                self.invalidate_position_cache()
                
                message = f"Должность '{position_name}' добавлена (ID: {next_id})"
                if role_id:
                    message += f" с ролью Discord ID: {role_id}"
                
                print(f"✅ {message}")
                return True, message
                
        except Exception as e:
            error_msg = f"Ошибка при добавлении должности: {e}"
            print(f"❌ {error_msg}")
            return False, error_msg
    
    def get_all_positions(self) -> List[Dict[str, Any]]:
        """Get all positions from database"""
        try:
            with get_db_cursor() as cursor:
                cursor.execute("SELECT id, name, role_id FROM positions ORDER BY id")
                result = cursor.fetchall()
                
                return [dict(row) for row in result] if result else []
                
        except Exception as e:
            print(f"❌ Error getting positions: {e}")
            return []
    
    def update_position_role(self, position_id: int, role_id: Optional[int]) -> Tuple[bool, str]:
        """Update Discord role for position"""
        try:
            with get_db_cursor() as cursor:
                # Check if role_id is already used by another position
                if role_id:
                    cursor.execute("SELECT id, name FROM positions WHERE role_id = %s AND id != %s", (role_id, position_id))
                    existing_position = cursor.fetchone()
                    
                    if existing_position:
                        return False, f"Роль уже используется должностью '{existing_position['name']}'"
                
                # Get position name
                cursor.execute("SELECT name FROM positions WHERE id = %s", (position_id,))
                position = cursor.fetchone()
                
                if not position:
                    return False, "Должность не найдена"
                
                # Update role_id
                cursor.execute("UPDATE positions SET role_id = %s WHERE id = %s", (role_id, position_id))
                
                action = "назначена" if role_id else "удалена"
                message = f"Роль {action} для должности '{position['name']}'"
                return True, message
                
        except Exception as e:
            return False, f"Ошибка: {e}"
    
    def remove_position_from_database(self, position_id: int) -> Tuple[bool, str]:
        """Remove position from database"""
        try:
            with get_db_cursor() as cursor:
                # Get position name
                cursor.execute("SELECT name FROM positions WHERE id = %s", (position_id,))
                position_data = cursor.fetchone()
                
                if not position_data:
                    return False, "Должность не найдена"
                
                position_name = position_data['name']
                
                # Remove users from this position
                cursor.execute("UPDATE user_data SET position_id = NULL WHERE position_id = %s", (position_id,))
                
                # Remove position
                cursor.execute("DELETE FROM positions WHERE id = %s", (position_id,))
                
                message = f"Должность '{position_name}' удалена"
                return True, message
                
        except Exception as e:
            return False, f"Ошибка: {e}"
    
    def extract_role_name_from_mention(self, role_input: str, guild: discord.Guild) -> Tuple[Optional[str], Optional[int]]:
        """Extract role name and ID from user input"""
        try:
            # Try role mention <@&123456>
            if role_input.startswith('<@&') and role_input.endswith('>'):
                role_id = int(role_input[3:-1])
                if guild:
                    role = guild.get_role(role_id)
                    return (role.name, role_id) if role else (f"Role ID {role_id}", role_id)
                return f"Role ID {role_id}", role_id
            
            # Try plain ID
            try:
                role_id = int(role_input)
                if guild:
                    role = guild.get_role(role_id)
                    return (role.name, role_id) if role else (f"Role ID {role_id}", role_id)
                return f"Role ID {role_id}", role_id
            except ValueError:
                pass
            
            # Treat as position name
            return role_input, None
            
        except Exception as e:
            print(f"❌ Error extracting role info: {e}")
            return role_input, None

    async def smart_update_user_position_roles(self, guild: discord.Guild, user: discord.Member, 
                                             new_position_id: Optional[int]) -> bool:
        """Smart update - automatically detect current position roles and remove them (optimized)"""
        try:
            # Get position roles from cache (much faster than DB query)
            cache_data = self._get_position_roles_cached()
            all_position_roles = cache_data['role_to_position']  # {role_id: position_id}
            position_to_role = cache_data['position_to_role']    # {position_id: role_id}
            
            # Get new role ID from cache (NO DB QUERY!)
            new_role_id = None
            if new_position_id and new_position_id in position_to_role:
                new_role_id = position_to_role[new_position_id]
            elif new_position_id:
                print(f"⚠️ Position {new_position_id} not found in cache")
            
            # Find current position roles user has (without API calls)
            roles_to_remove = []
            
            for role in user.roles:
                if role.id in all_position_roles:
                    # Only remove if it's not the new role we're adding
                    if role.id != new_role_id:
                        roles_to_remove.append(role)
                    else:
                        print(f"🔍 Keeping role (already assigned): {role.name}")
            
            # Batch role operations for better performance
            role_changes = []
            
            # Remove old position roles (if any)
            if roles_to_remove:
                try:
                    await user.remove_roles(*roles_to_remove, reason="Position change")
                    for role in roles_to_remove:
                        print(f"🔄 Removed position role: {role.name}")
                        role_changes.append(f"-{role.name}")
                except Exception as e:
                    print(f"⚠️ Error removing roles: {e}")
            
            # Add new position role (if needed and different)
            if new_position_id and new_role_id:
                # Check if user already has this role
                has_new_role = any(role.id == new_role_id for role in user.roles)
                
                if not has_new_role:
                    new_role = guild.get_role(new_role_id)
                    if new_role:
                        try:
                            await user.add_roles(new_role, reason="Position assignment")
                            role_changes.append(f"+{new_role.name}")
                        except Exception as e:
                            print(f"⚠️ Error adding role: {e}")
                    else:
                        print(f"⚠️ Role with ID {new_role_id} not found in guild")
                else:
                    print(f"ℹ️ User already has the target role")
            
            # Summary
            if role_changes:
                print(f"📋 Role changes: {', '.join(role_changes)}")
            else:
                print(f"ℹ️ No role changes needed for {user.display_name}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error in smart position role update: {e}")
            return False
    
    def get_user_position_from_db(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user's current position"""
        try:
            with get_db_cursor() as cursor:
                cursor.execute("""
                    SELECT p.id, p.name, p.role_id
                    FROM user_data ud
                    LEFT JOIN positions p ON ud.position_id = p.id
                    WHERE ud.user_id = %s
                """, (user_id,))
                result = cursor.fetchone()
                
                if result and result['id']:
                    return {
                        'id': result['id'],
                        'name': result['name'],
                        'role_id': result['role_id']
                    }
                
                return None
                
        except Exception as e:
            print(f"❌ Error getting user position: {e}")
            return None
    
    async def update_position_subdivision_by_role_id(self, user_discord_id: int, position_role_id: int, 
                                                     dept_code: str, moderator_discord_id: int) -> bool:
        """
        Update position_subdivision_id in employees table based on Discord role ID.
        Used for department applications where positions are assigned automatically.
        
        Args:
            user_discord_id: Discord user ID
            position_role_id: Discord role ID of the position
            dept_code: Department code (УВП, ССО, etc.)
            moderator_discord_id: Discord ID of the moderator who approved
            
        Returns:
            bool: Success status
        """
        try:
            from utils.database_manager import SubdivisionMapper
            from datetime import datetime, timezone, timedelta
            import json
            
            # Initialize subdivision mapper to get subdivision_id
            subdivision_mapper = SubdivisionMapper()
            subdivision_id = await subdivision_mapper.get_subdivision_id(dept_code)
            
            if not subdivision_id:
                print(f"⚠️ Could not find subdivision_id for department {dept_code}")
                return False
            
            with get_db_cursor() as cursor:
                # Get personnel_id
                cursor.execute("SELECT id FROM personnel WHERE discord_id = %s AND is_dismissal = false;", (user_discord_id,))
                personnel_result = cursor.fetchone()
                if not personnel_result:
                    print(f"⚠️ Could not find personnel record for user {user_discord_id}")
                    return False
                personnel_id = personnel_result['id']
                
                # Find position_subdivision_id by matching Discord role ID
                cursor.execute("""
                    SELECT ps.id, p.name as position_name, p.role_id
                    FROM position_subdivision ps
                    JOIN positions p ON ps.position_id = p.id
                    WHERE ps.subdivision_id = %s AND p.role_id = %s
                    LIMIT 1;
                """, (subdivision_id, position_role_id))
                
                ps_result = cursor.fetchone()
                if not ps_result:
                    print(f"⚠️ Could not find position_subdivision for role ID {position_role_id} in department {dept_code}")
                    return False
                
                position_subdivision_id = ps_result['id']
                position_name = ps_result['position_name']
                
                # Update employee with new position
                cursor.execute("""
                    UPDATE employees 
                    SET position_subdivision_id = %s
                    WHERE personnel_id = %s;
                """, (position_subdivision_id, personnel_id))
                
                # Get moderator personnel ID for history
                cursor.execute("SELECT id FROM personnel WHERE discord_id = %s;", (moderator_discord_id,))
                moderator_result = cursor.fetchone()
                if not moderator_result:
                    print(f"⚠️ Could not find moderator personnel record for {moderator_discord_id}")
                    return False
                moderator_personnel_id = moderator_result['id']
                
                # Create history record for position assignment (action_id = 5)
                changes = {
                    "rank": {"new": None, "previous": None},
                    "position": {"new": position_name, "previous": None},
                    "subdivision": {"new": None, "previous": None}
                }
                
                cursor.execute("""
                    INSERT INTO history (personnel_id, action_id, performed_by, details, changes, action_date)
                    VALUES (%s, %s, %s, %s, %s, %s);
                """, (
                    personnel_id,
                    5,  # Position assignment action_id
                    moderator_personnel_id,
                    None,
                    json.dumps(changes, ensure_ascii=False),
                    datetime.now(timezone(timedelta(hours=3)))  # Moscow time
                ))
                
                print(f"✅ Updated position_subdivision_id to {position_subdivision_id} ({position_name}) for user {user_discord_id} in department {dept_code}")
                return True
                
        except Exception as e:
            print(f"❌ Error updating position in database for user {user_discord_id}: {e}")
            return False

    async def smart_update_user_department_roles(self, guild: discord.Guild, user: discord.Member, dept_key: str, old_dept_key: str = None):
        """
        Update user roles based on department change
        
        Args:
            guild: Discord guild
            user: Discord user member
            dept_key: Department config key (e.g., 'genshtab', 'УВП')
            old_dept_key: Previous department config key (optional, will be auto-detected if not provided)
        """
        try:
            print(f"🔄 Updating department roles for {user.display_name}: {old_dept_key} → {dept_key}")
            
            # Import config manager to get department roles
            from ..config_manager import load_config
            config = load_config()
            
            # Get department configs
            departments = config.get('departments', {})
            new_dept_config = departments.get(dept_key, {})
            
            role_changes = []
            
            # If old_dept_key not provided, try to detect it from user's Discord roles
            if old_dept_key is None:
                try:
                    # Detect old department by checking user's Discord roles against config
                    old_dept_key = self._detect_department_by_user_roles(user, departments)
                    if old_dept_key:
                        print(f"✅ Auto-detected old department for {user.display_name}: {old_dept_key}")
                    else:
                        print(f"ℹ️ Could not auto-detect old department for {user.display_name} (no matching roles found)")
                except Exception as e:
                    print(f"⚠️ Could not auto-detect old department: {e}")
            
            # Remove old department roles if old_dept_key is known
            if old_dept_key and old_dept_key != dept_key:
                old_dept_config = departments.get(old_dept_key, {})
                
                # Get roles from old department config
                old_roles_to_remove = old_dept_config.get('roles', {}).get('remove', [])
                old_role_id = old_dept_config.get('role_id')
                
                # Collect all roles to remove from old department
                roles_to_remove_from_old = old_roles_to_remove.copy()
                if old_role_id:
                    old_role = guild.get_role(old_role_id)
                    if old_role and old_role.name not in roles_to_remove_from_old:
                        roles_to_remove_from_old.append(old_role.name)
                
                # Remove old department roles
                for role_name in roles_to_remove_from_old:
                    role = discord.utils.get(guild.roles, name=role_name)
                    if role and role in user.roles:
                        try:
                            await user.remove_roles(role)
                            role_changes.append(f"Removed {role_name} (old dept)")
                            print(f"✅ Removed old department role {role_name} from {user.display_name}")
                        except Exception as e:
                            print(f"⚠️ Failed to remove old role {role_name}: {e}")
            
            # Get roles to add/remove for new department
            roles_to_add = new_dept_config.get('roles', {}).get('add', [])
            roles_to_remove = new_dept_config.get('roles', {}).get('remove', [])
            
            # If no roles structure, use role_id from PostgreSQL
            if not roles_to_add and not roles_to_remove:
                role_id = new_dept_config.get('role_id')
                if role_id:
                    # Get role name from guild roles
                    role = guild.get_role(role_id)
                    if role:
                        roles_to_add = [role.name]
                        print(f"ℹ️ Using role_id for department {dept_key}: {role.name}")
            
            # Remove roles specified in new department config (cleanup roles)
            for role_name in roles_to_remove:
                role = discord.utils.get(guild.roles, name=role_name)
                if role and role in user.roles:
                    try:
                        await user.remove_roles(role)
                        role_changes.append(f"Removed {role_name}")
                        print(f"✅ Removed cleanup role {role_name} from {user.display_name}")
                    except Exception as e:
                        print(f"⚠️ Failed to remove role {role_name}: {e}")
            
            # Add new department roles
            for role_name in roles_to_add:
                role = discord.utils.get(guild.roles, name=role_name)
                if role and role not in user.roles:
                    try:
                        await user.add_roles(role)
                        role_changes.append(f"Added {role_name}")
                        print(f"✅ Added role {role_name} to {user.display_name}")
                    except Exception as e:
                        print(f"⚠️ Failed to add role {role_name}: {e}")
                elif not role:
                    print(f"⚠️ Role '{role_name}' not found in guild")
            
            if role_changes:
                print(f"📋 Department role changes for {user.display_name}: {', '.join(role_changes)}")
            else:
                print(f"ℹ️ No department role changes needed for {user.display_name}")
                
        except Exception as e:
            print(f"❌ Error updating department roles for {user.display_name}: {e}")


    def _detect_department_by_user_roles(self, user: discord.Member, departments: Dict) -> Optional[str]:
        """
        Detect user's current department by checking their Discord roles against config.

        Args:
            user: Discord user member
            departments: Departments config from config.json

        Returns:
            Department key (e.g., 'УВП', 'ССО') or None if not found
        """
        try:
            # Get user's role IDs for faster lookup
            user_role_ids = {role.id for role in user.roles}

            # Check each department's role_id (PostgreSQL-based)
            for dept_key, dept_config in departments.items():
                role_id = dept_config.get('role_id')

                # Check if user has this department's role_id
                if role_id and role_id in user_role_ids:
                    return dept_key

            return None

        except Exception as e:
            print(f"Error detecting department by user roles: {e}")
            return None


# Global instance
position_manager = PositionManager()