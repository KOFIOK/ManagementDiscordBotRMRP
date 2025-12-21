"""
Department Manager - Centralized management for departments
"""
import discord
from typing import Dict, List, Optional, Tuple
from utils.config_manager import load_config, save_config
from utils.postgresql_pool import get_db_cursor
import logging
from utils.logging_setup import get_logger

logger = get_logger(__name__)

class DepartmentManager:
    """Централизованное управление подразделениями"""
    
    # Предустановленные цвета для выбора
    PRESET_COLORS = {
        # Русские названия
        'Синий': 0x3498db,
        'Зелёный': 0x2ecc71,
        'Красный': 0xe74c3c,
        'Оранжевый': 0xf39c12,
        'Фиолетовый': 0x9b59b6,
        'Бирюзовый': 0x1abc9c,
        'Жёлтый': 0xf1c40f,
        'Розовый': 0xe91e63,
        'Серый': 0x95a5a6,
        'Тёмно-синий': 0x2c3e50,
        # Английские названия
        'Blue': 0x3498db,
        'Green': 0x2ecc71,
        'Red': 0xe74c3c,
        'Orange': 0xf39c12,
        'Purple': 0x9b59b6,
        'Teal': 0x1abc9c,
        'Yellow': 0xf1c40f,
        'Pink': 0xe91e63,
        'Gray': 0x95a5a6,
        'Dark Blue': 0x2c3e50,
        # Дополнительные английские цвета
        'Cyan': 0x00ffff,
        'Magenta': 0xff00ff,
        'Lime': 0x00ff00,
        'Navy': 0x000080,
        'Maroon': 0x800000,
        'Olive': 0x808000,
        'Silver': 0xc0c0c0,
        'Gold': 0xffd700,
        'Indigo': 0x4b0082,
        'Violet': 0x8a2be2
    }
    
    @classmethod
    def initialize_system_departments(cls):
        """Инициализация системных подразделений - больше не используется (абстрактная система)"""
        # Системные подразделения удалены для поддержки любой организации
        # Метод оставлен для обратной совместимости
        pass
    
    @classmethod
    def get_all_departments(cls) -> Dict[str, Dict]:
        """Получить все подразделения"""
        cls.initialize_system_departments()  # Убедиться что системные инициализированы
        config = load_config()
        return config.get('departments', {})
    
    @classmethod
    def get_department(cls, dept_code: str) -> Optional[Dict]:
        """Получить конкретное подразделение"""
        departments = cls.get_all_departments()
        return departments.get(dept_code)
    
    @classmethod
    def get_color_hex_by_name(cls, color_name: str) -> int:
        """Получить HEX-код цвета по его названию или HEX коду, регистронезависимо."""
        if not color_name:
            return cls.PRESET_COLORS['Синий']  # Цвет по умолчанию

        # Сначала проверяем, является ли это HEX кодом
        is_valid_hex, hex_value = cls.validate_hex_color(color_name)
        if is_valid_hex:
            return hex_value

        # Если не HEX, ищем среди предустановленных цветов
        for name, hex_code in cls.PRESET_COLORS.items():
            if name.lower() == color_name.lower():
                return hex_code

        return cls.PRESET_COLORS['Синий']  # Цвет по умолчанию

    @classmethod
    def add_department(cls, dept_id: str, name: str, description: Optional[str] = None,
                      emoji: Optional[str] = None, color: Optional[str] = None,
                      role_id: Optional[int] = None) -> bool:
        """
        Добавить новое подразделение

        Args:
            dept_id: ID подразделения
            name: Название подразделения
            description: Описание подразделения (добавлено)
            emoji: Эмодзи подразделения
            color: Цвет подразделения (название из списка)
            role_id: ID основной роли подразделения (для связи с PostgreSQL БД)

        Returns:
            bool: Успешность операции
        """
        try:
            config = load_config()
            if 'departments' not in config:
                config['departments'] = {}

            # Валидация
            if not dept_id or not name:
                logger.error("Dept ID and name are required.")
                return False

            if dept_id in config['departments']:
                logger.error(f"Department with ID '{dept_id}' already exists.")
                return False

            # Определение финального цвета для сохранения (всегда как int)
            final_color_value = None
            if color:
                # Проверяем, является ли это HEX кодом
                is_valid_hex, hex_value = cls.validate_hex_color(color)
                if is_valid_hex:
                    # Сохраняем как числовой HEX код
                    final_color_value = hex_value
                else:
                    # Ищем среди предустановленных цветов и сохраняем числовой код
                    final_color_value = cls.get_color_hex_by_name(color)
            else:
                # Цвет по умолчанию
                final_color_value = cls.PRESET_COLORS['Синий']

            new_department = {
                'name': name,
                'description': description or 'Описание отсутствует', # Устанавливаем описание
                'emoji': emoji or '🏛️',
                'color': final_color_value, # СОХРАНЯЕМ ЧИСЛОВОЙ ИЛИ СТРОКОВОЙ КОД
                'role_id': role_id,  # Связь с PostgreSQL БД
                'ping_contexts': {},
                'application_channel_id': None
            }

            config['departments'][dept_id] = new_department
            save_config(config)

            # Синхронизация с БД: добавляем запись в subdivisions
            if role_id:
                try:
                    with get_db_cursor() as cursor:
                        # Проверяем, существует ли уже запись с таким role_id
                        cursor.execute("SELECT id FROM subdivisions WHERE role_id = %s", (role_id,))
                        existing = cursor.fetchone()

                        if not existing:
                            # Получаем следующий ID
                            cursor.execute("SELECT MAX(id) FROM subdivisions")
                            max_id_result = cursor.fetchone()
                            next_id = (max_id_result['max'] or 0) + 1

                            # Определяем аббревиатуру на основе dept_id
                            abbreviation = cls._get_abbreviation_for_dept_id(dept_id)

                            # Добавляем в subdivisions
                            cursor.execute("""
                                INSERT INTO subdivisions (id, name, abbreviation, role_id)
                                VALUES (%s, %s, %s, %s)
                            """, (next_id, name, abbreviation, role_id))

                            logger.info(f"Added subdivision to DB: {name} ({abbreviation}) with role_id {role_id}")
                        else:
                            logger.warning(f"Subdivision with role_id {role_id} already exists in DB")
                except Exception as e:
                    logger.error(f"Error syncing department {dept_id} to database: {e}")
                    # Не возвращаем False, так как config.json уже обновлен

            logger.info(f"Added department: {dept_id} - {name}")
            return True

        except Exception as e:
            logger.error(f"Error adding department {dept_id}: {e}")
            return False

    @classmethod
    def _get_abbreviation_for_dept_id(cls, dept_id: str) -> str:
        """Получить аббревиатуру для dept_id - просто dept_id в нижнем регистре, ограничено 10 символами"""
        return dept_id.lower()[:10]

    @classmethod
    def generate_select_options(cls) -> List[discord.SelectOption]:
        """Динамически генерировать опции для select menu"""
        departments = cls.get_all_departments()
        options = []

        for dept_code, dept_data in departments.items():
            # Здесь color в dept_data уже будет HEX-кодом
            color_hex = dept_data.get('color', 0x3498db)

            options.append(discord.SelectOption(
                label=f"{dept_code} - {dept_data['name']}",
                description=dept_data.get('description', 'Нет описания')[:100],  # Discord limit
                emoji=dept_data.get('emoji', '🏛️'),
                value=dept_code
            ))

        return options

    @classmethod
    def get_departments_by_role(cls, role_id: int) -> List[str]:
        """Получить подразделения по ID роли (для ping-совместимости)"""
        departments = cls.get_all_departments()
        matching_departments = []

        for dept_code, dept_data in departments.items():
            if dept_data.get('role_id') == role_id:
                matching_departments.append(dept_code)

        return matching_departments

    @classmethod
    def get_color_options(cls) -> List[discord.SelectOption]:
        """Получить опции цветов для select menu (для отображения в UI)"""
        options = []

        for color_name, color_value in cls.PRESET_COLORS.items():
            options.append(discord.SelectOption(
                label=color_name,
                value=color_name, # Value теперь будет строковым названием цвета
                emoji="🎨"
            ))

        return options

    @classmethod
    def get_available_colors(cls) -> List[str]:
        """Получить список доступных цветов для валидации"""
        return list(cls.PRESET_COLORS.keys())

    @classmethod
    def validate_hex_color(cls, color_input: str) -> Tuple[bool, int]:
        """
        Валидировать HEX код цвета и вернуть числовое значение
        
        Args:
            color_input: Строка с HEX кодом (с # или без)
            
        Returns:
            Tuple[bool, int]: (is_valid, hex_value)
        """
        import re
        
        # Убираем # если есть
        color_input = color_input.strip().lstrip('#')
        
        # Проверяем формат: 3 или 6 символов, только hex символы
        if not re.match(r'^[0-9a-fA-F]{3,6}$', color_input):
            return False, 0
        
        # Если 3 символа, расширяем до 6
        if len(color_input) == 3:
            color_input = ''.join(c * 2 for c in color_input)
        
        # Конвертируем в int
        try:
            hex_value = int(color_input, 16)
            return True, hex_value
        except ValueError:
            return False, 0

    @classmethod
    def get_department_statistics(cls) -> Dict[str, int]:
        """Получить статистику подразделений"""
        departments = cls.get_all_departments()

        stats = {
            'total': len(departments),
            'with_channels': 0,
            'with_pings': 0
        }

        for dept_data in departments.values():
            if dept_data.get('application_channel_id'):
                stats['with_channels'] += 1

            if dept_data.get('ping_contexts'):
                stats['with_pings'] += 1

        return stats

    @classmethod
    def department_exists(cls, dept_id: str) -> bool:
        """Проверить, существует ли подразделение"""
        departments = cls.get_all_departments()
        return dept_id in departments

    @classmethod
    def edit_department(cls, dept_id: str, name: Optional[str] = None,
                       emoji: Optional[str] = None, color: Optional[str] = None, # color теперь Optional[str]
                       role_id: Optional[int] = None, description: Optional[str] = None) -> bool: # Добавлен description
        """
        Редактировать существующее подразделение

        Args:
            dept_id: ID подразделения
            name: Новое название
            emoji: Новое эмодзи
            color: Новый цвет (название)
            role_id: Новый ID основной роли подразделения (для связи с PostgreSQL БД)
            description: Новое описание

        Returns:
            bool: Успешность операции
        """
        try:
            config = load_config()
            departments = config.get('departments', {})

            if dept_id not in departments:
                logger.error(f"Department {dept_id} not found")
                return False

            department = departments[dept_id]

            # Сохраняем старый role_id для синхронизации с БД
            old_role_id = department.get('role_id')
            
            # Обновляем только переданные поля
            if name is not None:
                department['name'] = name
            if emoji is not None:
                department['emoji'] = emoji
            if description is not None: # Обновляем описание
                department['description'] = description
            if color is not None:
                # Преобразуем строковое название цвета в числовой HEX-код перед сохранением
                department['color'] = cls.get_color_hex_by_name(color)
            if role_id is not None:
                department['role_id'] = role_id

            config['departments'][dept_id] = department
            save_config(config)

            # Синхронизация с PostgreSQL БД
            if role_id is not None:
                try:
                    with get_db_cursor() as cursor:
                        # Сначала попробуем найти запись по старому role_id
                        update_query = """
                        UPDATE subdivisions 
                        SET role_id = %s, name = %s, abbreviation = %s
                        WHERE role_id = %s
                        """
                        new_name = name if name is not None else department.get('name', '')
                        abbreviation = cls._get_abbreviation_for_dept_id(dept_id)
                        
                        cursor.execute(update_query, (role_id, new_name, abbreviation, old_role_id))
                        rows_affected = cursor.rowcount
                        
                        # Если не нашли по старому role_id, попробуем найти по текущему имени подразделения
                        if rows_affected == 0:
                            current_name = department.get('name', '')
                            find_by_name_query = "SELECT id, role_id FROM subdivisions WHERE name = %s"
                            cursor.execute(find_by_name_query, (current_name,))
                            existing_by_name = cursor.fetchone()
                            
                            if existing_by_name:
                                # Обновляем найденную запись
                                update_by_id_query = """
                                UPDATE subdivisions 
                                SET role_id = %s, name = %s, abbreviation = %s
                                WHERE id = %s
                                """
                                cursor.execute(update_by_id_query, (role_id, new_name, abbreviation, existing_by_name[0]))
                                rows_affected = cursor.rowcount
                            else:
                                # Если совсем не нашли, создадим новую запись (fallback)
                                cursor.execute("SELECT MAX(id) FROM subdivisions")
                                max_id_result = cursor.fetchone()
                                next_id = (max_id_result['max'] or 0) + 1
                                
                                insert_query = """
                                INSERT INTO subdivisions (id, name, abbreviation, role_id)
                                VALUES (%s, %s, %s, %s)
                                """
                                cursor.execute(insert_query, (next_id, new_name, abbreviation, role_id))
                except Exception as db_e:
                    logger.error(f"DB sync error in edit_department: {db_e}")

            logger.info(f"Updated department: {dept_id}")
            return True

        except Exception as e:
            logger.error(f"Error editing department {dept_id}: {e}")
            return False

    @classmethod
    def delete_department(cls, dept_id: str) -> bool:
        """
        Удалить подразделение и все связанные настройки

        Args:
            dept_id: ID подразделения

        Returns:
            bool: Успешность операции
        """
        try:
            config = load_config()
            departments = config.get('departments', {})

            if dept_id not in departments:
                logger.error(f"Department {dept_id} not found")
                return False

            # Удаляем подразделение
            del departments[dept_id]
            config['departments'] = departments

            # Очищаем связанные настройки пингов
            if 'ping_contexts' in config:
                ping_contexts = config['ping_contexts']
                for context_key in list(ping_contexts.keys()):
                    if context_key.startswith(f"{dept_id}_"):
                        del ping_contexts[context_key]
                config['ping_contexts'] = ping_contexts

            save_config(config)

            logger.info(f"Deleted department: {dept_id}")
            return True

        except Exception as e:
            logger.error(f"Error deleting department {dept_id}: {e}")
            return False

    @classmethod
    def get_user_department(cls, user: discord.Member) -> Optional[str]:
        """
        Определить подразделение пользователя по его ролям (PostgreSQL-based)

        Args:
            user: Пользователь Discord

        Returns:
            str: ID подразделения или None если не найдено
        """
        departments = cls.get_all_departments()

        # Get user's role IDs for faster lookup
        user_role_ids = {role.id for role in user.roles}

        # Check each department's role_id (PostgreSQL-based)
        for dept_id, dept_data in departments.items():
            role_id = dept_data.get('role_id')

            # Check if user has this department's role_id
            if role_id and role_id in user_role_ids:
                return dept_id

        return None

    @classmethod
    def get_user_department_name(cls, user: discord.Member) -> str:
        """
        Получить название подразделения пользователя

        Args:
            user: Пользователь Discord

        Returns:
            str: Название подразделения или "Неизвестно"
        """
        department_id = cls.get_user_department(user)
        if department_id:
            departments = cls.get_all_departments()
            dept_data = departments.get(department_id, {})
            return dept_data.get('name', department_id)
        return "Неизвестно"

    @classmethod
    def get_department_safe(cls, dept_code: str) -> Optional[Dict]:
        """
        Безопасное получение подразделения с валидацией типов данных

        Args:
            dept_code: Код подразделения

        Returns:
            Словарь с данными подразделения или None
        """
        departments = cls.get_all_departments()
        dept_data = departments.get(dept_code)

        if not dept_data:
            return None

        # Создаем копию данных с валидацией типов
        safe_data = {
            'name': dept_data.get('name', dept_code),
            'description': dept_data.get('description', 'Описание отсутствует'),
            'emoji': dept_data.get('emoji', '🏛️'),
            'role_id': dept_data.get('role_id'),
            'ping_contexts': dept_data.get('ping_contexts', {}),
            'application_channel_id': dept_data.get('application_channel_id')
        }

        # Обработка цвета - теперь 'color' в config.json всегда будет int (HEX-кодом)
        # благодаря исправленным add_department и edit_department.
        # Этот блок теперь будет работать корректно.
        color = dept_data.get('color', 0x3498db)
        if isinstance(color, str): # Это условие может срабатывать для старых записей
            try:
                safe_data['color'] = int(color) # Если старая запись содержит HEX в виде строки
            except (ValueError, TypeError):
                safe_data['color'] = 0x3498db  # Синий по умолчанию
        else:
            safe_data['color'] = color if isinstance(color, int) else 0x3498db

        return safe_data
