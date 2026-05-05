from __future__ import annotations

import logging
import shutil
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
LOG_DIR = BASE_DIR / "logs"
SESSION_LOG_DIR = LOG_DIR / "sessions"
APP_LOG_PATH = LOG_DIR / "secure_browser.log"
ERROR_LOG_PATH = LOG_DIR / "secure_browser_errors.log"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


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
    if kind == "all":
        return APP_LOG_PATH
    if kind == "errors":
        return ERROR_LOG_PATH
    raise ValueError(f"Unknown log file kind: {kind}")
