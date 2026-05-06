from __future__ import annotations

import sqlite3
from pathlib import Path

from app_config import APP_CONFIG
from models.session_entry import SessionEntry

from . import config
from .mappers import row_to_session


def default_profile_path(session_id: int) -> str:
    return str(config.PROFILES_DIR / f"{APP_CONFIG.storage.session_profile_prefix}{session_id}")


def normalize_profile_path(profile_path: str, session_id: int) -> str:
    raw_path = profile_path.strip()
    path = Path(raw_path).expanduser() if raw_path else Path(default_profile_path(session_id))
    if not path.is_absolute():
        path = config.BASE_DIR / path
    return str(path)


def get_all_sessions() -> list[SessionEntry]:
    with config.connect() as connection:
        rows = connection.execute("""
            SELECT id,
                   name,
                   url,
                   browser,
                   profile_path,
                   proxy_id,
                   proxy_label,
                   fingerprint_id,
                   custom_user_agent,
                   notes,
                   window_width,
                   window_height,
                   status
            FROM sessions
            ORDER BY id
            """).fetchall()
    return [row_to_session(row) for row in rows]


def get_session(session_id: int) -> SessionEntry | None:
    with config.connect() as connection:
        row = connection.execute(
            """
            SELECT id,
                   name,
                   url,
                   browser,
                   profile_path,
                   proxy_id,
                   proxy_label,
                   fingerprint_id,
                   custom_user_agent,
                   notes,
                   window_width,
                   window_height,
                   status
            FROM sessions
            WHERE id = ?
            """,
            (session_id,),
        ).fetchone()
    return row_to_session(row) if row else None


def create_session(
    session: SessionEntry,
    *,
    connection: sqlite3.Connection | None = None,
) -> SessionEntry:
    owns_connection = connection is None
    active_connection = connection or config.connect()

    try:
        cursor = active_connection.execute(
            """
            INSERT INTO sessions (name, url, browser, profile_path, proxy_id, fingerprint_id,
                                  proxy_label, custom_user_agent, notes,
                                  window_width, window_height, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session.name,
                session.url,
                session.browser.strip() or APP_CONFIG.storage.default_browser_key,
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
            browser=session.browser.strip() or APP_CONFIG.storage.default_browser_key,
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

    with config.connect() as connection:
        connection.execute(
            """
            UPDATE sessions
            SET name              = ?,
                url               = ?,
                browser           = ?,
                profile_path      = ?,
                proxy_id          = ?,
                fingerprint_id    = ?,
                proxy_label       = ?,
                custom_user_agent = ?,
                notes             = ?,
                window_width      = ?,
                window_height     = ?,
                status            = ?
            WHERE id = ?
            """,
            (
                session.name,
                session.url,
                session.browser.strip() or APP_CONFIG.storage.default_browser_key,
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
    with config.connect() as connection:
        connection.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
