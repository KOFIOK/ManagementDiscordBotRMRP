"""
Скрипт для исправления синтаксических ошибок, которые оставил print_to_logger.py
Исправляет:
1. Недопарные скобки в f-strings
2. Неправильные преобразования logger вызовов
"""
from pathlib import Path
import re

def fix_syntax_errors(file_path: Path) -> tuple[bool, str]:
    """Исправляет синтаксические ошибки в файле."""
    try:
        text = file_path.read_text(encoding='utf-8', errors='ignore')
    except Exception as e:
        return False, f"Ошибка чтения: {e}"
    
    original_text = text
    
    # ИСПРАВЛЕНИЕ 1: Недопарные скобки в logger вызовах
    # Например: logger.info("msg {var.method("...") → logger.info(f"msg {var.method('...')}")
    # Паттерн: logger.LEVEL("...(.*?['\"].*?['\"])
    
    # ИСПРАВЛЕНИЕ 2: Неправильно закрытые f-strings с методами
    # Например: logger.info("msg {var.get('key")}")  → logger.info(f"msg {var.get('key')}")
    fixes_applied = 0
    
    # Исправление logger.info("msg {expr")} → logger.info(f"msg {expr}")
    pattern1 = re.compile(r'logger\.(info|error|warning|debug)\("([^"]*)\{([^}]*)["\'](\)})"', re.MULTILINE)
    if pattern1.search(text):
        text = pattern1.sub(r'logger.\1(f"\2{\3}")', text)
        fixes_applied += 1
    
    # Исправление logger.info("msg {expr"}) → logger.info(f"msg {expr}")
    # Для случаев где закрывающая скобка на новой строке
    pattern2 = re.compile(r'logger\.(info|error|warning|debug)\((["\'])([^"\']*)\{([^}]*)["\']([}\)])', re.MULTILINE)
    if pattern2.search(text):
        # Нужно быть осторожнее здесь
        pass
    
    # Исправление 3: Незакрытые скобки в get() вызовах
    # Например: {personnel_data.get('name")}")  → {personnel_data.get('name')})
    pattern3 = re.compile(r"(\{[^}]*\.get\(['\"])(\w+)['\"])([})])", re.MULTILINE)
    if pattern3.search(text):
        text = pattern3.sub(r"\1\2\3", text)
        fixes_applied += 1
    
    # Исправление 4: logger = get_logger(__name__): заменить на logger = get_logger(__name__)
    pattern4 = re.compile(r'(logger\s*=\s*get_logger\([^)]+)\):', re.MULTILINE)
    if pattern4.search(text):
        text = pattern4.sub(r'\1)', text)
        fixes_applied += 1
    
    if text != original_text:
        try:
            file_path.write_text(text, encoding='utf-8')
            return True, f"Применено {fixes_applied} исправлений"
        except Exception as e:
            return False, f"Ошибка записи: {e}"
    
    return False, "Нет ошибок"


def main():
    root = Path(".")
    files_to_check = list(root.rglob("*.py"))
    
    fixed_count = 0
    for file_path in files_to_check:
        if ".venv" in file_path.parts or "__pycache__" in file_path.parts:
            continue
        
        success, message = fix_syntax_errors(file_path)
        if success:
            fixed_count += 1
            print(f"✅ {file_path.relative_to(root)}: {message}")
    
    print(f"\n✅ Исправлено файлов: {fixed_count}")


if __name__ == "__main__":
    main()
