from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from app.app_service import AppService
from browser_backends.base import BrowserBackend
from db import config as db_config
from db import profile_cache
from db import storage
from models.browser_config import BrowserConfig
from models.session_entry import SessionEntry


class _DummyBrowserBackend(BrowserBackend):
    def open_session(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        return None

    def close_session(self, session_id: int) -> None:
        return None

    def close_all(self) -> None:
        return None

    def discover_installed_browsers(self) -> list[BrowserConfig]:
        return []


class ProfileCacheTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._old_db_path = db_config.DB_PATH
        self._old_profiles_dir = db_config.PROFILES_DIR
        self.base_path = Path(self._tmp.name)
        db_config.DB_PATH = self.base_path / "sessions.sqlite3"
        db_config.PROFILES_DIR = self.base_path / "profiles"
        storage.init_db()
        for session in storage.get_all_sessions():
            if session.id is not None:
                storage.delete_session(session.id)
        for profile_dir in db_config.PROFILES_DIR.iterdir():
            storage.delete_profile_directory(profile_dir)

    def tearDown(self) -> None:
        db_config.DB_PATH = self._old_db_path
        db_config.PROFILES_DIR = self._old_profiles_dir
        self._tmp.cleanup()

    def test_disabled_profile_cache_deletes_profile_on_session_delete(self) -> None:
        storage.set_setting("profile_cache_enabled", "0")
        app_service = AppService(_DummyBrowserBackend())
        session = storage.create_session(
            SessionEntry(
                id=None,
                name="Delete profile",
                url="about:blank",
                browser="chrome",
                profile_path="",
            )
        )
        profile_path = Path(session.profile_path)
        (profile_path / "marker.txt").write_text("profile", encoding="utf-8")

        app_service.delete_session(session.id or 0)

        self.assertFalse(profile_path.exists())
        self.assertEqual(storage.get_all_sessions(), [])

    def test_profile_cache_cleanup_removes_only_expired_orphan_profiles(self) -> None:
        storage.set_setting("profile_cache_enabled", "1")
        storage.set_setting("profile_cache_days", "1")
        active_session = storage.create_session(
            SessionEntry(
                id=None,
                name="Keep profile",
                url="about:blank",
                browser="chrome",
                profile_path="",
            )
        )
        active_path = Path(active_session.profile_path)
        orphan_path = db_config.PROFILES_DIR / "session_999"
        orphan_path.mkdir(parents=True)
        old_profile_created_at = profile_cache._profile_created_at  # noqa: SLF001
        try:
            profile_cache._profile_created_at = lambda _path: datetime(2000, 1, 1, tzinfo=UTC)  # type: ignore[assignment]  # noqa: SLF001

            deleted = storage.cleanup_expired_profile_cache()
        finally:
            profile_cache._profile_created_at = old_profile_created_at  # type: ignore[assignment]  # noqa: SLF001

        self.assertEqual(deleted, 1)
        self.assertTrue(active_path.exists())
        self.assertFalse(orphan_path.exists())


if __name__ == "__main__":
    unittest.main()
