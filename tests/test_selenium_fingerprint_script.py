from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from selenium.webdriver.chrome.options import Options as ChromeOptions

from app_config import APP_CONFIG
from browser_backends import selenium_backend as selenium_backend_module
from browser_backends.fingerprint.templates import JS_DIR
from browser_backends.selenium_backend import (
    SeleniumBrowserBackend,
    _apply_chromium_fingerprint,
    _build_chromium_fingerprint_script,
    _build_user_agent_metadata,
    _configure_chromium_fingerprint_extension,
    _configure_default_extensions,
    _log_fingerprint_runtime_state,
    _webrtc_leak_prevent_extension_path,
)
from models.browser_config import BrowserConfig
from models.fingerprint_config import FingerprintConfig
from models.session_entry import SessionEntry


class _LegacyFingerprintConfig:
    hide_automation = True
    hide_headless = True
    spoof_plugins = True
    spoof_languages: list[str] = []
    user_agent = None
    canvas_mode = "noise"
    canvas_noise_level = 0.02
    webgl_vendor = None
    webgl_renderer = None
    audio_noise = False
    font_list: list[str] = []
    font_spoof_count = 0
    timezone = None
    geolocation = None
    locale: list[str] = []
    webrtc_mode = "proxy_dns"
    hardware_concurrency = None
    device_memory = None
    platform = None
    tls_profile = None
    spoof_touch_support = True
    spoof_connection = True
    spoof_permissions = True
    spoof_feature_detection = True
    hide_adblock_signs = False
    spoof_battery = True
    custom_js_before_load: list[str] = []
    custom_js_after_load: list[str] = []


class SeleniumFingerprintScriptTest(unittest.TestCase):
    def test_chromium_options_use_fingerprint_user_agent(self) -> None:
        user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/134.0.0.0 Safari/537.36"
        )
        session = SessionEntry(
            id=1,
            name="Session",
            url="about:blank",
            browser="chrome",
            profile_path="profile",
            custom_user_agent="Legacy session User-Agent",
        )
        browser_config = BrowserConfig(
            id=None,
            key="chrome",
            display_name="Chrome / Chromium",
            browser_type="chromium",
        )
        driver = mock.Mock()

        with tempfile.TemporaryDirectory() as profile_dir:
            with (
                mock.patch.object(
                    selenium_backend_module,
                    "_browser_binary_from_config",
                    return_value=None,
                ),
                mock.patch.object(selenium_backend_module, "_configure_default_extensions"),
                mock.patch.object(
                    selenium_backend_module,
                    "_configure_chromium_fingerprint_extension",
                ),
                mock.patch.object(selenium_backend_module, "_apply_chromium_fingerprint"),
                mock.patch.object(
                    selenium_backend_module.webdriver,
                    "Chrome",
                    return_value=driver,
                ) as chrome_mock,
            ):
                SeleniumBrowserBackend._open_chromium(
                    session,
                    browser_config,
                    Path(profile_dir),
                    proxy_config=None,
                    fingerprint_config=FingerprintConfig(user_agent=user_agent),
                )

        options = chrome_mock.call_args.kwargs["options"]
        self.assertIn(f"--user-agent={user_agent}", options.arguments)
        self.assertNotIn("--user-agent=Legacy session User-Agent", options.arguments)

    def test_chromium_options_ignore_legacy_session_user_agent_without_fingerprint(self) -> None:
        session = SessionEntry(
            id=1,
            name="Session",
            url="about:blank",
            browser="chrome",
            profile_path="profile",
            custom_user_agent="Legacy session User-Agent",
        )
        browser_config = BrowserConfig(
            id=None,
            key="chrome",
            display_name="Chrome / Chromium",
            browser_type="chromium",
        )
        driver = mock.Mock()

        with tempfile.TemporaryDirectory() as profile_dir:
            with (
                mock.patch.object(
                    selenium_backend_module,
                    "_browser_binary_from_config",
                    return_value=None,
                ),
                mock.patch.object(selenium_backend_module, "_configure_default_extensions"),
                mock.patch.object(
                    selenium_backend_module.webdriver,
                    "Chrome",
                    return_value=driver,
                ) as chrome_mock,
            ):
                SeleniumBrowserBackend._open_chromium(
                    session,
                    browser_config,
                    Path(profile_dir),
                    proxy_config=None,
                    fingerprint_config=None,
                )

        options = chrome_mock.call_args.kwargs["options"]
        self.assertFalse(
            any(argument.startswith("--user-agent=") for argument in options.arguments)
        )

    def test_runtime_state_verification_reads_preload_marker(self) -> None:
        driver = mock.Mock()
        driver.execute_script.return_value = {
            "marker": True,
            "platform": "Win32",
            "webdriver": None,
            "userAgent": "Mozilla/5.0",
        }

        _log_fingerprint_runtime_state(driver, 1)

        driver.execute_script.assert_called_once()

    def test_script_contains_canvas_webgl_and_font_patches(self) -> None:
        script = _build_chromium_fingerprint_script(
            FingerprintConfig(
                canvas_mode="noise",
                canvas_noise_level=0.02,
                canvas_noise_seed=123456789,
                webgl_vendor="Google Inc. (NVIDIA)",
                webgl_renderer="ANGLE (NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0)",
                font_list=["Arial", "Calibri"],
                font_spoof_count=1,
            )
        )

        self.assertIn("CanvasRenderingContext2D.prototype", script)
        self.assertIn("prototype.getImageData", script)
        self.assertIn("OffscreenCanvasRenderingContext2D", script)
        self.assertIn("HTMLCanvasElement.prototype.toDataURL", script)
        self.assertIn("HTMLCanvasElement.prototype.toBlob", script)
        self.assertIn("OffscreenCanvas.prototype.convertToBlob", script)
        self.assertIn("__secureBrowserCanvasExportPatched", script)
        self.assertIn("copyCanvasWithNoise", script)
        self.assertIn("applyCanvasFingerprint(imageData)", script)
        self.assertIn('"seed": 123456789', script)
        self.assertIn("WEBGL_debug_renderer_info", script)
        self.assertIn("WebGLRenderingContext", script)
        self.assertIn("secureBrowserWeakWebGLNoise", script)
        self.assertIn("prototype.readPixels", script)
        self.assertIn("noisyWebGLCanvasDataURL", script)
        self.assertIn("queryLocalFonts", script)
        self.assertIn("Object.getPrototypeOf(document.fonts)", script)
        self.assertIn("stripFontShorthand", script)
        self.assertIn("CanvasRenderingContext2D.prototype.measureText", script)
        self.assertIn("secureBrowserPatchWorkerConstructor('Worker')", script)
        self.assertIn("secureBrowserPatchWorkerConstructor('SharedWorker')", script)
        self.assertIn("secureBrowserWorkerFingerprintScript", script)
        self.assertIn("secureBrowserWorkerCanvas2DPatched", script)
        self.assertIn("HTMLElement.prototype, 'offsetWidth'", script)
        self.assertIn("HTMLElement.prototype, 'offsetHeight'", script)
        self.assertIn("Element.prototype.getBoundingClientRect", script)
        self.assertIn("Element.prototype.getClientRects", script)
        self.assertNotIn("__SECURE_BROWSER_CONFIG__", script)
        self.assertNotIn("__SECURE_BROWSER_WORKER_SCRIPT__", script)

    def test_canvas_patch_changes_with_canvas_seed(self) -> None:
        first = _build_chromium_fingerprint_script(
            FingerprintConfig(canvas_noise_seed=111, audio_noise=False)
        )
        second = _build_chromium_fingerprint_script(
            FingerprintConfig(canvas_noise_seed=222, audio_noise=False)
        )

        self.assertIn('"seed": 111', first)
        self.assertIn('"seed": 222', second)
        self.assertNotEqual(first, second)

    def test_canvas_patch_accepts_legacy_config_without_canvas_seed(self) -> None:
        script = _build_chromium_fingerprint_script(_LegacyFingerprintConfig())  # type: ignore[arg-type]

        self.assertIn("secureBrowserCanvasSeed", script)
        self.assertIn('"seed": ', script)

    def test_fingerprint_js_templates_are_present(self) -> None:
        expected_templates = {
            "audio.js",
            "canvas.js",
            "content_filter.js",
            "device.js",
            "features_core.js",
            "fonts.js",
            "geolocation.js",
            "headless.js",
            "webgl.js",
            "worker_fingerprint.js",
            "worker_wrapper.js",
        }

        self.assertEqual(
            expected_templates,
            {path.name for path in JS_DIR.glob("*.js")},
        )

    def test_script_contains_headless_audio_and_content_filter_patches(self) -> None:
        script = _build_chromium_fingerprint_script(FingerprintConfig(hide_adblock_signs=True))

        self.assertIn("secureBrowserStripHeadless", script)
        self.assertIn("secureBrowserAudioNoiseSeed", script)
        self.assertIn("AudioBuffer.prototype.getChannelData", script)
        self.assertIn("AnalyserNode.prototype", script)
        self.assertIn("secureBrowserAdBlockBaitPattern", script)
        self.assertIn("window.getComputedStyle", script)
        self.assertIn("patchAdBlockMetric", script)

    def test_headless_audio_and_content_filter_patches_can_be_disabled(self) -> None:
        script = _build_chromium_fingerprint_script(
            FingerprintConfig(
                hide_headless=False,
                audio_noise=False,
                hide_adblock_signs=False,
            )
        )

        self.assertNotIn("secureBrowserStripHeadless", script)
        self.assertNotIn("secureBrowserAudioNoiseSeed", script)
        self.assertNotIn("secureBrowserAdBlockBaitPattern", script)

    def test_script_contains_features_detection_patch(self) -> None:
        script = _build_chromium_fingerprint_script(
            FingerprintConfig(
                connection_downlink=22.0,
                connection_effective_type="4g",
                connection_rtt=50,
                connection_type="wifi",
                battery_level=0.74,
            )
        )

        self.assertIn("secureBrowserFeatureDetectionProfile", script)
        self.assertIn("Navigator.prototype", script)
        self.assertIn("'pdfViewerEnabled'", script)
        self.assertIn("'cookieEnabled'", script)
        self.assertIn("Navigator.prototype.javaEnabled", script)
        self.assertIn("window.chrome", script)
        self.assertIn("patchModernizrResults", script)
        self.assertIn("Object.entries(stableResults)", script)
        self.assertIn("HTMLAudioElement.prototype", script)
        self.assertIn("HTMLVideoElement.prototype", script)
        self.assertIn("CSS.supports", script)
        self.assertIn("localstorage: true", script)
        self.assertIn("peerconnection: secureBrowserFeatureDetectionProfile.webrtc", script)
        self.assertIn("RTCPeerConnection", script)
        self.assertIn("Navigator.prototype, 'maxTouchPoints'", script)
        self.assertIn("Navigator.prototype, 'connection'", script)
        self.assertIn('"downlink": 22.0', script)
        self.assertIn('"type": "wifi"', script)
        self.assertIn("Navigator.prototype.getBattery", script)
        self.assertIn("level: 0.74", script)
        self.assertIn("navigator.permissions.query", script)

    def test_script_contains_screen_device_patch_when_configured(self) -> None:
        script = _build_chromium_fingerprint_script(
            FingerprintConfig(
                screen_width=1512,
                screen_height=982,
                screen_avail_width=1512,
                screen_avail_height=944,
                color_depth=30,
                pixel_depth=30,
                device_scale_factor=2.0,
            )
        )

        self.assertIn("secureBrowserDeviceConfig", script)
        self.assertIn("Screen.prototype", script)
        self.assertIn("'devicePixelRatio'", script)
        self.assertIn('"screenWidth": 1512', script)

    def test_script_contains_geolocation_patch_when_configured(self) -> None:
        script = _build_chromium_fingerprint_script(
            FingerprintConfig(geolocation=(55.755826, 37.6173))
        )

        self.assertIn("secureBrowserGeolocationConfig", script)
        self.assertIn("Navigator.prototype, 'geolocation'", script)
        self.assertIn('"latitude": 55.755826', script)
        self.assertIn('"longitude": 37.6173', script)
        self.assertIn('geolocation: "granted"', script)

    def test_apply_chromium_fingerprint_grants_geolocation_permission(self) -> None:
        driver = mock.Mock()
        config = FingerprintConfig(geolocation=(55.755826, 37.6173))

        _apply_chromium_fingerprint(driver, config, "https://browserleaks.com/geo")

        driver.execute_cdp_cmd.assert_any_call(
            "Browser.grantPermissions",
            {
                "permissions": ["geolocation"],
                "origin": "https://browserleaks.com",
            },
        )
        driver.execute_cdp_cmd.assert_any_call(
            "Emulation.setGeolocationOverride",
            {
                "latitude": 55.755826,
                "longitude": 37.6173,
                "accuracy": 100,
            },
        )

    def test_features_detection_patch_can_be_disabled(self) -> None:
        script = _build_chromium_fingerprint_script(
            FingerprintConfig(
                spoof_feature_detection=False,
                spoof_touch_support=False,
                spoof_connection=False,
                spoof_permissions=False,
                spoof_battery=False,
            )
        )

        self.assertNotIn("secureBrowserFeatureDetectionProfile", script)
        self.assertNotIn("patchModernizrResults", script)
        self.assertNotIn("'pdfViewerEnabled'", script)
        self.assertNotIn("Navigator.prototype.getBattery", script)

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

    def test_client_hint_metadata_uses_manual_device_values(self) -> None:
        config = FingerprintConfig(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/134.0.0.0 Safari/537.36"
            ),
            platform="Win32",
            client_hints_platform_version="15.0.0",
            client_hints_architecture="x86",
            client_hints_bitness="64",
            client_hints_model="Workstation",
        )

        metadata = _build_user_agent_metadata(config)

        self.assertIsNotNone(metadata)
        self.assertEqual(metadata["platformVersion"], "15.0.0")  # type: ignore[index]
        self.assertEqual(metadata["model"], "Workstation")  # type: ignore[index]

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
        self.assertIn(f"--disable-extensions-except={extension_path}", options.arguments)
        self.assertIn(
            "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
            options.arguments,
        )

    def test_fingerprint_extension_is_loaded_with_webrtc_extension(self) -> None:
        profile_dir = Path(tempfile.mkdtemp())
        options = ChromeOptions()
        _configure_default_extensions(options)
        _configure_chromium_fingerprint_extension(
            options,
            profile_dir,
            FingerprintConfig(
                canvas_mode="noise",
                webgl_vendor="Google Inc. (NVIDIA)",
                webgl_renderer="ANGLE (NVIDIA)",
                font_list=["Arial"],
            ),
        )

        extension_dirs = [
            path
            for path in profile_dir.iterdir()
            if path.name.startswith(
                f"{APP_CONFIG.chromium_extensions.fingerprint_extension_dirname}_"
            )
        ]
        self.assertEqual(len(extension_dirs), 1)
        extension_dir = extension_dirs[0]
        self.assertTrue((extension_dir / "manifest.json").is_file())
        self.assertTrue((extension_dir / "fingerprint.js").is_file())
        self.assertTrue((extension_dir / "background.js").is_file())
        manifest = json.loads((extension_dir / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["background"]["service_worker"], "background.js")
        self.assertIn("scripting", manifest["permissions"])
        self.assertIn("webNavigation", manifest["permissions"])
        self.assertIn("<all_urls>", manifest["host_permissions"])
        background_script = (extension_dir / "background.js").read_text(encoding="utf-8")
        self.assertIn("chrome.webNavigation.onCommitted", background_script)
        self.assertIn("chrome.scripting.registerContentScripts", background_script)
        self.assertIn("runAt: 'document_start'", background_script)
        self.assertIn("chrome.scripting.executeScript", background_script)
        self.assertIn("world: 'MAIN'", background_script)

        load_extension_args = [
            argument for argument in options.arguments if argument.startswith("--load-extension=")
        ]
        self.assertEqual(len(load_extension_args), 1)
        self.assertIn(str(_webrtc_leak_prevent_extension_path()), load_extension_args[0])
        self.assertIn(str(extension_dir), load_extension_args[0])
        enable_extension_args = [
            argument
            for argument in options.arguments
            if argument.startswith("--disable-extensions-except=")
        ]
        self.assertEqual(len(enable_extension_args), 1)
        self.assertIn(str(_webrtc_leak_prevent_extension_path()), enable_extension_args[0])
        self.assertIn(str(extension_dir), enable_extension_args[0])

    def test_fingerprint_extension_path_changes_with_script_digest(self) -> None:
        profile_dir = Path(tempfile.mkdtemp())
        stale_dir = profile_dir / APP_CONFIG.chromium_extensions.fingerprint_extension_dirname
        stale_dir.mkdir()
        (stale_dir / "fingerprint.js").write_text("old", encoding="utf-8")

        first_options = ChromeOptions()
        _configure_chromium_fingerprint_extension(
            first_options,
            profile_dir,
            FingerprintConfig(canvas_noise_seed=111),
        )
        first_extension_dirs = {
            path.name
            for path in profile_dir.iterdir()
            if path.name.startswith(
                f"{APP_CONFIG.chromium_extensions.fingerprint_extension_dirname}_"
            )
        }
        self.assertEqual(len(first_extension_dirs), 1)
        self.assertFalse(stale_dir.exists())

        second_options = ChromeOptions()
        _configure_chromium_fingerprint_extension(
            second_options,
            profile_dir,
            FingerprintConfig(canvas_noise_seed=222),
        )
        second_extension_dirs = {
            path.name
            for path in profile_dir.iterdir()
            if path.name.startswith(
                f"{APP_CONFIG.chromium_extensions.fingerprint_extension_dirname}_"
            )
        }

        self.assertEqual(len(second_extension_dirs), 1)
        self.assertNotEqual(first_extension_dirs, second_extension_dirs)


if __name__ == "__main__":
    unittest.main()
