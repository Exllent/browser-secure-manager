from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from models.browser_config import BrowserConfig
from models.fingerprint_config import FingerprintConfig
from models.fingerprint_profile import FingerprintProfile
from models.proxy_config import ProxyConfig
from models.session_entry import SessionEntry

from . import config
from .browsers import get_browser_config, get_browser_configs, make_browser_key
from .fingerprints import get_fingerprint_profile, get_fingerprint_profiles
from .proxies import get_proxy_config, get_proxy_configs
from .sessions import get_all_sessions, get_session, normalize_profile_path
from .settings import get_all_settings

logger = logging.getLogger(__name__)

BACKUP_FORMAT = "secure_browser_backup"
BACKUP_VERSION = 1


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
            _browser_config_to_backup_dict(browser_config)
            for browser_config in get_browser_configs()
        ],
        "proxy_configs": [_proxy_config_to_backup_dict(proxy) for proxy in get_proxy_configs()],
        "fingerprint_profiles": [
            _fingerprint_profile_to_backup_dict(profile)
            for profile in get_fingerprint_profiles()
        ],
        "app_settings": get_all_settings(),
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


def _browser_config_to_backup_dict(browser_config: BrowserConfig) -> dict[str, object]:
    return asdict(browser_config)


def _proxy_config_to_backup_dict(proxy: ProxyConfig) -> dict[str, object]:
    return asdict(proxy)


def _fingerprint_profile_to_backup_dict(profile: FingerprintProfile) -> dict[str, object]:
    return {
        "id": profile.id,
        "name": profile.name,
        "config": profile.config.to_dict(),
        "enabled": profile.enabled,
    }


def _import_full_backup_data(data: dict[str, object]) -> dict[str, int]:
    sessions = _require_list(data, "sessions")
    browser_configs = _require_list(data, "browser_configs")
    proxy_configs = _require_list(data, "proxy_configs")
    fingerprint_profiles = _require_list(data, "fingerprint_profiles")
    app_settings = data.get("app_settings", {})
    if not isinstance(app_settings, dict):
        raise ValueError("Backup app_settings must be an object")

    with config.connect() as connection:
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

    with config.connect() as connection:
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
    fingerprint_config_data = data.get("config")
    if not isinstance(fingerprint_config_data, dict):
        raise ValueError("Fingerprint profile config must be an object")
    fingerprint_config = FingerprintConfig.from_dict(fingerprint_config_data)
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
