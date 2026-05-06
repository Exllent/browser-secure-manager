from __future__ import annotations

import json
import logging
import sqlite3

from models.browser_config import BrowserConfig
from models.fingerprint_config import FingerprintConfig
from models.fingerprint_profile import FingerprintProfile
from models.proxy_config import ProxyConfig
from models.session_entry import SessionEntry

logger = logging.getLogger(__name__)


def row_to_session(row: sqlite3.Row) -> SessionEntry:
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


def row_to_browser_config(row: sqlite3.Row) -> BrowserConfig:
    return BrowserConfig(
        id=row["id"],
        key=row["key"],
        display_name=row["display_name"],
        browser_type=row["browser_type"],
        executable_path=row["executable_path"],
        enabled=bool(row["enabled"]),
    )


def row_to_proxy_config(row: sqlite3.Row) -> ProxyConfig:
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


def row_to_fingerprint_profile(row: sqlite3.Row) -> FingerprintProfile:
    return FingerprintProfile(
        id=row["id"],
        name=row["name"],
        config=fingerprint_config_from_json(row["config_json"]),
        enabled=bool(row["enabled"]),
    )


def fingerprint_config_from_json(config_json: str) -> FingerprintConfig:
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
