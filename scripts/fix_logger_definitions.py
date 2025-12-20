"""
Скрипт для автоматического добавления logger = get_logger(__name__) в файлы.
"""
import re
from pathlib import Path

def fix_logger_definition(path: Path) -> tuple[bool, str]:
    """Добавляет определение logger если его нет."""
    try:
        text = path.read_text(encoding='utf-8', errors='ignore')
    except Exception as e:
        return False, f"Ошибка чтения: {e}"
    
    # Проверяем что есть вызовы logger.*
    has_logger_calls = bool(re.search(r'\blogger\.(info|error|warning|debug|fatal)', text))
    
    if not has_logger_calls:
        return False, "Нет вызовов logger"
    
    # Проверяем что есть определение logger
    has_logger_def = bool(re.search(r'logger\s*=\s*get_logger\(', text))
    
    if has_logger_def:
        return False, "Logger уже определён"
    
    # Проверяем что есть импорт get_logger
    has_import = bool(re.search(r'from utils\.logging_setup import get_logger', text))
    
    if not has_import:
        return False, "Нет импорта get_logger"
    
    # Найдём место после импорта get_logger и добавим определение
    import_match = re.search(r'from utils\.logging_setup import get_logger', text)
    if not import_match:
        return False, "Импорт не найден"
    
    # Ищем конец строки импорта
    import_end = import_match.end()
    next_newline = text.find('\n', import_end)
    
    if next_newline == -1:
        next_newline = len(text)
    
    # Вставляем определение logger после импорта
    logger_def = "\n\n# Initialize logger\nlogger = get_logger(__name__)"
    
    # Проверяем что следующая строка не пустая и не комментарий
    next_line_start = next_newline + 1
    if next_line_start < len(text):
        # Пропускаем пустые строки
        while next_line_start < len(text) and text[next_line_start] == '\n':
            next_line_start += 1
    
    new_text = text[:next_newline] + logger_def + text[next_newline:]
    
    try:
        path.write_text(new_text, encoding='utf-8')
        return True, "Исправлено"
    except Exception as e:
        return False, f"Ошибка записи: {e}"

def main():
    import sys
    # Исправляем кодировку вывода на Windows
    if sys.stdout.encoding and 'utf' not in sys.stdout.encoding.lower():
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    root = Path(".")
    files = [p for p in root.rglob("*.py") 
             if ".venv" not in p.parts and "__pycache__" not in p.parts]
    
    fixed_count = 0
    skipped_count = 0
    
    for path in files:
        success, message = fix_logger_definition(path)
        if success:
            fixed_count += 1
            print(f"✅ {path.relative_to(root)}")
        elif "Нет вызовов logger" in message or "Logger уже определён" in message:
            skipped_count += 1
        else:
            print(f"⚠️ {path.relative_to(root)}: {message}")
    
    print(f"\n✅ Исправлено файлов: {fixed_count}")
    print(f"⏭️ Пропущено (уже OK): {skipped_count}")

if __name__ == "__main__":
    main()
