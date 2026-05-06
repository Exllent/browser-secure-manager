from __future__ import annotations

import unittest

from gui.session_settings_dialog import _fingerprint_combo_label
from models.fingerprint_profile import FingerprintProfile


class SessionSettingsDialogTest(unittest.TestCase):
    def test_fingerprint_combo_label_uses_profile_name_only(self) -> None:
        profile = FingerprintProfile(
            id=20,
            name="Generated fingerprint",
        )

        label = _fingerprint_combo_label(profile)

        self.assertEqual(label, "Generated fingerprint")


if __name__ == "__main__":
    unittest.main()
