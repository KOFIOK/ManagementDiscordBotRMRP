"""
Скрипт для исправления сравнений field.name после fix_emoji_spaces.py
Добавляет пробел перед эмодзи в сравнениях: field.name == "📊..." -> field.name == " 📊..."
"""
import re
from pathlib import Path
from typing import List, Tuple

# Эмодзи, которые используются в названиях полей
EMOJI_LIST = "📊✅❌⚠️📋ℹ️🔧💼🎖️🏢📦👤🔗📝🎯🔢💬🏗️💡🧪🪖📧🎭👩‍⚕️📌📤🔫🛡️🎉⏰🏛️"

# Паттерн для поиска field.name == "emoji без пробела
FIELD_NAME_PATTERN = re.compile(
    rf'(field\.name\s*==\s*["\'])([{EMOJI_LIST}])',
    re.UNICODE
)

def fix_line(line: str) -> Tuple[str, bool]:
    """
    Исправляет строку, добавляя пробел после кавычки перед эмодзи
    в сравнениях field.name
    
    Returns:
        (исправленная_строка, было_ли_изменение)
    """
    def replacer(match):
        quote = match.group(1)  # field.name == "
        emoji = match.group(2)  # первый символ эмодзи
        return f"{quote} {emoji}"  # Добавляем пробел
    
    new_line, count = FIELD_NAME_PATTERN.subn(replacer, line)
    return new_line, count > 0

def process_file(file_path: Path) -> int:
    """
    Обрабатывает один файл
    
    Returns:
        Количество исправленных строк
    """
    try:
        content = file_path.read_text(encoding='utf-8')
        lines = content.splitlines(keepends=True)
        
        changed_lines = 0
        new_lines = []
        
        for i, line in enumerate(lines, 1):
            new_line, changed = fix_line(line)
            if changed:
                print(f"  Line {i}: {line.strip()[:80]}")
                print(f"      -> {new_line.strip()[:80]}")
                changed_lines += 1
            new_lines.append(new_line)
        
        if changed_lines > 0:
            file_path.write_text(''.join(new_lines), encoding='utf-8')
            try:
                rel_path = file_path.relative_to(Path.cwd())
            except ValueError:
                rel_path = file_path
            print(f"✅ {rel_path}: {changed_lines} изменений")
        
        return changed_lines
        
    except Exception as e:
        print(f"❌ Ошибка при обработке {file_path}: {e}")
        return 0

def main():
    """Основная функция"""
    root = Path(".")
    
    # Обрабатываем только файлы в forms/
    pattern = "forms/**/*.py"
    
    files = [
        f for f in root.glob(pattern)
        if f.is_file() and not any(
            part in f.parts for part in ['__pycache__', '.venv', 'backups']
        )
    ]
    
    print(f"🔍 Найдено {len(files)} файлов для проверки\n")
    
    total_changes = 0
    files_changed = 0
    
    for file_path in sorted(files):
        changes = process_file(file_path)
        if changes > 0:
            total_changes += changes
            files_changed += 1
            print()
    
    print(f"\n{'='*60}")
    print(f"✅ Готово!")
    print(f"📊 Изменено файлов: {files_changed}")
    print(f"📝 Всего исправлений: {total_changes}")

if __name__ == "__main__":
    main()
