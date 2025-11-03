"""
New Position Service Layer
Новый слой сервисов для управления должностями с правильной схемой БД
"""

import discord
from typing import Optional, Dict, Any, List, Tuple, Set
from utils.postgresql_pool import get_db_cursor
from utils.message_manager import get_role_reason, get_moderator_display_name
from utils.database_manager.position_validator import PositionValidator

class PositionService:
    """New position service with proper database schema integration"""

    def __init__(self):
        self._position_cache = {}
        self._cache_timestamp = 0
        self._cache_ttl = 300  # 5 minutes
        
        # New cache for position roles mapping
        self._position_roles_cache = None
        self._roles_cache_timestamp = 0
        self._roles_cache_ttl = 300  # 5 minutes
        self._cache_stats = {
            'hits': 0,
            'misses': 0,
            'refreshes': 0
        }

    def invalidate_cache(self):
        """Invalidate position cache"""
        self._position_cache = {}
        self._cache_timestamp = 0
        print("🗑️ Position service cache invalidated")
    
    def invalidate_roles_cache(self):
        """Invalidate position roles cache"""
        self._position_roles_cache = None
        self._roles_cache_timestamp = 0
        print("🗑️ Position roles cache invalidated")
    
    def get_cache_stats(self):
        """Get cache statistics"""
        return {
            'hits': self._cache_stats['hits'],
            'misses': self._cache_stats['misses'],
            'refreshes': self._cache_stats['refreshes'],
            'ttl_seconds': self._roles_cache_ttl,
            'is_cached': self._position_roles_cache is not None
        }
    
    def _get_position_roles_cached(self):
        """Get position roles with caching"""
        import time
        current_time = time.time()
        
        if (self._position_roles_cache is None or 
            current_time - self._roles_cache_timestamp > self._roles_cache_ttl):
            
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
                    self._roles_cache_timestamp = current_time
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

    def get_positions_for_subdivision(self, subdivision_id: int) -> List[Dict[str, Any]]:
        """
        Get all positions linked to a specific subdivision

        Args:
            subdivision_id: Subdivision ID

        Returns:
            List of position dictionaries with role info
        """
        try:
            with get_db_cursor() as cursor:
                cursor.execute("""
                    SELECT
                        p.id,
                        p.name,
                        p.role_id,
                        ps.id as position_subdivision_id
                    FROM positions p
                    JOIN position_subdivision ps ON p.id = ps.position_id
                    WHERE ps.subdivision_id = %s
                    ORDER BY p.name
                """, (subdivision_id,))

                result = cursor.fetchall()
                return [dict(row) for row in result] if result else []

        except Exception as e:
            print(f"❌ Error getting positions for subdivision {subdivision_id}: {e}")
            return []

    def get_all_positions_with_subdivisions(self) -> List[Dict[str, Any]]:
        """
        Get all positions with their subdivision links

        Returns:
            List of positions with subdivision info
        """
        try:
            with get_db_cursor() as cursor:
                cursor.execute("""
                    SELECT
                        p.id,
                        p.name,
                        p.role_id,
                        s.id as subdivision_id,
                        s.name as subdivision_name,
                        s.abbreviation as subdivision_abbr,
                        ps.id as position_subdivision_id
                    FROM positions p
                    JOIN position_subdivision ps ON p.id = ps.position_id
                    JOIN subdivisions s ON ps.subdivision_id = s.id
                    ORDER BY s.name, p.name
                """)

                result = cursor.fetchall()
                return [dict(row) for row in result] if result else []

        except Exception as e:
            print(f"❌ Error getting all positions with subdivisions: {e}")
            return []

    def add_position_to_subdivision(self, position_name: str, subdivision_id: int,
                                  role_id: Optional[int] = None) -> Tuple[bool, str]:
        """
        Add new position linked to specific subdivision

        Args:
            position_name: Name of the position
            subdivision_id: Subdivision ID to link to
            role_id: Optional Discord role ID

        Returns:
            Tuple[bool, str]: (success, message)
        """
        # Validate position name
        is_valid, error_msg = PositionValidator.validate_position_name(position_name)
        if not is_valid:
            return False, error_msg

        # Validate subdivision exists
        if not self._subdivision_exists(subdivision_id):
            return False, "Подразделение не найдено"

        # Validate role if provided
        if role_id:
            # We'll validate role when we have guild context
            pass

        try:
            with get_db_cursor() as cursor:
                # Check if position with this name already exists in this subdivision
                cursor.execute("""
                    SELECT p.id FROM positions p
                    JOIN position_subdivision ps ON p.id = ps.position_id
                    WHERE p.name = %s AND ps.subdivision_id = %s
                """, (position_name, subdivision_id))

                if cursor.fetchone():
                    return False, f"Должность '{position_name}' уже существует в этом подразделении"

                # Get next position ID
                cursor.execute("SELECT MAX(id) FROM positions")
                max_id_result = cursor.fetchone()
                max_id = max_id_result['max'] if max_id_result and max_id_result['max'] else 0
                next_id = max_id + 1

                # Add position
                cursor.execute(
                    "INSERT INTO positions (id, name, role_id) VALUES (%s, %s, %s)",
                    (next_id, position_name, role_id)
                )

                # Link to subdivision
                cursor.execute(
                    "INSERT INTO position_subdivision (position_id, subdivision_id) VALUES (%s, %s)",
                    (next_id, subdivision_id)
                )

                self.invalidate_cache()
                self.invalidate_roles_cache()

                message = f"Должность '{position_name}' добавлена (ID: {next_id})"
                if role_id:
                    message += f" с ролью Discord ID: {role_id}"

                print(f"✅ {message}")
                return True, message

        except Exception as e:
            error_msg = f"Ошибка при добавлении должности: {e}"
            print(f"❌ {error_msg}")
            return False, error_msg

    def update_position_role(self, position_id: int, role_id: Optional[int],
                           guild: discord.Guild = None) -> Tuple[bool, str]:
        """
        Update Discord role for position

        Args:
            position_id: Position ID
            role_id: New Discord role ID (None to remove)
            guild: Discord guild for role validation

        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            with get_db_cursor() as cursor:
                # Check if position exists
                cursor.execute("SELECT name FROM positions WHERE id = %s", (position_id,))
                position = cursor.fetchone()

                if not position:
                    return False, "Должность не найдена"

                # Validate role if provided and guild available
                if role_id and guild:
                    is_valid, role_name_or_error = PositionValidator.validate_discord_role(role_id, guild)
                    if not is_valid:
                        return False, role_name_or_error

                # Check if role is already used by another position
                if role_id:
                    cursor.execute(
                        "SELECT id, name FROM positions WHERE role_id = %s AND id != %s",
                        (role_id, position_id)
                    )
                    existing = cursor.fetchone()
                    if existing:
                        return False, f"Роль уже используется должностью '{existing['name']}'"

                # Update role
                cursor.execute("UPDATE positions SET role_id = %s WHERE id = %s", (role_id, position_id))

                self.invalidate_cache()
                self.invalidate_roles_cache()

                action = "назначена" if role_id else "удалена"
                message = f"Роль {action} для должности '{position['name']}'"
                return True, message

        except Exception as e:
            return False, f"Ошибка: {e}"

    def remove_position(self, position_id: int) -> Tuple[bool, str]:
        """
        Remove position and all its links (with dependency checks)

        Args:
            position_id: Position ID to remove

        Returns:
            Tuple[bool, str]: (success, message)
        """
        # Check dependencies
        dependencies = PositionValidator.check_position_dependencies(position_id)

        if dependencies['has_dependencies']:
            return False, (
                f"Невозможно удалить должность. Она используется:\n"
                f"• {dependencies['active_employees']} активных сотрудников\n"
                f"• {dependencies['subdivisions']} подразделений"
            )

        try:
            with get_db_cursor() as cursor:
                # Get position name
                cursor.execute("SELECT name FROM positions WHERE id = %s", (position_id,))
                position = cursor.fetchone()

                if not position:
                    return False, "Должность не найдена"

                position_name = position['name']

                # Remove from position_subdivision first (FK constraint)
                cursor.execute("DELETE FROM position_subdivision WHERE position_id = %s", (position_id,))

                # Remove position
                cursor.execute("DELETE FROM positions WHERE id = %s", (position_id,))

                self.invalidate_cache()
                self.invalidate_roles_cache()

                message = f"Должность '{position_name}' удалена"
                print(f"✅ {message}")
                return True, message

        except Exception as e:
            return False, f"Ошибка при удалении должности: {e}"

    def update_position_name(self, position_id: int, new_name: str) -> Tuple[bool, str]:
        """
        Update position name

        Args:
            position_id: Position ID
            new_name: New position name

        Returns:
            Tuple[bool, str]: (success, message)
        """
        # Validate new name
        is_valid, error_msg = PositionValidator.validate_position_name(new_name, position_id)
        if not is_valid:
            return False, error_msg

        try:
            with get_db_cursor() as cursor:
                # Get current name
                cursor.execute("SELECT name FROM positions WHERE id = %s", (position_id,))
                position = cursor.fetchone()

                if not position:
                    return False, "Должность не найдена"

                old_name = position['name']

                # Update name
                cursor.execute("UPDATE positions SET name = %s WHERE id = %s", (new_name, position_id))

                self.invalidate_cache()
                self.invalidate_roles_cache()

                message = f"Название должности изменено: '{old_name}' → '{new_name}'"
                return True, message

        except Exception as e:
            return False, f"Ошибка при изменении названия: {e}"

    def _subdivision_exists(self, subdivision_id: int) -> bool:
        """Check if subdivision exists"""
        try:
            with get_db_cursor() as cursor:
                cursor.execute("SELECT id FROM subdivisions WHERE id = %s", (subdivision_id,))
                return cursor.fetchone() is not None
        except Exception:
            return False

    async def assign_position_to_user(self, user: discord.Member, position_id: int,
                                    moderator=None) -> Tuple[bool, str]:
        """
        Assign position to user (update employee record)

        Args:
            user: Discord user
            position_id: Position ID to assign
            moderator: Moderator who performed action

        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            moderator_display = await get_moderator_display_name(moderator)

            # Get position data
            positions = self.get_all_positions_with_subdivisions()
            position_data = next((p for p in positions if p['id'] == position_id), None)

            if not position_data:
                return False, "Должность не найдена"

            # Get personnel ID
            personnel_id = await self._get_personnel_id(user.id)
            if not personnel_id:
                return False, "Пользователь не найден в базе данных"

            # Get current employee record
            current_employee = await self._get_current_employee_record(personnel_id)

            with get_db_cursor() as cursor:
                if current_employee:
                    # Update existing employee record
                    cursor.execute("""
                        UPDATE employees
                        SET position_subdivision_id = %s
                        WHERE id = %s
                    """, (position_data['position_subdivision_id'], current_employee['id']))
                else:
                    # Create new employee record (need rank - get from somewhere?)
                    # This is complex - might need additional parameters
                    return False, "Пользователь не имеет записи сотрудника. Сначала нужно назначить звание."

                # Use smart role management instead of manual role assignment
                from utils.role_utils import role_utils
                await role_utils.smart_update_user_position_roles(user.guild, user, position_id, moderator)

                message = f"Должность '{position_data['name']}' назначена пользователю {user.display_name}"
                return True, message

        except Exception as e:
            return False, f"Ошибка при назначении должности: {e}"

    async def _get_personnel_id(self, discord_id: int) -> Optional[int]:
        """Get personnel ID by Discord ID"""
        try:
            with get_db_cursor() as cursor:
                cursor.execute("SELECT id FROM personnel WHERE discord_id = %s", (discord_id,))
                result = cursor.fetchone()
                return result['id'] if result else None
        except Exception:
            return None

    async def _get_current_employee_record(self, personnel_id: int) -> Optional[Dict[str, Any]]:
        """Get current employee record for personnel"""
        try:
            with get_db_cursor() as cursor:
                cursor.execute("""
                    SELECT id, rank_id, subdivision_id, position_subdivision_id
                    FROM employees
                    WHERE personnel_id = %s
                """, (personnel_id,))
                result = cursor.fetchone()
                return dict(result) if result else None
        except Exception:
            return None

    def get_position_by_id(self, position_id: int) -> Optional[Dict[str, Any]]:
        """
        Get position data by ID
        
        Args:
            position_id: Position ID
            
        Returns:
            Position data dict or None
        """
        try:
            with get_db_cursor() as cursor:
                cursor.execute("""
                    SELECT p.id, p.name, p.role_id, s.name as subdivision_name, s.abbreviation as subdivision_abbr
                    FROM positions p
                    JOIN position_subdivision ps ON p.id = ps.position_id
                    JOIN subdivisions s ON ps.subdivision_id = s.id
                    WHERE p.id = %s
                    LIMIT 1
                """, (position_id,))
                
                result = cursor.fetchone()
                return dict(result) if result else None
                
        except Exception as e:
            print(f"❌ Error getting position by ID {position_id}: {e}")
            return None

    def get_user_position_from_db(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get user's current position from employees table
        
        Args:
            user_id: Discord user ID
            
        Returns:
            Position data dict or None
        """
        try:
            with get_db_cursor() as cursor:
                cursor.execute("""
                    SELECT p.id, p.name, p.role_id, s.name as subdivision_name, s.abbreviation as subdivision_abbr
                    FROM employees e
                    JOIN position_subdivision ps ON e.position_subdivision_id = ps.id
                    JOIN positions p ON ps.position_id = p.id
                    JOIN subdivisions s ON ps.subdivision_id = s.id
                    JOIN personnel pr ON e.personnel_id = pr.id
                    WHERE pr.discord_id = %s AND pr.is_dismissal = false
                    LIMIT 1
                """, (user_id,))
                
                result = cursor.fetchone()
                if result and result['id']:
                    return {
                        'id': result['id'],
                        'name': result['name'],
                        'role_id': result['role_id'],
                        'subdivision_name': result['subdivision_name'],
                        'subdivision_abbr': result['subdivision_abbr']
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

    def get_position_roles_cache(self):
        """
        Get position roles cache data for external use
        
        Returns:
            dict: Cache data with role_to_position and position_to_role mappings
        """
        return self._get_position_roles_cached()

# Global instance
position_service = PositionService()