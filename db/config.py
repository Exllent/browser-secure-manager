from __future__ import annotations

import sqlite3

from app_config import APP_CONFIG

BASE_DIR = APP_CONFIG.paths.base_dir
DB_PATH = APP_CONFIG.paths.db_path
PROFILES_DIR = APP_CONFIG.paths.profiles_dir


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection
