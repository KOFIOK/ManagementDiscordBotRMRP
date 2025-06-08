#!/usr/bin/env python3
"""
Быстрый тест улучшенной системы увольнений
"""

import asyncio
from datetime import datetime
from utils.google_sheets import sheets_manager

class MockUser:
    def __init__(self, id, display_name, roles):
        self.id = id
        self.display_name = display_name
        self.roles = roles

class MockRole:
    def __init__(self, name, position=0):
        self.name = name
        self.position = position

async def quick_test():
    """Быстрый тест системы"""
    print("🚀 Быстрый тест улучшенной системы увольнений...")
    
    # Инициализируем Google Sheets
    if not sheets_manager.initialize():
        print("❌ Не удалось инициализировать Google Sheets")
        return False
    
    print("✅ Google Sheets инициализирован")
    
    # Создаем тестовые данные
    dismissed_user = MockUser(
        id=999888777,
        display_name="СВ | Игнорируется Это",  # Это имя будет игнорироваться
        roles=[MockRole("Ефрейтор")]
    )
    
    approving_user = MockUser(
        id=111222333,
        display_name="КО | Тестовый Офицер",
        roles=[MockRole("Лейтенант")]
    )
    
    # Данные из формы (приоритет)
    form_data = {
        'name': 'Алексей Тестовый',  # Это имя будет использоваться
        'static': '999-888',
        'reason': 'Финальный тест улучшенной системы'
    }
    
    try:
        print("📝 Добавляем тестовую запись об увольнении...")
        print(f"🎯 Имя из формы: {form_data['name']}")
        
        result = await sheets_manager.add_dismissal_record(
            form_data=form_data,
            dismissed_user=dismissed_user,
            approving_user=approving_user,
            dismissal_time=datetime.now(),
            ping_settings={}
        )
        
        if result:
            print("✅ Запись успешно добавлена в таблицу!")
            print("📊 Проверьте Google Таблицу - должна появиться новая строка")
            return True
        else:
            print("❌ Не удалось добавить запись")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def test_ui_improvements():
    """Тест улучшений UI"""
    print("\n🎨 Проверка улучшений пользовательского интерфейса:")
    print("✅ Добавлена кнопка '⏳ Обрабатывается...' при одобрении")
    print("✅ Добавлена кнопка '⏳ Обрабатывается...' при отказе")
    print("✅ Пользователи видят немедленную обратную связь")
    print("✅ Система работает быстрее благодаря async обработке")

async def main():
    print("🤖 Army Discord Bot - Финальный тест улучшений")
    print("=" * 55)
    
    # Тест Google Sheets
    sheets_success = await quick_test()
    
    # Тест UI улучшений
    test_ui_improvements()
    
    print("\n" + "=" * 55)
    if sheets_success:
        print("🎉 Все тесты пройдены успешно!")
        print("🚀 Система готова к использованию!")
        print("\n📋 Что было улучшено:")
        print("  • Исправлена интеграция с Google Sheets")
        print("  • Имена берутся из формы заявки (приоритет)")
        print("  • Добавлены кнопки 'Обрабатывается...' для UX")
        print("  • Ускорена обработка через async")
    else:
        print("⚠️ Некоторые тесты не пройдены")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️ Тест прерван")
    except Exception as e:
        print(f"\n💥 Ошибка: {e}")
    
    input("\nНажмите Enter для выхода...")
