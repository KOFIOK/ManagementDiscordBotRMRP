"""
Data Validation for Position Management
Валидация данных должностей
"""

from typing import Optional, Dict, Any, Tuple, List
from utils.postgresql_pool import get_db_cursor

class PositionValidator:
    """Validate position data and dependencies"""

    @staticmethod
    def validate_position_name(name: str, exclude_id: Optional[int] = None) -> Tuple[bool, str]:
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

    @staticmethod
    def check_position_dependencies(position_id: int) -> Dict[str, Any]:
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
            print(f"❌ Error checking dependencies: {e}")
            return {
                'active_employees': 0,
                'subdivisions': 0,
                'has_dependencies': False,
                'error': str(e)
            }

    @staticmethod
    def validate_discord_role(role_id: int, guild) -> Tuple[bool, str]:
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

    @staticmethod
    def validate_subdivision_position_link(subdivision_id: int, position_id: int) -> Tuple[bool, str]:
        """
        Validate that position can be linked to subdivision

        Args:
            subdivision_id: Subdivision ID
            position_id: Position ID

        Returns:
            Tuple[bool, str]: (is_valid, error_message)
        """
        try:
            with get_db_cursor() as cursor:
                # Check if subdivision exists
                cursor.execute("SELECT id, name FROM subdivisions WHERE id = %s", (subdivision_id,))
                subdivision = cursor.fetchone()
                if not subdivision:
                    return False, "Подразделение не найдено"

                # Check if position exists
                cursor.execute("SELECT id, name FROM positions WHERE id = %s", (position_id,))
                position = cursor.fetchone()
                if not position:
                    return False, "Должность не найдена"

                # Check if link already exists
                cursor.execute("""
                    SELECT id FROM position_subdivision
                    WHERE position_id = %s AND subdivision_id = %s
                """, (position_id, subdivision_id))

                existing_link = cursor.fetchone()
                if existing_link:
                    return False, f"Связь между '{position['name']}' и '{subdivision['name']}' уже существует"

                return True, ""

        except Exception as e:
            return False, f"Ошибка валидации связи: {e}"