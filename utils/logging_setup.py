import gzip
import logging
import logging.config
import os
import shutil
from logging.handlers import TimedRotatingFileHandler
from typing import Optional

WARN_LEVEL = logging.WARNING
logging.addLevelName(logging.WARNING, "WARN")
FATAL_LEVEL = logging.CRITICAL
logging.addLevelName(logging.CRITICAL, "FATAL")

class GZipTimedRotatingFileHandler(TimedRotatingFileHandler):
    """Хендлер с ротацией по дате и gzip-сжатием старых файлов."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Добавляем .gz к архивам
        self.namer = lambda name: f"{name}.gz"

    def rotator(self, source: str, dest: str) -> None:
        with open(source, "rb") as src, gzip.open(dest, "wb") as dst:
            shutil.copyfileobj(src, dst)
        os.remove(source)

def setup_logging(level: str = "INFO", log_file: Optional[str] = "logs/app.log") -> None:
    """
    Инициализация централизованного логирования.
    Настройки можно переопределить переменными окружения:
        - LOG_LEVEL: общий уровень (по умолчанию INFO)
        - LOG_CONSOLE_LEVEL: уровень для консоли (по умолчанию LOG_LEVEL)
        - LOG_FILE_LEVEL: уровень для файла (по умолчанию LOG_LEVEL)
        - LOG_FILE: путь к файлу ("" или "none" → отключить файловый хендлер)
        - LOG_BACKUP_COUNT: количество сохраняемых архивов (по умолчанию 14)
    """

    env_level = os.getenv("LOG_LEVEL", level)
    console_level = os.getenv("LOG_CONSOLE_LEVEL", "") or env_level
    file_level = os.getenv("LOG_FILE_LEVEL", "") or env_level
    env_log_file = os.getenv("LOG_FILE", log_file)
    backup_count = int(os.getenv("LOG_BACKUP_COUNT", "14"))
    disable_file = env_log_file is not None and str(env_log_file).strip().lower() in {"", "none", "false"}

    console_format = "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s"
    file_format = "[%(asctime)s] [%(levelname)s] [%(name)s] [%(filename)s:%(lineno)d]: %(message)s"

    handlers = {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "console",
            "level": console_level,
        }
    }

    if not disable_file and env_log_file:
        log_dir = os.path.dirname(env_log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

        handlers["file"] = {
            "class": "utils.logging_setup.GZipTimedRotatingFileHandler",
            "formatter": "file",
            "filename": env_log_file,
            "when": "midnight",
            "backupCount": backup_count,
            "encoding": "utf-8",
            "level": file_level,
        }

    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "console": {"format": console_format},
            "file": {"format": file_format},
        },
        "handlers": handlers,
        "root": {
            "handlers": list(handlers.keys()),
            "level": env_level,
        },
    }

    logging.config.dictConfig(logging_config)


def get_logger(name: str) -> logging.Logger:
    """Получить logger по имени модуля."""
    return logging.getLogger(name)
