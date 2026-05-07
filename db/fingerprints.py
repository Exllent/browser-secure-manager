from __future__ import annotations

import json
import sqlite3

from models.fingerprint_profile import FingerprintProfile

from . import config
from .mappers import row_to_fingerprint_profile


def get_fingerprint_profiles(*, enabled_only: bool = False) -> list[FingerprintProfile]:
    where = "WHERE enabled = 1" if enabled_only else ""
    with config.connect() as connection:
        rows = connection.execute(f"""
            SELECT id, name, config_json, enabled
            FROM fingerprint_profiles
            {where}
            ORDER BY name COLLATE NOCASE, id
            """).fetchall()
    return [row_to_fingerprint_profile(row) for row in rows]


def get_fingerprint_profile(fingerprint_id: int | None) -> FingerprintProfile | None:
    if fingerprint_id is None:
        return None
    with config.connect() as connection:
        row = connection.execute(
            """
            SELECT id, name, config_json, enabled
            FROM fingerprint_profiles
            WHERE id = ?
            """,
            (fingerprint_id,),
        ).fetchone()
    return row_to_fingerprint_profile(row) if row else None


def upsert_fingerprint_profile(
    profile: FingerprintProfile,
    *,
    connection: sqlite3.Connection | None = None,
) -> FingerprintProfile:
    owns_connection = connection is None
    active_connection = connection or config.connect()
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
            fingerprint_id = int(cursor.lastrowid)
        else:
            active_connection.execute(
                """
                UPDATE fingerprint_profiles
                SET name        = ?,
                    config_json = ?,
                    enabled     = ?
                WHERE id = ?
                """,
                (name, config_json, int(profile.enabled), profile.id),
            )
            fingerprint_id = profile.id

        if owns_connection:
            active_connection.commit()
    finally:
        if owns_connection:
            active_connection.close()

    return FingerprintProfile(
        id=fingerprint_id,
        name=name,
        config=profile.config,
        enabled=profile.enabled,
    )


def delete_fingerprint_profile(fingerprint_id: int) -> None:
    with config.connect() as connection:
        connection.execute("DELETE FROM fingerprint_profiles WHERE id = ?", (fingerprint_id,))
        connection.execute(
            "UPDATE sessions SET fingerprint_id = NULL WHERE fingerprint_id = ?",
            (fingerprint_id,),
        )
