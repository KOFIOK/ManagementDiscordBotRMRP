"""
Утилиты для системы электронных заявок
Вспомогательные функции для парсинга, поиска и обработки шаблонов
"""

import re
import discord
from pathlib import Path
from typing import Optional
from utils.logging_setup import get_logger

logger = get_logger(__name__)


def markdown_to_discord(content: str) -> str:
    """
    Конвертация markdown в Discord-формат
    - # заголовки остаются (Discord их конвертирует в bold)
    - - списки остаются как есть
    """
    lines = content.strip().split('\n')
    converted_lines = []
    
    for line in lines:
        # Оставляем заголовки и списки, убираем лишние пробелы
        converted_lines.append(line.rstrip())
    
    return '\n'.join(converted_lines)


def parse_discord_tag_from_content(content: str, pattern: str) -> Optional[str]:
    """
    Парсинг Discord-тага из контента сообщения с использованием регулярки
    Поддерживает несколько вариантов формата входных данных
    
    Args:
        content: Контент сообщения
        pattern: Regex-паттерн из конфига
        
    Returns:
        Discord-тег или None
    """
    try:
        # Вариант 1: Используем основной паттерн из конфига с флагом DOTALL для переносов
        match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
        if match:
            tag = match.group(1).strip()
            logger.info(f"ELEC_APP: Найден Discord-тег (основной паттерн): {tag}")
            return tag
        
        # Вариант 2: Если основной паттерн не сработал, ищем Discord-теги
        # Берем теги которые идут после @ или похожи на Discord username
        fallback_pattern = r'@([\w.#\d-]+)'
        
        # Сначала ищем теги с @ (более надежно)
        matches_with_at = re.findall(fallback_pattern, content)
        if matches_with_at:
            # Фильтруем служебные слова (например, @user из примеров)
            excluded_words = {'user', 'пример', 'example', 'username', 'nickname'}
            
            for tag in matches_with_at:
                if tag.lower() not in excluded_words and len(tag) > 2:
                    logger.info(f"ELEC_APP: Найден Discord-тег (@tag паттерн): {tag}")
                    return tag.strip()
        
        # Вариант 3: Если @ не найдены, ищем любые потенциальные теги
        simple_pattern = r'([\w.#\d-]+)'
        matches = re.findall(simple_pattern, content)
        
        if matches:
            # Фильтруем служебные слова и берем самый подходящий тег
            excluded_words = {
                'для', 'вас', 'мск', 'кпп', 'пример', 'example', 'user',
                'пользователь', 'имя', 'фамилия', 'возраст', 'номер',
                'паспорта', 'онлайн', 'часы', 'служить', 'военный'
            }
            
            for potential_tag in matches:
                if (len(potential_tag) > 2 and 
                    potential_tag.lower() not in excluded_words and
                    # Исключаем очень короткие теги (вероятно артефакты)
                    not all(c.isdigit() for c in potential_tag)):
                    logger.info(f"ELEC_APP: Найден Discord-тег (fallback паттерн): {potential_tag}")
                    return potential_tag.strip()
        
        logger.debug(f"ELEC_APP: Теги не найдены ни по основному, ни по fallback паттерну")
        return None
    except Exception as e:
        logger.warning(f"ELEC_APP PARSE ERROR: Ошибка парсинга: {e}")
        return None


def find_user_by_tag(guild: discord.Guild, tag: str) -> Optional[discord.Member]:
    """
    Поиск пользователя на текущем сервере по Discord-тегу
    Поддерживает форматы:
    - @username
    - username
    - username#1234 (старый формат)
    
    Args:
        guild: Discord сервер
        tag: Discord-тег для поиска
        
    Returns:
        Member объект или None
    """
    if not tag:
        return None
    
    tag = tag.strip()
    
    # Вариант 1: Прямой поиск по имени (новый формат без #)
    for member in guild.members:
        if member.name.lower() == tag.lower():
            logger.info(f"ELEC_APP: Пользователь найден по имени: {member.display_name}")
            return member
    
    # Вариант 2: Поиск с discriminator (старый формат username#1234)
    if '#' in tag:
        name_part, disc_part = tag.rsplit('#', 1)
        for member in guild.members:
            if member.name.lower() == name_part.lower() and member.discriminator == disc_part:
                logger.info(f"ELEC_APP: Пользователь найден по имени#disc: {member.display_name}")
                return member
    
    # Вариант 3: Поиск по display_name (ник на сервере)
    for member in guild.members:
        if member.display_name.lower() == tag.lower():
            logger.info(f"ELEC_APP: Пользователь найден по display_name: {member.display_name}")
            return member
    
    logger.warning(f"ELEC_APP: Пользователь не найден на сервере: {tag}")
    return None


def load_template(template_path: str) -> Optional[str]:
    """Загрузка шаблона сообщения из файла"""
    try:
        path = Path(template_path)
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            return content
        else:
            logger.warning(f"ELEC_APP: Файл шаблона не найден: {template_path}")
            return None
    except Exception as e:
        logger.error(f"ELEC_APP: Ошибка загрузки шаблона: {e}")
        return None


def get_application_type(content: str) -> str:
    """
    Определение типа заявки по содержимому
    
    Returns:
        'вступление' или 'восстановление' или 'unknown'
    """
    if "Заявление на восстановление" in content:
        return "восстановление"
    elif "Заявление на вступление" in content:
        return "вступление"
    else:
        return "unknown"
