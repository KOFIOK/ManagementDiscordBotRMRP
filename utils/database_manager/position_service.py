"""
New Position Service Layer
Новый слой сервисов для управления должностями с правильной схемой БД
"""

import discord
from typing import Optional, Dict, Any, List, Tuple, Set
from utils.postgresql_pool import get_db_cursor
from utils.message_manager import get_role_reason, get_moderator_display_name
from utils.logging_setup import get_logger

# Initialize logger
logger = get_logger(__name__)

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
        logger.info("Position service cache invalidated")
    
    def invalidate_roles_cache(self):
        """Invalidate position roles cache"""
        self._position_roles_cache = None
        self._roles_cache_timestamp = 0
        logger.info("Position roles cache invalidated")
    
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
                    logger.info(f"Refreshed position roles cache: {len(role_to_position)} roles")
            except Exception as e:
                logger.warning("Failed to refresh position roles cache: %s", e)
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
            logger.warning("Error getting positions for subdivision %s: %s", subdivision_id, e)
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
            logger.warning("Error getting all positions with subdivisions: %s", e)
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
        is_valid, error_msg = self.validate_position_name(position_name)
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
                    message += f"с ролью Discord ID: {role_id}"

                logger.info("%s", message)
                return True, message

        except Exception as e:
            error_msg = f"Ошибка при добавлении должности: {e}"
            logger.warning("%s", error_msg)
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
                    is_valid, role_name_or_error = self.validate_discord_role(role_id, guild)
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

    def remove_position(self, position_id: int, force: bool = False) -> Tuple[bool, str]:
        """
        Remove position and all its links

        Args:
            position_id: Position ID to remove
            force: If True, allow removal even with active employees (will clear their position assignments)

        Returns:
            Tuple[bool, str]: (success, message)
        """
        # Check dependencies
        dependencies = self.check_position_dependencies(position_id)

        warning_message = ""
        if dependencies['active_employees'] > 0:
            warning_message = f"⚠️ Внимание: {dependencies['active_employees']} активных сотрудников имеют эту должность. Их назначения будут очищены.\n\n"

        if dependencies['has_dependencies'] and not force:
            return False, (
                f"{warning_message}Невозможно удалить должность. Она используется:\n"
                f"• {dependencies['active_employees']} активных сотрудников\n"
                f"• {dependencies['subdivisions']} подразделений\n\n"
                f"Используйте force=True для принудительного удаления."
            )

        try:
            with get_db_cursor() as cursor:
                # Get position name
                cursor.execute("SELECT name FROM positions WHERE id = %s", (position_id,))
                position = cursor.fetchone()

                if not position:
                    return False, "Должность не найдена"

                position_name = position['name']

                # If there are active employees, clear their position assignments
                if dependencies['active_employees'] > 0:
                    # Find all position_subdivision_ids for this position
                    cursor.execute("SELECT id FROM position_subdivision WHERE position_id = %s", (position_id,))
                    ps_ids = [row['id'] for row in cursor.fetchall()]

                    if ps_ids:
                        # Clear position assignments for employees
                        placeholders = ','.join(['%s'] * len(ps_ids))
                        cursor.execute(
                            f"UPDATE employees SET position_subdivision_id = NULL WHERE position_subdivision_id IN ({placeholders})",
                            ps_ids
                        )
                        logger.info(f" Cleared position assignments for {dependencies['active_employees']} employees")

                # Remove from position_subdivision first (FK constraint)
                cursor.execute("DELETE FROM position_subdivision WHERE position_id = %s", (position_id,))

                # Remove position
                cursor.execute("DELETE FROM positions WHERE id = %s", (position_id,))

                self.invalidate_cache()
                self.invalidate_roles_cache()

                message = f"Должность '{position_name}' удалена"
                if dependencies['active_employees'] > 0:
                    message += f" (очищены назначения {dependencies['active_employees']} сотрудников)"

                logger.info("%s", message)
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
        is_valid, error_msg = self.validate_position_name(new_name, position_id)
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

    def update_position_role(self, position_id: int, role_id: Optional[int], guild=None) -> Tuple[bool, str]:
        """
        Update position Discord role

        Args:
            position_id: Position ID
            role_id: New Discord role ID (None to remove)
            guild: Discord guild for validation

        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            # Validate role if provided and guild available
            if role_id and guild:
                is_valid, role_name_or_error = self.validate_discord_role(role_id, guild)
                if not is_valid:
                    return False, f"Недопустимая роль: {role_name_or_error}"

            with get_db_cursor() as cursor:
                # Get current role
                cursor.execute("SELECT role_id, name FROM positions WHERE id = %s", (position_id,))
                position = cursor.fetchone()

                if not position:
                    return False, "Должность не найдена"

                old_role_id = position['role_id']
                position_name = position['name']

                # Update role
                cursor.execute("UPDATE positions SET role_id = %s WHERE id = %s", (role_id, position_id))

                self.invalidate_cache()
                self.invalidate_roles_cache()

                if role_id:
                    if old_role_id:
                        message = f"Роль должности '{position_name}' изменена"
                    else:
                        message = f"Роль назначена должности '{position_name}'"
                else:
                    message = f"Роль удалена у должности '{position_name}'"

                return True, message

        except Exception as e:
            return False, f"Ошибка при изменении роли: {e}"

    def update_position_subdivision(self, position_id: int, new_subdivision_id: int) -> Tuple[bool, str]:
        """
        Update position subdivision assignment

        Args:
            position_id: Position ID
            new_subdivision_id: New subdivision ID

        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            # Validate new subdivision exists
            if not self._subdivision_exists(new_subdivision_id):
                return False, "Новое подразделение не найдено"

            with get_db_cursor() as cursor:
                # Get current subdivision
                cursor.execute("""
                    SELECT s.name as current_subdivision, p.name as position_name
                    FROM position_subdivision ps
                    JOIN subdivisions s ON ps.subdivision_id = s.id
                    JOIN positions p ON ps.position_id = p.id
                    WHERE ps.position_id = %s
                    LIMIT 1
                """, (position_id,))

                current = cursor.fetchone()
                if not current:
                    return False, "Должность не найдена или не привязана к подразделению"

                current_subdivision_name = current['current_subdivision']
                position_name = current['position_name']

                # Get new subdivision name
                cursor.execute("SELECT name FROM subdivisions WHERE id = %s", (new_subdivision_id,))
                new_subdivision = cursor.fetchone()
                if not new_subdivision:
                    return False, "Новое подразделение не найдено"

                new_subdivision_name = new_subdivision['name']

                # Update subdivision assignment
                cursor.execute(
                    "UPDATE position_subdivision SET subdivision_id = %s WHERE position_id = %s",
                    (new_subdivision_id, position_id)
                )

                self.invalidate_cache()

                message = f"Должность '{position_name}' перемещена из '{current_subdivision_name}' в '{new_subdivision_name}'"
                return True, message

        except Exception as e:
            return False, f"Ошибка при изменении подразделения: {e}"

    def update_position(self, position_id: int, name: Optional[str] = None,
                       role_id: Optional[int] = None, subdivision_id: Optional[int] = None) -> Tuple[bool, str]:
        """
        Update position with multiple fields

        Args:
            position_id: Position ID
            name: New position name (optional)
            role_id: New Discord role ID (optional)
            subdivision_id: New subdivision ID (optional)

        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            changes = []
            success_messages = []

            # Update name if provided
            if name is not None:
                name_success, name_message = self.update_position_name(position_id, name)
                if not name_success:
                    return False, name_message
                success_messages.append(name_message)
                changes.append("название")

            # Update role if provided
            if role_id is not None:
                role_success, role_message = self.update_position_role(position_id, role_id)
                if not role_success:
                    return False, role_message
                success_messages.append(role_message)
                changes.append("роль")

            # Update subdivision if provided
            if subdivision_id is not None:
                sub_success, sub_message = self.update_position_subdivision(position_id, subdivision_id)
                if not sub_success:
                    return False, sub_message
                success_messages.append(sub_message)
                changes.append("подразделение")

            if not changes:
                return False, "Не указано никаких изменений"

            message = f"Должность обновлена ({', '.join(changes)})"
            return True, message

        except Exception as e:
            return False, f"Ошибка при обновлении должности: {e}"

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
            logger.warning("Error getting position by ID %s: %s", position_id, e)
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
            logger.warning("Error getting user position: %s", e)
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
                logger.info("No role_id found for department %s", dept_code)
                return False
            
            subdivision_id = None
            try:
                with get_db_cursor() as cursor:
                    cursor.execute("SELECT id FROM subdivisions WHERE role_id = %s", (role_id,))
                    result = cursor.fetchone()
                    if result:
                        subdivision_id = result['id']
            except Exception as e:
                logger.warning("Error getting subdivision_id: %s", e)
                return False
            
            if not subdivision_id:
                logger.info("Could not find subdivision_id for department %s", dept_code)
                return False
            
            with get_db_cursor() as cursor:
                # Get personnel_id
                cursor.execute("SELECT id FROM personnel WHERE discord_id = %s AND is_dismissal = false;", (user_discord_id,))
                personnel_result = cursor.fetchone()
                if not personnel_result:
                    logger.info("Could not find personnel record for user %s", user_discord_id)
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
                    logger.info("Could not find position_subdivision for role ID %s in department %s", position_role_id, dept_code)
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
                    logger.info("Could not find moderator personnel record for %s", moderator_discord_id)
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
                
                logger.info("Updated position_subdivision_id to %s (%s) for user %s in department %s", position_subdivision_id, position_name, user_discord_id, dept_code)
                return True
                
        except Exception as e:
            logger.warning("Error updating position in database for user %s: %s", user_discord_id, e)
            return False

    def get_position_roles_cache(self):
        """
        Get position roles cache data for external use
        
        Returns:
            dict: Cache data with role_to_position and position_to_role mappings
        """
        return self._get_position_roles_cached()

    # Validation methods (moved from PositionValidator)
    def validate_position_name(self, name: str, exclude_id: Optional[int] = None) -> Tuple[bool, str]:
        """
        Validate position name uniqueness

        Args:
            name: Position name to validate
            exclude_id: Position ID to exclude from check (for updates)

        Returns:
            Tuple[bool, str]: (is_valid, error_message)
        """
        if not name or not name.strip():
            return False, "Название должности не может быть пустым"

        name = name.strip()

        if len(name) > 200:
            return False, "Название должности не может превышать 200 символов"

        try:
            with get_db_cursor() as cursor:
                if exclude_id:
                    cursor.execute(
                        "SELECT id FROM positions WHERE name = %s AND id != %s",
                        (name, exclude_id)
                    )
                else:
                    cursor.execute("SELECT id FROM positions WHERE name = %s", (name,))

                existing = cursor.fetchone()
                if existing:
                    return False, f"Должность с названием '{name}' уже существует"

                return True, ""

        except Exception as e:
            return False, f"Ошибка валидации: {e}"

    def check_position_dependencies(self, position_id: int) -> Dict[str, Any]:
        """
        Check position dependencies before deletion

        Args:
            position_id: Position ID to check

        Returns:
            Dict with dependency information
        """
        try:
            with get_db_cursor() as cursor:
                dependencies = {
                    'active_employees': 0,
                    'subdivisions': 0,
                    'has_dependencies': False
                }

                # Check active employees with this position
                cursor.execute("""
                    SELECT COUNT(*) as count
                    FROM employees e
                    JOIN position_subdivision ps ON e.position_subdivision_id = ps.id
                    WHERE ps.position_id = %s
                """, (position_id,))

                result = cursor.fetchone()
                dependencies['active_employees'] = result['count'] if result else 0

                # Check subdivisions using this position
                cursor.execute("""
                    SELECT COUNT(DISTINCT subdivision_id) as count
                    FROM position_subdivision
                    WHERE position_id = %s
                """, (position_id,))

                result = cursor.fetchone()
                dependencies['subdivisions'] = result['count'] if result else 0

                # Determine if has dependencies
                dependencies['has_dependencies'] = (
                    dependencies['active_employees'] > 0 or
                    dependencies['subdivisions'] > 0
                )

                return dependencies

        except Exception as e:
            logger.warning("Error checking dependencies: %s", e)
            return {
                'active_employees': 0,
                'subdivisions': 0,
                'has_dependencies': False,
                'error': str(e)
            }

    def validate_discord_role(self, role_id: int, guild) -> Tuple[bool, str]:
        """
        Validate Discord role exists and is accessible

        Args:
            role_id: Discord role ID
            guild: Discord guild object

        Returns:
            Tuple[bool, str]: (is_valid, role_name_or_error)
        """
        try:
            if not guild:
                return False, "Сервер не найден"

            role = guild.get_role(role_id)
            if not role:
                return False, "Роль не найдена на сервере"

            # Check if bot can manage this role
            if role.position >= guild.me.top_role.position:
                return False, "Бот не может управлять этой ролью (роль выше роли бота)"

            return True, role.name

        except Exception as e:
            return False, f"Ошибка валидации роли: {e}"

# Global instance
position_service = PositionService()