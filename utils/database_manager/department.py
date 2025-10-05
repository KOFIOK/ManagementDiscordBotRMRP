"""
Department Operations Module

Handles department join/transfer applications and operations.
"""

import logging
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timezone, timedelta
from ..postgresql_pool import get_db_cursor

logger = logging.getLogger(__name__)


class DepartmentOperations:
    """Handle department join and transfer operations"""
    
    def __init__(self, personnel_manager):
        self.personnel_manager = personnel_manager
        
    async def process_department_join(self, application_data: Dict, user_discord_id: int, moderator_discord_id: int, moderator_info: str) -> Tuple[bool, str]:
        """
        Process department join application
        
        Args:
            application_data: Application data containing target department, reason, etc.
            user_discord_id: Discord user ID of applicant
            moderator_discord_id: Discord user ID of moderator who approved
            moderator_info: Moderator authorization info
            
        Returns:
            Tuple[bool, str]: (success, detailed_message)
        """
        try:
            # Get personnel ID
            personnel_id = await self._get_personnel_id(user_discord_id)
            if not personnel_id:
                return False, "Пользователь не найден в базе данных personnel"
            
            # Get target subdivision ID
            target_department = application_data.get('target_department', '')
            subdivision_id = await self._get_subdivision_id(target_department)
            if not subdivision_id:
                return False, f"Подразделение '{target_department}' не найдено"
            
            # Check if user is already in this department
            current_subdivision = await self._get_current_subdivision(personnel_id)
            if current_subdivision and current_subdivision == subdivision_id:
                return False, f"Пользователь уже состоит в подразделении '{target_department}'"
            
            # Get user's current rank for department join
            rank_id = await self._get_user_rank_id(personnel_id)
            if not rank_id:
                return False, "Не удалось определить звание пользователя"
            
            # Update employee record with new subdivision
            success = await self._update_employee_subdivision(personnel_id, subdivision_id, rank_id)
            if not success:
                return False, "Не удалось обновить запись сотрудника"
            
            # Log the action in history
            await self._log_department_action(
                personnel_id=personnel_id,
                action_id=7,  # Department join
                moderator_discord_id=moderator_discord_id,
                application_data=application_data,
                old_subdivision=current_subdivision,
                new_subdivision=subdivision_id
            )
            
            subdivision_name = await self._get_subdivision_name(subdivision_id)
            return True, f"Успешно добавлен в подразделение '{subdivision_name}'"
            
        except Exception as e:
            logger.error(f"process_department_join failed: {e}")
            return False, f"Ошибка при обработке заявки в подразделение: {str(e)}"
    
    async def process_department_transfer(self, application_data: Dict, user_discord_id: int, moderator_discord_id: int, moderator_info: str) -> Tuple[bool, str]:
        """
        Process department transfer application
        
        Args:
            application_data: Application data containing target department, reason, etc.
            user_discord_id: Discord user ID of applicant
            moderator_discord_id: Discord user ID of moderator who approved
            moderator_info: Moderator authorization info
            
        Returns:
            Tuple[bool, str]: (success, detailed_message)
        """
        try:
            # Get personnel ID
            personnel_id = await self._get_personnel_id(user_discord_id)
            if not personnel_id:
                return False, "Пользователь не найден в базе данных personnel"
            
            # Get current subdivision
            current_subdivision = await self._get_current_subdivision(personnel_id)
            if not current_subdivision:
                return False, "Пользователь не состоит ни в каком подразделении"
            
            # Get target subdivision ID
            target_department = application_data.get('target_department', '')
            new_subdivision_id = await self._get_subdivision_id(target_department)
            if not new_subdivision_id:
                return False, f"Целевое подразделение '{target_department}' не найдено"
            
            # Check if trying to transfer to same department
            if current_subdivision == new_subdivision_id:
                return False, f"Пользователь уже состоит в подразделении '{target_department}'"
            
            # Get user's current rank for transfer
            rank_id = await self._get_user_rank_id(personnel_id)
            if not rank_id:
                return False, "Не удалось определить звание пользователя"
            
            # Update employee record with new subdivision
            success = await self._update_employee_subdivision(personnel_id, new_subdivision_id, rank_id)
            if not success:
                return False, "Не удалось обновить запись сотрудника"
            
            # Log the action in history
            await self._log_department_action(
                personnel_id=personnel_id,
                action_id=8,  # Department transfer
                moderator_discord_id=moderator_discord_id,
                application_data=application_data,
                old_subdivision=current_subdivision,
                new_subdivision=new_subdivision_id
            )
            
            old_subdivision_name = await self._get_subdivision_name(current_subdivision)
            new_subdivision_name = await self._get_subdivision_name(new_subdivision_id)
            return True, f"Успешно переведен из '{old_subdivision_name}' в '{new_subdivision_name}'"
            
        except Exception as e:
            logger.error(f"process_department_transfer failed: {e}")
            return False, f"Ошибка при обработке заявки на перевод: {str(e)}"
    
    # Helper methods
    async def _get_personnel_id(self, user_discord_id: int) -> Optional[int]:
        """Get personnel ID by Discord ID"""
        try:
            with get_db_cursor() as cursor:
                cursor.execute("""
                    SELECT id FROM personnel 
                    WHERE discord_id = %s AND is_dismissal = false;
                """, (user_discord_id,))
                result = cursor.fetchone()
                return result['id'] if result else None
        except Exception as e:
            logger.error(f"_get_personnel_id failed: {e}")
            return None
    
    async def _get_subdivision_id(self, subdivision_name: str) -> Optional[int]:
        """Get subdivision ID by name or abbreviation"""
        try:
            with get_db_cursor() as cursor:
                # Try exact name match first
                cursor.execute("""
                    SELECT id FROM subdivisions 
                    WHERE name = %s OR abbreviation = %s;
                """, (subdivision_name, subdivision_name))
                result = cursor.fetchone()
                
                if result:
                    return result['id']
                
                # Try partial matching
                cursor.execute("""
                    SELECT id FROM subdivisions 
                    WHERE name ILIKE %s OR abbreviation ILIKE %s;
                """, (f"%{subdivision_name}%", f"%{subdivision_name}%"))
                result = cursor.fetchone()
                
                return result['id'] if result else None
        except Exception as e:
            logger.error(f"_get_subdivision_id failed: {e}")
            return None
    
    async def _get_current_subdivision(self, personnel_id: int) -> Optional[int]:
        """Get current subdivision ID for personnel"""
        try:
            with get_db_cursor() as cursor:
                cursor.execute("""
                    SELECT subdivision_id FROM employees 
                    WHERE personnel_id = %s;
                """, (personnel_id,))
                result = cursor.fetchone()
                return result['subdivision_id'] if result else None
        except Exception as e:
            logger.error(f"_get_current_subdivision failed: {e}")
            return None
    
    async def _get_user_rank_id(self, personnel_id: int) -> Optional[int]:
        """Get current rank ID for personnel"""
        try:
            with get_db_cursor() as cursor:
                cursor.execute("""
                    SELECT rank_id FROM employees 
                    WHERE personnel_id = %s;
                """, (personnel_id,))
                result = cursor.fetchone()
                return result['rank_id'] if result else None
        except Exception as e:
            logger.error(f"_get_user_rank_id failed: {e}")
            return None
    
    async def _get_subdivision_name(self, subdivision_id: int) -> str:
        """Get subdivision name by ID"""
        try:
            with get_db_cursor() as cursor:
                cursor.execute("""
                    SELECT name FROM subdivisions WHERE id = %s;
                """, (subdivision_id,))
                result = cursor.fetchone()
                return result['name'] if result else "Неизвестно"
        except Exception as e:
            logger.error(f"_get_subdivision_name failed: {e}")
            return "Неизвестно"
    
    async def _update_employee_subdivision(self, personnel_id: int, subdivision_id: int, rank_id: int) -> bool:
        """Update employee subdivision and clear position"""
        try:
            with get_db_cursor() as cursor:
                cursor.execute("""
                    UPDATE employees 
                    SET subdivision_id = %s, position_subdivision_id = NULL
                    WHERE personnel_id = %s;
                """, (subdivision_id, personnel_id))
                return True
        except Exception as e:
            logger.error(f"_update_employee_subdivision failed: {e}")
            return False
    
    async def _log_department_action(self, personnel_id: int, action_id: int, moderator_discord_id: int, 
                                   application_data: Dict, old_subdivision: Optional[int], new_subdivision: int):
        """Log department action in history table"""
        try:
            with get_db_cursor() as cursor:
                # Get moderator personnel ID
                cursor.execute("""
                    SELECT id FROM personnel WHERE discord_id = %s;
                """, (moderator_discord_id,))
                moderator_result = cursor.fetchone()
                
                if not moderator_result:
                    logger.warning(f"Moderator {moderator_discord_id} not found in personnel table")
                    return
                
                moderator_personnel_id = moderator_result['id']
                
                # Prepare changes JSON in standard format
                import json
                old_subdivision_name = await self._get_subdivision_name(old_subdivision) if old_subdivision else None
                new_subdivision_name = await self._get_subdivision_name(new_subdivision)
                
                changes = {
                    "rank": {
                        "new": None,  # Rank doesn't change during department operations
                        "previous": None
                    },
                    "position": {
                        "new": None,  # Position is cleared on department change
                        "previous": None
                    },
                    "subdivision": {
                        "new": new_subdivision_name,
                        "previous": old_subdivision_name
                    }
                }
                
                # Insert history record with standard details format
                cursor.execute("""
                    INSERT INTO history (personnel_id, action_id, performed_by, details, changes, action_date)
                    VALUES (%s, %s, %s, %s, %s, %s);
                """, (
                    personnel_id,
                    action_id,
                    moderator_personnel_id,
                    application_data.get('reason', ''),
                    json.dumps(changes, ensure_ascii=False),
                    datetime.now(timezone(timedelta(hours=3)))  # Moscow time UTC+3
                ))
                
        except Exception as e:
            logger.error(f"_log_department_action failed: {e}")
    
    async def get_personnel_data_for_audit(self, user_discord_id: int) -> Optional[Dict[str, Any]]:
        """Get comprehensive personnel data for audit logging"""
        try:
            with get_db_cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        p.first_name,
                        p.last_name,
                        p.static,
                        r.name as rank_name,
                        s.name as subdivision_name,
                        pos.name as position_name
                    FROM personnel p
                    LEFT JOIN employees e ON p.id = e.personnel_id
                    LEFT JOIN ranks r ON e.rank_id = r.id
                    LEFT JOIN subdivisions s ON e.subdivision_id = s.id
                    LEFT JOIN position_subdivision ps ON e.position_subdivision_id = ps.id
                    LEFT JOIN positions pos ON ps.position_id = pos.id
                    WHERE p.discord_id = %s AND p.is_dismissal = false;
                """, (user_discord_id,))
                
                result = cursor.fetchone()
                if result:
                    return {
                        'name': f"{result['first_name'] or ''} {result['last_name'] or ''}".strip(),
                        'static': result['static'] or '',
                        'rank': result['rank_name'] or 'Не назначено',
                        'department': result['subdivision_name'] or 'Не назначено',
                        'position': result['position_name'] or 'Не назначено'
                    }
                return None
        except Exception as e:
            logger.error(f"get_personnel_data_for_audit failed: {e}")
            return None