from __future__ import annotations

import unittest
from pathlib import Path

from browser_backends.fingerprint.boundaries import (
    FINGERPRINT_SURFACE_BOUNDARIES,
    MAC_ADDRESS_BOUNDARY,
    WEBGPU_DEEP_SPOOFING_BOUNDARY,
)


class FingerprintBoundariesTest(unittest.TestCase):
    def test_mac_address_is_documented_as_non_browser_exposed(self) -> None:
        self.assertIs(FINGERPRINT_SURFACE_BOUNDARIES["mac_address"], MAC_ADDRESS_BOUNDARY)
        self.assertEqual(MAC_ADDRESS_BOUNDARY.status, "success")
        self.assertFalse(MAC_ADDRESS_BOUNDARY.browser_exposed)
        self.assertIn("does not expose", MAC_ADDRESS_BOUNDARY.reason)
        self.assertIn("outside the browser", MAC_ADDRESS_BOUNDARY.action)

    def test_mac_address_boundary_is_in_docs(self) -> None:
        docs = Path("docs/fingerprint_boundaries.md").read_text(encoding="utf-8")

        self.assertIn("MAC Address", docs)
        self.assertIn("does not expose", docs)
        self.assertIn("outside the browser fingerprint script", docs)

    def test_webgpu_deep_spoofing_is_documented_as_bounded(self) -> None:
        self.assertIs(
            FINGERPRINT_SURFACE_BOUNDARIES["webgpu_deep_spoofing"],
            WEBGPU_DEEP_SPOOFING_BOUNDARY,
        )
        self.assertEqual(WEBGPU_DEEP_SPOOFING_BOUNDARY.status, "success")
        self.assertTrue(WEBGPU_DEEP_SPOOFING_BOUNDARY.browser_exposed)
        self.assertIn("host adapter", WEBGPU_DEEP_SPOOFING_BOUNDARY.reason)
        self.assertIn("DevTools-level strategy", WEBGPU_DEEP_SPOOFING_BOUNDARY.action)

    def test_webgpu_deep_spoofing_boundary_is_in_docs(self) -> None:
        docs = Path("docs/fingerprint_boundaries.md").read_text(encoding="utf-8")

        self.assertIn("WebGPU Deep Spoofing", docs)
        self.assertIn("host WebGPU adapter", docs)
        self.assertIn("browser-engine patch", docs)


if __name__ == "__main__":
    unittest.main()
