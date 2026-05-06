from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError

from app_config import APP_CONFIG


class AppConfigTest(unittest.TestCase):
    def test_app_config_is_frozen(self) -> None:
        with self.assertRaises(FrozenInstanceError):
            APP_CONFIG.storage = APP_CONFIG.storage  # type: ignore[misc]

        with self.assertRaises(FrozenInstanceError):
            APP_CONFIG.storage.default_browser_key = "firefox"  # type: ignore[misc]

    def test_app_config_uses_immutable_collections(self) -> None:
        self.assertIsInstance(APP_CONFIG.profile_cache.day_options, tuple)
        self.assertIsInstance(APP_CONFIG.browser_discovery.candidates, tuple)
        self.assertIsInstance(APP_CONFIG.fingerprint_generation.presets, tuple)


if __name__ == "__main__":
    unittest.main()
