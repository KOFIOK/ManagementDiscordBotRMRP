"""
Утилита для миграции модулей на централизованное логирование.
Запуск (просмотр):
  python scripts/logging_migration.py --root .

Ключи:
  --root PATH          Корень проекта (по умолчанию текущая папка).
  --report             Показать отчёт по файлам: print(), эмодзи, logging.getLogger и т.д.
  --fix-getlogger      Заменить get_logger(__name__).

Примеры:
  python scripts/logging_migration.py --root . --report
  python scripts/logging_migration.py --root . --fix-getlogger
  python scripts/logging_migration.py --root . --clean-emoji --fix-getlogger

Скрипт безопасен: без флагов только просмотр.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
import sys

# Добавляем корень проекта в sys.path, чтобы импортировать utils из скрипта
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.logging_setup import get_logger

EMOJI_PATTERN = re.compile(r"[\U0001F300-\U0001FAFF]\ufe0f?|||||||||||||")
PRINT_PATTERN = re.compile(r"\bprint\s*\(")
LOGGING_GETLOGGER_PATTERN = re.compile(r"logging\.getLogger\s*\(\s*['\"]?([^'\"]*)['\"]?\s*\)")
GET_LOGGER_PATTERN = re.compile(r"get_logger\s*\(")
IMPORT_PATTERN = re.compile(r"^import logging\b|^from logging", re.MULTILINE)
GET_LOGGER_IMPORT = "from utils.logging_setup import get_logger"

# Initialize logger
logger = get_logger(__name__)

def scan_file(path: Path):
    text = path.read_text(encoding="utf-8", errors="ignore")
    findings = {
        "prints": [],
        "emoji": [],
        "logging_getlogger": False,
        "uses_get_logger": "get_logger(" in text,
    }

    for m in PRINT_PATTERN.finditer(text):
        findings["prints"].append(m.start())
    for m in EMOJI_PATTERN.finditer(text):
        findings["emoji"].append(m.start())
    findings["logging_getlogger"] = bool(LOGGING_GETLOGGER_PATTERN.search(text))
    return findings


def add_get_logger_import(text: str) -> str:
    """Добавляет импорт get_logger после остальных импортов, если его нет."""
    if GET_LOGGER_IMPORT in text:
        return text
    
    # Найдём последний импорт и добавим после него
    last_import_match = None
    for match in re.finditer(r"^(import|from).*$", text, re.MULTILINE):
        last_import_match = match
    
    if last_import_match:
        end_pos = last_import_match.end()
        return text[:end_pos] + f"\n{GET_LOGGER_IMPORT}" + text[end_pos:]
    else:
        # Если импортов нет, добавим в начало после docstring/comments
        return GET_LOGGER_IMPORT + "\n" + text


def fix_logging_getlogger(path: Path) -> bool:
    """Заменяет get_logger(__name__)."""
    text = path.read_text(encoding="utf-8", errors="ignore")
    
    # Заменяем get_logger(__name__)
    new_text = LOGGING_GETLOGGER_PATTERN.sub("get_logger(__name__)", text)
    
    if new_text == text:
        return False  # Нет изменений
    
    # Добавляем импорт если нужно
    if "get_logger(__name__)" in new_text and GET_LOGGER_IMPORT not in new_text:
        new_text = add_get_logger_import(new_text)
    
    path.write_text(new_text, encoding="utf-8")
    return True


def clean_emojis(path: Path):
    text = path.read_text(encoding="utf-8", errors="ignore")
    new_text = EMOJI_PATTERN.sub("", text)
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
        return True
    return False



def main():
    parser = argparse.ArgumentParser(description="Логирование: поиск и упрощение миграции")
    parser.add_argument("--root", default=".", help="Корень проекта")
    parser.add_argument("--report", action="store_true", help="Показать отчёт (по умолчанию включён если нет других флагов)")
    parser.add_argument("--fix-getlogger", action="store_true", help="Заменить get_logger(__name__")
    # ВНИМАНИЕ: --clean-emoji теперь выполняет УМНУЮ очистку (только logger/print)
    parser.add_argument("--clean-emoji", action="store_true", help="Удалить эмодзи только из строк логирования/print (умно)")
    # Опционально: агрессивная очистка всех эмодзи (может сломать UI)
    parser.add_argument("--clean-emoji-aggressive", action="store_true", help="Удалить эмодзи везде (ОПАСНО, может сломать UI)")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    targets = [p for p in root.rglob("*.py") if ".venv" not in p.parts and "__pycache__" not in p.parts]

    # Если ничего не указано, показываем отчёт
    if not args.fix_getlogger and not args.clean_emoji and not args.clean_emoji_aggressive:
        args.report = True

    total = {
        "files": 0,
        "prints": 0,
        "emoji_files": 0,
        "logging_getlogger": 0,
        "fixed_getlogger": 0,
        # По умолчанию считаем умную очистку как cleaned_emoji
        "cleaned_emoji": 0,
        # Для агрессивной очистки отдельный счётчик
        "cleaned_emoji_aggressive": 0,
    }

    for path in targets:
        findings = scan_file(path)
        total["files"] += 1
        total["prints"] += len(findings["prints"])
        if findings["emoji"]:
            total["emoji_files"] += 1
        if findings["logging_getlogger"]:
            total["logging_getlogger"] += 1

        # Обработка флагов
        if args.fix_getlogger and findings["logging_getlogger"]:
            if fix_logging_getlogger(path):
                total["fixed_getlogger"] += 1
                logger.info(f"[fixed] {path.relative_to(root)} - get_logger(__name__) ")

        # Умная очистка: удаляет эмодзи только из строк с logger.* или print(...)
        if args.clean_emoji:
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
                changed = False
                lines = text.splitlines()
                new_lines = []
                for line in lines:
                    if ("logger." in line) or PRINT_PATTERN.search(line):
                        cleaned_line = EMOJI_PATTERN.sub("", line)
                        if cleaned_line != line:
                            changed = True
                        new_lines.append(cleaned_line)
                    else:
                        new_lines.append(line)
                if changed:
                    path.write_text("\n".join(new_lines), encoding="utf-8")
                    total["cleaned_emoji"] += 1
                    logger.info(f"[cleaned] {path.relative_to(root)} - emojis removed only from logger/print lines")
            except Exception:
                # Пропускаем файл при ошибке чтения/записи
                pass

        # Агрессивная очистка: удаляет все эмодзи (может сломать UI)
        if args.clean_emoji_aggressive and findings["emoji"]:
            if clean_emojis(path):
                total["cleaned_emoji_aggressive"] += 1
                logger.info(f"[cleaned-aggressive] {path.relative_to(root)} - removed {len(findings['emoji'])} emojis")

        

        # Отчёт
        if args.report:
            if findings["prints"] or findings["emoji"] or findings["logging_getlogger"]:
                logger.info(f"--- {path.relative_to(root)}")
                if findings["prints"]:
                    logger.info(f"  print(): {len(findings['prints'])}")
                if findings["emoji"]:
                    logger.info(f"  emoji occurrences: {len(findings['emoji'])}")
                if findings["logging_getlogger"]:
                    logger.info("   uses get_logger(__name__)")

    logger.info("\nИтог:")
    logger.info(f"  файлов: {total['files']}")
    logger.info(f"  print(): {total['prints']}")
    logger.info(f"  файлов с эмодзи: {total['emoji_files']}")
    logger.info(f"  get_logger(__name__): {total['logging_getlogger']}")
    if args.fix_getlogger:
        logger.info(f"  исправлено get_logger(__name__): {total['fixed_getlogger']}")
    if args.clean_emoji:
        logger.info(f"  очищено файлов от эмодзи (умно): {total['cleaned_emoji']}")
    if args.clean_emoji_aggressive:
        logger.info(f"  очищено файлов от эмодзи (агрессивно): {total['cleaned_emoji_aggressive']}")


if __name__ == "__main__":
    main()
