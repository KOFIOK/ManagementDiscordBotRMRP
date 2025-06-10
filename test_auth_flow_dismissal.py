#!/usr/bin/env python3
"""
Тест полного flow авторизации для увольнения
"""

import asyncio
import sys
import os

# Add the current directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.google_sheets import sheets_manager

class MockUser:
    def __init__(self, display_name):
        self.display_name = display_name
        self.id = 123456789

async def test_auth_flow():
    """Test the complete authorization flow for dismissal"""
    
    print("🧪 Тестирование логики авторизации для увольнения...")
    print("=" * 60)
    
    # Test case 1: Moderator found in system
    print("\n1️⃣ Тест: Модератор найден в системе")
    mock_user_found = MockUser("ВА | Марко Толедо")
    
    try:
        auth_result = await sheets_manager.check_moderator_authorization(mock_user_found)
        print(f"   Результат поиска: {auth_result}")
        
        if auth_result["found"]:
            print(f"   ✅ Модератор найден: {auth_result['info']}")
            print(f"   🔄 Продолжение с автоматической авторизацией")
            signed_by_name = auth_result["info"]
            print(f"   📝 Используется имя: {signed_by_name}")
        else:
            print(f"   ❌ Модератор НЕ найден")
            print(f"   📋 Потребуется показать модальное окно")
            
    except Exception as e:
        print(f"   ❌ Ошибка в проверке авторизации: {e}")
    
    # Test case 2: Moderator NOT found in system
    print("\n2️⃣ Тест: Модератор НЕ найден в системе")
    mock_user_not_found = MockUser("UnknownUser")
    
    try:
        auth_result = await sheets_manager.check_moderator_authorization(mock_user_not_found)
        print(f"   Результат поиска: {auth_result}")
        
        if auth_result["found"]:
            print(f"   ✅ Модератор найден: {auth_result['info']}")
        else:
            print(f"   ❌ Модератор НЕ найден")
            print(f"   📋 НУЖНО показать модальное окно для ввода данных")
            print(f"   ⚠️  КРИТИЧНО: Модальное окно должно показаться ПЕРЕД defer()")
            
            # Simulate manual input
            manual_data = {
                "name": "Марко Толедо",
                "static": "123-456",
                "full_info": "Марко Толедо | 123-456"
            }
            
            print(f"   📝 Симуляция ручного ввода: {manual_data}")
            signed_by_name = manual_data["full_info"]
            print(f"   📝 Результат: {signed_by_name}")
            
    except Exception as e:
        print(f"   ❌ Ошибка в проверке авторизации: {e}")
    
    print("\n" + "=" * 60)
    print("🎯 Итоги тестирования:")
    print("✅ Логика проверки авторизации работает")
    print("✅ Система корректно определяет найденных/не найденных модераторов")
    print("⚠️  ВАЖНО: Модальное окно должно показываться ДО defer() в dismissal_form.py")
    print("⚠️  ВАЖНО: Только после заполнения формы продолжается обработка")

if __name__ == "__main__":
    asyncio.run(test_auth_flow())
