"""
🏷️ АВТОМАТИЧЕСКОЕ УПРАВЛЕНИЕ НИКНЕЙМАМИ
========================================

Модуль для автоматического изменения никнеймов пользователей в зависимости от:
• Приёма на службу
• Перевода в подразделение
• Повышения в звании
• Увольнения

ФОРМАТЫ НИКНЕЙМОВ:
• При приёме: "ВА | АББР_ранга | Имя Фамилия"
• При переводе: "АББР_подразделения | АББР_ранга | Имя Фамилия"
• При повышении: обновляем аббревиатуру ранга
• При увольнении: "Уволен | Имя Фамилия"

ОСОБЕННОСТИ:
• Учитывает должностные никнеймы типа "[Нач. Штаба] А.Тимонов"
• Автоматическое сокращение при превышении лимита длины
• Извлечение имени/фамилии из различных форматов
"""

import re
import logging
from typing import Optional, Tuple, Dict, Any
from utils.database_manager.subdivision_mapper import SubdivisionMapper  
from utils.database_manager.rank_manager import rank_manager
from utils.database_manager import personnel_manager
from utils.config_manager import load_config
from utils.message_manager import get_military_ranks

logger = logging.getLogger(__name__)

class NicknameManager:
    """Менеджер автоматического управления никнеймами"""
    
    # Максимальная длина никнейма в Discord
    MAX_NICKNAME_LENGTH = 32

    def __init__(self):
        self.subdivision_mapper = SubdivisionMapper()
        
        # Загружаем конфигурацию
        self.config = load_config()
        
        # Список известных рангов (fallback для случаев недоступности БД)
        self.known_ranks = self._load_known_ranks_fallback()
        
        # Инициализируем паттерны с учетом кастомных настроек
        self._init_patterns()
        
    def _load_known_ranks_fallback(self) -> set:
        """Load minimal fallback ranks for cases when database is unavailable"""
        # Minimal fallback list - should be rarely used
        fallback_ranks = {
            'Рядовой', 'Ефрейтор', 'Сержант', 'Старшина',
            'Лейтенант', 'Капитан', 'Майор', 'Полковник', 'Генерал',
            # Common abbreviations
            'Р-й', 'Еф-р', 'С-т', 'Ст-на', 'Л-т', 'К-н'
        }
        logger.warning("Using fallback rank list - database ranks should be used instead")
        return fallback_ranks
        
    def _init_patterns(self):
        """Инициализация паттернов с учетом кастомных настроек"""
        # Получаем кастомные шаблоны из конфига
        custom_templates = self.config.get('nickname_auto_replacement', {}).get('custom_templates', {})
        
        # Базовые паттерны (могут быть переопределены кастомными)
        base_patterns = {
            # Стандартный формат с подгруппами: "РОиО[ПГ] | Ст. Л-т | Виктор Верпов"
            'standard_with_subgroup': r'^([А-ЯЁA-Zа-яё]{1,15})\[([А-ЯЁA-Zа-яё]{1,10})\]\s*\|\s*([А-ЯЁа-яёA-Za-z\-\.\s]+?)\s*\|\s*(.+)$',
            
            # Стандартный формат: "ПОДР | РАНГ | Имя Фамилия" или "ПОДР | Имя Фамилия"
            'standard': r'^([А-ЯЁA-Zа-яё]{1,15}(?:\[\d+\])?)\s*\|\s*([А-ЯЁа-яёA-Za-z\-\.\s]+?)\s*(?:\|\s*(.+))?$',
            
            # Сложный особый формат: "!![Должность] Имя" или "![Должность] Имя"
            'complex_special': r'^!{1,2}\[([^\]]+)\]\s*(.+)$',
            
            # Должностной формат: "[Должность] И.Фамилия"
            'position': r'^\[([^\]]+)\]\s*([А-ЯA-Z]\.?\s*[А-Яа-яA-Za-z]+)$',
            
            # Простой особый формат: "! Имя Фамилия"
            'simple_special': r'^!\s+(.+)$',
            
            # Простой формат: "Имя Фамилия" или "И.Фамилия"
            'simple': r'^([А-ЯA-Z]\.?\s*[А-Яа-яA-Za-z]+\s*[А-Яа-яA-Za-z]+)$',
            
            # Уволенный: "Уволен | Имя Фамилия"
            'dismissed': r'^Уволен\s*\|\s*(.+)$'
        }
        
        # Применяем кастомные настройки
        for template_id, custom_settings in custom_templates.items():
            if template_id in base_patterns:
                pattern = self._build_custom_pattern(template_id, custom_settings, base_patterns[template_id])
                base_patterns[template_id] = pattern
        
        # Компилируем паттерны
        self.PATTERNS = {name: re.compile(pattern) for name, pattern in base_patterns.items()}
        
    def _build_custom_pattern(self, template_id: str, custom_settings: dict, base_pattern: str) -> str:
        """Создает кастомный паттерн на основе пользовательских настроек"""
        
        # Получаем настройки с дефолтными значениями
        separator_raw = custom_settings.get('separator', '|')
        name_chars = custom_settings.get('name_chars', 'А-ЯЁа-яёA-Za-z\\-\\.\\s')
        subdivision_chars = custom_settings.get('subdivision_chars', 'А-ЯЁA-Zа-яё\\d')
        
        # Автоматически добавляем пробелы вокруг разделителя для паттерна
        separator = f" {separator_raw.strip()} "
        
        # Экранируем специальные символы в разделителях
        separator_escaped = re.escape(separator).replace(' ', '\\s*')
        
        if template_id == 'standard':
            # Паттерн: ПОДР | РАНГ | Имя Фамилия (единый разделитель)
            return f'^([{subdivision_chars}]{{1,15}}(?:\\[\\d+\\])?){separator_escaped}([{name_chars}]+?){separator_escaped}(?:(.+))?$'
            
        elif template_id == 'standard_with_subgroup':
            # Паттерн: ПОДР[ПГ] | РАНГ | Имя Фамилия (единый разделитель)
            subgroup_brackets = custom_settings.get('subgroup_brackets', '[ ]')
            if len(subgroup_brackets) >= 2:
                open_br = re.escape(subgroup_brackets[0])
                close_br = re.escape(subgroup_brackets[-1])
            else:
                open_br, close_br = '\\[', '\\]'
                
            return f'^([{subdivision_chars}]{{1,15}}){open_br}([{subdivision_chars}]{{1,10}}){close_br}{separator_escaped}([{name_chars}]+?){separator_escaped}(.+)$'
            
        elif template_id == 'positional':
            # Паттерн: ПОДР | ДОЛЖНОСТЬ | Имя Фамилия (единый разделитель)
            return f'^([{subdivision_chars}]{{1,15}}){separator_escaped}([{name_chars}]+?){separator_escaped}(.+)$'
            
        elif template_id == 'simple':
            # Паттерн: Имя Фамилия
            return f'^([{name_chars}]+)$'
            
        elif template_id == 'dismissed':
            # Паттерн: Уволен | Имя Фамилия (автоматически добавляем пробелы)
            status_text = custom_settings.get('status_text', 'Уволен')
            return f'^{re.escape(status_text)}{separator_escaped}(.+)$'
        
        # Если неизвестный тип, возвращаем базовый паттерн
        return base_pattern
    
    def _is_rank(self, text: str) -> bool:
        """Проверяет, является ли текст званием"""
        return text in self.known_ranks
    
    def _is_position(self, text: str) -> bool:
        """Проверяет, является ли текст должностью"""
        # Получаем список должностей из настроек
        try:
            config = load_config()
            nickname_settings = config.get('nickname_auto_replacement', {})
            custom_positions = nickname_settings.get('known_positions', [])
            
            # Проверяем точные совпадения с настроенными должностями
            if text in custom_positions:
                return True
        except Exception:
            pass
        
        # Fallback к старой логике
        position_keywords = ['Нач.', 'Зам.', 'Ком.', 'по', 'Отдела', 'Бриг', 'КР', 'Штаба']
        return any(keyword in text for keyword in position_keywords)
    
    # ================================================================
    # 🔧 ПРОВЕРКА НАСТРОЕК АВТОЗАМЕНЫ
    # ================================================================
    
    def _is_nickname_replacement_enabled_globally(self) -> bool:
        """Проверяет, включена ли автозамена никнеймов глобально"""
        try:
            config = load_config()
            nickname_settings = config.get('nickname_auto_replacement', {})
            return nickname_settings.get('enabled', True)  # По умолчанию включена
        except Exception as e:
            logger.error(f"Ошибка при проверке глобальных настроек автозамены: {e}")
            return True  # При ошибке работаем как раньше
    
    def _is_nickname_replacement_enabled_for_department(self, subdivision_key: str) -> bool:
        """Проверяет, включена ли автозамена никнеймов для конкретного подразделения"""
        try:
            config = load_config()
            nickname_settings = config.get('nickname_auto_replacement', {})
            department_settings = nickname_settings.get('departments', {})
            return department_settings.get(subdivision_key, True)  # По умолчанию включена
        except Exception as e:
            logger.error(f"Ошибка при проверке настроек автозамены для подразделения {subdivision_key}: {e}")
            return True  # При ошибке работаем как раньше
    
    def _is_nickname_replacement_enabled_for_module(self, module_name: str) -> bool:
        """Проверяет, включена ли автозамена никнеймов для конкретного модуля"""
        try:
            config = load_config()
            nickname_settings = config.get('nickname_auto_replacement', {})
            module_settings = nickname_settings.get('modules', {})
            return module_settings.get(module_name, True)  # По умолчанию включена
        except Exception as e:
            logger.error(f"Ошибка при проверке настроек автозамены для модуля {module_name}: {e}")
            return True  # При ошибке работаем как раньше
    
    def _should_update_nickname(self, operation: str, current_department: str = None, target_department: str = None) -> bool:
        """
        Определяет, следует ли обновлять никнейм согласно настройкам
        
        Args:
            operation: Тип операции ('hiring', 'transfer', 'promotion', 'dismissal')
            current_department: Текущее подразделение пользователя
            target_department: Целевое подразделение (для переводов)
        
        Returns:
            True если никнейм следует обновить, False иначе
        """
        # Проверяем глобальные настройки
        if not self._is_nickname_replacement_enabled_globally():
            logger.info(f"Автозамена никнеймов отключена глобально для операции {operation}")
            return False
        
        # Проверяем настройки модуля
        if not self._is_nickname_replacement_enabled_for_module(operation):
            logger.info(f"Автозамена никнеймов отключена для модуля {operation}")
            return False
        
        # Особые правила для разных операций
        if operation == 'dismissal':
            # Увольнение ВСЕГДА меняет никнейм, независимо от подразделения
            return True
        
        elif operation == 'transfer':
            # При переводе проверяем оба подразделения
            if current_department and not self._is_nickname_replacement_enabled_for_department(current_department):
                # Если в текущем подразделении отключено, но переводим в другое - меняем
                logger.info(f"Перевод ИЗ подразделения {current_department} с отключенной автозаменой - обновляем никнейм")
                return True
            
            if target_department and not self._is_nickname_replacement_enabled_for_department(target_department):
                # Если в целевом подразделении отключено, но переводим туда - меняем
                logger.info(f"Перевод В подразделение {target_department} с отключенной автозаменой - обновляем никнейм")
                return True
            
            return True  # Перевод всегда меняет никнейм
        
        elif operation in ['promotion', 'hiring', 'name_change']:
            # Для повышения/понижения/приёма/изменения ФИО проверяем текущее/целевое подразделение
            # Примечание: 'promotion' используется для всех изменений звания (повышение/понижение/восстановление)
            department_to_check = target_department or current_department
            if department_to_check and not self._is_nickname_replacement_enabled_for_department(department_to_check):
                logger.info(f"Автозамена никнеймов отключена для подразделения {department_to_check} при операции {operation}")
                return False
            return True
        
        return True  # По умолчанию разрешаем
    
    # ================================================================
    # 🔍 АНАЛИЗ И ИЗВЛЕЧЕНИЕ ДАННЫХ ИЗ НИКНЕЙМА
    # ================================================================
    
    def parse_nickname(self, nickname: str) -> Dict[str, Optional[str]]:
        """
        Анализирует никнейм и извлекает компоненты
        
        Returns:
            Dict с полями: subdivision, rank, position, name, format_type, is_special, subgroup
        """
        if not nickname:
            return {'subdivision': None, 'rank': None, 'position': None, 'name': None, 'format_type': 'empty', 'is_special': False, 'subgroup': None}
        
        # Проверяем сложный особый формат первым
        match = self.PATTERNS['complex_special'].match(nickname)
        if match:
            return {
                'subdivision': None,
                'rank': None,
                'position': None,
                'name': match.group(2).strip(),
                'format_type': 'complex_special',
                'is_special': True,
                'subgroup': None
            }
        
        # Проверяем простой особый формат
        match = self.PATTERNS['simple_special'].match(nickname)
        if match:
            return {
                'subdivision': None,
                'rank': None,
                'position': None,
                'name': match.group(1).strip(),
                'format_type': 'simple_special',
                'is_special': True,
                'subgroup': None
            }
        
        # НОВЫЙ: Проверяем формат с подгруппой: "РОиО[ПГ] | Ст. Л-т | Виктор Верпов"
        match = self.PATTERNS['standard_with_subgroup'].match(nickname)
        if match:
            subdivision = match.group(1).strip()
            subgroup = match.group(2).strip()
            middle_part = match.group(3).strip()
            name_part = match.group(4).strip()
            
            # Определяем тип средней части
            if self._is_rank(middle_part):
                return {
                    'subdivision': subdivision,
                    'subgroup': subgroup,
                    'rank': middle_part,
                    'position': None,
                    'name': name_part,
                    'format_type': 'standard_with_subgroup',
                    'is_special': False
                }
            elif self._is_position(middle_part):
                return {
                    'subdivision': subdivision,
                    'subgroup': subgroup,
                    'rank': None,
                    'position': middle_part,
                    'name': name_part,
                    'format_type': 'positional_with_subgroup',
                    'is_special': True  # Должностные никнеймы не трогаем
                }
            else:
                # Неизвестный тип, считаем рангом
                return {
                    'subdivision': subdivision,
                    'subgroup': subgroup,
                    'rank': middle_part,
                    'position': None,
                    'name': name_part,
                    'format_type': 'standard_with_subgroup',
                    'is_special': False
                }
        
        # Проверяем стандартный формат
        match = self.PATTERNS['standard'].match(nickname)
        if match:
            subdivision = match.group(1).strip()
            middle_part = match.group(2).strip()
            name_part = match.group(3) if match.group(3) else None
            
            # Если есть третья группа (name_part)
            if name_part:
                # Определяем, является ли middle_part рангом или должностью
                if self._is_rank(middle_part):
                    return {
                        'subdivision': subdivision,
                        'rank': middle_part,
                        'position': None,
                        'name': name_part.strip(),
                        'format_type': 'standard',
                        'is_special': False,
                        'subgroup': None
                    }
                elif self._is_position(middle_part):
                    return {
                        'subdivision': subdivision,
                        'rank': None,
                        'position': middle_part,  # Должность вместо звания
                        'name': name_part.strip(),
                        'format_type': 'positional',
                        'is_special': True,  # Должностные никнеймы особые - не трогаем при повышении
                        'subgroup': None
                    }
                else:
                    # Неизвестный тип, считаем рангом
                    return {
                        'subdivision': subdivision,
                        'rank': middle_part,
                        'position': None,
                        'name': name_part.strip(),
                        'format_type': 'standard',
                        'is_special': False,
                        'subgroup': None
                    }
            else:
                # Если нет третьей группы, то middle_part - это имя (формат "ПОДР | Имя")
                return {
                    'subdivision': subdivision,
                    'rank': None,
                    'position': None,
                    'name': middle_part,
                    'format_type': 'standard',
                    'is_special': False,
                    'subgroup': None
                }
        
        # Проверяем должностной формат
        match = self.PATTERNS['position'].match(nickname)
        if match:
            return {
                'subdivision': None,
                'rank': None,
                'position': None,
                'name': match.group(2).strip(),
                'format_type': 'position',
                'is_special': True,  # Не трогаем должностные никнеймы
                'subgroup': None
            }
        
        # Проверяем формат увольнения
        match = self.PATTERNS['dismissed'].match(nickname)
        if match:
            return {
                'subdivision': 'Уволен',
                'rank': None,
                'position': None,
                'name': match.group(1).strip(),
                'format_type': 'dismissed',
                'is_special': False,
                'subgroup': None
            }
        
        # Проверяем простой формат
        match = self.PATTERNS['simple'].match(nickname)
        if match:
            return {
                'subdivision': None,
                'rank': None,
                'position': None,
                'name': match.group(1).strip(),
                'format_type': 'simple',
                'is_special': False,
                'subgroup': None
            }
        
        # Неизвестный формат
        return {
            'subdivision': None,
            'rank': None,
            'position': None,
            'name': nickname.strip(),
            'format_type': 'unknown',
            'is_special': True,  # Не трогаем неизвестные форматы
            'subgroup': None
        }
    
    def extract_name_parts(self, full_name: str) -> Tuple[str, str]:
        """
        Извлекает имя и фамилию из полного имени
        
        Returns:
            Tuple (first_name, last_name)
        """
        if not full_name:
            return "Неизвестно", "Неизвестно"
        
        # Очищаем имя от особых префиксов
        cleaned_name = full_name.strip()
        
        # Удаляем префиксы ! и ![ если они есть
        if cleaned_name.startswith('!'):
            # Удаляем все ! в начале
            cleaned_name = re.sub(r'^!+', '', cleaned_name).strip()
            # Удаляем [должность] если есть
            cleaned_name = re.sub(r'^\[[^\]]+\]\s*', '', cleaned_name).strip()
        
        # Убираем лишние пробелы и разбиваем
        parts = [part.strip() for part in cleaned_name.split() if part.strip()]
        
        if len(parts) == 1:
            # Если одно слово, проверяем на формат "И.Фамилия"
            if '.' in parts[0] and len(parts[0]) > 2:
                # "И.Фамилия" -> извлекаем фамилию
                name_part = parts[0]
                if name_part[1:2] == '.':
                    return name_part[0], name_part[2:].strip()
                else:
                    return parts[0], ""
            else:
                # Одно слово без точки - считаем фамилией
                return "Неизвестно", parts[0]
        
        elif len(parts) == 2:
            # Два слова - имя и фамилия
            first_name = parts[0]
            last_name = parts[1]
            
            # Если первое слово с точкой, это сокращенное имя
            if first_name.endswith('.'):
                first_name = first_name[:-1]
            
            return first_name, last_name
        
        else:
            # Более двух слов - берем первое как имя, остальные как фамилию
            first_name = parts[0]
            last_name = ' '.join(parts[1:])
            
            if first_name.endswith('.'):
                first_name = first_name[:-1]
            
            return first_name, last_name
    
    # ================================================================
    # 🏗️ ФОРМИРОВАНИЕ НИКНЕЙМОВ
    # ================================================================
    
    def format_name_for_nickname(self, first_name: str, last_name: str, max_length: int) -> str:
        """
        Форматирует имя и фамилию с учетом ограничения длины
        
        Args:
            first_name: Имя
            last_name: Фамилия
            max_length: Максимальная длина результата
            
        Returns:
            Отформатированное имя
        """
        # Очищаем входные данные
        first_name = first_name.strip() if first_name else ""
        last_name = last_name.strip() if last_name else ""
        
        # Если нет имени или фамилии
        if not first_name and not last_name:
            return "Неизвестно"
        if not first_name:
            return last_name[:max_length] if last_name else "Неизвестно"
        if not last_name:
            return first_name[:max_length] if first_name else "Неизвестно"
        
        # Пробуем полное имя и фамилию
        full_name = f"{first_name} {last_name}"
        if len(full_name) <= max_length:
            return full_name
        
        # Пробуем сокращенное имя (первая буква + точка)
        short_first = f"{first_name[0]}."
        short_name = f"{short_first} {last_name}"
        if len(short_name) <= max_length:
            return short_name
        
        # Обрезаем фамилию
        available_for_lastname = max_length - len(short_first) - 1  # -1 для пробела
        if available_for_lastname > 0:
            truncated_lastname = last_name[:available_for_lastname]
            return f"{short_first} {truncated_lastname}"
        
        # В крайнем случае возвращаем только сокращенное имя
        return short_first[:max_length] if len(short_first) <= max_length else first_name[0]
    
    def build_service_nickname(self, subdivision_abbr: str, rank_abbr: str, 
                              first_name: str, last_name: str) -> str:
        """
        Строит никнейм для служащего
        
        Format: "ПОДР | РАНГ | Имя Фамилия" или "ПОДР | Имя Фамилия" (если нет звания)
        """
        # Фильтруем None и пустые значения
        valid_subdivision = subdivision_abbr if subdivision_abbr and subdivision_abbr.strip() and subdivision_abbr != "None" else None
        valid_rank = rank_abbr if rank_abbr and rank_abbr.strip() and rank_abbr != "None" else None
        
        # Строим компоненты никнейма
        components = []
        
        # Добавляем подразделение если есть
        if valid_subdivision:
            components.append(valid_subdivision)
        
        # Добавляем звание если есть
        if valid_rank:
            components.append(valid_rank)
        
        # Формируем префикс из компонентов
        if components:
            prefix = " | ".join(components) + " | "
        else:
            # Если нет ни подразделения, ни звания - только имя
            prefix = ""
        
        # Вычисляем доступную длину для имени
        available_length = self.MAX_NICKNAME_LENGTH - len(prefix)
        
        if available_length <= 0 and prefix:
            # Если префикс слишком длинный, упрощаем без разделителей
            logger.warning(f"Префикс слишком длинный: {prefix}")
            short_components = []
            if valid_subdivision:
                short_components.append(valid_subdivision)
            if valid_rank:
                short_components.append(valid_rank)
            short_prefix = "|".join(short_components) + "|"
            available_length = self.MAX_NICKNAME_LENGTH - len(short_prefix)
            formatted_name = self.format_name_for_nickname(first_name, last_name, available_length)
            return f"{short_prefix}{formatted_name}"
        
        # Форматируем имя
        formatted_name = self.format_name_for_nickname(first_name, last_name, available_length)
        
        # Собираем результат
        if prefix:
            result = f"{prefix}{formatted_name}"
        else:
            result = formatted_name
        
        # Проверяем итоговую длину
        if len(result) > self.MAX_NICKNAME_LENGTH:
            result = result[:self.MAX_NICKNAME_LENGTH]
        
        return result
    
    def build_dismissed_nickname(self, first_name: str, last_name: str) -> str:
        """
        Строит никнейм для уволенного с учетом кастомных настроек
        
        Format: "{status_text} {separator} Имя Фамилия"
        """
        # Получаем настройки шаблона увольнения из конфига
        custom_templates = self.config.get('nickname_auto_replacement', {}).get('custom_templates', {})
        dismissed_settings = custom_templates.get('dismissed', {})
        
        # Используем кастомные настройки или дефолтные
        status_text = dismissed_settings.get('status_text', 'Уволен')
        separator = dismissed_settings.get('separator', '|')
        
        # Автоматически добавляем пробелы вокруг разделителя
        separator_with_spaces = f" {separator.strip()} "
        
        prefix = f"{status_text}{separator_with_spaces}"
        available_length = self.MAX_NICKNAME_LENGTH - len(prefix)
        
        formatted_name = self.format_name_for_nickname(first_name, last_name, available_length)
        result = f"{prefix}{formatted_name}"
        
        if len(result) > self.MAX_NICKNAME_LENGTH:
            result = result[:self.MAX_NICKNAME_LENGTH]
        
        return result
    
    # ================================================================
    # 🎯 ОСНОВНЫЕ ОПЕРАЦИИ
    # ================================================================
    
    async def handle_hiring(self, member: Any, rank_name: str, 
                           first_name: str, last_name: str, static: str = None) -> Optional[str]:
        """
        Обрабатывает никнейм при приёме на службу
        
        Args:
            member: Участник Discord
            rank_name: Название звания
            first_name: Имя (для записи в БД)
            last_name: Фамилия (для записи в БД)
            static: Статический номер (для записи в БД)
            
        Returns:
            Новый никнейм или None если не удалось
        """
        try:
            # Проверяем настройки автозамены никнеймов
            if not self._should_update_nickname('hiring', target_department='ВА'):
                logger.info(f"Автозамена никнеймов отключена для приёма, пропускаем обновление для {member}")
                return None
            
            # Добавляем персонал в базу данных при приёме
            if static:
                success, message = personnel_manager.add_personnel(
                    member.id, first_name, last_name, static
                )
                if not success:
                    logger.warning(f"Не удалось добавить персонал в БД: {message}")
            
            # Получаем аббревиатуру звания
            rank_data = rank_manager.get_rank_by_name(rank_name)
            if not rank_data or not rank_data.get('abbreviation'):
                logger.warning(f"Не найдена аббревиатура для звания: {rank_name}")
                rank_abbr = ""  # Пустая аббревиатура
            else:
                rank_abbr = rank_data['abbreviation']
            
            # При приёме используем "ВА" (Военная Академия)
            new_nickname = self.build_service_nickname("ВА", rank_abbr, first_name, last_name)
            
            await member.edit(nick=new_nickname, reason="Приём на службу")
            logger.info(f"✅ Никнейм при приёме: {member} -> {new_nickname}")
            
            return new_nickname
            
        except Exception as e:
            logger.error(f"❌ Ошибка изменения никнейма при приёме {member}: {e}")
            if 'new_nickname' in locals():
                logger.error(f"❌ Ожидаемый никнейм был: '{new_nickname}'")
            return None
    
    async def handle_transfer(self, member: Any, subdivision_key: str, 
                             rank_name: str) -> Optional[str]:
        """
        Обрабатывает никнейм при переводе в подразделение
        
        Args:
            member: Участник Discord
            subdivision_key: Ключ подразделения в config.json
            rank_name: Название звания
            
        Returns:
            Новый никнейм или None если не удалось
        """
        new_nickname = None
        try:
            # Анализируем текущий никнейм для определения текущего подразделения
            current_nickname = member.display_name
            parsed = self.parse_nickname(current_nickname)
            current_department = parsed.get('subdivision', 'unknown')
            
            # Проверяем настройки автозамены никнеймов
            if not self._should_update_nickname('transfer', current_department, subdivision_key):
                logger.info(f"Автозамена никнеймов отключена для перевода из {current_department} в {subdivision_key}, пропускаем обновление для {member}")
                return None
            
            # Получаем полную информацию пользователя из БД (включая звание из employees)
            from utils.database_manager import PersonnelManager
            pm = PersonnelManager()
            personnel_data = await pm.get_personnel_summary(member.id)
            if not personnel_data:
                logger.warning(f"Персонал не найден в БД для пользователя {member.id}")
                # Fallback - пытаемся извлечь из текущего никнейма
                parsed = self.parse_nickname(member.display_name)
                if parsed.get('name'):
                    first_name, last_name = self.extract_name_parts(parsed['name'])
                else:
                    logger.error(f"Не удалось получить имя для пользователя {member.id}")
                    return None
            else:
                first_name = personnel_data['first_name']
                last_name = personnel_data['last_name']
            
            # Получаем данные подразделения
            subdivision_data = await self.subdivision_mapper.get_subdivision_full_data(subdivision_key)
            if not subdivision_data or not subdivision_data.get('abbreviation'):
                logger.warning(f"Подразделение не найдено или нет аббревиатуры: {subdivision_key}")
                # Используем ключ как fallback если нет аббревиатуры
                subdivision_abbr = subdivision_key.upper() if subdivision_key else "ВА"
            else:
                # Получаем аббревиатуру подразделения из БД
                subdivision_abbr = subdivision_data['abbreviation']
            
            # Если это должностной никнейм, сохраняем должность
            if parsed.get('format_type') == 'standard_position' and parsed.get('position'):
                # Для должностных никнеймов меняем только подразделение
                new_nickname = f"{subdivision_abbr} | {parsed['position']} | {first_name} {last_name}"
                reason = f"Перевод в {subdivision_data.get('name', subdivision_key)} (должность сохранена)"
            else:
                # Обычная логика с рангом
                # Получаем аббревиатуру звания
                rank_data = rank_manager.get_rank_by_name(rank_name)
                if not rank_data or not rank_data.get('abbreviation'):
                    logger.warning(f"Не найдена аббревиатура для звания: {rank_name}")
                    rank_abbr = ""  # Пустая аббревиатура
                else:
                    rank_abbr = rank_data['abbreviation']
                
                new_nickname = self.build_service_nickname(subdivision_abbr, rank_abbr, first_name, last_name)
                reason = f"Перевод в {subdivision_data.get('name', subdivision_key)}"
            
            await member.edit(nick=new_nickname, reason=reason)
            logger.info(f"✅ Никнейм при переводе: {member} -> {new_nickname}")
            
            return new_nickname
            
        except Exception as e:
            logger.error(f"❌ Ошибка изменения никнейма при переводе {member}: {e}")
            if new_nickname:
                logger.error(f"❌ Ожидаемый никнейм был: '{new_nickname}'")
            return None
    
    async def handle_rank_change(self, member: Any, new_rank_name: str, change_type: str = "изменение") -> Optional[str]:
        """
        Обрабатывает никнейм при изменении звания (повышение/понижение/восстановление)
        
        Args:
            member: Участник Discord
            new_rank_name: Новое звание
            change_type: Тип изменения для логирования ("повышение", "понижение", "восстановление", "изменение")
            
        Returns:
            Новый никнейм или None если не удалось
        """
        new_nickname = None
        try:
            # Анализируем текущий никнейм для определения подразделения
            current_nickname = member.display_name
            parsed = self.parse_nickname(current_nickname)
            current_department = parsed.get('subdivision', 'unknown')
            
            # Проверяем настройки автозамены никнеймов
            # Используем 'promotion' для всех изменений звания (совместимость с настройками)
            if not self._should_update_nickname('promotion', current_department):
                logger.info(f"Автозамена никнеймов отключена для изменения звания в подразделении {current_department}, пропускаем обновление для {member}")
                return None
            
            # Получаем полную информацию пользователя из БД
            from utils.database_manager import PersonnelManager
            pm = PersonnelManager()
            personnel_data = await pm.get_personnel_summary(member.id)
            if not personnel_data:
                logger.warning(f"Персонал не найден в БД для пользователя {member.id}")
                # Fallback - пытаемся извлечь из текущего никнейма
                if parsed.get('name'):
                    first_name, last_name = self.extract_name_parts(parsed['name'])
                else:
                    logger.error(f"Не удалось получить имя для пользователя {member.id}")
                    return None
            else:
                first_name = personnel_data['first_name']
                last_name = personnel_data['last_name']
            
            logger.info(f"� RANK_CHANGE DEBUG: Текущий никнейм: '{current_nickname}'")
            logger.info(f"� RANK_CHANGE DEBUG: Parsed: {parsed}")
            logger.info(f"� RANK_CHANGE DEBUG: Извлеченное имя: {first_name} {last_name}")
            logger.info(f"🔄 RANK_CHANGE DEBUG: Тип изменения: {change_type}")
            
            # Если никнейм имеет особый формат или должностной, не трогаем его
            if parsed['is_special']:
                logger.info(f"Никнейм имеет особый/должностной формат, пропускаем: {current_nickname}")
                return None
            
            # Получаем новую аббревиатуру звания
            rank_data = rank_manager.get_rank_by_name(new_rank_name)
            logger.info(f"� RANK_CHANGE DEBUG: Ранг '{new_rank_name}' -> данные: {rank_data}")
            
            if not rank_data or not rank_data.get('abbreviation'):
                logger.warning(f"Не найдена аббревиатура для нового звания: {new_rank_name}")
                new_rank_abbr = ""  # Пустая аббревиатура
            else:
                new_rank_abbr = rank_data['abbreviation']
            
            logger.info(f"� RANK_CHANGE DEBUG: Аббревиатура ранга: '{new_rank_abbr}'")
            
            # Определяем подразделение
            subdivision_abbr = None
            if parsed['format_type'] == 'standard' and parsed['subdivision'] and parsed['subdivision'] != "None":
                # Обновляем существующий формат
                subdivision_abbr = parsed['subdivision']
                logger.info(f"� RANK_CHANGE DEBUG: Используем подразделение из никнейма: '{subdivision_abbr}'")
            else:
                # Если нет подразделения в никнейме, проверяем БД
                if personnel_data and personnel_data.get('subdivision_abbreviation'):
                    subdivision_abbr = personnel_data['subdivision_abbreviation']
                    logger.info(f"� RANK_CHANGE DEBUG: Используем подразделение из БД: '{subdivision_abbr}'")
                else:
                    # Если нигде нет подразделения, используем ВА
                    subdivision_abbr = "ВА"
                    logger.info(f"� RANK_CHANGE DEBUG: Используем подразделение по умолчанию: '{subdivision_abbr}'")
            
            new_nickname = self.build_service_nickname(subdivision_abbr, new_rank_abbr, first_name, last_name)
            logger.info(f"� RANK_CHANGE DEBUG: Построенный никнейм: '{new_nickname}'")
            
            await member.edit(nick=new_nickname, reason=f"{change_type.capitalize()} до {new_rank_name}")
            logger.info(f"✅ Никнейм при изменении звания ({change_type}): {member} -> {new_nickname}")
            
            return new_nickname
            
        except Exception as e:
            logger.error(f"❌ Ошибка изменения никнейма при {change_type} {member}: {e}")
            if new_nickname:
                logger.error(f"❌ Ожидаемый никнейм был: '{new_nickname}'")
            return None
    
    async def handle_promotion(self, member: Any, new_rank_name: str) -> Optional[str]:
        """
        УСТАРЕЛ: Используйте handle_rank_change с change_type="повышение"
        Оставлен для обратной совместимости
        """
        return await self.handle_rank_change(member, new_rank_name, "повышение")
    
    async def handle_demotion(self, member: Any, new_rank_name: str) -> Optional[str]:
        """
        УСТАРЕЛ: Используйте handle_rank_change с change_type="понижение"
        Оставлен для обратной совместимости
        """
        return await self.handle_rank_change(member, new_rank_name, "понижение")
    
    async def handle_name_change(self, member: Any, new_first_name: str, new_last_name: str, current_rank_name: str = None) -> Optional[str]:
        """
        Обрабатывает никнейм при изменении ФИО
        
        Args:
            member: Участник Discord
            new_first_name: Новое имя
            new_last_name: Новая фамилия
            current_rank_name: Текущее звание (если известно)
            
        Returns:
            Новый никнейм или None если не удалось
        """
        new_nickname = None
        try:
            # Анализируем текущий никнейм для определения формата и подразделения
            current_nickname = member.display_name
            parsed = self.parse_nickname(current_nickname)
            current_department = parsed.get('subdivision', 'unknown')
            
            # Проверяем настройки автозамены никнеймов
            if not self._should_update_nickname('name_change', current_department):
                logger.info(f"Автозамена никнеймов отключена для изменения ФИО в подразделении {current_department}, пропускаем обновление для {member}")
                return None
            
            logger.info(f"🔍 NAME_CHANGE DEBUG: Текущий никнейм: '{current_nickname}'")
            logger.info(f"🔍 NAME_CHANGE DEBUG: Parsed: {parsed}")
            logger.info(f"🔍 NAME_CHANGE DEBUG: Новое ФИО: {new_first_name} {new_last_name}")
            
            # Если никнейм имеет особый формат или должностной, не трогаем его
            if parsed['is_special']:
                logger.info(f"Никнейм имеет особый/должностной формат, пропускаем: {current_nickname}")
                return None
            
            # Определяем звание
            rank_abbr = ""
            if current_rank_name:
                # Используем переданное звание
                rank_data = rank_manager.get_rank_by_name(current_rank_name)
                if rank_data and rank_data.get('abbreviation'):
                    rank_abbr = rank_data['abbreviation']
                    logger.info(f"🔍 NAME_CHANGE DEBUG: Звание из параметра: '{current_rank_name}' -> '{rank_abbr}'")
            elif parsed['format_type'] == 'standard' and parsed['rank']:
                # Используем звание из текущего никнейма
                rank_abbr = parsed['rank']
                logger.info(f"🔍 NAME_CHANGE DEBUG: Звание из никнейма: '{rank_abbr}'")
            else:
                # Пытаемся получить звание из БД
                try:
                    from utils.database_manager import PersonnelManager
                    pm = PersonnelManager()
                    personnel_data = await pm.get_personnel_summary(member.id)
                    if personnel_data and personnel_data.get('current_rank'):
                        rank_data = rank_manager.get_rank_by_name(personnel_data['current_rank'])
                        if rank_data and rank_data.get('abbreviation'):
                            rank_abbr = rank_data['abbreviation']
                            logger.info(f"🔍 NAME_CHANGE DEBUG: Звание из БД: '{personnel_data['current_rank']}' -> '{rank_abbr}'")
                except Exception as db_error:
                    logger.warning(f"Ошибка получения звания из БД: {db_error}")
            
            # Определяем подразделение
            subdivision_abbr = "ВА"  # По умолчанию
            if parsed['format_type'] == 'standard' and parsed['subdivision'] and parsed['subdivision'] != "None":
                subdivision_abbr = parsed['subdivision']
                logger.info(f"🔍 NAME_CHANGE DEBUG: Подразделение из никнейма: '{subdivision_abbr}'")
            else:
                # Пытаемся получить из БД
                try:
                    from utils.database_manager import PersonnelManager
                    pm = PersonnelManager()
                    personnel_data = await pm.get_personnel_summary(member.id)
                    if personnel_data and personnel_data.get('subdivision_abbreviation'):
                        subdivision_abbr = personnel_data['subdivision_abbreviation']
                        logger.info(f"🔍 NAME_CHANGE DEBUG: Подразделение из БД: '{subdivision_abbr}'")
                except Exception as db_error:
                    logger.warning(f"Ошибка получения подразделения из БД: {db_error}")
            
            # Строим новый никнейм с новым ФИО
            new_nickname = self.build_service_nickname(subdivision_abbr, rank_abbr, new_first_name, new_last_name)
            logger.info(f"🔍 NAME_CHANGE DEBUG: Построенный никнейм: '{new_nickname}'")
            
            await member.edit(nick=new_nickname, reason=f"Изменение ФИО: {new_first_name} {new_last_name}")
            logger.info(f"✅ Никнейм при изменении ФИО: {member} -> {new_nickname}")
            
            return new_nickname
            
        except Exception as e:
            logger.error(f"❌ Ошибка изменения никнейма при смене ФИО {member}: {e}")
            if new_nickname:
                logger.error(f"❌ Ожидаемый никнейм был: '{new_nickname}'")
            return None
    
    async def handle_dismissal(self, member: Any, reason: str = None, 
                              provided_name: Optional[str] = None) -> Optional[str]:
        """
        Обрабатывает никнейм при увольнении
        
        Args:
            member: Участник Discord
            reason: Причина увольнения
            provided_name: Предоставленное имя (из формы увольнения)
            
        Returns:
            Новый никнейм или None если не удалось
        """
        try:
            # Проверяем настройки автозамены никнеймов
            # Примечание: увольнение ВСЕГДА меняет никнейм, независимо от настроек подразделения
            if not self._should_update_nickname('dismissal'):
                logger.info(f"Автозамена никнеймов отключена для увольнения, пропускаем обновление для {member}")
                return None
            
            # Увольняем из базы данных
            success, message = personnel_manager.dismiss_personnel(member.id, reason)
            if success:
                logger.info(f"Персонал уволен из БД: {message}")
            else:
                logger.warning(f"Не удалось уволить из БД: {message}")
            
            # Получаем имя и фамилию из базы данных (до увольнения данные еще есть)
            from utils.database_manager import PersonnelManager
            pm = PersonnelManager()
            personnel_data = await pm.get_personnel_summary(member.id)
            
            if provided_name:
                # Используем предоставленное имя
                first_name, last_name = self.extract_name_parts(provided_name)
            elif personnel_data:
                # Используем данные из БД
                first_name = personnel_data['first_name']
                last_name = personnel_data['last_name']
            else:
                # Fallback - извлекаем из текущего никнейма
                current_nickname = member.display_name
                parsed = self.parse_nickname(current_nickname)
                
                if parsed['name']:
                    first_name, last_name = self.extract_name_parts(parsed['name'])
                else:
                    # Fallback к отображаемому имени
                    first_name, last_name = self.extract_name_parts(current_nickname)
            
            new_nickname = self.build_dismissed_nickname(first_name, last_name)
            
            # Проверяем разрешения перед изменением никнейма
            if not member.guild.me.guild_permissions.manage_nicknames:
                logger.error(f"❌ У бота нет разрешения 'Manage Nicknames' для изменения никнейма {member}")
                logger.error(f"❌ Ожидаемый никнейм был: '{new_nickname}'")
                return None
            
            # Проверяем иерархию ролей
            if member.top_role >= member.guild.me.top_role and member != member.guild.owner:
                logger.error(f"❌ Роль бота ниже роли пользователя {member}. Невозможно изменить никнейм.")
                logger.error(f"❌ Ожидаемый никнейм был: '{new_nickname}'")
                return None
            
            await member.edit(nick=new_nickname, reason="Увольнение")
            logger.info(f"✅ Никнейм при увольнении: {member} -> {new_nickname}")
            
            return new_nickname
            
        except Exception as e:
            logger.error(f"❌ Ошибка изменения никнейма при увольнении {member}: {e}")
            if new_nickname:
                logger.error(f"❌ Ожидаемый никнейм был: '{new_nickname}'")
            return None
    
    # ================================================================
    # 🔧 УТИЛИТЫ
    # ================================================================
    
    def preview_nickname_change(self, current_nickname: str, operation: str, **kwargs) -> str:
        """
        Предварительный просмотр изменения никнейма без применения
        
        Args:
            current_nickname: Текущий никнейм
            operation: Тип операции ('hiring', 'transfer', 'promotion', 'dismissal')
            **kwargs: Дополнительные параметры для операции
            
        Returns:
            Предполагаемый новый никнейм
        """
        parsed = self.parse_nickname(current_nickname)
        
        if operation == 'dismissal':
            name = kwargs.get('name') or parsed.get('name', current_nickname)
            first_name, last_name = self.extract_name_parts(name)
            return self.build_dismissed_nickname(first_name, last_name)
        
        elif operation == 'hiring':
            rank_abbr = kwargs.get('rank_abbr', 'Неизв')
            first_name = kwargs.get('first_name', 'Имя')
            last_name = kwargs.get('last_name', 'Фамилия')
            return self.build_service_nickname("ВА", rank_abbr, first_name, last_name)
        
        elif operation == 'transfer':
            subdivision_abbr = kwargs.get('subdivision_abbr')
            if not subdivision_abbr or subdivision_abbr == "None":
                subdivision_abbr = "ВА"
            rank_abbr = kwargs.get('rank_abbr')
            if rank_abbr == "None":
                rank_abbr = ""
            first_name = kwargs.get('first_name', 'Имя')
            last_name = kwargs.get('last_name', 'Фамилия')
            return self.build_service_nickname(subdivision_abbr, rank_abbr, first_name, last_name)
        
        elif operation == 'promotion':
            rank_abbr = kwargs.get('rank_abbr')
            if rank_abbr == "None":
                rank_abbr = ""
            subdivision_abbr = parsed.get('subdivision')
            if not subdivision_abbr or subdivision_abbr == "None":
                subdivision_abbr = "ВА"
            first_name, last_name = self.extract_name_parts(parsed.get('name', current_nickname))
            return self.build_service_nickname(subdivision_abbr, rank_abbr, first_name, last_name)
        
        return current_nickname


# ================================================================
# 🎯 ЭКЗЕМПЛЯР МЕНЕДЖЕРА
# ================================================================

nickname_manager = NicknameManager()