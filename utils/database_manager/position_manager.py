"""
Position Management System for Discord Bot
Simple version: positions with Discord roles only
"""

import discord
from typing import Optional, Dict, List, Any, Tuple, Set
from utils.postgresql_pool import get_db_cursor
from utils.message_manager import get_role_reason, get_moderator_display_name

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
    
    def get_position_by_id(self, position_id: int) -> Optional[Dict[str, Any]]:
        """Get position information by ID from database"""
        try:
            with get_db_cursor() as cursor:
                cursor.execute("SELECT id, name, role_id FROM positions WHERE id = %s", (position_id,))
                result = cursor.fetchone()
                
                return dict(result) if result else None
                
        except Exception as e:
            print(f"❌ Error getting position {position_id}: {e}")
            return None
    
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
                                             new_position_id: Optional[int], moderator=None) -> bool:
        """Smart update - automatically detect current position roles and remove them (optimized)"""
        try:
            # Get moderator display name for audit reasons
            moderator_display = await get_moderator_display_name(moderator)
            
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
                    reason = get_role_reason(guild.id, "role_removal.position_change", "Смена должности: снята роль").format(moderator=moderator_display)
                    await user.remove_roles(*roles_to_remove, reason=reason)
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
                            # Get position name from database
                            position_data = self.get_position_by_id(new_position_id)
                            position_name = position_data['name'] if position_data else f"Position ID {new_position_id}"
                            
                            reason = get_role_reason(guild.id, "position_assignment.assigned", "Назначение должности").format(position=position_name)
                            await user.add_roles(new_role, reason=reason)
                            role_changes.append(f"+{position_name}")
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
            from utils.config_manager import load_config
            from utils.postgresql_pool import get_db_cursor
            from datetime import datetime, timezone, timedelta
            import json
            
            # Get subdivision_id directly from config and DB
            config = load_config()
            dept_config = config.get('departments', {}).get(dept_code, {})
            role_id = dept_config.get('role_id')
            
            if not role_id:
                print(f"⚠️ No role_id found for department {dept_code}")
                return False
            
            subdivision_id = None
            try:
                with get_db_cursor() as cursor:
                    cursor.execute("SELECT id FROM subdivisions WHERE role_id = %s", (role_id,))
                    result = cursor.fetchone()
                    if result:
                        subdivision_id = result['id']
            except Exception as e:
                print(f"⚠️ Error getting subdivision_id: {e}")
                return False
            
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

        DEPRECATED: Use UnifiedRoleManager.smart_scan_and_update_roles() instead
        This method is kept for backward compatibility.
        """
        try:
            print(f"🔄 Updating department roles for {user.display_name}: {old_dept_key} → {dept_key}")

            # Import unified role manager
            from .unified_role_manager import unified_role_manager

            # Get target department role IDs
            target_role_ids = await self._get_department_role_ids_for_key(dept_key)

            # Use unified role manager
            result = await unified_role_manager.smart_scan_and_update_roles(
                guild=guild,
                user=user,
                role_type='department',
                target_role_ids=target_role_ids,
                reason_template="department_change"
            )

            # Log results
            if result['success']:
                if result['added'] or result['removed']:
                    print(f"✅ Department roles updated: +{len(result['added'])}, -{len(result['removed'])}")
                else:
                    print(f"ℹ️ No department role changes needed")
            else:
                print(f"❌ Failed to update department roles: {result.get('error', 'Unknown error')}")

            return result['success']

        except Exception as e:
            print(f"❌ Error in department role update: {e}")
            return False

    async def _get_department_role_ids_for_key(self, dept_key: str) -> Set[int]:
        """Get department role IDs for a specific department key"""
        try:
            from utils.config_manager import load_config
            from utils.postgresql_pool import get_db_cursor
            
            config = load_config()
            dept_config = config.get('departments', {}).get(dept_key, {})
            role_id = dept_config.get('role_id')
            
            if role_id:
                return {role_id}
            else:
                print(f"⚠️ No role found for department key: {dept_key}")
                return set()

        except Exception as e:
            print(f"❌ Error getting department role IDs: {e}")
            return set()

        except Exception as e:
            print(f"❌ Error getting department role IDs for key '{dept_key}': {e}")
            return set()


    async def _detect_user_department(self, user: discord.Member) -> Optional[str]:
        """
        Detect user's current department by checking their Discord roles against database subdivision.role_id.

        Args:
            user: Discord user member

        Returns:
            Department key (e.g., 'УВП', 'ССО') or None if not found
        """
        try:
            # Get user's role IDs for faster lookup
            user_role_ids = {role.id for role in user.roles}

            # Get all department role_ids from config
            from utils.config_manager import load_config
            config = load_config()
            departments = config.get('departments', {})

            # Check each department's role_id against user's roles
            for dept_key, dept_config in departments.items():
                role_id = dept_config.get('role_id')
                if role_id and role_id in user_role_ids:
                    return dept_key

            return None

        except Exception as e:
            print(f"Error detecting department by user roles: {e}")
            return None


# Global instance
position_manager = PositionManager()