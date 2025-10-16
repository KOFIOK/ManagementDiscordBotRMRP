"""
Department Manager - Centralized management for departments
"""
import discord
from typing import Dict, List, Optional, Tuple
from utils.config_manager import load_config, save_config
import logging

logger = logging.getLogger(__name__)

class DepartmentManager:
    """Централизованное управление подразделениями"""
    
    # Предустановленные цвета для выбора
    PRESET_COLORS = {
        'Синий': 0x3498db,
        'Зелёный': 0x2ecc71,
        'Красный': 0xe74c3c,
        'Оранжевый': 0xf39c12,
        'Фиолетовый': 0x9b59b6,
        'Бирюзовый': 0x1abc9c,
        'Жёлтый': 0xf1c40f,
        'Розовый': 0xe91e63,
        'Серый': 0x95a5a6,
        'Тёмно-синий': 0x2c3e50
    }
    
    # Системные подразделения (защищены флагом is_system)
    SYSTEM_DEPARTMENTS = {
        'УВП': {
            'name': 'Управление Военной Полиции',
            'description': 'Контроль и надзор за соблюдением воинской дисциплины',
            'color': 0x3498db,
            'emoji': '🎓',
            'is_system': True
        },
        'ССО': {
            'name': 'Силы Специальных Операций',
            'description': 'Элитное подразделение для выполнения специальных задач',
            'color': 0x2ecc71,
            'emoji': '🎯',
            'is_system': True
        },
        'РОиО': {
            'name': 'Рота Охраны и Обеспечения',
            'description': 'Разведывательная деятельность и оборонительные операции',
            'color': 0x9b59b6,
            'emoji': '🔍',
            'is_system': True
        },
        'ВК': {
            'name': 'Военный Комиссариат',
            'description': 'Обучение и мобилизация гражданского населения',
            'color': 0xe74c3c,
            'emoji': '🚔',
            'is_system': True
        },
        'МР': {
            'name': 'Медицинская Рота',
            'description': 'Медицинское обеспечение и помощь личному составу',
            'color': 0xf39c12,
            'emoji': '🏥',
            'is_system': True
        },
        'ВА': {
            'name': 'Военная Академия',
            'description': 'Высшее военное образование и подготовка офицерского состава',
            'color': 0x1abc9c,
            'emoji': '🎖️',
            'is_system': True
        }
    }
    
    @classmethod
    def initialize_system_departments(cls):
        """Инициализация системных подразделений при первом запуске"""
        config = load_config()
        departments = config.get('departments', {})
        
        updated = False
        for dept_code, dept_data in cls.SYSTEM_DEPARTMENTS.items():
            if dept_code not in departments:
                # Добавляем системное подразделение с полными полями
                full_dept_data = dept_data.copy()
                full_dept_data.update({
                    'application_channel_id': None,
                    'persistent_message_id': None,
                    'ping_contexts': {}
                })
                departments[dept_code] = full_dept_data
                updated = True
                logger.info(f"Initialized system department: {dept_code}")
            else:
                # Обновляем is_system флаг для существующих и добавляем недостающие поля
                existing_dept = departments[dept_code]
                if not existing_dept.get('is_system', False):
                    existing_dept['is_system'] = True
                    updated = True
                
                # Добавляем недостающие поля если их нет
                missing_fields = {
                    'application_channel_id': None,
                    'persistent_message_id': None,
                    'ping_contexts': {}
                }
                for field, default_value in missing_fields.items():
                    if field not in existing_dept:
                        existing_dept[field] = default_value
                        updated = True
        
        if updated:
            config['departments'] = departments
            save_config(config)
            logger.info("System departments initialized/updated")
    
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
    
    # НОВЫЙ МЕТОД: Получение HEX-кода цвета по названию
    @classmethod
    def get_color_hex_by_name(cls, color_name: str) -> int:
        """Получить HEX-код цвета по его названию, регистронезависимо."""
        for name, hex_code in cls.PRESET_COLORS.items():
            if name.lower() == color_name.lower():
                return hex_code
        return cls.PRESET_COLORS['Синий'] # Цвет по умолчанию

    # ИСПРАВЛЕННЫЙ МЕТОД: add_department (бывшее второе определение, первое удалено)
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

            # Получение ЧИСЛОВОГО цветового кода из строкового названия
            final_color_hex = cls.get_color_hex_by_name(color) if color else cls.PRESET_COLORS['Синий']

            new_department = {
                'name': name,
                'description': description or 'Описание отсутствует', # Устанавливаем описание
                'emoji': emoji or '🏛️',
                'color': final_color_hex, # СОХРАНЯЕМ ЧИСЛОВОЙ HEX-КОД
                'role_id': role_id,  # Связь с PostgreSQL БД
                'is_system': False,
                'ping_contexts': {},
                'application_channel_id': None
            }

            config['departments'][dept_id] = new_department
            save_config(config)

            logger.info(f"Added department: {dept_id} - {name}")
            return True

        except Exception as e:
            logger.error(f"Error adding department {dept_id}: {e}")
            return False

    @classmethod
    def edit_department(cls, dept_id: str, name: str, description: Optional[str] = None,
                       emoji: Optional[str] = None, color: Optional[str] = None,
                       role_id: Optional[int] = None) -> bool:
        """
        Редактировать существующее подразделение

        Args:
            dept_id: ID подразделения
            name: Название подразделения
            description: Описание подразделения
            emoji: Эмодзи подразделения
            color: Цвет подразделения (название из списка)
            role_id: ID основной роли подразделения

        Returns:
            bool: Успешность операции
        """
        try:
            config = load_config()
            departments = config.get('departments', {})

            if dept_id not in departments:
                logger.error(f"Department '{dept_id}' not found")
                return False

            department = departments[dept_id]

            # Обновляем поля
            if name is not None:
                department['name'] = name
            if description is not None:
                department['description'] = description
            if emoji is not None:
                department['emoji'] = emoji
            if color is not None:
                if isinstance(color, str):
                    if color.startswith('#'):
                        # HEX строка, конвертируем в число
                        is_valid, hex_value = cls.validate_hex_color(color)
                        department['color'] = hex_value if is_valid else cls.PRESET_COLORS['Синий']
                    else:
                        # Название цвета
                        department['color'] = cls.get_color_hex_by_name(color)
                elif isinstance(color, int):
                    # Числовой HEX код
                    department['color'] = color
            if role_id is not None:
                department['role_id'] = role_id

            save_config(config)
            logger.info(f"Edited department: {dept_id} - {name}")
            return True

        except Exception as e:
            logger.error(f"Error editing department {dept_id}: {e}")
            return False

    # ИСПРАВЛЕННЫЙ МЕТОД: update_department
    # Это отдельный метод для обновления, не путать с add_department.
    # Если вы используете его через kwargs, он уже принимает 'color'.
    # Нужно убедиться, что kwargs передает HEX-код, или добавить здесь преобразование.
    # Ваш метод edit_department (ниже) будет использовать get_color_hex_by_name
    # Так что этот метод update_department может остаться как есть, если его вызывающие функции
    # передают HEX-код, или быть адаптированным.
    # Для единообразия лучше, чтобы он тоже мог принимать строковое имя цвета.
    @classmethod
    def update_department(cls, dept_code: str, **kwargs) -> Tuple[bool, str]:
        """
        Обновить существующее подразделение

        Args:
            dept_code: Код подразделения
            **kwargs: Поля для обновления (name, description, role_id, color (str or int), emoji)
        """
        try:
            departments = cls.get_all_departments()

            if dept_code not in departments:
                return False, f"Подразделение '{dept_code}' не найдено"

            department = departments[dept_code]

            # Обновление полей
            for field, value in kwargs.items():
                if field == 'color' and isinstance(value, str):
                    # Если передано строковое название цвета, преобразуем в HEX
                    department[field] = cls.get_color_hex_by_name(value)
                elif field in ['name', 'description', 'role_id', 'emoji']:
                    department[field] = value

            # Сохранение
            config = load_config()
            config['departments'][dept_code] = department
            save_config(config)

            logger.info(f"Updated department: {dept_code}")
            return True, f"Подразделение '{dept_code}' успешно обновлено"

        except Exception as e:
            logger.error(f"Error updating department {dept_code}: {e}")
            return False, f"Ошибка при обновлении подразделения: {e}"

    @classmethod
    def remove_department(cls, dept_code: str) -> Tuple[bool, str]:
        """
        Удалить подразделение и все связанные настройки

        Returns:
            Tuple[bool, str]: (успех, сообщение)
        """
        try:
            departments = cls.get_all_departments()

            if dept_code not in departments:
                return False, f"Подразделение '{dept_code}' не найдено"

            # Проверка системного флага
            department = departments[dept_code]
            if department.get('is_system', False):
                return False, f"Нельзя удалить системное подразделение '{dept_code}'"

            # Удаление подразделения
            config = load_config()

            # Очистка всех связанных настроек
            if 'departments' in config and dept_code in config['departments']:
                del config['departments'][dept_code]

            # Очистка legacy ping_settings (если есть)
            ping_settings = config.get('ping_settings', {})
            role_id = department.get('role_id')
            if role_id and str(role_id) in ping_settings:
                del ping_settings[str(role_id)]
                config['ping_settings'] = ping_settings

            save_config(config)

            logger.info(f"Removed department: {dept_code}")
            return True, f"Подразделение '{dept_code}' и все связанные настройки удалены"

        except Exception as e:
            logger.error(f"Error removing department {dept_code}: {e}")
            return False, f"Ошибка при удалении подразделения: {e}"

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
            'system': 0,
            'custom': 0,
            'with_channels': 0,
            'with_pings': 0
        }

        for dept_data in departments.values():
            if dept_data.get('is_system', False):
                stats['system'] += 1
            else:
                stats['custom'] += 1

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

    # ИСПРАВЛЕННЫЙ МЕТОД: edit_department
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
            'is_system': dept_data.get('is_system', False),
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

# Инициализация при импорте модуля
DepartmentManager.initialize_system_departments()