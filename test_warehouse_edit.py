#!/usr/bin/env python3
"""
Тест функциональности редактирования заявок склада
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
    
    print("✅ Все тесты завершены!")
