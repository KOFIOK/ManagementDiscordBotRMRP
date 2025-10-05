"""
Comprehensive Personnel Management System for PostgreSQL Integration

This module provides enhanced functionality for managing personnel records,
employee assignments, and role approval workflow with proper PostgreSQL integration.
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
import logging
from ..postgresql_pool import get_db_cursor, get_connection_pool

logger = logging.getLogger(__name__)


class PersonnelManager:
    """Advanced personnel management with full PostgreSQL schema integration"""
    
    def __init__(self):
        self._pool = get_connection_pool()
        # Initialize department operations module
        from .department import DepartmentOperations
        self.department_ops = DepartmentOperations(self)
        logger.info("PersonnelManager инициализирован с connection pooling и модулями")
    
    async def process_role_application_approval(self, application_data: Dict, user_discord_id: int, moderator_discord_id: int, moderator_info: str) -> Tuple[bool, str]:
        """
        Role application processing - only military recruits go to database
        
        Args:
            application_data: Role application data from Discord form
            user_discord_id: Discord user ID of applicant
            moderator_discord_id: Discord user ID of moderator who approved
            moderator_info: Moderator authorization info (name/description)
            
        Returns:
            Tuple[bool, str]: (success, detailed_message)
        """
        try:
            application_type = application_data.get('type', '').lower()
            recruitment_type = application_data.get('recruitment_type', '').lower()
            
            print(f"Обработка заявки: {application_type}, призыв: {recruitment_type}")
            
            # Only military recruits (Призыв/Экскурсия) go to database
            if application_type == "military" and recruitment_type in ["призыв", "экскурсия"]:
                # Step 1: Ensure personnel record exists
                personnel_id, personnel_created = await self._ensure_personnel_record(application_data, user_discord_id)
                if not personnel_id:
                    return False, "Не удалось создать запись в таблице personnel"
                
                # Step 2: Create employee record
                employee_created = await self._create_employee_record(
                    personnel_id, 
                    application_data, 
                    moderator_info
                )
                if employee_created:
                    status_msg = f"Создана запись военнослужащего (Personnel: {'создан' if personnel_created else 'обновлен'}, Employee: создан)"
                else:
                    status_msg = f"Personnel {'создан' if personnel_created else 'обновлен'}, но не удалось создать Employee запись"
                
                # Step 3: Log the approval action
                await self._log_approval_action(personnel_id, application_data, moderator_discord_id, moderator_info)
                
                return True, status_msg
                    
            elif application_type == "civilian":
                # Civilian - NO database actions, only Discord role assignment
                return True, "Заявка гражданского одобрена (только роли Discord, БД не затрагивается)"
                    
            elif application_type == "supplier":
                # Supplier - NO database actions, only Discord role assignment
                return True, "Доступ к поставкам одобрен (только роли Discord, БД не затрагивается)"
                
            elif application_type == "military":
                # Military but NOT recruit (e.g. transfer, promotion) - NO database actions
                return True, f"Военная заявка одобрена (тип: {recruitment_type}, только роли Discord, БД не затрагивается)"
                
            else:
                # Other cases - NO database actions
                return True, "Заявка одобрена (только роли Discord, БД не затрагивается)"
            
        except Exception as e:
            error_msg = f"Ошибка при обработке заявки: {str(e)}"
            logger.error(f"process_role_application_approval failed: {e}")
            return False, error_msg
    
    async def _ensure_personnel_record(self, application_data: Dict, user_discord_id: int) -> Tuple[Optional[int], bool]:
        """
        Ensure personnel record exists, create if needed
        
        Returns:
            Tuple[Optional[int], bool]: (personnel_id, was_created)
        """
        try:
            with get_db_cursor() as cursor:
                # Check if personnel record exists
                cursor.execute("""
                    SELECT id FROM personnel WHERE discord_id = %s;
                """, (user_discord_id,))
                existing = cursor.fetchone()
                
                if existing:
                    # Update existing record
                    personnel_id = existing['id']
                    await self._update_personnel_record(personnel_id, application_data, cursor)
                    return personnel_id, False
                else:
                    # Create new personnel record
                    personnel_id = await self._create_personnel_record(application_data, user_discord_id, cursor)
                    return personnel_id, True
                    
        except Exception as e:
            logger.error(f"_ensure_personnel_record failed: {e}")
            return None, False
    
    async def _create_personnel_record(self, application_data: Dict, user_discord_id: int, cursor) -> Optional[int]:
        """Create new personnel record"""
        try:
            full_name = application_data.get("name", "").strip()
            name_parts = full_name.split()
            first_name = name_parts[0] if name_parts else ""
            last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
            
            # Fix static format to match constraint (XX-XXX or XXX-XXX)
            static_raw = application_data.get("static", "").strip()
            static_id = self._format_static_for_db(static_raw)
            
            cursor.execute("""
                INSERT INTO personnel (discord_id, first_name, last_name, static, join_date, last_updated, is_dismissal)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
            """, (
                user_discord_id, 
                first_name, 
                last_name, 
                static_id, 
                datetime.now().date(),
                datetime.now(timezone.utc),
                False
            ))
            
            result = cursor.fetchone()
            personnel_id = result['id'] if result else None
            
            print(f"Создана запись personnel: {first_name} {last_name} (ID: {personnel_id})")
            return personnel_id
            
        except Exception as e:
            logger.error(f"_create_personnel_record failed: {e}")
            return None
    
    def _format_static_for_db(self, static_raw: str) -> str:
        """Format static to match database constraint (XX-XXX or XXX-XXX)"""
        # Remove all non-digits
        digits_only = ''.join(filter(str.isdigit, static_raw))
        
        if len(digits_only) >= 5:
            # Use first 5-6 digits and format as XX-XXX or XXX-XXX
            if len(digits_only) == 5:
                return f"{digits_only[:2]}-{digits_only[2:]}"  # XX-XXX
            else:
                return f"{digits_only[:3]}-{digits_only[3:6]}"  # XXX-XXX
        elif len(digits_only) >= 2:
            # Pad with zeros if needed
            padded = digits_only.ljust(5, '0')
            return f"{padded[:2]}-{padded[2:]}"
        else:
            # Generate unique static code based on current time
            import time
            timestamp = str(int(time.time()))[-5:]  # Last 5 digits of timestamp
            return f"{timestamp[:2]}-{timestamp[2:]}"
    
    async def _update_personnel_record(self, personnel_id: int, application_data: Dict, cursor):
        """Update existing personnel record"""
        try:
            full_name = application_data.get("name", "").strip()
            name_parts = full_name.split()
            first_name = name_parts[0] if name_parts else ""
            last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
            
            # Fix static format to match constraint
            static_raw = application_data.get("static", "").strip()
            static_id = self._format_static_for_db(static_raw)
            
            cursor.execute("""
                UPDATE personnel 
                SET first_name = %s, last_name = %s, static = %s, last_updated = %s, is_dismissal = false
                WHERE id = %s;
            """, (first_name, last_name, static_id, datetime.now(timezone.utc), personnel_id))
            
            print(f"Обновлена запись personnel: {first_name} {last_name} (ID: {personnel_id})")
            
        except Exception as e:
            logger.error(f"_update_personnel_record failed: {e}")
    
    async def _create_employee_record(self, personnel_id: int, application_data: Dict, moderator_info: str) -> bool:
        """Create employee record for military personnel"""
        try:
            with get_db_cursor() as cursor:
                # Check if employee record already exists
                cursor.execute("""
                    SELECT id FROM employees WHERE personnel_id = %s;
                """, (personnel_id,))
                existing = cursor.fetchone()
                
                if existing:
                    print(f"Employee запись уже существует для personnel_id {personnel_id}")
                    return True
                
                # Get rank ID
                rank_name = application_data.get("rank", "Рядовой")
                rank_id = await self._get_or_create_rank_id(rank_name, cursor)

                # Get subdivision ID for Военная Академия (default for new recruits)
                subdivision_id = await self._get_subdivision_id("Военная Академия", cursor)

                # For new recruits (Рядовой), no specific position is assigned
                # Only officers and specialists have positions
                position_subdivision_id = None
                if rank_name not in ["Рядовой", "Ефрейтор"]:
                    # Only assign position to higher ranks
                    position_name = application_data.get("position")
                    if position_name:
                        position_subdivision_id = await self._get_position_subdivision_id(
                            position_name, subdivision_id, cursor
                        )                # Create employee record (using only existing columns)
                cursor.execute("""
                    INSERT INTO employees (
                        personnel_id, rank_id, subdivision_id, position_subdivision_id
                    ) VALUES (%s, %s, %s, %s)
                    RETURNING id;
                """, (
                    personnel_id,
                    rank_id,
                    subdivision_id,
                    position_subdivision_id
                ))
                
                result = cursor.fetchone()
                employee_id = result['id'] if result else None
                
                if employee_id:
                    print(f"Создана запись employee: {rank_name} в Военная Академия (ID: {employee_id})")
                    return True
                
                return False
                
        except Exception as e:
            logger.error(f"_create_employee_record failed: {e}")
            return False
    
    async def _get_or_create_rank_id(self, rank_name: str, cursor) -> int:
        """Get rank ID, create if doesn't exist"""
        try:
            # Try to find existing rank
            cursor.execute("SELECT id FROM ranks WHERE name = %s;", (rank_name,))
            rank = cursor.fetchone()
            
            if rank:
                return rank['id']
            
            # Create new rank
            cursor.execute("""
                INSERT INTO ranks (name) 
                VALUES (%s) 
                RETURNING id;
            """, (rank_name,))
            
            result = cursor.fetchone()
            rank_id = result['id'] if result else 1  # Fallback to ID 1
            
            print(f"Создано новое звание: {rank_name} (ID: {rank_id})")
            return rank_id
            
        except Exception as e:
            logger.error(f"_get_or_create_rank_id failed: {e}")
            return 1  # Fallback to default rank ID
    
    async def _get_subdivision_id(self, subdivision_name: str, cursor) -> int:
        """Get subdivision ID with smart matching"""
        try:
            # First try exact name match
            cursor.execute("SELECT id FROM subdivisions WHERE name = %s;", (subdivision_name,))
            subdivision = cursor.fetchone()
            
            if subdivision:
                return subdivision['id']
            
            # Try partial matching or abbreviation lookup
            cursor.execute("""
                SELECT id, name, abbreviation FROM subdivisions 
                WHERE name ILIKE %s OR abbreviation ILIKE %s;
            """, (f"%{subdivision_name}%", f"%{subdivision_name}%"))
            similar = cursor.fetchone()
            
            if similar:
                print(f"📍 Найдено похожее подразделение: {similar['name']} ({similar['abbreviation']}) для запроса '{subdivision_name}'")
                return similar['id']
            
            # Only create new subdivision if really needed
            print(f"Подразделение '{subdivision_name}' не найдено, используем Военная Академия по умолчанию")
            
            # Return Военная Академия as default (ID=7)
            cursor.execute("SELECT id FROM subdivisions WHERE name = 'Военная Академия';")
            default = cursor.fetchone()
            if default:
                return default['id']
            
            # Fallback to first subdivision
            return 1
            
        except Exception as e:
            logger.error(f"_get_subdivision_id failed: {e}")
            return 7  # Fallback to Военная Академия ID
    
    def _generate_abbreviation(self, subdivision_name: str) -> str:
        """Generate abbreviation for subdivision"""
        # Simple abbreviation generator
        words = subdivision_name.split()
        if len(words) == 1:
            return words[0][:3].upper()
        else:
            return ''.join([word[0].upper() for word in words if word])[:5]
    
    async def _get_position_subdivision_id(self, position_name: str, subdivision_id: int, cursor) -> int:
        """Get position_subdivision ID with smart matching"""
        try:
            # First find or get position by exact name
            cursor.execute("SELECT id FROM positions WHERE name = %s;", (position_name,))
            position = cursor.fetchone()
            
            if not position:
                # For "Курсант" specifically, use exact match first
                if position_name == "Курсант":
                    cursor.execute("SELECT id FROM positions WHERE name = 'Курсант';")
                    exact_match = cursor.fetchone()
                    if exact_match:
                        position_id = exact_match['id']
                    else:
                        print(f"Точная должность 'Курсант' не найдена, используем ID 59 по умолчанию")
                        position_id = 59
                else:
                    # Try partial matching for other positions
                    cursor.execute("SELECT id, name FROM positions WHERE name ILIKE %s;", (f"%{position_name}%",))
                    similar_position = cursor.fetchone()
                    
                    if similar_position:
                        print(f"📍 Найдена похожая должность: {similar_position['name']} для запроса '{position_name}'")
                        position_id = similar_position['id']
                    else:
                        # Default to "Курсант" for new recruits if position not found
                        print(f"Должность '{position_name}' не найдена, используем 'Курсант' по умолчанию")
                        position_id = 59  # Known Курсант ID
            else:
                position_id = position['id']
            
            # Find existing position_subdivision link
            cursor.execute("""
                SELECT id FROM position_subdivision 
                WHERE position_id = %s AND subdivision_id = %s;
            """, (position_id, subdivision_id))
            
            ps_link = cursor.fetchone()
            
            if ps_link:
                return ps_link['id']
            
            # Create position_subdivision link if not exists
            cursor.execute("""
                INSERT INTO position_subdivision (position_id, subdivision_id)
                VALUES (%s, %s)
                RETURNING id;
            """, (position_id, subdivision_id))
            ps_link = cursor.fetchone()
            
            # Get position name for logging
            cursor.execute("SELECT name FROM positions WHERE id = %s;", (position_id,))
            pos_name = cursor.fetchone()['name']
            
            print(f"Создана связь должность-подразделение: {pos_name} → subdivision_id {subdivision_id} (PS_ID: {ps_link['id']})")
            return ps_link['id']
            
        except Exception as e:
            logger.error(f"_get_position_subdivision_id failed: {e}")
            return 527  # Fallback to the created Курсант + Военная Академия link
    
    async def _log_approval_action(self, personnel_id: int, application_data: Dict, moderator_discord_id: int, moderator_info: str):
        """Log approval action using existing history table"""
        try:
            with get_db_cursor() as cursor:
                import json
                
                # СТРОГИЙ поиск модератора по discord_id
                if moderator_discord_id == 0:
                    # Fallback для случаев, когда moderator_discord_id недоступен
                    print(f"Warning: moderator_discord_id = 0, using fallback personnel ID 1")
                    performed_by_id = 0  # Используем первую запись как fallback
                else:
                    cursor.execute("SELECT id FROM personnel WHERE discord_id = %s;", (moderator_discord_id,))
                    moderator_personnel = cursor.fetchone()
                    
                    if not moderator_personnel:
                        raise ValueError(f"Модератор с discord_id {moderator_discord_id} не найден в системе personnel")
                    
                    performed_by_id = moderator_personnel['id']
                
                # УПРОЩЕННЫЕ details - простой текст вместо JSON
                recruitment_type = application_data.get('recruitment_type', '')
                details = recruitment_type.capitalize() if recruitment_type else 'Призыв'
                
                # ГРОМОЗДКИЙ JSON для changes (как требуется)
                rank_name = application_data.get('rank', 'Рядовой')
                subdivision_name = application_data.get('subdivision', 'Военная Академия')
                
                changes = {
                    "rank": {
                        "new": rank_name,
                        "previous": None
                    },
                    "position": {
                        "new": None,  # Рядовые без должности
                        "previous": None
                    },
                    "subdivision": {
                        "new": subdivision_name,
                        "previous": None
                    }
                }
                
                # Insert into existing history table
                cursor.execute("""
                    INSERT INTO history (
                        action_date, details, performed_by, action_id, personnel_id, changes
                    ) VALUES (%s, %s, %s, %s, %s, %s);
                """, (
                    datetime.now(),  # action_date
                    details,  # details (простой текст)
                    performed_by_id,  # performed_by (строго найденный модератор)
                    10,  # action_id = 10 (Принят на службу)
                    personnel_id,  # personnel_id
                    json.dumps(changes)  # changes (громоздкий JSON)
                ))
                
                print(f"Логирование в history для personnel_id {personnel_id} (действие выполнил: {performed_by_id})")
                
        except Exception as e:
            # Non-critical error, just log it
            logger.error(f"_log_approval_action failed (non-critical): {e}")
    
    async def get_personnel_summary(self, user_discord_id: int) -> Optional[Dict[str, Any]]:
        """Get comprehensive personnel summary for user"""
        try:
            with get_db_cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        p.id as personnel_id,
                        p.first_name,
                        p.last_name,
                        p.static,
                        p.discord_id,
                        p.join_date,
                        p.last_updated,
                        e.id as employee_id,
                        pos.name as position_name,
                        sub.name as subdivision_name,
                        r.name as rank_name
                    FROM personnel p
                    LEFT JOIN employees e ON p.id = e.personnel_id
                    LEFT JOIN position_subdivision ps ON e.position_subdivision_id = ps.id
                    LEFT JOIN positions pos ON ps.position_id = pos.id
                    LEFT JOIN subdivisions sub ON e.subdivision_id = sub.id
                    LEFT JOIN ranks r ON e.rank_id = r.id
                    WHERE p.discord_id = %s AND p.is_dismissal = false;
                """, (user_discord_id,))
                
                result = cursor.fetchone()
                
                if result:
                    return {
                        'personnel_id': result['personnel_id'],
                        'first_name': result['first_name'] or '',
                        'last_name': result['last_name'] or '',
                        'static': result['static'] or '',
                        'discord_id': result['discord_id'],
                        'join_date': result['join_date'],
                        'last_updated': result['last_updated'],
                        'employee_id': result['employee_id'],
                        'employee_status': 'active' if result['employee_id'] else None,
                        'rank': result['rank_name'] or 'Не назначено',
                        'department': result['subdivision_name'] or 'Не назначено',
                        'position': result['position_name'] or 'Не назначено',
                        'full_name': f"{result['first_name'] or ''} {result['last_name'] or ''}".strip(),
                        'has_employee_record': result['employee_id'] is not None
                    }
                
                logger.warning(f"⚠️ No personnel record found for Discord ID: {user_discord_id}")
                return None
                
        except Exception as e:
            logger.error(f"get_personnel_summary failed: {e}")
            return None

    async def process_personnel_dismissal(self, user_discord_id: int, dismissal_data: Dict, moderator_discord_id: int, moderator_info: str) -> Tuple[bool, str]:
        """
        Process personnel dismissal - removes from employees but keeps personnel record for history
        
        Args:
            user_discord_id: Discord user ID of person being dismissed
            dismissal_data: Dismissal data (reason, static, etc.)
            moderator_discord_id: Discord user ID of moderator who approved dismissal
            moderator_info: Moderator authorization info (name/description)
            
        Returns:
            Tuple[bool, str]: (success, detailed_message)
        """
        try:
            with get_db_cursor() as cursor:
                # Check if user exists in personnel and get current employment data
                cursor.execute("""
                    SELECT 
                        p.id, p.first_name, p.last_name, p.static, 
                        e.id as employee_id,
                        r.name as current_rank,
                        pos.name as current_position,
                        sub.name as current_subdivision
                    FROM personnel p
                    LEFT JOIN employees e ON p.id = e.personnel_id
                    LEFT JOIN ranks r ON e.rank_id = r.id
                    LEFT JOIN position_subdivision ps ON e.position_subdivision_id = ps.id
                    LEFT JOIN positions pos ON ps.position_id = pos.id
                    LEFT JOIN subdivisions sub ON e.subdivision_id = sub.id
                    WHERE p.discord_id = %s AND p.is_dismissal = false
                """, (user_discord_id,))
                
                personnel_record = cursor.fetchone()
                if not personnel_record:
                    return False, "Пользователь не найден в базе данных или уже уволен"
                
                personnel_id = personnel_record['id']
                employee_id = personnel_record['employee_id']
                
                current_time = datetime.now(timezone.utc)
                
                # Step 1: Remove from employees table if exists
                if employee_id:
                    cursor.execute("""
                        DELETE FROM employees WHERE id = %s
                    """, (employee_id,))
                    logger.info(f"Removed employee record {employee_id} for personnel {personnel_id}")
                
                # Step 2: Mark personnel as dismissed (soft delete for history)
                cursor.execute("""
                    UPDATE personnel 
                    SET is_dismissal = true, 
                        dismissal_date = %s, 
                        last_updated = %s
                    WHERE id = %s
                """, (current_time.date(), current_time, personnel_id))
                
                # Step 3: Add history entry with proper changes format
                import json
                changes_data = {
                    "rank": {
                        "new": None,
                        "previous": personnel_record.get('current_rank')
                    },
                    "position": {
                        "new": None,
                        "previous": personnel_record.get('current_position')
                    },
                    "subdivision": {
                        "new": None,
                        "previous": personnel_record.get('current_subdivision')
                    },
                    "dismissal_info": {
                        "reason": dismissal_data.get('reason', ''),
                        "static": dismissal_data.get('static', ''),
                        "moderator_info": moderator_info,
                        "dismissed_at": current_time.isoformat()
                    }
                }
                
                # Step 4: Get moderator's personnel ID for proper foreign key reference
                cursor.execute("""
                    SELECT id FROM personnel WHERE discord_id = %s
                """, (moderator_discord_id,))
                
                moderator_record = cursor.fetchone()
                if not moderator_record:
                    # If moderator is not in personnel table, we can't record this properly
                    # This is a limitation of the current DB schema
                    logger.warning(f"Moderator {moderator_discord_id} not found in personnel table")
                    return False, "Модератор не найден в базе данных personnel. Обратитесь к администратору."
                
                moderator_personnel_id = moderator_record['id']
                
                cursor.execute("""
                    INSERT INTO history (personnel_id, action_id, performed_by, details, changes, action_date)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    personnel_id,
                    3,  # Action ID for "Уволен со службы"
                    moderator_personnel_id,  # Use moderator's personnel.id instead of discord_id
                    dismissal_data.get('reason', 'Увольнение'),
                    json.dumps(changes_data, ensure_ascii=False),
                    current_time
                ))
                
                logger.info(f"Successfully processed dismissal for user {user_discord_id}")
                
                full_name = f"{personnel_record['first_name'] or ''} {personnel_record['last_name'] or ''}".strip()
                return True, f"Сотрудник {full_name} успешно уволен из базы данных"
                
        except Exception as e:
            logger.error(f"process_personnel_dismissal failed: {e}")
            return False, f"Ошибка при увольнении: {str(e)}"

    # Department Operations Methods
    async def process_department_join(self, application_data: Dict, user_discord_id: int, moderator_discord_id: int, moderator_info: str) -> Tuple[bool, str]:
        """Process department join application (delegates to department_ops)"""
        return await self.department_ops.process_department_join(application_data, user_discord_id, moderator_discord_id, moderator_info)
    
    async def process_department_transfer(self, application_data: Dict, user_discord_id: int, moderator_discord_id: int, moderator_info: str) -> Tuple[bool, str]:
        """Process department transfer application (delegates to department_ops)"""
        return await self.department_ops.process_department_transfer(application_data, user_discord_id, moderator_discord_id, moderator_info)
    
    async def get_personnel_data_for_audit(self, user_discord_id: int) -> Optional[Dict[str, Any]]:
        """Get personnel data for audit logging (delegates to department_ops)"""
        return await self.department_ops.get_personnel_data_for_audit(user_discord_id)

    # ================================================================
    # 👤 БАЗОВЫЕ ОПЕРАЦИИ С PERSONNEL (для nickname_manager)
    # ================================================================
    
    def get_personnel_by_discord_id(self, discord_id: int) -> Optional[Dict[str, Any]]:
        """
        Получить данные персонала по Discord ID (синхронный метод для nickname_manager)
        
        Args:
            discord_id (int): Discord ID пользователя
            
        Returns:
            Optional[Dict[str, Any]]: Данные персонала или None
        """
        try:
            with get_db_cursor() as cursor:
                cursor.execute("""
                    SELECT discord_id, first_name, last_name, static, 
                           is_dismissal, join_date, dismissal_date
                    FROM personnel 
                    WHERE discord_id = %s AND is_dismissal = false;
                """, (discord_id,))
                
                result = cursor.fetchone()
                
                if result:
                    return {
                        'discord_id': result['discord_id'],
                        'first_name': result['first_name'],
                        'last_name': result['last_name'],
                        'static': result['static'],
                        'is_dismissal': result['is_dismissal'],
                        'join_date': result['join_date'],
                        'dismissal_date': result['dismissal_date']
                    }
                    
                return None
                
        except Exception as e:
            logger.error(f"Ошибка получения данных персонала для {discord_id}: {e}")
            return None
    
    def add_personnel(self, discord_id: int, first_name: str, last_name: str, 
                     static: str) -> Tuple[bool, str]:
        """
        Добавить нового сотрудника в таблицу personnel (синхронный метод)
        
        Args:
            discord_id (int): Discord ID пользователя
            first_name (str): Имя
            last_name (str): Фамилия
            static (str): Статический номер
            
        Returns:
            Tuple[bool, str]: (успех, сообщение)
        """
        try:
            with get_db_cursor() as cursor:
                # Проверяем, нет ли уже такого пользователя
                cursor.execute("""
                    SELECT discord_id FROM personnel 
                    WHERE discord_id = %s AND is_dismissal = false;
                """, (discord_id,))
                
                if cursor.fetchone():
                    return False, f"Пользователь {discord_id} уже есть в базе персонала"
                
                # Добавляем нового сотрудника
                cursor.execute("""
                    INSERT INTO personnel (discord_id, first_name, last_name, static, is_dismissal, join_date)
                    VALUES (%s, %s, %s, %s, false, CURRENT_DATE);
                """, (discord_id, first_name, last_name, static))
                
                logger.info(f"✅ Добавлен персонал: {first_name} {last_name} (ID: {discord_id})")
                return True, f"Персонал {first_name} {last_name} добавлен успешно"
                
        except Exception as e:
            error_msg = f"Ошибка добавления персонала: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def dismiss_personnel(self, discord_id: int, reason: str = None) -> Tuple[bool, str]:
        """
        Уволить сотрудника (синхронный метод)
        
        Args:
            discord_id (int): Discord ID пользователя
            reason (str): Причина увольнения
            
        Returns:
            Tuple[bool, str]: (успех, сообщение)
        """
        try:
            with get_db_cursor() as cursor:
                # Проверяем, есть ли активный сотрудник
                cursor.execute("""
                    SELECT first_name, last_name FROM personnel 
                    WHERE discord_id = %s AND is_dismissal = false;
                """, (discord_id,))
                
                personnel = cursor.fetchone()
                if not personnel:
                    return False, f"Активный персонал с ID {discord_id} не найден"
                
                # Увольняем сотрудника
                cursor.execute("""
                    UPDATE personnel 
                    SET is_dismissal = true, 
                        dismissal_date = CURRENT_DATE,
                        dismissal_reason = %s,
                        last_updated = CURRENT_TIMESTAMP
                    WHERE discord_id = %s AND is_dismissal = false;
                """, (reason, discord_id))
                
                if cursor.rowcount > 0:
                    full_name = f"{personnel['first_name']} {personnel['last_name']}"
                    logger.info(f"✅ Уволен персонал: {full_name} (ID: {discord_id})")
                    return True, f"Персонал {full_name} уволен успешно"
                else:
                    return False, "Не удалось обновить статус увольнения"
                
        except Exception as e:
            error_msg = f"Ошибка увольнения персонала: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def update_personnel_name(self, discord_id: int, first_name: str, 
                             last_name: str) -> Tuple[bool, str]:
        """
        Обновить имя и фамилию сотрудника (синхронный метод)
        
        Args:
            discord_id (int): Discord ID пользователя
            first_name (str): Новое имя
            last_name (str): Новая фамилия
            
        Returns:
            Tuple[bool, str]: (успех, сообщение)
        """
        try:
            with get_db_cursor() as cursor:
                cursor.execute("""
                    UPDATE personnel 
                    SET first_name = %s, 
                        last_name = %s,
                        last_updated = CURRENT_TIMESTAMP
                    WHERE discord_id = %s AND is_dismissal = false;
                """, (first_name, last_name, discord_id))
                
                if cursor.rowcount > 0:
                    logger.info(f"✅ Обновлены данные персонала: {first_name} {last_name} (ID: {discord_id})")
                    return True, f"Данные персонала обновлены: {first_name} {last_name}"
                else:
                    return False, f"Активный персонал с ID {discord_id} не найден"
                
        except Exception as e:
            error_msg = f"Ошибка обновления данных персонала: {e}"
            logger.error(error_msg)
            return False, error_msg

    async def get_all_personnel(self) -> List[Dict[str, Any]]:
        """
        Получить всех активных сотрудников (для user_cache)
        
        Returns:
            List[Dict[str, Any]]: Список всех активных сотрудников
        """
        try:
            with get_db_cursor() as cursor:
                cursor.execute("""
                    SELECT p.discord_id, p.first_name, p.last_name, p.static, 
                           p.join_date, p.dismissal_date, p.is_dismissal,
                           r.name as rank_name, s.name as subdivision_name,
                           pos.name as position_name
                    FROM personnel p
                    LEFT JOIN employees e ON p.id = e.personnel_id
                    LEFT JOIN ranks r ON e.rank_id = r.id
                    LEFT JOIN subdivisions s ON e.subdivision_id = s.id
                    LEFT JOIN position_subdivision ps ON e.position_subdivision_id = ps.id
                    LEFT JOIN positions pos ON ps.position_id = pos.id
                    WHERE p.is_dismissal = false
                    ORDER BY p.last_updated DESC;
                """)
                
                results = cursor.fetchall()
                
                personnel_list = []
                for row in results:
                    personnel_data = {
                        'discord_id': row['discord_id'],
                        'first_name': row['first_name'],
                        'last_name': row['last_name'],
                        'static': row['static'],
                        'join_date': row['join_date'],
                        'dismissal_date': row['dismissal_date'],
                        'is_dismissal': row['is_dismissal'],
                        'rank': row['rank_name'],
                        'subdivision': row['subdivision_name'],
                        'position': row['position_name'] or 'Не указано'
                    }
                    personnel_list.append(personnel_data)
                
                logger.info(f"✅ Получено {len(personnel_list)} записей персонала")
                return personnel_list
                
        except Exception as e:
            logger.error(f"Ошибка получения всех записей персонала: {e}")
            return []


# Global instance
personnel_manager = PersonnelManager()
