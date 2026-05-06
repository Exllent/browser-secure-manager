from __future__ import annotations

import sqlite3

from models.proxy_config import ProxyConfig

from . import config
from .mappers import row_to_proxy_config


def get_proxy_configs(*, enabled_only: bool = False) -> list[ProxyConfig]:
    where = "WHERE enabled = 1" if enabled_only else ""
    with config.connect() as connection:
        rows = connection.execute(
            f"""
            SELECT id, label, host, port, proxy_type, username, password, enabled
            FROM proxy_configs
            {where}
            ORDER BY label COLLATE NOCASE, host COLLATE NOCASE, port
            """
        ).fetchall()
    return [row_to_proxy_config(row) for row in rows]


def get_proxy_config(proxy_id: int | None) -> ProxyConfig | None:
    if proxy_id is None:
        return None
    with config.connect() as connection:
        row = connection.execute(
            """
            SELECT id, label, host, port, proxy_type, username, password, enabled
            FROM proxy_configs
            WHERE id = ?
            """,
            (proxy_id,),
        ).fetchone()
    return row_to_proxy_config(row) if row else None


def upsert_proxy_config(
    proxy: ProxyConfig,
    *,
    connection: sqlite3.Connection | None = None,
) -> ProxyConfig:
    owns_connection = connection is None
    active_connection = connection or config.connect()

    try:
        if proxy.id is None:
            cursor = active_connection.execute(
                """
                INSERT INTO proxy_configs (
                    label, host, port, proxy_type, username, password, enabled
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                _proxy_values(proxy),
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
                (*_proxy_values(proxy), proxy.id),
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
    with config.connect() as connection:
        connection.execute("DELETE FROM proxy_configs WHERE id = ?", (proxy_id,))
        connection.execute("UPDATE sessions SET proxy_id = NULL WHERE proxy_id = ?", (proxy_id,))


def _proxy_values(proxy: ProxyConfig) -> tuple[object, ...]:
    return (
        proxy.label.strip(),
        proxy.host.strip(),
        proxy.port,
        proxy.normalized_type(),
        proxy.username.strip(),
        proxy.password,
        int(proxy.enabled),
    )
