"""Быстрое удаление лишних пробелов перед эмодзи в строковых присваиваниях.

Ищет паттерны типа:
  name=" 📊 Статус"  ->  name="📊 Статус"
  title=" ❌ Ошибка"  ->  title="❌ Ошибка"
  label=" ✅ Готово"  ->  label="✅ Готово"

Обрабатывает все варианты кавычек и префиксов строк (f/r/b/u).

Использование:
  python scripts/fix_emoji_spaces.py            # dry-run
  python scripts/fix_emoji_spaces.py --apply    # применить
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parent.parent

# Кастомные Discord эмодзи
CUSTOM_EMOJI_RE = re.compile(r"^<a?:[\w~]+:\d+>")

def starts_with_emoji(text: str) -> bool:
    """Проверка, начинается ли текст с эмодзи (unicode или Discord custom)."""
    if CUSTOM_EMOJI_RE.match(text):
        return True
    return bool(text) and ord(text[0]) > 127


def is_logging_line(text: str) -> bool:
    """Проверка, является ли строка логированием."""
    lower = text.lower()
    return "logger." in lower or "logging." in lower or "print(" in lower


# Паттерн: = [префиксы]" (без захвата пробела)
STRING_ASSIGNMENT_RE = re.compile(
    r"=\s*(?:[fFrRbBuU]{0,3})?([\"\'])"
)


def fix_line(line: str) -> Tuple[str, int]:
    """Удалить лишние пробелы перед эмодзи в строке.
    
    Returns:
        (new_line, changes_count)
    """
    if is_logging_line(line):
        return line, 0

    matches = list(STRING_ASSIGNMENT_RE.finditer(line))
    if not matches:
        return line, 0

    changed = 0
    new_line = line

    # Обрабатываем с конца, чтобы не сбивать индексы
    for match in reversed(matches):
        quote = match.group(1)
        value_start = match.end()  # Позиция сразу после открывающей кавычки
        
        # Найдём закрывающую кавычку
        close_pos = new_line.find(quote, value_start)
        if close_pos == -1:
            continue
        
        # Текущее значение между кавычками
        current_value = new_line[value_start:close_pos]
        
        # Проверяем, что строка начинается с пробела и затем эмодзи
        if not current_value.startswith(" ") or len(current_value) < 2:
            continue
            
        # Проверяем, что после пробела идёт эмодзи
        value_without_space = current_value[1:]  # Убираем первый пробел
        if not starts_with_emoji(value_without_space):
            continue
        
        # Заменяем значение без ведущего пробела
        new_line = new_line[:value_start] + value_without_space + new_line[close_pos:]
        changed += 1
    
    return new_line, changed


def fix_file(path: Path, apply: bool) -> Tuple[int, List[str]]:
    """Обработать один файл.
    
    Returns:
        (total_changes, list_of_changes_description)
    """
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return 0, []

    lines = text.splitlines()
    replacements: List[str] = []
    total = 0

    for i, line in enumerate(lines):
        new_line, inc = fix_line(line)
        if inc:
            replacements.append(f"L{i+1}: {line.strip()[:50]}...")
            lines[i] = new_line
            total += inc

    if apply and total:
        path.write_text("\n".join(lines), encoding="utf-8")

    return total, replacements


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Удаление лишних пробелов перед эмодзи в UI-строках"
    )
    parser.add_argument("--apply", action="store_true", help="Применить изменения")
    args = parser.parse_args()

    total_changed = 0
    total_files = 0

    for path in ROOT.rglob("*.py"):
        posix = path.as_posix()
        # Пропускаем служебные директории
        if any(skip in posix for skip in ["/.venv/", "/backups/", "/__pycache__/", "/scripts/"]):
            continue
            
        changed, replacements = fix_file(path, args.apply)
        if changed:
            total_files += 1
            total_changed += changed
            print(f"{path.relative_to(ROOT)}: {changed} замен")
            for rep in replacements:
                print(f"  {rep}")

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"\nИтого файлов: {total_files}, замен: {total_changed}, режим: {mode}")


if __name__ == "__main__":
    main()
