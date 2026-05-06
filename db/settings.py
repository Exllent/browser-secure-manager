from __future__ import annotations

from . import config


def get_setting(key: str, default: str = "") -> str:
    with config.connect() as connection:
        row = connection.execute(
            "SELECT value FROM app_settings WHERE key = ?",
            (key,),
        ).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with config.connect() as connection:
        connection.execute(
            """
            INSERT INTO app_settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )


def get_all_settings() -> dict[str, str]:
    with config.connect() as connection:
        rows = connection.execute(
            "SELECT key, value FROM app_settings ORDER BY key"
        ).fetchall()
    return {str(row["key"]): str(row["value"]) for row in rows}
