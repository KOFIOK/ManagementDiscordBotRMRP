"""Восстановление ведущих эмодзи по паттерну из старого коммита.

Алгоритм (простой и точный):
- В каждой строке ищем присваивания строк, где сразу после открывающей кавычки стоит пробел:
    паттерны `=" `, `=f" `, а также варианты с `'` и любыми префиксами `f/r/b/u`.
- Берём соответствующую строку из указанного старого коммита и проверяем, было ли
    на этом месте ведущие эмодзи (unicode или кастомный `<:name:id>`).
- Если было — восстанавливаем значение из старого коммита только внутри кавычек.
- Логи (`logger`, `logging`, `print`) и шаблоны/Markdown не трогаем.

Использование:
    python scripts/restore_ui_emoji.py            # dry-run, только отчёт
    python scripts/restore_ui_emoji.py --apply    # применить замены
    python scripts/restore_ui_emoji.py --commit a501a88c284c6f0f9cdd7875f332c4a496a0c44c
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import List, Tuple
import subprocess

ROOT = Path(__file__).resolve().parent.parent
# Коммит, из которого хотим ОТМЕНИТЬ изменения (берём его родителя commit^)
DEFAULT_COMMIT = "25f646fa2832df388d7b95cd4b5d02a58bd26984"


# --- Определение эмодзи и полезные проверки ---
CUSTOM_EMOJI_RE = re.compile(r"^<a?:[\w~]+:\d+>\s*")

def starts_with_emoji(text: str) -> bool:
    if CUSTOM_EMOJI_RE.match(text):
        return True
    return bool(text) and ord(text[0]) > 127


def is_logging_line(text: str) -> bool:
    lower = text.lower()
    return "logger." in lower or "logging." in lower or "print(" in lower


def strip_emoji(text: str) -> str:
    """Удалить из строки все эмодзи (юникод и кастомные)."""
    text = re.sub(r"<a?:[\w~]+:\d+>", "", text)
    return "".join(ch for ch in text if ord(ch) <= 127)


# Любые строковые присваивания с пробелом сразу после кавычки.
# Паттерн ищет: = [префиксы]" пробел... или = [префиксы]' пробел...
STRING_ASSIGNMENT_RE = re.compile(
    r"=\s*(?:[fFrRbBuU]{0,3})?([\"\'])\s"
)


def get_old_lines(commit: str, path: Path) -> List[str]:
    rel = path.relative_to(ROOT)
    try:
        result = subprocess.run(
            ["git", "show", f"{commit}^:{rel.as_posix()}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True,
            encoding="utf-8",
        )
        return result.stdout.splitlines()
    except subprocess.CalledProcessError:
        # запасной вариант: commit~1
        try:
            result = subprocess.run(
                ["git", "show", f"{commit}~1:{rel.as_posix()}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                text=True,
                encoding="utf-8",
            )
            return result.stdout.splitlines()
        except subprocess.CalledProcessError:
            return []


def is_template_or_md(value: str) -> bool:
    t = value.strip().lower()
    if not t:
        return True
    if t.startswith("##") or t.startswith("{"):
        return True
    if any(p in t for p in ["{emoji", "{role_status", "{role_info"]):
        return True
    return False


def process_line_with_old(line: str, old_lines: List[str], line_index: int) -> Tuple[str, int]:
    if is_logging_line(line):
        return line, 0

    # Ищем все присваивания с пробелом после кавычки
    matches = list(STRING_ASSIGNMENT_RE.finditer(line))
    if not matches:
        return line, 0

    changed = 0
    new_line = line
    
    # Обрабатываем с конца, чтобы не сбивать индексы
    for match in reversed(matches):
        quote = match.group(1)
        # Позиция начала значения (после кавычки и пробела)
        value_start = match.end()
        
        # Найдём закрывающую кавычку (простой поиск)
        close_pos = new_line.find(quote, value_start)
        if close_pos == -1:
            continue
            
        # Текущее значение между кавычками (с ведущим пробелом)
        current_value = new_line[value_start:close_pos]
        
        # Пропускаем шаблоны и Markdown
        if is_template_or_md(current_value):
            continue
        
        # Префикс до кавычки (включая =, пробелы, префиксы строк)
        prefix_start = match.start()
        prefix = new_line[prefix_start:match.start(1)]
        
        # Ищем соответствие в старом файле
        candidate = None
        
        # 1) Попытка по той же строке
        old_line = old_lines[line_index] if 0 <= line_index < len(old_lines) else ""
        if old_line:
            pos = old_line.find(prefix)
            if pos != -1:
                # Ищем значение после префикса+кавычка (с потенциальным пробелом или эмодзи)
                pattern = re.escape(prefix) + re.escape(quote) + r"(.+?)" + re.escape(quote)
                mm = re.search(pattern, old_line[pos:])
                if mm:
                    candidate = mm.group(1)
        
        # 2) Глобальный поиск по всему файлу
        if candidate is None:
            # Нормализуем для поиска - убираем эмодзи
            search_line = strip_emoji(line)
            for ol in old_lines:
                if strip_emoji(ol) == search_line:
                    pos = ol.find(prefix)
                    if pos != -1:
                        pattern = re.escape(prefix) + re.escape(quote) + r"(.+?)" + re.escape(quote)
                        mm = re.search(pattern, ol[pos:])
                        if mm:
                            candidate = mm.group(1)
                            break
        
        if candidate is None:
            continue
        
        # Проверяем, есть ли ведущий эмодзи в старом значении
        if not starts_with_emoji(candidate):
            continue
        
        # Убираем ведущий пробел перед эмодзи, если он есть
        if candidate.startswith(" ") and len(candidate) > 1 and starts_with_emoji(candidate[1:]):
            candidate = candidate[1:]
        
        # Заменяем текущее значение на старое
        new_line = new_line[:value_start] + candidate + new_line[close_pos:]
        changed += 1
    
    return new_line, changed


def restore_file(path: Path, commit: str, apply: bool) -> Tuple[int, List[str]]:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return 0, []

    lines = text.splitlines()
    old_lines = get_old_lines(commit, path)
    replacements: List[str] = []
    total = 0

    for i, line in enumerate(lines):
        new_line, inc = process_line_with_old(line, old_lines, i)
        if inc:
            replacements.append(f"L{i+1}: {line.strip()[:40]} -> {new_line.strip()[:40]}")
            lines[i] = new_line
            total += inc

    if apply and total:
        path.write_text("\n".join(lines), encoding="utf-8")

    return total, replacements


def main() -> None:
    parser = argparse.ArgumentParser(description="Восстановление ведущих эмодзи из старого коммита")
    parser.add_argument("--apply", action="store_true", help="Применить изменения")
    parser.add_argument("--commit", default=DEFAULT_COMMIT, help="SHA коммита, чьи изменения нужно отменить (будет использован его родитель commit^)")
    args = parser.parse_args()

    total_changed = 0
    total_files = 0

    for path in ROOT.rglob("*.py"):
        posix = path.as_posix()
        if "/.venv/" in posix or "/backups/" in posix or "/__pycache__/" in posix or "/scripts/" in posix:
            # скрипты не трогаем, чтобы не портить отчёты/тексты
            continue
        changed, replacements = restore_file(path, args.commit, args.apply)
        if changed:
            total_files += 1
            total_changed += changed
            print(f"{path.relative_to(ROOT)}: {changed} замен")
            for rep in replacements:
                print(f"  {rep}")

    print(f"\nИтого файлов: {total_files}, замен: {total_changed}, режим: {'APPLY' if args.apply else 'DRY-RUN'}")


if __name__ == "__main__":
    main()
