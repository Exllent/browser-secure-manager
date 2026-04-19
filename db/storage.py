from __future__ import annotations

import logging
import json
import sqlite3
from pathlib import Path
import re
from typing import Iterable

from models.browser_config import BrowserConfig
from models.fingerprint_config import FingerprintConfig
from models.fingerprint_profile import FingerprintProfile
from models.proxy_config import ProxyConfig
from models.session_entry import SessionEntry

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "sessions.sqlite3"
PROFILES_DIR = BASE_DIR / "profiles"


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def _row_to_session(row: sqlite3.Row) -> SessionEntry:
    return SessionEntry(
        id=row["id"],
        name=row["name"],
        url=row["url"],
        browser=row["browser"],
        profile_path=row["profile_path"],
        proxy_id=row["proxy_id"],
        fingerprint_id=row["fingerprint_id"],
        proxy_label=row["proxy_label"],
        custom_user_agent=row["custom_user_agent"],
        notes=row["notes"],
        window_width=row["window_width"],
        window_height=row["window_height"],
        status=row["status"],
    )


def _row_to_browser_config(row: sqlite3.Row) -> BrowserConfig:
    return BrowserConfig(
        id=row["id"],
        key=row["key"],
        display_name=row["display_name"],
        browser_type=row["browser_type"],
        executable_path=row["executable_path"],
        enabled=bool(row["enabled"]),
    )


def _row_to_proxy_config(row: sqlite3.Row) -> ProxyConfig:
    return ProxyConfig(
        id=row["id"],
        label=row["label"],
        host=row["host"],
        port=row["port"],
        proxy_type=row["proxy_type"],
        username=row["username"],
        password=row["password"],
        enabled=bool(row["enabled"]),
    )


def _row_to_fingerprint_profile(row: sqlite3.Row) -> FingerprintProfile:
    return FingerprintProfile(
        id=row["id"],
        name=row["name"],
        config=_fingerprint_config_from_json(row["config_json"]),
        enabled=bool(row["enabled"]),
    )


def _fingerprint_config_from_json(config_json: str) -> FingerprintConfig:
    try:
        data = json.loads(config_json)
    except json.JSONDecodeError:
        logger.exception("Invalid fingerprint config JSON")
        return FingerprintConfig()

    if not isinstance(data, dict):
        return FingerprintConfig()

    try:
        return FingerprintConfig.from_dict(data)
    except TypeError:
        logger.exception("Invalid fingerprint config fields")
        return FingerprintConfig()


def default_profile_path(session_id: int) -> str:
    return str(PROFILES_DIR / f"session_{session_id}")


def normalize_profile_path(profile_path: str, session_id: int) -> str:
    raw_path = profile_path.strip()
    path = Path(raw_path).expanduser() if raw_path else Path(default_profile_path(session_id))
    if not path.is_absolute():
        path = BASE_DIR / path
    return str(path)


def init_db() -> None:
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)

    with _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                browser TEXT NOT NULL,
                profile_path TEXT NOT NULL,
                proxy_id INTEGER,
                fingerprint_id INTEGER,
                proxy_label TEXT DEFAULT '',
                custom_user_agent TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                window_width INTEGER DEFAULT 1280,
                window_height INTEGER DEFAULT 800,
                status TEXT DEFAULT 'idle'
            )
            """
        )
        _ensure_session_columns(connection)
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS proxy_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                label TEXT DEFAULT '',
                host TEXT NOT NULL,
                port INTEGER NOT NULL,
                proxy_type TEXT DEFAULT 'socks5',
                username TEXT DEFAULT '',
                password TEXT DEFAULT '',
                enabled INTEGER DEFAULT 1
            )
            """
        )
        _ensure_proxy_columns(connection)
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS browser_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                browser_type TEXT NOT NULL,
                executable_path TEXT DEFAULT '',
                enabled INTEGER DEFAULT 1
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS fingerprint_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                config_json TEXT NOT NULL,
                enabled INTEGER DEFAULT 1
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        _seed_default_browser_configs(connection)
        _remove_unsupported_browser_configs(connection)

        count = connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        if count == 0:
            logger.info("Creating demo browser session records")
            for session in _demo_sessions():
                create_session(session, connection=connection)


def _seed_default_browser_configs(connection: sqlite3.Connection) -> None:
    for config in (
        BrowserConfig(
            id=None,
            key="chrome",
            display_name="Chrome / Chromium",
            browser_type="chromium",
            executable_path="",
        ),
    ):
        existing = connection.execute(
            "SELECT id FROM browser_configs WHERE key = ?",
            (config.key,),
        ).fetchone()
        if existing is None:
            upsert_browser_config(config, connection=connection)


def _remove_unsupported_browser_configs(connection: sqlite3.Connection) -> None:
    connection.execute(
        "DELETE FROM browser_configs WHERE lower(browser_type) != 'chromium'"
    )
    connection.execute(
        """
        UPDATE sessions
        SET browser = 'chrome'
        WHERE browser NOT IN (SELECT key FROM browser_configs)
        """
    )


def _ensure_session_columns(connection: sqlite3.Connection) -> None:
    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(sessions)").fetchall()
    }
    if "proxy_id" not in columns:
        connection.execute("ALTER TABLE sessions ADD COLUMN proxy_id INTEGER")
    if "fingerprint_id" not in columns:
        connection.execute("ALTER TABLE sessions ADD COLUMN fingerprint_id INTEGER")
    if "custom_user_agent" not in columns:
        connection.execute(
            "ALTER TABLE sessions ADD COLUMN custom_user_agent TEXT DEFAULT ''"
        )


def _ensure_proxy_columns(connection: sqlite3.Connection) -> None:
    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(proxy_configs)").fetchall()
    }
    if "proxy_type" not in columns:
        connection.execute(
            "ALTER TABLE proxy_configs ADD COLUMN proxy_type TEXT DEFAULT 'socks5'"
        )


def _demo_sessions() -> Iterable[SessionEntry]:
    return (
        SessionEntry(
            id=None,
            name="Chrome demo",
            url="https://www.python.org",
            browser="chrome",
            profile_path="",
            proxy_id=None,
            fingerprint_id=None,
            proxy_label="local profile",
            custom_user_agent="",
            notes="Demo Chrome session with its own browser profile.",
        ),
    )


def get_all_sessions() -> list[SessionEntry]:
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT id, name, url, browser, profile_path, proxy_id, proxy_label,
                   fingerprint_id, custom_user_agent, notes,
                   window_width, window_height, status
            FROM sessions
            ORDER BY id
            """
        ).fetchall()
    return [_row_to_session(row) for row in rows]


def get_fingerprint_profiles(*, enabled_only: bool = False) -> list[FingerprintProfile]:
    where = "WHERE enabled = 1" if enabled_only else ""
    with _connect() as connection:
        rows = connection.execute(
            f"""
            SELECT id, name, config_json, enabled
            FROM fingerprint_profiles
            {where}
            ORDER BY name COLLATE NOCASE, id
            """
        ).fetchall()
    return [_row_to_fingerprint_profile(row) for row in rows]


def get_fingerprint_profile(fingerprint_id: int | None) -> FingerprintProfile | None:
    if fingerprint_id is None:
        return None
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT id, name, config_json, enabled
            FROM fingerprint_profiles
            WHERE id = ?
            """,
            (fingerprint_id,),
        ).fetchone()
    return _row_to_fingerprint_profile(row) if row else None


def upsert_fingerprint_profile(
    profile: FingerprintProfile,
    *,
    connection: sqlite3.Connection | None = None,
) -> FingerprintProfile:
    owns_connection = connection is None
    active_connection = connection or _connect()
    name = profile.display_name()
    errors = profile.config.validate()
    if errors:
        raise ValueError("; ".join(errors))
    config_json = json.dumps(profile.config.to_dict(), ensure_ascii=False, sort_keys=True)

    try:
        if profile.id is None:
            cursor = active_connection.execute(
                """
                INSERT INTO fingerprint_profiles (name, config_json, enabled)
                VALUES (?, ?, ?)
                """,
                (name, config_json, int(profile.enabled)),
            )
            profile_id = int(cursor.lastrowid)
        else:
            active_connection.execute(
                """
                UPDATE fingerprint_profiles
                SET name = ?,
                    config_json = ?,
                    enabled = ?
                WHERE id = ?
                """,
                (name, config_json, int(profile.enabled), profile.id),
            )
            profile_id = profile.id

        if owns_connection:
            active_connection.commit()
    finally:
        if owns_connection:
            active_connection.close()

    return FingerprintProfile(
        id=profile_id,
        name=name,
        config=profile.config,
        enabled=profile.enabled,
    )


def delete_fingerprint_profile(fingerprint_id: int) -> None:
    with _connect() as connection:
        connection.execute("DELETE FROM fingerprint_profiles WHERE id = ?", (fingerprint_id,))
        connection.execute(
            "UPDATE sessions SET fingerprint_id = NULL WHERE fingerprint_id = ?",
            (fingerprint_id,),
        )


def get_proxy_configs(*, enabled_only: bool = False) -> list[ProxyConfig]:
    where = "WHERE enabled = 1" if enabled_only else ""
    with _connect() as connection:
        rows = connection.execute(
            f"""
            SELECT id, label, host, port, proxy_type, username, password, enabled
            FROM proxy_configs
            {where}
            ORDER BY label COLLATE NOCASE, host COLLATE NOCASE, port
            """
        ).fetchall()
    return [_row_to_proxy_config(row) for row in rows]


def get_proxy_config(proxy_id: int | None) -> ProxyConfig | None:
    if proxy_id is None:
        return None
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT id, label, host, port, proxy_type, username, password, enabled
            FROM proxy_configs
            WHERE id = ?
            """,
            (proxy_id,),
        ).fetchone()
    return _row_to_proxy_config(row) if row else None


def upsert_proxy_config(
    proxy: ProxyConfig,
    *,
    connection: sqlite3.Connection | None = None,
) -> ProxyConfig:
    owns_connection = connection is None
    active_connection = connection or _connect()

    try:
        if proxy.id is None:
            cursor = active_connection.execute(
                """
                INSERT INTO proxy_configs (
                    label, host, port, proxy_type, username, password, enabled
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    proxy.label.strip(),
                    proxy.host.strip(),
                    proxy.port,
                    proxy.normalized_type(),
                    proxy.username.strip(),
                    proxy.password,
                    int(proxy.enabled),
                ),
            )
            proxy_id = int(cursor.lastrowid)
        else:
            active_connection.execute(
                """
                UPDATE proxy_configs
                SET label = ?,
                    host = ?,
                    port = ?,
                    proxy_type = ?,
                    username = ?,
                    password = ?,
                    enabled = ?
                WHERE id = ?
                """,
                (
                    proxy.label.strip(),
                    proxy.host.strip(),
                    proxy.port,
                    proxy.normalized_type(),
                    proxy.username.strip(),
                    proxy.password,
                    int(proxy.enabled),
                    proxy.id,
                ),
            )
            proxy_id = proxy.id

        if owns_connection:
            active_connection.commit()
    finally:
        if owns_connection:
            active_connection.close()

    return ProxyConfig(
        id=proxy_id,
        label=proxy.label.strip(),
        host=proxy.host.strip(),
        port=proxy.port,
        proxy_type=proxy.normalized_type(),
        username=proxy.username.strip(),
        password=proxy.password,
        enabled=proxy.enabled,
    )


def delete_proxy_config(proxy_id: int) -> None:
    with _connect() as connection:
        connection.execute("DELETE FROM proxy_configs WHERE id = ?", (proxy_id,))
        connection.execute("UPDATE sessions SET proxy_id = NULL WHERE proxy_id = ?", (proxy_id,))


def get_browser_configs(*, enabled_only: bool = False) -> list[BrowserConfig]:
    where = "WHERE enabled = 1" if enabled_only else ""
    with _connect() as connection:
        rows = connection.execute(
            f"""
            SELECT id, key, display_name, browser_type, executable_path, enabled
            FROM browser_configs
            {where}
            ORDER BY display_name COLLATE NOCASE
            """
        ).fetchall()
    return [_row_to_browser_config(row) for row in rows]


def get_browser_config(key: str) -> BrowserConfig | None:
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT id, key, display_name, browser_type, executable_path, enabled
            FROM browser_configs
            WHERE key = ?
            """,
            (key,),
        ).fetchone()
    return _row_to_browser_config(row) if row else None


def upsert_browser_config(
    config: BrowserConfig,
    *,
    connection: sqlite3.Connection | None = None,
) -> BrowserConfig:
    owns_connection = connection is None
    active_connection = connection or _connect()
    key = config.key.strip() or make_browser_key(config.display_name)

    try:
        if config.id is None:
            active_connection.execute(
                """
                INSERT INTO browser_configs (
                    key, display_name, browser_type, executable_path, enabled
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    display_name = excluded.display_name,
                    browser_type = excluded.browser_type,
                    executable_path = excluded.executable_path,
                    enabled = excluded.enabled
                """,
                (
                    key,
                    config.display_name.strip() or key,
                    config.normalized_type(),
                    config.executable_path.strip(),
                    int(config.enabled),
                ),
            )
        else:
            active_connection.execute(
                """
                UPDATE browser_configs
                SET key = ?,
                    display_name = ?,
                    browser_type = ?,
                    executable_path = ?,
                    enabled = ?
                WHERE id = ?
                """,
                (
                    key,
                    config.display_name.strip() or key,
                    config.normalized_type(),
                    config.executable_path.strip(),
                    int(config.enabled),
                    config.id,
                ),
            )

        if owns_connection:
            active_connection.commit()
    finally:
        if owns_connection:
            active_connection.close()

    return BrowserConfig(
        id=config.id,
        key=key,
        display_name=config.display_name.strip() or key,
        browser_type=config.normalized_type(),
        executable_path=config.executable_path.strip(),
        enabled=config.enabled,
    )


def delete_browser_config(config_id: int) -> None:
    with _connect() as connection:
        connection.execute("DELETE FROM browser_configs WHERE id = ?", (config_id,))


def make_browser_key(display_name: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", display_name.strip().lower())
    return key.strip("_") or "browser"


def create_session(
    session: SessionEntry,
    *,
    connection: sqlite3.Connection | None = None,
) -> SessionEntry:
    owns_connection = connection is None
    active_connection = connection or _connect()

    try:
        cursor = active_connection.execute(
            """
            INSERT INTO sessions (
                name, url, browser, profile_path, proxy_id, fingerprint_id,
                proxy_label, custom_user_agent, notes,
                window_width, window_height, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session.name,
                session.url,
                session.browser.strip() or "chrome",
                session.profile_path.strip(),
                session.proxy_id,
                session.fingerprint_id,
                session.proxy_label,
                session.custom_user_agent,
                session.notes,
                session.window_width,
                session.window_height,
                session.status,
            ),
        )
        session_id = int(cursor.lastrowid)
        profile_path = normalize_profile_path(session.profile_path, session_id)
        Path(profile_path).expanduser().mkdir(parents=True, exist_ok=True)

        active_connection.execute(
            "UPDATE sessions SET profile_path = ? WHERE id = ?",
            (profile_path, session_id),
        )
        if owns_connection:
            active_connection.commit()

        return SessionEntry(
            id=session_id,
            name=session.name,
            url=session.url,
            browser=session.browser.strip() or "chrome",
            profile_path=profile_path,
            proxy_id=session.proxy_id,
            fingerprint_id=session.fingerprint_id,
            proxy_label=session.proxy_label,
            custom_user_agent=session.custom_user_agent,
            notes=session.notes,
            window_width=session.window_width,
            window_height=session.window_height,
            status=session.status,
        )
    finally:
        if owns_connection:
            active_connection.close()


def update_session(session: SessionEntry) -> SessionEntry:
    if session.id is None:
        return create_session(session)

    profile_path = normalize_profile_path(session.profile_path, session.id)
    Path(profile_path).expanduser().mkdir(parents=True, exist_ok=True)

    with _connect() as connection:
        connection.execute(
            """
            UPDATE sessions
            SET name = ?,
                url = ?,
                browser = ?,
                profile_path = ?,
                proxy_id = ?,
                fingerprint_id = ?,
                proxy_label = ?,
                custom_user_agent = ?,
                notes = ?,
                window_width = ?,
                window_height = ?,
                status = ?
            WHERE id = ?
            """,
            (
                session.name,
                session.url,
                session.browser.strip() or "chrome",
                profile_path,
                session.proxy_id,
                session.fingerprint_id,
                session.proxy_label,
                session.custom_user_agent,
                session.notes,
                session.window_width,
                session.window_height,
                session.status,
                session.id,
            ),
        )

    session.profile_path = profile_path
    return session


def delete_session(session_id: int) -> None:
    with _connect() as connection:
        connection.execute("DELETE FROM sessions WHERE id = ?", (session_id,))


def get_setting(key: str, default: str = "") -> str:
    with _connect() as connection:
        row = connection.execute(
            "SELECT value FROM app_settings WHERE key = ?",
            (key,),
        ).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO app_settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
