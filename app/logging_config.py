from __future__ import annotations

import logging
import shutil
import sys
from pathlib import Path

from app_config import APP_CONFIG

BASE_DIR = APP_CONFIG.paths.base_dir
LOG_DIR = APP_CONFIG.paths.logs_dir
SESSION_LOG_DIR = APP_CONFIG.paths.session_logs_dir
APP_LOG_PATH = LOG_DIR / APP_CONFIG.logging.app_log_filename
ERROR_LOG_PATH = LOG_DIR / APP_CONFIG.logging.error_log_filename
LOG_FORMAT = APP_CONFIG.logging.format


def configure_logging(*, extra_handlers: list[logging.Handler] | None = None) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    APP_LOG_PATH.touch(exist_ok=True)
    ERROR_LOG_PATH.touch(exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(logging.INFO)

    formatter = logging.Formatter(LOG_FORMAT)
    handlers: list[logging.Handler] = []
    stream = sys.stderr or sys.__stderr__
    if stream is not None:
        stream_handler = logging.StreamHandler(stream)
        stream_handler.setLevel(logging.INFO)
        handlers.append(stream_handler)

    all_log_handler = logging.FileHandler(APP_LOG_PATH, encoding="utf-8")
    all_log_handler.setLevel(logging.INFO)
    handlers.append(all_log_handler)

    error_log_handler = logging.FileHandler(ERROR_LOG_PATH, encoding="utf-8")
    error_log_handler.setLevel(logging.ERROR)
    handlers.append(error_log_handler)

    if extra_handlers:
        handlers.extend(extra_handlers)

    for handler in handlers:
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)

    logging.captureWarnings(True)


def export_log_file(kind: str, destination: str | Path) -> Path:
    source = log_file_path(kind)
    if not source.exists():
        source.parent.mkdir(parents=True, exist_ok=True)
        source.touch()

    destination_path = Path(destination).expanduser()
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination_path)
    return destination_path


def log_file_path(kind: str) -> Path:
    if kind == APP_CONFIG.logging.all_kind:
        return APP_LOG_PATH
    if kind == APP_CONFIG.logging.errors_kind:
        return ERROR_LOG_PATH
    raise ValueError(f"Unknown log file kind: {kind}")
