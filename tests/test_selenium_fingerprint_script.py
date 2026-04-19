from __future__ import annotations

import json
import unittest

from selenium.webdriver.chrome.options import Options as ChromeOptions

from browser_backends.selenium_backend import (
    _build_chromium_fingerprint_script,
    _build_user_agent_metadata,
    _configure_default_extensions,
    _webrtc_leak_prevent_extension_path,
)
from models.fingerprint_config import FingerprintConfig


class SeleniumFingerprintScriptTest(unittest.TestCase):
    def test_script_contains_canvas_webgl_and_font_patches(self) -> None:
        script = _build_chromium_fingerprint_script(
            FingerprintConfig(
                canvas_mode="noise",
                canvas_noise_level=0.02,
                webgl_vendor="Google Inc. (NVIDIA)",
                webgl_renderer="ANGLE (NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0)",
                font_list=["Arial", "Calibri"],
                font_spoof_count=1,
            )
        )

        self.assertIn("CanvasRenderingContext2D.prototype.getImageData", script)
        self.assertIn("HTMLCanvasElement.prototype.toDataURL", script)
        self.assertIn("HTMLCanvasElement.prototype.toBlob", script)
        self.assertIn("WEBGL_debug_renderer_info", script)
        self.assertIn("WebGLRenderingContext", script)
        self.assertIn("secureBrowserWeakWebGLNoise", script)
        self.assertIn("prototype.readPixels", script)
        self.assertIn("noisyWebGLCanvasDataURL", script)
        self.assertIn("window.queryLocalFonts", script)
        self.assertIn("document.fonts.check", script)
        self.assertIn("CanvasRenderingContext2D.prototype.measureText", script)
        self.assertIn("HTMLElement.prototype, 'offsetWidth'", script)
        self.assertIn("HTMLElement.prototype, 'offsetHeight'", script)
        self.assertIn("Element.prototype.getBoundingClientRect", script)
        self.assertIn("Element.prototype.getClientRects", script)

    def test_script_contains_client_hints_patch_for_macos_fingerprint(self) -> None:
        config = FingerprintConfig(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/134.0.0.0 Safari/537.36"
            ),
            platform="MacIntel",
            webgl_renderer="ANGLE (Apple, ANGLE Metal Renderer: Apple M2 Pro, Unspecified Version)",
        )

        metadata = _build_user_agent_metadata(config)
        script = _build_chromium_fingerprint_script(config)

        self.assertIsNotNone(metadata)
        self.assertEqual(metadata["platform"], "macOS")  # type: ignore[index]
        self.assertEqual(metadata["architecture"], "arm")  # type: ignore[index]
        self.assertIn("Navigator.prototype, 'userAgentData'", script)
        self.assertIn('"platform": "macOS"', script)
        self.assertIn("getHighEntropyValues", script)

    def test_webrtc_leak_prevent_extension_is_loaded_by_default(self) -> None:
        extension_path = _webrtc_leak_prevent_extension_path()
        manifest_path = extension_path / "manifest.json"
        background_path = extension_path / "background.js"

        self.assertTrue(manifest_path.is_file())
        self.assertTrue(background_path.is_file())

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["manifest_version"], 3)
        self.assertIn("privacy", manifest["permissions"])

        options = ChromeOptions()
        _configure_default_extensions(options)

        self.assertIn(f"--load-extension={extension_path}", options.arguments)
        self.assertIn(
            "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
            options.arguments,
        )


if __name__ == "__main__":
    unittest.main()
