from __future__ import annotations

import logging
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

from . import config
from .sessions import get_all_sessions
from .settings import get_setting

logger = logging.getLogger(__name__)

PROFILE_CACHE_ENABLED_KEY = "profile_cache_enabled"
PROFILE_CACHE_DAYS_KEY = "profile_cache_days"
PROFILE_CACHE_DAY_OPTIONS = ("1", "3", "7", "30", "90", "120", "forever")


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
    if not config.PROFILES_DIR.exists():
        return 0

    for profile_dir in config.PROFILES_DIR.iterdir():
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
        config.BASE_DIR.resolve(),
        config.PROFILES_DIR.resolve(),
        Path("/").resolve(),
    }
    if resolved in unsafe_paths or len(resolved.parts) <= 2:
        return False
    if resolved.is_relative_to(config.PROFILES_DIR.resolve()):
        return True
    return _looks_like_browser_profile(resolved)


def _looks_like_browser_profile(path: Path) -> bool:
    return (path / "Local State").exists() or (path / "Default").is_dir()
