#!/usr/bin/env python3
"""
Тест функциональности редактирования и восстановления заявок склада
"""

import re

def test_item_parsing():
    """Тестируем парсинг предметов из embed поля"""
    
    test_field_value = """1. **AK-74M** × 2
2. **Бронежилет 6Б23-1** × 1
3. **Аптечка войсковая** × 10
4. **Материалы** × 500"""

    items = []
    lines = test_field_value.split('\n')
    
    for line in lines:
        line = line.strip()
        if '×' in line or 'x' in line:
            # Паттерн для строки "1. **название** × количество"
            match = re.match(r'(\d+)\.\s*\*\*(.*?)\*\*\s*[×x]\s*(\d+)', line)
            if match:
                number, item_name, quantity = match.groups()
                items.append((line, item_name.strip(), int(quantity)))
                print(f"✅ Парсинг успешен: '{item_name}' × {quantity}")
            else:
                print(f"❌ Не удалось парсить: '{line}'")
    
    return items

def test_item_parsing_with_deleted():
    """Тестируем парсинг предметов включая удаленные"""
    
    print("\\n=== ТЕСТ ПАРСИНГА С УДАЛЕННЫМИ ПРЕДМЕТАМИ ===")
    
    test_field_value = """❌ ~~1. **AK-74M** × 2~~
2. **Бронежилет 6Б23-1** × 3 *(из 1)*
❌ ~~3. **Аптечка войсковая** × 10~~
4. **Материалы** × 500"""

    items = []
    lines = test_field_value.split('\n')
    
    for line in lines:
        line = line.strip()
        if '×' in line or 'x' in line:
            is_deleted = False
            original_line = line
            
            # Проверяем, удален ли предмет (зачеркнут)
            if line.startswith('❌ ~~') and line.endswith('~~'):
                is_deleted = True
                # Убираем зачеркивание для парсинга
                line = line[5:-2]  # Убираем "❌ ~~" в начале и "~~" в конце
            
            # Извлекаем номер, название и количество
            match = re.match(r'(\d+)\.\s*\*\*(.*?)\*\*\s*[×x]\s*(\d+)', line)
            if match:
                number, item_name, quantity = match.groups()
                status = "УДАЛЕН" if is_deleted else "АКТИВЕН"
                items.append((original_line, item_name.strip(), int(quantity), is_deleted))
                print(f"✅ Парсинг: '{item_name}' × {quantity} [{status}]")
            else:
                # Fallback для измененных количеств
                if '**' in line and ('×' in line or 'x' in line):
                    parts = line.split('**')
                    if len(parts) >= 3:
                        item_name = parts[1].strip()
                        quantity_part = line.split('×')[-1] if '×' in line else line.split('x')[-1]
                        try:
                            quantity_part = quantity_part.split('*')[0].strip()
                            quantity = int(quantity_part.strip())
                            status = "УДАЛЕН" if is_deleted else "АКТИВЕН"
                            items.append((original_line, item_name, quantity, is_deleted))
                            print(f"✅ Fallback парсинг: '{item_name}' × {quantity} [{status}]")
                        except ValueError:
                            print(f"❌ Не удалось парсить количество в: '{line}'")
    
    return items

def test_quantity_update():
    """Тестируем обновление количества в строке"""
    
    original_text = "1. **AK-74M** × 2"
    new_quantity = 5
    old_quantity = 2
    
    # Заменяем количество и добавляем пометку
    match = re.match(r'(\d+\.\s*\*\*.*?\*\*)\s*[×x]\s*(\d+)', original_text)
    if match:
        item_part = match.group(1)
        new_text = f"{item_part} × {new_quantity} *(из {old_quantity})*"
        print(f"✅ Обновление количества: '{original_text}' → '{new_text}'")
        return new_text
    else:
        print(f"❌ Не удалось обновить количество в: '{original_text}'")
        return original_text

def test_item_deletion():
    """Тестируем удаление (зачеркивание) предмета"""
    
    original_text = "2. **Бронежилет 6Б23-1** × 1"
    deleted_text = f"❌ ~~{original_text}~~"
    
    print(f"✅ Удаление предмета: '{original_text}' → '{deleted_text}'")
    return deleted_text

def test_restoration_logic():
    """Тестируем логику восстановления удаленных предметов"""
    
    print("\\n=== ТЕСТ ВОССТАНОВЛЕНИЯ ПРЕДМЕТОВ ===")
    
    # Тестовые данные удаленных предметов
    deleted_items = [
        ("❌ ~~1. **AK-74M** × 2~~", 1),
        ("❌ ~~3. **Аптечка войсковая** × 10~~", 3),
        ("❌ ~~5. **Таурус Бешеный бык** × 1~~", 5),
        ("❌ ~~**Без номера** × 1~~", 2)  # Случай когда номер потерялся
    ]
    
    import re
    
    for deleted_line, expected_index in deleted_items:
        print(f"Удаленная строка: {deleted_line}")
        
        # Логика восстановления (как в коде)
        if deleted_line.startswith('❌ ~~') and deleted_line.endswith('~~'):
            content = deleted_line[5:-2]  # Убираем "❌ ~~" и "~~"
            
            # Если номер потерялся, восстанавливаем его
            if not content.strip().startswith(str(expected_index) + '.'):
                # Проверяем, есть ли номер в начале
                match = re.match(r'^(\d+)\.\s*(.*)$', content.strip())
                if match:
                    # Номер есть, используем его
                    restored_line = content
                else:
                    # Номера нет, добавляем правильный
                    restored_line = f"{expected_index}. {content.strip()}"
            else:
                restored_line = content
                
            print(f"Восстановленная:  {restored_line}")
            print("✅ Восстановление успешно\\n")
        else:
            print("❌ Ошибка: строка не распознана как удаленная\\n")

def test_select_menu_display():
    """Тестируем отображение предметов в Select Menu"""
    
    print("\\n=== ТЕСТ ОТОБРАЖЕНИЯ SELECT MENU ===")
    
    # Тестовые данные (смешанные предметы)
    test_items = [
        ("1. **АК-74М** × 3", "АК-74М", 3, False),
        ("❌ ~~2. **Средний бронежилет** × 2~~", "Средний бронежилет", 2, True),
        ("3. **Таурус Бешеный бык** × 1", "Таурус Бешеный бык", 1, False),
        ("❌ ~~4. **Аптечка войсковая** × 10~~", "Аптечка войсковая", 10, True)
    ]
    
    print("Отображение в Select Menu:")
    for i, (item_text, item_name, quantity, is_deleted) in enumerate(test_items):
        if is_deleted:
            # Удаленный предмет - отображаем с крестиком
            label = f"❌ {i+1}. {item_name}"
            description = f"Удален | Было: {quantity}"
            emoji = "🗑️"
            action = "→ Доступно: ВОССТАНОВИТЬ"
        else:
            # Обычный предмет
            label = f"{i+1}. {item_name}"
            description = f"Количество: {quantity}"
            emoji = "📦"
            action = "→ Доступно: УДАЛИТЬ, ИЗМЕНИТЬ КОЛИЧЕСТВО"
        
        print(f"   {emoji} {label}")
        print(f"      ├─ {description}")
        print(f"      └─ {action}")
        print()

if __name__ == "__main__":
    print("🧪 Тестирование функциональности редактирования заявок склада\n")
    
    print("1. Тест парсинга предметов:")
    items = test_item_parsing()
    print(f"Найдено предметов: {len(items)}\n")
    
    print("2. Тест обновления количества:")
    test_quantity_update()
    print()
    
    print("3. Тест удаления предмета:")
    test_item_deletion()
    print()
    
    print("4. Тест восстановления предметов:")
    test_restoration_logic()
    print()
    
    print("5. Тест отображения в Select Menu:")
    test_select_menu_display()
    print()
    
    print("✅ Все тесты завершены!")
