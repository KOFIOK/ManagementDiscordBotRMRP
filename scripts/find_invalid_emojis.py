"""Поиск потенциально некорректных emoji в UI-компонентах Discord.

Сценарий сканирует *.py на вхождения параметра emoji= и классифицирует:
- empty: пустая строка (частая причина Invalid Form Body)
- custom: формат <:name:id> или <a:name:id>
- unicode: содержит не-ASCII символы (обычно валидные эмодзи)
- plain_text: только ASCII текст/символы — чаще всего ошибка

Опция --fix-empty заменяет emoji="" на emoji=None.

Пример запуска:
  python scripts/find_invalid_emojis.py
  python scripts/find_invalid_emojis.py --fix-empty
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parent.parent
PY_PATTERN = re.compile(r"emoji\s*=\s*([\"\'])(.*?)\1")
CUSTOM_PATTERN = re.compile(r"<a?:[\w~]+:\d+>")


def classify(value: str) -> str:
    stripped = value.strip()
    if stripped == "":
        return "empty"
    if CUSTOM_PATTERN.fullmatch(stripped):
        return "custom"
    if any(ord(ch) > 127 for ch in stripped):
        return "unicode"
    return "plain_text"


def find_in_file(path: Path) -> List[Tuple[int, str, str]]:
    """Возвращает список (line_no, raw_value, class)."""
    results: List[Tuple[int, str, str]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return results

    for idx, line in enumerate(text.splitlines(), 1):
        for match in PY_PATTERN.finditer(line):
            raw = match.group(2)
            cls = classify(raw)
            results.append((idx, raw, cls))
    return results


def fix_empty(path: Path) -> int:
    """Заменяет emoji="" на emoji=None. Возвращает число замен."""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return 0

    changed = 0

    def replacer(match: re.Match[str]) -> str:
        nonlocal changed
        raw = match.group(2)
        if raw.strip() == "":
            changed += 1
            return "emoji=None"
        return match.group(0)

    new_text = PY_PATTERN.sub(replacer, text)
    if changed:
        path.write_text(new_text, encoding="utf-8")
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description="Сканер emoji параметров в Discord-компонентах")
    parser.add_argument("--root", type=Path, default=ROOT, help="Корень поиска (по умолчанию корень репо)")
    parser.add_argument("--fix-empty", action="store_true", help="Автозаменить emoji=\"\" на emoji=None")
    args = parser.parse_args()

    candidates = []
    total = 0
    for path in args.root.rglob("*.py"):
        if any(part.startswith(".") for part in path.parts):
            continue
        matches = find_in_file(path)
        if matches:
            candidates.append((path, matches))
            total += len(matches)

    print("Найдены emoji-параметры:\n")
    for path, matches in candidates:
        print(f"{path.relative_to(args.root)}")
        for line_no, raw, cls in matches:
            print(f"  L{line_no:05d}: emoji=\"{raw}\" [{cls}]")
        print()

    print(f"Всего вхождений: {total}")

    if args.fix_empty:
        fixed = 0
        for path, _ in candidates:
            fixed += fix_empty(path)
        print(f"Заменено пустых emoji: {fixed}")


if __name__ == "__main__":
    main()
