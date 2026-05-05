from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from db import storage
from models.fingerprint_config import FingerprintConfig
from models.fingerprint_profile import FingerprintProfile
from models.proxy_config import ProxyConfig
from models.session_entry import SessionEntry


class BackupStorageTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._old_db_path = storage.DB_PATH
        self._old_profiles_dir = storage.PROFILES_DIR
        self.base_path = Path(self._tmp.name)
        storage.DB_PATH = self.base_path / "sessions.sqlite3"
        storage.PROFILES_DIR = self.base_path / "profiles"
        storage.init_db()
        for session in storage.get_all_sessions():
            if session.id is not None:
                storage.delete_session(session.id)

    def tearDown(self) -> None:
        storage.DB_PATH = self._old_db_path
        storage.PROFILES_DIR = self._old_profiles_dir
        self._tmp.cleanup()

    def test_full_backup_replaces_current_data(self) -> None:
        proxy = storage.upsert_proxy_config(
            ProxyConfig(
                id=None,
                label="Residential",
                host="127.0.0.1",
                port=9050,
                proxy_type="socks5",
            )
        )
        fingerprint = storage.upsert_fingerprint_profile(
            FingerprintProfile(
                id=None,
                name="Desktop RU",
                config=FingerprintConfig(timezone="Europe/Moscow", platform="Win32"),
            )
        )
        storage.create_session(
            SessionEntry(
                id=None,
                name="Portable",
                url="https://example.com",
                browser="chrome",
                profile_path="",
                proxy_id=proxy.id,
                fingerprint_id=fingerprint.id,
                notes="Important note",
            )
        )
        storage.set_setting("language", "ru")
        backup_path = self.base_path / "full_backup.json"

        storage.export_full_backup(backup_path)
        storage.create_session(
            SessionEntry(
                id=None,
                name="Remove me",
                url="about:blank",
                browser="chrome",
                profile_path="",
            )
        )
        storage.set_setting("language", "en")

        result = storage.import_backup(backup_path)

        sessions = storage.get_all_sessions()
        self.assertEqual(result["scope"], "full")
        self.assertEqual([session.name for session in sessions], ["Portable"])
        self.assertEqual(sessions[0].notes, "Important note")
        self.assertEqual(storage.get_setting("language"), "ru")
        self.assertIsNotNone(storage.get_proxy_config(sessions[0].proxy_id))
        self.assertIsNotNone(storage.get_fingerprint_profile(sessions[0].fingerprint_id))

    def test_session_backup_imports_only_related_records(self) -> None:
        proxy = storage.upsert_proxy_config(
            ProxyConfig(
                id=None,
                label="Session proxy",
                host="10.0.0.1",
                port=8080,
                proxy_type="http",
            )
        )
        fingerprint = storage.upsert_fingerprint_profile(
            FingerprintProfile(
                id=None,
                name="Session fingerprint",
                config=FingerprintConfig(locale=["en-US"], platform="Win32"),
            )
        )
        session = storage.create_session(
            SessionEntry(
                id=None,
                name="Single",
                url="https://python.org",
                browser="chrome",
                profile_path="",
                proxy_id=proxy.id,
                fingerprint_id=fingerprint.id,
                notes="Only this session",
            )
        )
        storage.set_setting("language", "ru")
        backup_path = self.base_path / "session_backup.json"

        storage.export_session_backup(session.id or 0, backup_path)
        storage.DB_PATH = self.base_path / "imported.sqlite3"
        storage.PROFILES_DIR = self.base_path / "imported_profiles"
        storage.init_db()
        for existing in storage.get_all_sessions():
            if existing.id is not None:
                storage.delete_session(existing.id)

        result = storage.import_backup(backup_path)

        imported_sessions = storage.get_all_sessions()
        self.assertEqual(result["scope"], "session")
        self.assertEqual([item.name for item in imported_sessions], ["Single"])
        self.assertEqual(imported_sessions[0].notes, "Only this session")
        self.assertEqual(storage.get_setting("language", "en"), "en")
        self.assertIsNotNone(storage.get_proxy_config(imported_sessions[0].proxy_id))
        self.assertIsNotNone(storage.get_fingerprint_profile(imported_sessions[0].fingerprint_id))


if __name__ == "__main__":
    unittest.main()
