from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from db import config as db_config
from db import storage
from models.fingerprint_config import FingerprintConfig
from models.fingerprint_profile import FingerprintProfile
from models.session_entry import SessionEntry


class FingerprintStorageTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._old_db_path = db_config.DB_PATH
        self._old_profiles_dir = db_config.PROFILES_DIR
        base_path = Path(self._tmp.name)
        db_config.DB_PATH = base_path / "sessions.sqlite3"
        db_config.PROFILES_DIR = base_path / "profiles"
        storage.init_db()

    def tearDown(self) -> None:
        db_config.DB_PATH = self._old_db_path
        db_config.PROFILES_DIR = self._old_profiles_dir
        self._tmp.cleanup()

    def test_fingerprint_profile_can_be_attached_to_session(self) -> None:
        profile = storage.upsert_fingerprint_profile(
            FingerprintProfile(
                id=None,
                name="Desktop RU",
                config=FingerprintConfig(
                    timezone="Europe/Moscow",
                    locale=["ru-RU", "ru"],
                    platform="Win32",
                ),
            )
        )
        session = storage.create_session(
            SessionEntry(
                id=None,
                name="Session",
                url="about:blank",
                browser="chrome",
                profile_path="",
                fingerprint_id=profile.id,
            )
        )

        saved = storage.get_all_sessions()[-1]

        self.assertEqual(saved.id, session.id)
        self.assertEqual(saved.fingerprint_id, profile.id)
        self.assertEqual(storage.get_fingerprint_profile(profile.id).config.timezone, "Europe/Moscow")

    def test_deleting_fingerprint_detaches_sessions(self) -> None:
        profile = storage.upsert_fingerprint_profile(
            FingerprintProfile(id=None, name="Temporary", config=FingerprintConfig())
        )
        storage.create_session(
            SessionEntry(
                id=None,
                name="Session",
                url="about:blank",
                browser="chrome",
                profile_path="",
                fingerprint_id=profile.id,
            )
        )

        storage.delete_fingerprint_profile(profile.id)

        self.assertIsNone(storage.get_all_sessions()[-1].fingerprint_id)
        self.assertIsNone(storage.get_fingerprint_profile(profile.id))

    def test_init_db_removes_unsupported_browser_configs(self) -> None:
        with storage._connect() as connection:  # noqa: SLF001
            connection.execute(
                """
                INSERT INTO browser_configs (key, display_name, browser_type, executable_path, enabled)
                VALUES ('firefox', 'Firefox', 'firefox', '', 1)
                """
            )
            connection.execute(
                """
                INSERT INTO sessions (
                    name, url, browser, profile_path, proxy_id, fingerprint_id,
                    proxy_label, custom_user_agent, notes, window_width, window_height, status
                )
                VALUES ('Firefox session', 'about:blank', 'firefox', '', NULL, NULL, '', '', '', 1280, 800, 'idle')
                """
            )

        storage.init_db()

        browser_keys = {config.key for config in storage.get_browser_configs()}
        migrated_session = storage.get_all_sessions()[-1]

        self.assertNotIn("firefox", browser_keys)
        self.assertEqual(migrated_session.browser, "chrome")


if __name__ == "__main__":
    unittest.main()
