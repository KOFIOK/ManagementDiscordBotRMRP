#!/usr/bin/env python3
"""
Тестовый скрипт для интеграции с Google Таблицами
Запустите это, чтобы проверить настройку Google Sheets перед запуском основного бота
"""

import asyncio
import sys
import os
from utils.google_sheets import sheets_manager

async def test_google_sheets():
    """Тестирование подключения к Google Таблицам и базовой функциональности."""
    print("🔍 Тестирование интеграции с Google Таблицами...")
      # Тест инициализации
    print("\n1️⃣ Тестирование инициализации...")
    success = sheets_manager.initialize()
    
    if not success:
        print("❌ Инициализация Google Таблиц не удалась!")
        print("\nПожалуйста, проверьте:")
        print("1. Файл credentials.json существует и действителен")
        print("2. Сервисный аккаунт имеет доступ к таблице")
        print("3. ID таблицы правильный")
        return False
    
    print("✅ Google Таблицы успешно инициализированы!")
    
    # Тест доступа к листу
    print("\n2️⃣ Тестирование доступа к листу...")
    if sheets_manager.worksheet:
        print(f"✅ Подключен к листу: {sheets_manager.worksheet.title}")
        
        # Получаем базовую информацию о листе
        try:
            row_count = sheets_manager.worksheet.row_count
            col_count = sheets_manager.worksheet.col_count
            print(f"📊 Размер листа: {row_count} строк x {col_count} столбцов")
            
            # Получаем заголовки для проверки структуры
            headers = sheets_manager.worksheet.row_values(1)
            print(f"📋 Найдено заголовков: {len(headers)} столбцов")
            for i, header in enumerate(headers[:5], 1):  # Показываем первые 5 заголовков
                print(f"   Столбец {i}: {header}")
            
        except Exception as e:
            print(f"⚠️ Предупреждение: Не удалось прочитать детали листа: {e}")
    else:
        print("❌ Лист не подключен!")
        return False
    
    print("\n✅ Тест Google Таблиц завершен успешно!")
    print("🚀 Теперь вы можете запустить основного бота с интеграцией Google Таблиц.")
    return True

async def main():
    """Основная тестовая функция."""
    print("🤖 Army Discord Bot - Тест Google Таблиц")
    print("=" * 50)
    
    # Проверяем наличие учетных данных
    if not os.path.exists('credentials.json') and not os.getenv('GOOGLE_CREDENTIALS_JSON'):
        print("❌ Учетные данные Google не найдены!")
        print("\nПожалуйста:")
        print("1. Поместите файл credentials.json в папку бота, ИЛИ")
        print("2. Установите переменную окружения GOOGLE_CREDENTIALS_JSON")
        print("\nСм. google_sheets_setup.md для подробных инструкций.")
        return
    
    success = await test_google_sheets()
    
    if success:
        print("\n🎉 Все тесты пройдены! Интеграция с Google Таблицами готова.")
    else:
        print("\n💥 Тесты не пройдены! Пожалуйста, проверьте вашу конфигурацию.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️ Тест прерван пользователем")
    except Exception as e:
        print(f"\n💥 Тест завершился с ошибкой: {e}")
    
    input("\nНажмите Enter для выхода...")
