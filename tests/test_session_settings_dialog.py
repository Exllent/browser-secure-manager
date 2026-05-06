from __future__ import annotations

import unittest

from gui.session_settings_dialog import _fingerprint_combo_label
from models.fingerprint_config import FingerprintConfig
from models.fingerprint_profile import FingerprintProfile


class SessionSettingsDialogTest(unittest.TestCase):
    def test_fingerprint_combo_label_includes_runtime_identity(self) -> None:
        profile = FingerprintProfile(
            id=20,
            name="Generated fingerprint",
            config=FingerprintConfig(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/134.0.0.0 Safari/537.36"
                ),
                platform="Win32",
                canvas_noise_seed=123456789,
            ),
        )

        label = _fingerprint_combo_label(profile)

        self.assertIn("Generated fingerprint", label)
        self.assertIn("#20", label)
        self.assertIn("Windows", label)
        self.assertIn("Win32", label)
        self.assertIn("canvas 123456789", label)


if __name__ == "__main__":
    unittest.main()
