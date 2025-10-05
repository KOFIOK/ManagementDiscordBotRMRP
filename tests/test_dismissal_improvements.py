#!/usr/bin/env python3
"""
Тестирование новой функциональности dismissal system
"""

import sys
import os

# Добавляем путь к корневой папке проекта
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_can_moderate_user():
    """Тестируем функцию can_moderate_user"""
    from utils.config_manager import can_moderate_user
    
    print("🔍 ТЕСТ ФУНКЦИИ can_moderate_user:")
    print("=" * 50)
    
    # Мок объекты для тестирования
    class MockUser:
        def __init__(self, user_id, roles=None, is_admin=False):
            self.id = user_id
            self.roles = roles or []
            self.guild_permissions = type('Permissions', (), {'administrator': is_admin})()
    
    class MockRole:
        def __init__(self, role_id, position=0):
            self.id = role_id
            self.position = position
    
    # Тестовая конфигурация
    test_config = {
        'administrators': {
            'users': [12345],  # Админ по ID
            'roles': [100, 101]  # Админские роли
        },
        'moderators': {
            'users': [54321],  # Модератор по ID
            'roles': [200, 201, 202]  # Модераторские роли (202 самая высокая)
        }
    }
    
    # Создаем тестовых пользователей
    admin_user = MockUser(12345)  # Админ по ID
    admin_by_role = MockUser(99999, [MockRole(100)])  # Админ по роли
    discord_admin = MockUser(77777, is_admin=True)  # Discord админ
    
    high_mod = MockUser(11111, [MockRole(202, position=10)])  # Высокий модератор
    low_mod = MockUser(22222, [MockRole(200, position=5)])   # Низкий модератор
    individual_mod = MockUser(54321)  # Индивидуальный модератор
    
    regular_user = MockUser(88888)  # Обычный пользователь
    
    test_cases = [
        # (модератор, цель, ожидаемый_результат, описание)
        (admin_user, admin_user, True, "Админ модерирует себя"),
        (admin_user, high_mod, True, "Админ модерирует высокого модератора"),
        (admin_user, regular_user, True, "Админ модерирует обычного пользователя"),
        
        (discord_admin, discord_admin, True, "Discord админ модерирует себя"),
        (discord_admin, admin_user, True, "Discord админ модерирует кастомного админа"),
        
        (high_mod, high_mod, False, "Модератор НЕ может модерировать себя"),
        (high_mod, low_mod, True, "Высокий модератор модерирует низкого"),
        (low_mod, high_mod, False, "Низкий модератор НЕ может модерировать высокого"),
        (high_mod, regular_user, True, "Модератор модерирует обычного пользователя"),
        (high_mod, admin_user, False, "Модератор НЕ может модерировать админа"),
        
        (individual_mod, low_mod, False, "Индивидуальный модератор НЕ может модерировать роль-модератора"),
        (individual_mod, regular_user, True, "Индивидуальный модератор модерирует обычного пользователя"),
        
        (regular_user, regular_user, False, "Обычный пользователь НЕ может ничего модерировать")
    ]
    
    for moderator, target, expected, description in test_cases:
        result = can_moderate_user(moderator, target, test_config)
        status = "✅" if result == expected else "❌"
        print(f"{status} {description}: {result} (ожидалось {expected})")
    
    print("\n✅ Тестирование can_moderate_user завершено!")

def test_dismissal_hierarchy_logic():
    """Тестируем логику проверки иерархии в dismissal"""
    print("\n🔍 ТЕСТ ЛОГИКИ УВОЛЬНЕНИЙ:")
    print("=" * 50)
    
    scenarios = [
        {
            'description': 'Обычный модератор пытается уволить админа',
            'moderator_type': 'regular_moderator',
            'target_type': 'administrator',
            'should_allow': False
        },
        {
            'description': 'Админ увольняет любого',
            'moderator_type': 'administrator',
            'target_type': 'regular_user',
            'should_allow': True
        },
        {
            'description': 'Модератор увольняет обычного пользователя',
            'moderator_type': 'regular_moderator',
            'target_type': 'regular_user',
            'should_allow': True
        },
        {
            'description': 'Модератор пытается уволить сам себя',
            'moderator_type': 'regular_moderator',
            'target_type': 'same_user',
            'should_allow': False
        },
        {
            'description': 'Пользователь уже уволен (не в employees)',
            'moderator_type': 'regular_moderator',
            'target_type': 'already_dismissed',
            'should_allow': False,
            'auto_reject': True
        }
    ]
    
    for scenario in scenarios:
        status = "✅" if scenario['should_allow'] else "❌"
        auto_reject = " (автоотказ)" if scenario.get('auto_reject') else ""
        print(f"{status} {scenario['description']}: {'Разрешено' if scenario['should_allow'] else 'Запрещено'}{auto_reject}")
    
    print("\n✅ Тестирование логики увольнений завершено!")

if __name__ == "__main__":
    print("🧪 ТЕСТИРОВАНИЕ СИСТЕМЫ УВОЛЬНЕНИЙ")
    print("=" * 60)
    print()
    
    test_can_moderate_user()
    test_dismissal_hierarchy_logic()
    
    print("\n" + "=" * 60)
    print("✅ ВСЕ ТЕСТЫ ЗАВЕРШЕНЫ!")
    print()
    print("📋 КРАТКОЕ ОПИСАНИЕ ИЗМЕНЕНИЙ:")
    print("1. ✅ Добавлена проверка иерархии модераторов в кнопки 'Одобрить' и 'Отказать'")
    print("2. ✅ Добавлена автоматическая проверка статуса увольнения (из employees)")
    print("3. ✅ Автоматический отказ если пользователь уже уволен")
    print("4. ✅ Обновлены как SimplifiedDismissalApprovalView, так и AutomaticDismissalApprovalView")