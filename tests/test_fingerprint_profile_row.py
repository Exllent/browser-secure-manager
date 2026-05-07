from __future__ import annotations

import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from gui.fingerprint_profile_row import FingerprintProfileRow
from models.fingerprint_config import FingerprintConfig
from models.fingerprint_profile import FingerprintProfile


class FingerprintProfileRowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_generate_profile_updates_visible_name(self) -> None:
        row = FingerprintProfileRow(
            FingerprintProfile(
                id=1,
                name="Old fingerprint",
                config=FingerprintConfig(platform="Win32"),
                enabled=True,
            )
        )
        generated = FingerprintProfile(
            id=None,
            name="WIN Desktop RU | Ryzen 5 5600X | RTX 3060 | 8C 8GB | 1920x1080",
            config=FingerprintConfig(platform="Win32"),
            enabled=True,
        )

        with mock.patch(
            "gui.fingerprint_profile_row.generate_fingerprint_profile",
            return_value=generated,
        ):
            row.generate_profile()

        self.assertEqual(row.name_edit.text(), generated.name)
        self.assertEqual(row.to_profile().config.platform, "Win32")


if __name__ == "__main__":
    unittest.main()
