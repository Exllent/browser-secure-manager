from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from browser_backends import browser_discovery
from browser_backends.browser_discovery import _validate_browser_binary


class BrowserDiscoveryTest(unittest.TestCase):
    def test_windows_validation_does_not_launch_browser_binary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            browser_path = Path(temp_dir) / "chrome.exe"
            browser_path.write_bytes(b"MZ\x90\x00fake browser")

            with (
                patch.object(browser_discovery.sys, "platform", "win32"),
                patch.object(browser_discovery, "_run_version_command") as run_version_command,
            ):
                _validate_browser_binary(
                    path=browser_path,
                    browser_name="Chrome / Chromium",
                    version_keywords=("Chrome",),
                )

            run_version_command.assert_not_called()

    def test_windows_discovery_accepts_candidate_without_version_probe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            local_app_data = Path(temp_dir) / "LocalAppData"
            browser_path = local_app_data / "Google" / "Chrome" / "Application" / "chrome.exe"
            browser_path.parent.mkdir(parents=True)
            browser_path.write_bytes(b"MZ\x90\x00fake browser")

            with (
                patch.object(browser_discovery.sys, "platform", "win32"),
                patch.dict(browser_discovery.os.environ, {"LOCALAPPDATA": str(local_app_data)}),
                patch.object(browser_discovery, "_run_version_command") as run_version_command,
            ):
                discovered = browser_discovery.discover_installed_browsers()

            run_version_command.assert_not_called()
            self.assertEqual(len(discovered), 1)
            self.assertEqual(discovered[0].key, "chrome")
            self.assertEqual(discovered[0].executable_path, str(browser_path))


if __name__ == "__main__":
    unittest.main()
