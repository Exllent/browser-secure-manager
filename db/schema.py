from __future__ import annotations

import logging
import sqlite3
from collections.abc import Iterable

from app_config import APP_CONFIG
from models.browser_config import BrowserConfig
from models.session_entry import SessionEntry

from . import config
from .browsers import upsert_browser_config
from .sessions import create_session

logger = logging.getLogger(__name__)


def init_db() -> None:
    logger.info("Opening SQLite storage at %s", config.DB_PATH)
    config.PROFILES_DIR.mkdir(parents=True, exist_ok=True)

    with config.connect() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS sessions
            (
                id
                INTEGER
                PRIMARY
                KEY
                AUTOINCREMENT,
                name
                TEXT
                NOT
                NULL,
                url
                TEXT
                NOT
                NULL,
                browser
                TEXT
                NOT
                NULL,
                profile_path
                TEXT
                NOT
                NULL,
                proxy_id
                INTEGER,
                fingerprint_id
                INTEGER,
                proxy_label
                TEXT
                DEFAULT
                '',
                custom_user_agent
                TEXT
                DEFAULT
                '',
                notes
                TEXT
                DEFAULT
                '',
                window_width
                INTEGER
                DEFAULT
                1280,
                window_height
                INTEGER
                DEFAULT
                800,
                status
                TEXT
                DEFAULT
                'idle'
            )
            """)
        _ensure_session_columns(connection)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS proxy_configs
            (
                id
                INTEGER
                PRIMARY
                KEY
                AUTOINCREMENT,
                label
                TEXT
                DEFAULT
                '',
                host
                TEXT
                NOT
                NULL,
                port
                INTEGER
                NOT
                NULL,
                proxy_type
                TEXT
                DEFAULT
                'socks5',
                username
                TEXT
                DEFAULT
                '',
                password
                TEXT
                DEFAULT
                '',
                enabled
                INTEGER
                DEFAULT
                1
            )
            """)
        _ensure_proxy_columns(connection)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS browser_configs
            (
                id
                INTEGER
                PRIMARY
                KEY
                AUTOINCREMENT,
                key
                TEXT
                NOT
                NULL
                UNIQUE,
                display_name
                TEXT
                NOT
                NULL,
                browser_type
                TEXT
                NOT
                NULL,
                executable_path
                TEXT
                DEFAULT
                '',
                enabled
                INTEGER
                DEFAULT
                1
            )
            """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS fingerprint_profiles
            (
                id
                INTEGER
                PRIMARY
                KEY
                AUTOINCREMENT,
                name
                TEXT
                NOT
                NULL,
                config_json
                TEXT
                NOT
                NULL,
                enabled
                INTEGER
                DEFAULT
                1
            )
            """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS app_settings
            (
                key
                TEXT
                PRIMARY
                KEY,
                value
                TEXT
                NOT
                NULL
            )
            """)
        _seed_default_browser_configs(connection)
        _remove_unsupported_browser_configs(connection)

        count = connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        if count == 0:
            logger.info("Creating demo browser session records")
            for session in _demo_sessions():
                create_session(session, connection=connection)
        logger.info("SQLite storage initialized")


def _seed_default_browser_configs(connection: sqlite3.Connection) -> None:
    config_record = BrowserConfig(
        id=None,
        key=APP_CONFIG.storage.default_browser_key,
        display_name=APP_CONFIG.storage.default_browser_display_name,
        browser_type=APP_CONFIG.storage.default_browser_type,
        executable_path="",
    )
    existing = connection.execute(
        "SELECT id FROM browser_configs WHERE key = ?",
        (config_record.key,),
    ).fetchone()
    if existing is None:
        logger.info("Seeding default browser config '%s'", config_record.key)
        upsert_browser_config(config_record, connection=connection)


def _remove_unsupported_browser_configs(connection: sqlite3.Connection) -> None:
    deleted = connection.execute(
        "DELETE FROM browser_configs WHERE lower(browser_type) != ?",
        (APP_CONFIG.storage.default_browser_type,),
    ).rowcount
    if deleted:
        logger.warning("Removed %s unsupported browser config(s)", deleted)
    connection.execute(
        """
        UPDATE sessions
        SET browser = ?
        WHERE browser NOT IN (SELECT key
        FROM browser_configs)
        """,
        (APP_CONFIG.storage.default_browser_key,),
    )


def _ensure_session_columns(connection: sqlite3.Connection) -> None:
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(sessions)").fetchall()}
    if "proxy_id" not in columns:
        logger.info("Adding missing sessions.proxy_id column")
        connection.execute("ALTER TABLE sessions ADD COLUMN proxy_id INTEGER")
    if "fingerprint_id" not in columns:
        logger.info("Adding missing sessions.fingerprint_id column")
        connection.execute("ALTER TABLE sessions ADD COLUMN fingerprint_id INTEGER")
    if "custom_user_agent" not in columns:
        logger.info("Adding missing sessions.custom_user_agent column")
        connection.execute("ALTER TABLE sessions ADD COLUMN custom_user_agent TEXT DEFAULT ''")


def _ensure_proxy_columns(connection: sqlite3.Connection) -> None:
    columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(proxy_configs)").fetchall()
    }
    if "proxy_type" not in columns:
        logger.info("Adding missing proxy_configs.proxy_type column")
        connection.execute("ALTER TABLE proxy_configs ADD COLUMN proxy_type TEXT DEFAULT 'socks5'")


def _demo_sessions() -> Iterable[SessionEntry]:
    return (
        SessionEntry(
            id=None,
            name=APP_CONFIG.storage.default_session_name,
            url=APP_CONFIG.storage.default_session_url,
            browser=APP_CONFIG.storage.default_browser_key,
            profile_path="",
            proxy_id=None,
            fingerprint_id=None,
            proxy_label=APP_CONFIG.storage.default_session_proxy_label,
            custom_user_agent="",
            notes=APP_CONFIG.storage.default_session_notes,
        ),
    )
