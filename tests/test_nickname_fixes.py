#!/usr/bin/env python3
"""
Тестирование nickname_manager после исправлений
"""

import sys
import os
import asyncio

# Добавляем путь к корневой папке проекта
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.nickname_manager import NicknameManager

def test_parse_nickname():
    """Тестируем парсинг никнейма"""
    manager = NicknameManager()
    
    test_cases = [
        # Стандартные форматы с рангами
        "DM | Марко Туалетто",
        "УВП | Мл. С-т | Иван Петров", 
        "ВА | Рядовой | А. Сидоров",
        
        # Должностные форматы с квадратными скобками
        "[Командир] И.Иванов",
        "[Нач. Штаба] А.Тимонов",
        "[Ком. Бриг] В.Задорожный",
        
        # Должностные форматы в стандартном виде (должность вместо ранга)
        "ВК | Зам. Нач. по КР | В. Карпов",
        "УВП | Нач. Отдела | И. Петров",
        "ГШ | Ком. Бриг | А. Сидоров",
        "МР | Зам. Нач. | Петр Иванов",
        
        # Особые форматы - простые
        "! Влад Задорожный",
        "! Имя Иванов",
        "!   Петр   Сидоров",
        
        # Особые форматы - сложные
        "!![Комиссар] Имя Иванов",
        "![Нач. Штаба] А.Тимонов", 
        "!![Ком. Бриг] В.Задорожный",
        "!!![Генерал] Максим Громов",
        
        # Простые форматы
        "Простое Имя",
        "А. Сидоров",
        "Очень Длинное Имя",
        
        # Уволенные
        "Уволен | Петр Сидоров",
        "Уволен | И. Иванов"
    ]
    
    print("🔍 ТЕСТ ПАРСИНГА НИКНЕЙМОВ:")
    print("=" * 50)
    
    for nickname in test_cases:
        parsed = manager.parse_nickname(nickname)
        print(f"Никнейм: '{nickname}'")
        print(f"  📋 Формат: {parsed['format_type']}")
        print(f"  🏢 Подразделение: {parsed['subdivision']}")
        print(f"  🎖️ Ранг: {parsed['rank']}")
        print(f"  👤 Имя: {parsed['name']}")
        print(f"  🔒 Особый: {parsed['is_special']}")
        print()

def test_extract_name_parts():
    """Тестируем извлечение имени и фамилии"""
    manager = NicknameManager()
    
    test_names = [
        "Марко Туалетто",
        "Иван Петров",
        "А. Сидоров",
        "И.Иванов",
        "Имя Иванов",
        "Имя Иванов",
        "Простое Имя",
        "Очень Длинное Составное Имя"
    ]
    
    print("🔍 ТЕСТ ИЗВЛЕЧЕНИЯ ИМЕН:")
    print("=" * 50)
    
    for name in test_names:
        first_name, last_name = manager.extract_name_parts(name)
        print(f"Полное имя: '{name}'")
        print(f"  👤 Имя: '{first_name}'")
        print(f"  👥 Фамилия: '{last_name}'")
        print()

def test_build_nickname():
    """Тестируем построение никнейма"""
    manager = NicknameManager()
    
    test_cases = [
        ("ВА", "Мл. Л-т", "Марко", "Туалетто"),
        ("УВП", "Мл. С-т", "Марко", "Туалетто"),
        ("DM", "", "Иван", "Петров"),
        ("", "Рядовой", "Петр", "Сидоров"),
        ("УВП", "Очень Длинный Ранг", "Очень", "Длинная Фамилия")
    ]
    
    print("🔍 ТЕСТ ПОСТРОЕНИЯ НИКНЕЙМОВ:")
    print("=" * 50)
    
    for subdivision, rank, first_name, last_name in test_cases:
        nickname = manager.build_service_nickname(subdivision, rank, first_name, last_name)
        print(f"Входные данные:")
        print(f"  🏢 Подразделение: '{subdivision}'")
        print(f"  🎖️ Ранг: '{rank}'")
        print(f"  👤 Имя: '{first_name} {last_name}'")
        print(f"Результат: '{nickname}' (длина: {len(nickname)})")
        print()

def test_preview_nickname_change():
    """Тестируем предварительный просмотр"""
    manager = NicknameManager()
    
    current_nickname = "DM | Марко Туалетто"
    
    print("🔍 ТЕСТ ПРЕДВАРИТЕЛЬНОГО ПРОСМОТРА:")
    print("=" * 50)
    print(f"Текущий никнейм: '{current_nickname}'")
    print()
    
    # Тест повышения
    preview = manager.preview_nickname_change(
        current_nickname, 
        'promotion',
        rank_abbr='Мл. Л-т'
    )
    print(f"Повышение до 'Мл. Л-т': '{preview}'")
    
    # Тест увольнения
    preview = manager.preview_nickname_change(
        current_nickname,
        'dismissal'
    )
    print(f"Увольнение: '{preview}'")
    print()

if __name__ == "__main__":
    print("🧪 ТЕСТИРОВАНИЕ NICKNAME_MANAGER")
    print("=" * 60)
    print()
    
    test_parse_nickname()
    test_extract_name_parts()
    test_build_nickname()
    test_preview_nickname_change()
    
    print("✅ Тестирование завершено!")