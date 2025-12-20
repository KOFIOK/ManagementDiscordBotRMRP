"""
Скрипт для автоматического добавления префикса 'f' к строкам с интерполяцией переменных.

Ищет паттерны вида:
    logger.info(f"text {variable} text")
    logger.debug("text {obj.method()} text")
    
И преобразует в:
    logger.info(f"text {variable} text")
    logger.debug(f"text {obj.method()} text")

Исключения:
- Строки с .format() методом (уже форматированные)
- Строки с %s, %d и т.д. (старый стиль форматирования)
- Строки уже с префиксом f, r, b и т.д.

Запуск:
    python scripts/fix_fstrings.py --root . --dry-run     # Просмотр без изменений
    python scripts/fix_fstrings.py --root . --fix         # Применить изменения
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, Tuple

# Добавляем корень проекта в путь для импорта utils
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.logging_setup import get_logger

logger = get_logger(__name__)

# Паттерн для поиска logger вызовов со строками содержащими {}
# Группы: 1=метод logger, 2=весь контент в скобках
LOGGER_PATTERN = re.compile(
    r'logger\.(debug|info|warning|error|critical|fatal)\((.*?)\)',
    re.DOTALL
)

# Паттерн для проверки наличия {} внутри строки
CURLY_BRACES_PATTERN = re.compile(r'\{[^}]*\}')


def has_fstring_interpolation(text: str) -> bool:
    """Проверяет есть ли в строке интерполяция переменных {variable}"""
    return bool(CURLY_BRACES_PATTERN.search(text))


def is_already_fstring(call_text: str) -> bool:
    """Проверяет имеет ли строка уже префикс f, r, b и т.д."""
    # Ищем кавычки после logger.xxx(
    # Может быть: f"...", r"...", b"...", rf"...", fr"..." и т.д.
    quote_patterns = [
        r'\bf["\']',    # f"..." или f'...'
        r'\brf["\']',   # rf"..."
        r'\bfr["\']',   # fr"..."
    ]
    for pattern in quote_patterns:
        if re.search(pattern, call_text, re.IGNORECASE):
            return True
    return False


def uses_format_method(call_text: str) -> bool:
    """Проверяет использует ли строка .format() метод"""
    return '.format(' in call_text


def uses_percent_formatting(text: str) -> bool:
    """Проверяет использует ли строка старый стиль форматирования %s, %d и т.д."""
    # Ищем % после которого идет s, d, f, x и т.д.
    return bool(re.search(r'%[sdifxXoeEgGcr]', text))


def extract_string_literal(call_content: str) -> Tuple[str, int, int] | None:
    """
    Извлекает строковый литерал из содержимого вызова logger.
    
    Возвращает: (строка, начальная_позиция, конечная_позиция) или None
    """
    # Ищем первую строку в кавычках (одинарных или двойных)
    # Может быть многострочная с тройными кавычками
    patterns = [
        (r'"""(.*?)"""', 3, 3),  # Тройные двойные
        (r"'''(.*?)'''", 3, 3),  # Тройные одинарные
        (r'"([^"\\]*(?:\\.[^"\\]*)*)"', 1, 1),  # Двойные
        (r"'([^'\\]*(?:\\.[^'\\]*)*)'", 1, 1),  # Одинарные
    ]
    
    for pattern, prefix_len, suffix_len in patterns:
        match = re.search(pattern, call_content, re.DOTALL)
        if match:
            # Возвращаем: строку, позицию начала кавычек, позицию конца кавычек
            string_content = match.group(1)
            start_pos = match.start()
            end_pos = match.end()
            return string_content, start_pos, end_pos, prefix_len
    
    return None


def should_add_fstring(call_text: str) -> bool:
    """Определяет нужно ли добавлять префикс f к строке"""
    # Извлекаем строку из вызова
    extracted = extract_string_literal(call_text)
    if not extracted:
        return False
    
    string_content, _, _, _ = extracted
    
    # Проверки:
    # 1. Есть ли {} интерполяция
    if not has_fstring_interpolation(string_content):
        return False
    
    # 2. Уже есть f префикс?
    if is_already_fstring(call_text):
        return False
    
    # 3. Использует .format()?
    if uses_format_method(call_text):
        return False
    
    # 4. Использует % форматирование?
    if uses_percent_formatting(string_content):
        return False
    
    return True


def add_fstring_prefix(call_text: str) -> str:
    """Добавляет префикс f к строке в вызове logger"""
    extracted = extract_string_literal(call_text)
    if not extracted:
        return call_text
    
    _, start_pos, end_pos, prefix_len = extracted
    
    # Находим позицию кавычек
    # Вставляем 'f' перед кавычками
    before = call_text[:start_pos]
    string_part = call_text[start_pos:end_pos]
    after = call_text[end_pos:]
    
    # Добавляем f перед кавычками
    # Нужно учесть тройные кавычки
    if prefix_len == 3:
        # Тройные кавычки: """ или '''
        quote_type = string_part[:3]
        new_string = f'f{quote_type}{call_text[start_pos+3:end_pos-3]}{quote_type}'
    else:
        # Обычные кавычки
        quote_type = string_part[0]
        new_string = f'f{quote_type}{call_text[start_pos+1:end_pos-1]}{quote_type}'
    
    return before + new_string + after


def fix_fstrings_in_file(file_path: Path, dry_run: bool = True) -> Tuple[int, List[str]]:
    """
    Исправляет f-строки в файле.
    
    Args:
        file_path: Путь к файлу
        dry_run: Если True, только показывает что будет изменено
        
    Returns:
        (количество_исправлений, список_примеров)
    """
    try:
        text = file_path.read_text(encoding='utf-8', errors='ignore')
    except Exception as e:
        logger.error(f"Ошибка чтения {file_path}: {e}")
        return 0, []
    
    fixes = 0
    examples = []
    new_lines = []
    
    for line_num, line in enumerate(text.split('\n'), 1):
        new_line = line
        
        # Ищем logger вызовы в строке
        for match in LOGGER_PATTERN.finditer(line):
            method = match.group(1)
            call_content = match.group(2)
            full_call = match.group(0)
            
            # Проверяем нужно ли добавлять f
            if should_add_fstring(call_content):
                # Добавляем f префикс
                new_call_content = add_fstring_prefix(call_content)
                new_full_call = f'logger.{method}({new_call_content})'
                
                new_line = new_line.replace(full_call, new_full_call)
                fixes += 1
                
                if len(examples) < 5:  # Показываем первые 5 примеров
                    examples.append(f"  Line {line_num}: {full_call.strip()[:80]}")
                    examples.append(f"       →  {new_full_call.strip()[:80]}")
        
        new_lines.append(new_line)
    
    # Применяем изменения если не dry-run
    if fixes > 0 and not dry_run:
        try:
            new_text = '\n'.join(new_lines)
            file_path.write_text(new_text, encoding='utf-8')
            logger.info(f"✅ Исправлено {fixes} f-строк в {file_path}")
        except Exception as e:
            logger.error(f"❌ Ошибка записи {file_path}: {e}")
            return 0, []
    
    return fixes, examples


def main():
    # Устанавливаем UTF-8 для консоли Windows
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    
    parser = argparse.ArgumentParser(
        description='Автоматическое исправление f-строк в logger вызовах'
    )
    parser.add_argument('--root', default='.', help='Корень проекта')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Показать что будет изменено без применения')
    parser.add_argument('--fix', action='store_true', 
                       help='Применить исправления')
    args = parser.parse_args()
    
    if not args.dry_run and not args.fix:
        print("⚠️  Используйте --dry-run для просмотра или --fix для применения изменений")
        return
    
    root = Path(args.root).resolve()
    targets = [
        p for p in root.rglob('*.py') 
        if '.venv' not in p.parts and '__pycache__' not in p.parts
    ]
    
    total_fixes = 0
    files_with_fixes = 0
    
    mode = "ПРОСМОТР" if args.dry_run else "ПРИМЕНЕНИЕ ИЗМЕНЕНИЙ"
    print(f"\n{'='*60}")
    print(f"РЕЖИМ: {mode}")
    print(f"Сканирование: {len(targets)} файлов")
    print(f"{'='*60}\n")
    
    for file_path in targets:
        fixes, examples = fix_fstrings_in_file(file_path, dry_run=args.dry_run)
        
        if fixes > 0:
            files_with_fixes += 1
            total_fixes += fixes
            
            rel_path = file_path.relative_to(root)
            print(f"\n{rel_path}")
            print(f"   Найдено: {fixes} f-строк без префикса")
            
            if examples:
                print("   Примеры:")
                for example in examples:
                    print(example)
    
    print(f"\n{'='*60}")
    print(f"ИТОГО:")
    print(f"   Файлов с исправлениями: {files_with_fixes}")
    print(f"   Всего исправлений: {total_fixes}")
    
    if args.dry_run and total_fixes > 0:
        print(f"\nДля применения используйте: python scripts/fix_fstrings.py --root . --fix")
    elif not args.dry_run and total_fixes > 0:
        print(f"\nВсе изменения применены!")
    
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
