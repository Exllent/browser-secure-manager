from __future__ import annotations

import re
import sqlite3

from models.browser_config import BrowserConfig

from . import config
from .mappers import row_to_browser_config


def get_browser_configs(*, enabled_only: bool = False) -> list[BrowserConfig]:
    where = "WHERE enabled = 1" if enabled_only else ""
    with config.connect() as connection:
        rows = connection.execute(
            f"""
            SELECT id, key, display_name, browser_type, executable_path, enabled
            FROM browser_configs
            {where}
            ORDER BY display_name COLLATE NOCASE
            """
        ).fetchall()
    return [row_to_browser_config(row) for row in rows]


def get_browser_config(key: str) -> BrowserConfig | None:
    with config.connect() as connection:
        row = connection.execute(
            """
            SELECT id, key, display_name, browser_type, executable_path, enabled
            FROM browser_configs
            WHERE key = ?
            """,
            (key,),
        ).fetchone()
    return row_to_browser_config(row) if row else None


def upsert_browser_config(
    browser_config: BrowserConfig,
    *,
    connection: sqlite3.Connection | None = None,
) -> BrowserConfig:
    owns_connection = connection is None
    active_connection = connection or config.connect()
    key = browser_config.key.strip() or make_browser_key(browser_config.display_name)

    try:
        if browser_config.id is None:
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
                    browser_config.display_name.strip() or key,
                    browser_config.normalized_type(),
                    browser_config.executable_path.strip(),
                    int(browser_config.enabled),
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
                    browser_config.display_name.strip() or key,
                    browser_config.normalized_type(),
                    browser_config.executable_path.strip(),
                    int(browser_config.enabled),
                    browser_config.id,
                ),
            )

        if owns_connection:
            active_connection.commit()
    finally:
        if owns_connection:
            active_connection.close()

    return BrowserConfig(
        id=browser_config.id,
        key=key,
        display_name=browser_config.display_name.strip() or key,
        browser_type=browser_config.normalized_type(),
        executable_path=browser_config.executable_path.strip(),
        enabled=browser_config.enabled,
    )


def delete_browser_config(config_id: int) -> None:
    with config.connect() as connection:
        connection.execute("DELETE FROM browser_configs WHERE id = ?", (config_id,))


def make_browser_key(display_name: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", display_name.strip().lower())
    return key.strip("_") or "browser"
