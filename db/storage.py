from __future__ import annotations

import logging

from .backups import (
    BACKUP_FORMAT,
    BACKUP_VERSION,
    export_full_backup,
    export_session_backup,
    import_backup,
)
from .browsers import (
    delete_browser_config,
    get_browser_config,
    get_browser_configs,
    make_browser_key,
    upsert_browser_config,
)
from .config import BASE_DIR, DB_PATH, PROFILES_DIR, connect as _connect
from .fingerprints import (
    delete_fingerprint_profile,
    get_fingerprint_profile,
    get_fingerprint_profiles,
    upsert_fingerprint_profile,
)
from .profile_cache import (
    PROFILE_CACHE_DAY_OPTIONS,
    PROFILE_CACHE_DAYS_KEY,
    PROFILE_CACHE_ENABLED_KEY,
    cleanup_expired_profile_cache,
    delete_profile_directory,
    get_profile_cache_days,
    is_profile_cache_enabled,
)
from .proxies import (
    delete_proxy_config,
    get_proxy_config,
    get_proxy_configs,
    upsert_proxy_config,
)
from .schema import init_db
from .sessions import (
    create_session,
    default_profile_path,
    delete_session,
    get_all_sessions,
    get_session,
    normalize_profile_path,
    update_session,
)
from .settings import get_setting, set_setting

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

__all__ = [
    "BACKUP_FORMAT",
    "BACKUP_VERSION",
    "BASE_DIR",
    "DB_PATH",
    "PROFILE_CACHE_DAY_OPTIONS",
    "PROFILE_CACHE_DAYS_KEY",
    "PROFILE_CACHE_ENABLED_KEY",
    "PROFILES_DIR",
    "_connect",
    "cleanup_expired_profile_cache",
    "create_session",
    "default_profile_path",
    "delete_browser_config",
    "delete_fingerprint_profile",
    "delete_profile_directory",
    "delete_proxy_config",
    "delete_session",
    "export_full_backup",
    "export_session_backup",
    "get_all_sessions",
    "get_browser_config",
    "get_browser_configs",
    "get_fingerprint_profile",
    "get_fingerprint_profiles",
    "get_profile_cache_days",
    "get_proxy_config",
    "get_proxy_configs",
    "get_session",
    "get_setting",
    "import_backup",
    "init_db",
    "is_profile_cache_enabled",
    "make_browser_key",
    "normalize_profile_path",
    "set_setting",
    "update_session",
    "upsert_browser_config",
    "upsert_fingerprint_profile",
    "upsert_proxy_config",
]
