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
                    'ping_contexts': {},
                    'key_role_id': None
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
                    'ping_contexts': {},
                    'key_role_id': None
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
    
    @classmethod
    def add_department(cls, dept_code: str, name: str, description: str, 
                      key_role_id: int, color: int, emoji: str = "🏛️") -> Tuple[bool, str]:
        """
        Добавить новое подразделение
        
        Returns:
            Tuple[bool, str]: (успех, сообщение)
        """
        try:
            # Валидация
            if not dept_code or not name:
                return False, "Код и название подразделения обязательны"
            
            # Проверка существования
            departments = cls.get_all_departments()
            if dept_code in departments:
                return False, f"Подразделение с кодом '{dept_code}' уже существует"
            
            # Создание нового подразделения
            new_department = {
                'name': name,
                'description': description or '',
                'key_role_id': key_role_id,
                'color': color,
                'emoji': emoji,
                'is_system': False,
                'ping_contexts': {},  # Пустые контексты по умолчанию
                'application_channel_id': None  # Будет настроено отдельно
            }
            
            # Сохранение
            config = load_config()
            if 'departments' not in config:
                config['departments'] = {}
            
            config['departments'][dept_code] = new_department
            save_config(config)
            
            logger.info(f"Added new department: {dept_code} - {name}")
            return True, f"Подразделение '{dept_code} - {name}' успешно добавлено"
            
        except Exception as e:
            logger.error(f"Error adding department {dept_code}: {e}")
            return False, f"Ошибка при добавлении подразделения: {e}"
    
    @classmethod
    def update_department(cls, dept_code: str, **kwargs) -> Tuple[bool, str]:
        """
        Обновить существующее подразделение
        
        Args:
            dept_code: Код подразделения
            **kwargs: Поля для обновления (name, description, key_role_id, color, emoji)
        """
        try:
            departments = cls.get_all_departments()
            
            if dept_code not in departments:
                return False, f"Подразделение '{dept_code}' не найдено"
            
            # Обновление полей
            department = departments[dept_code]
            
            for field, value in kwargs.items():
                if field in ['name', 'description', 'key_role_id', 'color', 'emoji']:
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
            role_id = department.get('key_role_id')
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
            if dept_data.get('key_role_id') == role_id:
                matching_departments.append(dept_code)
        
        return matching_departments
    
    @classmethod
    def get_color_options(cls) -> List[discord.SelectOption]:
        """Получить опции цветов для select menu"""
        options = []
        
        for color_name, color_value in cls.PRESET_COLORS.items():
            options.append(discord.SelectOption(
                label=color_name,
                value=str(color_value),
                emoji="🎨"
            ))
        
        return options
    
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
    
    @classmethod
    def get_available_colors(cls) -> List[str]:
        """Получить список доступных цветов"""
        return list(cls.PRESET_COLORS.keys())
    
    @classmethod
    def add_department(cls, dept_id: str, name: str, emoji: Optional[str] = None, 
                      color: Optional[str] = None, key_role_id: Optional[int] = None) -> bool:
        """
        Добавить новое подразделение
        
        Args:
            dept_id: ID подразделения
            name: Название подразделения  
            emoji: Эмодзи подразделения
            color: Цвет подразделения (название из списка)
            key_role_id: ID ключевой роли
            
        Returns:
            bool: Успешность операции
        """
        try:
            config = load_config()
            if 'departments' not in config:
                config['departments'] = {}
            
            # Получение цветового кода
            color_value = cls.PRESET_COLORS.get(color, cls.PRESET_COLORS['Синий'])
            
            new_department = {
                'name': name,
                'emoji': emoji or '🏛️',
                'color': color or 'синий',
                'key_role_id': key_role_id,
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
    def edit_department(cls, dept_id: str, name: Optional[str] = None, 
                       emoji: Optional[str] = None, color: Optional[str] = None, 
                       key_role_id: Optional[int] = None) -> bool:
        """
        Редактировать существующее подразделение
        
        Args:
            dept_id: ID подразделения
            name: Новое название
            emoji: Новое эмодзи
            color: Новый цвет
            key_role_id: Новый ID ключевой роли
            
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
            if color is not None:
                department['color'] = color
            if key_role_id is not None:
                department['key_role_id'] = key_role_id
            
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
        Определить подразделение пользователя по его ролям
        
        Args:
            user: Пользователь Discord
            
        Returns:
            str: ID подразделения или None если не найдено
        """
        departments = cls.get_all_departments()
        
        user_department = None
        highest_position = -1
        
        for dept_id, dept_data in departments.items():
            key_role_id = dept_data.get('key_role_id')
            if key_role_id:
                role = user.guild.get_role(key_role_id)
                if role and role in user.roles:
                    # Выбираем роль с наивысшей позицией в иерархии
                    if role.position > highest_position:
                        highest_position = role.position
                        user_department = dept_id
        
        return user_department
    
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
            'key_role_id': dept_data.get('key_role_id'),
            'ping_contexts': dept_data.get('ping_contexts', {}),
            'application_channel_id': dept_data.get('application_channel_id')
        }
        
        # Обработка цвета - приведение к правильному типу
        color = dept_data.get('color', 0x3498db)
        if isinstance(color, str):
            try:
                safe_data['color'] = int(color)
            except (ValueError, TypeError):
                safe_data['color'] = 0x3498db  # Синий по умолчанию
        else:
            safe_data['color'] = color if isinstance(color, int) else 0x3498db
        
        return safe_data

# Инициализация при импорте модуля
DepartmentManager.initialize_system_departments()
