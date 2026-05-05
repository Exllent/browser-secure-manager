from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime, timedelta
import logging
import json
import sqlite3
from pathlib import Path
import re
import shutil
from typing import Iterable

from models.browser_config import BrowserConfig
from models.fingerprint_config import FingerprintConfig
from models.fingerprint_profile import FingerprintProfile
from models.proxy_config import ProxyConfig
from models.session_entry import SessionEntry

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "sessions.sqlite3"
PROFILES_DIR = BASE_DIR / "profiles"
BACKUP_FORMAT = "secure_browser_backup"
BACKUP_VERSION = 1
PROFILE_CACHE_ENABLED_KEY = "profile_cache_enabled"
PROFILE_CACHE_DAYS_KEY = "profile_cache_days"
PROFILE_CACHE_DAY_OPTIONS = ("1", "3", "7", "30", "90", "120", "forever")


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
        logger.warning("Fingerprint config JSON root is not an object; using defaults")
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
    logger.info("Opening SQLite storage at %s", DB_PATH)
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
        logger.info("SQLite storage initialized")


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
            logger.info("Seeding default browser config '%s'", config.key)
            upsert_browser_config(config, connection=connection)


def _remove_unsupported_browser_configs(connection: sqlite3.Connection) -> None:
    deleted = connection.execute(
        "DELETE FROM browser_configs WHERE lower(browser_type) != 'chromium'"
    ).rowcount
    if deleted:
        logger.warning("Removed %s unsupported browser config(s)", deleted)
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
        logger.info("Adding missing sessions.proxy_id column")
        connection.execute("ALTER TABLE sessions ADD COLUMN proxy_id INTEGER")
    if "fingerprint_id" not in columns:
        logger.info("Adding missing sessions.fingerprint_id column")
        connection.execute("ALTER TABLE sessions ADD COLUMN fingerprint_id INTEGER")
    if "custom_user_agent" not in columns:
        logger.info("Adding missing sessions.custom_user_agent column")
        connection.execute(
            "ALTER TABLE sessions ADD COLUMN custom_user_agent TEXT DEFAULT ''"
        )


def _ensure_proxy_columns(connection: sqlite3.Connection) -> None:
    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(proxy_configs)").fetchall()
    }
    if "proxy_type" not in columns:
        logger.info("Adding missing proxy_configs.proxy_type column")
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


def is_profile_cache_enabled() -> bool:
    return get_setting(PROFILE_CACHE_ENABLED_KEY, "1") != "0"


def get_profile_cache_days() -> str:
    value = get_setting(PROFILE_CACHE_DAYS_KEY, "1")
    return value if value in PROFILE_CACHE_DAY_OPTIONS else "1"


def cleanup_expired_profile_cache() -> int:
    if not is_profile_cache_enabled():
        logger.info("Profile cache cleanup skipped because profile cache is disabled")
        return 0

    retention = get_profile_cache_days()
    if retention == "forever":
        logger.info("Profile cache cleanup skipped because retention is forever")
        return 0

    threshold = datetime.now(UTC) - timedelta(days=int(retention))
    active_profile_paths = {
        _resolve_profile_path(session.profile_path)
        for session in get_all_sessions()
        if session.profile_path
    }
    deleted = 0
    if not PROFILES_DIR.exists():
        return 0

    for profile_dir in PROFILES_DIR.iterdir():
        if not profile_dir.is_dir():
            continue
        resolved_path = _resolve_profile_path(str(profile_dir))
        if resolved_path in active_profile_paths:
            continue
        created_at = _profile_created_at(profile_dir)
        if created_at > threshold:
            continue
        if delete_profile_directory(profile_dir):
            deleted += 1

    if deleted:
        logger.info("Deleted %s expired cached profile(s)", deleted)
    return deleted


def delete_profile_directory(profile_path: str | Path) -> bool:
    path = Path(profile_path).expanduser()
    if not path.exists():
        return False
    if not path.is_dir():
        logger.warning("Profile path is not a directory and was not deleted: %s", path)
        return False
    if not _is_safe_profile_delete_target(path):
        logger.error("Refusing to delete unsafe profile path: %s", path)
        return False

    shutil.rmtree(path)
    logger.info("Deleted profile directory: %s", path)
    return True


def _resolve_profile_path(profile_path: str) -> Path:
    return Path(profile_path).expanduser().resolve()


def _profile_created_at(profile_path: Path) -> datetime:
    stat = profile_path.stat()
    timestamp = getattr(stat, "st_birthtime", stat.st_ctime)
    return datetime.fromtimestamp(timestamp, UTC)


def _is_safe_profile_delete_target(path: Path) -> bool:
    resolved = path.resolve()
    unsafe_paths = {
        Path.home().resolve(),
        BASE_DIR.resolve(),
        PROFILES_DIR.resolve(),
        Path("/").resolve(),
    }
    if resolved in unsafe_paths or len(resolved.parts) <= 2:
        return False
    if resolved.is_relative_to(PROFILES_DIR.resolve()):
        return True
    return _looks_like_browser_profile(resolved)


def _looks_like_browser_profile(path: Path) -> bool:
    return (path / "Local State").exists() or (path / "Default").is_dir()


def export_full_backup(destination: str | Path) -> Path:
    destination_path = Path(destination).expanduser()
    payload = _base_backup_payload("full")
    payload["data"] = _full_backup_data()
    _write_backup(destination_path, payload)
    logger.info("Full backup exported to %s", destination_path)
    return destination_path


def export_session_backup(session_id: int, destination: str | Path) -> Path:
    destination_path = Path(destination).expanduser()
    session = get_session(session_id)
    if session is None:
        raise ValueError(f"Session {session_id} was not found")

    payload = _base_backup_payload("session")
    payload["data"] = _session_backup_data(session)
    _write_backup(destination_path, payload)
    logger.info("Session %s backup exported to %s", session_id, destination_path)
    return destination_path


def import_backup(source: str | Path) -> dict[str, int | str]:
    source_path = Path(source).expanduser()
    try:
        payload = json.loads(source_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid backup JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Backup root must be an object")
    if payload.get("format") != BACKUP_FORMAT:
        raise ValueError("Unsupported backup file format")
    if int(payload.get("version", 0)) != BACKUP_VERSION:
        raise ValueError(f"Unsupported backup version: {payload.get('version')}")

    scope = str(payload.get("scope", ""))
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ValueError("Backup data must be an object")

    if scope == "full":
        result = _import_full_backup_data(data)
    elif scope == "session":
        result = _import_session_backup_data(data)
    else:
        raise ValueError(f"Unsupported backup scope: {scope}")

    logger.info("Backup imported from %s with scope %s", source_path, scope)
    return {"scope": scope, **result}


def get_session(session_id: int) -> SessionEntry | None:
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT id, name, url, browser, profile_path, proxy_id, proxy_label,
                   fingerprint_id, custom_user_agent, notes,
                   window_width, window_height, status
            FROM sessions
            WHERE id = ?
            """,
            (session_id,),
        ).fetchone()
    return _row_to_session(row) if row else None


def _base_backup_payload(scope: str) -> dict[str, object]:
    return {
        "format": BACKUP_FORMAT,
        "version": BACKUP_VERSION,
        "scope": scope,
        "created_at": datetime.now(UTC).isoformat(),
        "data": {},
    }


def _full_backup_data() -> dict[str, object]:
    return {
        "sessions": [_session_to_backup_dict(session) for session in get_all_sessions()],
        "browser_configs": [
            _browser_config_to_backup_dict(config) for config in get_browser_configs()
        ],
        "proxy_configs": [_proxy_config_to_backup_dict(proxy) for proxy in get_proxy_configs()],
        "fingerprint_profiles": [
            _fingerprint_profile_to_backup_dict(profile) for profile in get_fingerprint_profiles()
        ],
        "app_settings": _get_all_settings(),
    }


def _session_backup_data(session: SessionEntry) -> dict[str, object]:
    browser_config = get_browser_config(session.browser)
    proxy_config = get_proxy_config(session.proxy_id)
    fingerprint_profile = get_fingerprint_profile(session.fingerprint_id)
    return {
        "sessions": [_session_to_backup_dict(session)],
        "browser_configs": (
            [_browser_config_to_backup_dict(browser_config)] if browser_config is not None else []
        ),
        "proxy_configs": (
            [_proxy_config_to_backup_dict(proxy_config)] if proxy_config is not None else []
        ),
        "fingerprint_profiles": (
            [_fingerprint_profile_to_backup_dict(fingerprint_profile)]
            if fingerprint_profile is not None
            else []
        ),
        "app_settings": {},
    }


def _write_backup(destination_path: Path, payload: dict[str, object]) -> None:
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    destination_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _session_to_backup_dict(session: SessionEntry) -> dict[str, object]:
    data = asdict(session)
    data["status"] = "idle"
    return data


def _browser_config_to_backup_dict(config: BrowserConfig) -> dict[str, object]:
    return asdict(config)


def _proxy_config_to_backup_dict(proxy: ProxyConfig) -> dict[str, object]:
    return asdict(proxy)


def _fingerprint_profile_to_backup_dict(profile: FingerprintProfile) -> dict[str, object]:
    return {
        "id": profile.id,
        "name": profile.name,
        "config": profile.config.to_dict(),
        "enabled": profile.enabled,
    }


def _get_all_settings() -> dict[str, str]:
    with _connect() as connection:
        rows = connection.execute(
            "SELECT key, value FROM app_settings ORDER BY key"
        ).fetchall()
    return {str(row["key"]): str(row["value"]) for row in rows}


def _import_full_backup_data(data: dict[str, object]) -> dict[str, int]:
    sessions = _require_list(data, "sessions")
    browser_configs = _require_list(data, "browser_configs")
    proxy_configs = _require_list(data, "proxy_configs")
    fingerprint_profiles = _require_list(data, "fingerprint_profiles")
    app_settings = data.get("app_settings", {})
    if not isinstance(app_settings, dict):
        raise ValueError("Backup app_settings must be an object")

    with _connect() as connection:
        connection.execute("DELETE FROM sessions")
        connection.execute("DELETE FROM proxy_configs")
        connection.execute("DELETE FROM browser_configs")
        connection.execute("DELETE FROM fingerprint_profiles")
        connection.execute("DELETE FROM app_settings")

        for item in browser_configs:
            _insert_browser_config_from_backup(connection, _require_dict(item, "browser config"))
        for item in proxy_configs:
            _insert_proxy_config_from_backup(connection, _require_dict(item, "proxy config"))
        for item in fingerprint_profiles:
            _insert_fingerprint_profile_from_backup(
                connection,
                _require_dict(item, "fingerprint profile"),
            )
        for key, value in app_settings.items():
            connection.execute(
                "INSERT INTO app_settings (key, value) VALUES (?, ?)",
                (str(key), str(value)),
            )
        for item in sessions:
            _insert_session_from_backup(connection, _require_dict(item, "session"))

    return {
        "sessions": len(sessions),
        "browser_configs": len(browser_configs),
        "proxy_configs": len(proxy_configs),
        "fingerprint_profiles": len(fingerprint_profiles),
        "app_settings": len(app_settings),
    }


def _import_session_backup_data(data: dict[str, object]) -> dict[str, int]:
    sessions = _require_list(data, "sessions")
    if len(sessions) != 1:
        raise ValueError("Session backup must contain exactly one session")
    browser_configs = _require_list(data, "browser_configs")
    proxy_configs = _require_list(data, "proxy_configs")
    fingerprint_profiles = _require_list(data, "fingerprint_profiles")

    session_data = _require_dict(sessions[0], "session")
    old_proxy_id = _optional_int(session_data.get("proxy_id"))
    old_fingerprint_id = _optional_int(session_data.get("fingerprint_id"))

    with _connect() as connection:
        for item in browser_configs:
            _upsert_browser_config_from_backup(connection, _require_dict(item, "browser config"))

        proxy_id_map: dict[int, int] = {}
        for item in proxy_configs:
            proxy_data = _require_dict(item, "proxy config")
            old_id = _optional_int(proxy_data.get("id"))
            new_id = _upsert_proxy_from_backup(connection, proxy_data)
            if old_id is not None:
                proxy_id_map[old_id] = new_id

        fingerprint_id_map: dict[int, int] = {}
        for item in fingerprint_profiles:
            profile_data = _require_dict(item, "fingerprint profile")
            old_id = _optional_int(profile_data.get("id"))
            new_id = _upsert_fingerprint_from_backup(connection, profile_data)
            if old_id is not None:
                fingerprint_id_map[old_id] = new_id

        session_data = dict(session_data)
        session_data["id"] = None
        session_data["proxy_id"] = proxy_id_map.get(old_proxy_id) if old_proxy_id is not None else None
        session_data["fingerprint_id"] = (
            fingerprint_id_map.get(old_fingerprint_id)
            if old_fingerprint_id is not None
            else None
        )
        session_data["status"] = "idle"
        _insert_session_from_backup(connection, session_data)

    return {
        "sessions": 1,
        "browser_configs": len(browser_configs),
        "proxy_configs": len(proxy_configs),
        "fingerprint_profiles": len(fingerprint_profiles),
        "app_settings": 0,
    }


def _insert_session_from_backup(
    connection: sqlite3.Connection,
    data: dict[str, object],
) -> int:
    session_id = _optional_int(data.get("id"))
    profile_path = str(data.get("profile_path") or "")
    if session_id is None:
        cursor = connection.execute(
            """
            INSERT INTO sessions (
                name, url, browser, profile_path, proxy_id, fingerprint_id,
                proxy_label, custom_user_agent, notes,
                window_width, window_height, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            _session_insert_values(data, profile_path),
        )
        new_id = int(cursor.lastrowid)
    else:
        connection.execute(
            """
            INSERT INTO sessions (
                id, name, url, browser, profile_path, proxy_id, fingerprint_id,
                proxy_label, custom_user_agent, notes,
                window_width, window_height, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, *_session_insert_values(data, profile_path)),
        )
        new_id = session_id

    normalized_path = normalize_profile_path(profile_path, new_id)
    Path(normalized_path).expanduser().mkdir(parents=True, exist_ok=True)
    connection.execute(
        "UPDATE sessions SET profile_path = ? WHERE id = ?",
        (normalized_path, new_id),
    )
    return new_id


def _session_insert_values(
    data: dict[str, object],
    profile_path: str,
) -> tuple[object, ...]:
    return (
        str(data.get("name") or "Imported session"),
        str(data.get("url") or "about:blank"),
        str(data.get("browser") or "chrome"),
        profile_path,
        _optional_int(data.get("proxy_id")),
        _optional_int(data.get("fingerprint_id")),
        str(data.get("proxy_label") or ""),
        str(data.get("custom_user_agent") or ""),
        str(data.get("notes") or ""),
        int(data.get("window_width") or 1280),
        int(data.get("window_height") or 800),
        "idle",
    )


def _insert_browser_config_from_backup(
    connection: sqlite3.Connection,
    data: dict[str, object],
) -> None:
    connection.execute(
        """
        INSERT INTO browser_configs (id, key, display_name, browser_type, executable_path, enabled)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        _browser_config_values(data, include_id=True),
    )


def _upsert_browser_config_from_backup(
    connection: sqlite3.Connection,
    data: dict[str, object],
) -> None:
    connection.execute(
        """
        INSERT INTO browser_configs (key, display_name, browser_type, executable_path, enabled)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            display_name = excluded.display_name,
            browser_type = excluded.browser_type,
            executable_path = excluded.executable_path,
            enabled = excluded.enabled
        """,
        _browser_config_values(data, include_id=False),
    )


def _browser_config_values(data: dict[str, object], *, include_id: bool) -> tuple[object, ...]:
    values: tuple[object, ...] = (
        str(data.get("key") or make_browser_key(str(data.get("display_name") or "browser"))),
        str(data.get("display_name") or data.get("key") or "Browser"),
        str(data.get("browser_type") or "chromium"),
        str(data.get("executable_path") or ""),
        int(bool(data.get("enabled", True))),
    )
    if include_id:
        return (_required_int(data.get("id"), "browser config id"), *values)
    return values


def _insert_proxy_config_from_backup(
    connection: sqlite3.Connection,
    data: dict[str, object],
) -> None:
    connection.execute(
        """
        INSERT INTO proxy_configs (id, label, host, port, proxy_type, username, password, enabled)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (_required_int(data.get("id"), "proxy id"), *_proxy_values(data)),
    )


def _upsert_proxy_from_backup(connection: sqlite3.Connection, data: dict[str, object]) -> int:
    row = connection.execute(
        """
        SELECT id FROM proxy_configs
        WHERE host = ? AND port = ? AND proxy_type = ? AND username = ? AND password = ?
        """,
        (
            str(data.get("host") or "").strip(),
            int(data.get("port") or 0),
            str(data.get("proxy_type") or "socks5").strip().lower() or "socks5",
            str(data.get("username") or "").strip(),
            str(data.get("password") or ""),
        ),
    ).fetchone()
    if row is not None:
        return int(row["id"])

    cursor = connection.execute(
        """
        INSERT INTO proxy_configs (label, host, port, proxy_type, username, password, enabled)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        _proxy_values(data),
    )
    return int(cursor.lastrowid)


def _proxy_values(data: dict[str, object]) -> tuple[object, ...]:
    return (
        str(data.get("label") or "").strip(),
        str(data.get("host") or "").strip(),
        int(data.get("port") or 0),
        str(data.get("proxy_type") or "socks5").strip().lower() or "socks5",
        str(data.get("username") or "").strip(),
        str(data.get("password") or ""),
        int(bool(data.get("enabled", True))),
    )


def _insert_fingerprint_profile_from_backup(
    connection: sqlite3.Connection,
    data: dict[str, object],
) -> None:
    config_json = _fingerprint_config_json_from_backup(data)
    connection.execute(
        """
        INSERT INTO fingerprint_profiles (id, name, config_json, enabled)
        VALUES (?, ?, ?, ?)
        """,
        (
            _required_int(data.get("id"), "fingerprint id"),
            str(data.get("name") or "Imported fingerprint"),
            config_json,
            int(bool(data.get("enabled", True))),
        ),
    )


def _upsert_fingerprint_from_backup(
    connection: sqlite3.Connection,
    data: dict[str, object],
) -> int:
    name = str(data.get("name") or "Imported fingerprint")
    config_json = _fingerprint_config_json_from_backup(data)
    row = connection.execute(
        """
        SELECT id FROM fingerprint_profiles
        WHERE name = ? AND config_json = ?
        """,
        (name, config_json),
    ).fetchone()
    if row is not None:
        return int(row["id"])

    cursor = connection.execute(
        """
        INSERT INTO fingerprint_profiles (name, config_json, enabled)
        VALUES (?, ?, ?)
        """,
        (name, config_json, int(bool(data.get("enabled", True)))),
    )
    return int(cursor.lastrowid)


def _fingerprint_config_json_from_backup(data: dict[str, object]) -> str:
    config = data.get("config")
    if not isinstance(config, dict):
        raise ValueError("Fingerprint profile config must be an object")
    fingerprint_config = FingerprintConfig.from_dict(config)
    errors = fingerprint_config.validate()
    if errors:
        raise ValueError("; ".join(errors))
    return json.dumps(fingerprint_config.to_dict(), ensure_ascii=False, sort_keys=True)


def _require_list(data: dict[str, object], key: str) -> list[object]:
    value = data.get(key, [])
    if not isinstance(value, list):
        raise ValueError(f"Backup {key} must be a list")
    return value


def _require_dict(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"Backup {label} must be an object")
    return value


def _optional_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _required_int(value: object, label: str) -> int:
    if value is None or value == "":
        raise ValueError(f"Backup {label} is required")
    return int(value)
