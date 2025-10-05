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

logger = logging.getLogger(__name__)

class NicknameManager:
    """Менеджер автоматического управления никнеймами"""
    
    # Максимальная длина никнейма в Discord
    MAX_NICKNAME_LENGTH = 32
    
    # Паттерны для распознавания форматов никнеймов
    PATTERNS = {
        # Стандартный формат: "ПОДР | РАНГ | Имя Фамилия" или "ПОДР | Имя Фамилия"
        # Поддерживает номера подразделений: "РОиО[1] | Ст-на | Петя Петров"
        'standard': re.compile(r'^([А-ЯЁA-Zа-яё]{1,15}(?:\[\d+\])?)\s*\|\s*([А-ЯЁа-яёA-Za-z\-\.\s]+?)\s*(?:\|\s*(.+))?$'),
        
        # Сложный особый формат: "!![Должность] Имя" или "![Должность] Имя"
        'complex_special': re.compile(r'^!{1,2}\[([^\]]+)\]\s*(.+)$'),
        
        # Должностной формат: "[Должность] И.Фамилия"
        'position': re.compile(r'^\[([^\]]+)\]\s*([А-ЯA-Z]\.?\s*[А-Яа-яA-Za-z]+)$'),
        
        # Простой особый формат: "! Имя Фамилия"
        'simple_special': re.compile(r'^!\s+(.+)$'),
        
        # Простой формат: "Имя Фамилия" или "И.Фамилия"
        'simple': re.compile(r'^([А-ЯA-Z]\.?\s*[А-Яа-яA-Za-z]+\s*[А-Яа-яA-Za-z]+)$'),
        
        # Уволенный: "Уволен | Имя Фамилия"
        'dismissed': re.compile(r'^Уволен\s*\|\s*(.+)$')
    }
    
    def __init__(self):
        self.subdivision_mapper = SubdivisionMapper()
        
        # Список известных рангов для определения должностей
        self.known_ranks = {
            'Рядовой', 'Ефрейтор', 'Мл. Сержант', 'Сержант', 'Ст. Сержант', 
            'Старшина', 'Прапорщик', 'Ст. Прапорщик', 'Мл. Лейтенант',
            'Лейтенант', 'Ст. Лейтенант', 'Капитан', 'Майор', 'Подполковник', 'Полковник',
            # Аббревиатуры
            'Ефр-р', 'Мл. С-т', 'С-т', 'Ст. С-т', 'Ст-на', 'Ст. Прап-к', 'Мл. Л-т', 'Ст. Л-т', 'Подполк-к'
        }
    
    def _is_rank(self, text: str) -> bool:
        """Проверяет, является ли текст званием"""
        return text in self.known_ranks
    
    def _is_position(self, text: str) -> bool:
        """Проверяет, является ли текст должностью"""
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
        
        elif operation in ['promotion', 'hiring']:
            # Для повышения/приёма проверяем текущее/целевое подразделение
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
            Dict с полями: subdivision, rank, name, format_type, is_special
        """
        if not nickname:
            return {'subdivision': None, 'rank': None, 'name': None, 'format_type': 'empty', 'is_special': False}
        
        # Проверяем сложный особый формат первым
        match = self.PATTERNS['complex_special'].match(nickname)
        if match:
            return {
                'subdivision': None,
                'rank': None,
                'name': match.group(2).strip(),
                'format_type': 'complex_special',
                'is_special': True
            }
        
        # Проверяем простой особый формат
        match = self.PATTERNS['simple_special'].match(nickname)
        if match:
            return {
                'subdivision': None,
                'rank': None,
                'name': match.group(1).strip(),
                'format_type': 'simple_special',
                'is_special': True
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
                        'name': name_part.strip(),
                        'format_type': 'standard',
                        'is_special': False
                    }
                elif self._is_position(middle_part):
                    return {
                        'subdivision': subdivision,
                        'rank': None,
                        'position': middle_part,  # Добавляем поле должности
                        'name': name_part.strip(),
                        'format_type': 'standard_position',
                        'is_special': True  # Должностные никнеймы особые - не трогаем при повышении
                    }
                else:
                    # Неизвестный тип, считаем рангом
                    return {
                        'subdivision': subdivision,
                        'rank': middle_part,
                        'name': name_part.strip(),
                        'format_type': 'standard',
                        'is_special': False
                    }
            else:
                # Если нет третьей группы, то middle_part - это имя (формат "ПОДР | Имя")
                return {
                    'subdivision': subdivision,
                    'rank': None,
                    'name': middle_part,
                    'format_type': 'standard',
                    'is_special': False
                }
        
        # Проверяем должностной формат
        match = self.PATTERNS['position'].match(nickname)
        if match:
            return {
                'subdivision': None,
                'rank': None,
                'name': match.group(2).strip(),
                'format_type': 'position',
                'is_special': True  # Не трогаем должностные никнеймы
            }
        
        # Проверяем формат увольнения
        match = self.PATTERNS['dismissed'].match(nickname)
        if match:
            return {
                'subdivision': 'Уволен',
                'rank': None,
                'name': match.group(1).strip(),
                'format_type': 'dismissed',
                'is_special': False
            }
        
        # Проверяем простой формат
        match = self.PATTERNS['simple'].match(nickname)
        if match:
            return {
                'subdivision': None,
                'rank': None,
                'name': match.group(1).strip(),
                'format_type': 'simple',
                'is_special': False
            }
        
        # Неизвестный формат
        return {
            'subdivision': None,
            'rank': None,
            'name': nickname.strip(),
            'format_type': 'unknown',
            'is_special': True  # Не трогаем неизвестные форматы
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
        Строит никнейм для уволенного
        
        Format: "Уволен | Имя Фамилия"
        """
        prefix = "Уволен | "
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
    
    async def handle_promotion(self, member: Any, new_rank_name: str) -> Optional[str]:
        """
        Обрабатывает никнейм при повышении в звании
        
        Args:
            member: Участник Discord
            new_rank_name: Новое звание
            
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
            if not self._should_update_nickname('promotion', current_department):
                logger.info(f"Автозамена никнеймов отключена для повышения в подразделении {current_department}, пропускаем обновление для {member}")
                return None
            
            # Получаем полную информацию пользователя из БД (включая звание из employees)
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
            parsed = self.parse_nickname(current_nickname)
            
            logger.info(f"🔍 PROMOTION DEBUG: Текущий никнейм: '{current_nickname}'")
            logger.info(f"🔍 PROMOTION DEBUG: Parsed: {parsed}")
            logger.info(f"🔍 PROMOTION DEBUG: Извлеченное имя: {first_name} {last_name}")
            
            # Если никнейм имеет особый формат или должностной, не трогаем его
            if parsed['is_special']:
                logger.info(f"Никнейм имеет особый/должностной формат, пропускаем: {current_nickname}")
                return None
            
            # Получаем новую аббревиатуру звания
            rank_data = rank_manager.get_rank_by_name(new_rank_name)
            logger.info(f"🔍 PROMOTION DEBUG: Ранг '{new_rank_name}' -> данные: {rank_data}")
            
            if not rank_data or not rank_data.get('abbreviation'):
                logger.warning(f"Не найдена аббревиатура для нового звания: {new_rank_name}")
                new_rank_abbr = ""  # Пустая аббревиатура
            else:
                new_rank_abbr = rank_data['abbreviation']
            
            logger.info(f"🔍 PROMOTION DEBUG: Аббревиатура ранга: '{new_rank_abbr}'")
            
            # Определяем подразделение
            subdivision_abbr = None
            if parsed['format_type'] == 'standard' and parsed['subdivision'] and parsed['subdivision'] != "None":
                # Обновляем существующий формат
                subdivision_abbr = parsed['subdivision']
                logger.info(f"🔍 PROMOTION DEBUG: Используем подразделение из никнейма: '{subdivision_abbr}'")
            else:
                # Если нет подразделения в никнейме, проверяем БД
                if personnel_data and personnel_data.get('subdivision_abbreviation'):
                    subdivision_abbr = personnel_data['subdivision_abbreviation']
                    logger.info(f"🔍 PROMOTION DEBUG: Используем подразделение из БД: '{subdivision_abbr}'")
                else:
                    # Если нигде нет подразделения, используем ВА
                    subdivision_abbr = "ВА"
                    logger.info(f"🔍 PROMOTION DEBUG: Используем подразделение по умолчанию: '{subdivision_abbr}'")
            
            new_nickname = self.build_service_nickname(subdivision_abbr, new_rank_abbr, first_name, last_name)
            logger.info(f"🔍 PROMOTION DEBUG: Построенный никнейм: '{new_nickname}'")
            
            await member.edit(nick=new_nickname, reason=f"Повышение до {new_rank_name}")
            logger.info(f"✅ Никнейм при повышении: {member} -> {new_nickname}")
            
            return new_nickname
            
        except Exception as e:
            logger.error(f"❌ Ошибка изменения никнейма при повышении {member}: {e}")
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