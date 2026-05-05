from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions

from models.fingerprint_config import FingerprintConfig

from browser_backends.chromium_extensions import _add_chromium_extension

from .audio import _build_audio_patch
from .canvas import _build_canvas_patch
from .content_filter import _build_content_filter_patch
from .features_detection import _build_features_detection_patch
from .fonts import _build_font_patch
from .headless import _build_headless_patch
from .navigator import _build_navigator_patches
from .user_agent import _build_user_agent_metadata, _build_user_agent_patch
from .webgl import _build_webgl_patch
from .workers import _build_worker_fingerprint_patch, _needs_worker_fingerprint_patch


def _configure_chromium_options(options: ChromeOptions, config: FingerprintConfig) -> None:
    if config.hide_automation:
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument("--disable-blink-features=AutomationControlled")

    languages = config.spoof_languages or config.locale
    if languages:
        options.add_experimental_option("prefs", {"intl.accept_languages": ",".join(languages)})
        options.add_argument(f"--lang={languages[0]}")

    if config.webrtc_mode == "disable":
        options.add_argument("--disable-webrtc")
    elif config.webrtc_mode in {"proxy_dns", "public_ip_only"}:
        options.add_argument("--force-webrtc-ip-handling-policy=disable_non_proxied_udp")


def _configure_chromium_fingerprint_extension(
    options: ChromeOptions,
    profile_dir: Path,
    config: FingerprintConfig,
) -> None:
    script = _build_chromium_fingerprint_script(config)
    if not script:
        return

    extension_dir = profile_dir / "secure_browser_fingerprint_extension"
    extension_dir.mkdir(parents=True, exist_ok=True)
    (extension_dir / "manifest.json").write_text(
        json.dumps(
            {
                "manifest_version": 3,
                "name": "Secure Browser Fingerprint",
                "version": "1.0.0",
                "content_scripts": [
                    {
                        "matches": ["<all_urls>"],
                        "js": ["fingerprint.js"],
                        "run_at": "document_start",
                        "all_frames": True,
                        "match_about_blank": True,
                        "world": "MAIN",
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (extension_dir / "fingerprint.js").write_text(script, encoding="utf-8")
    _add_chromium_extension(options, extension_dir)


def _apply_chromium_fingerprint(
    driver: webdriver.Chrome,
    config: FingerprintConfig,
) -> None:
    if config.user_agent:
        override: dict[str, Any] = {
            "userAgent": config.user_agent,
            "platform": config.platform or "",
            "acceptLanguage": ",".join(config.spoof_languages or config.locale),
        }
        user_agent_metadata = _build_user_agent_metadata(config)
        if user_agent_metadata is not None:
            override["userAgentMetadata"] = user_agent_metadata
        driver.execute_cdp_cmd("Network.setUserAgentOverride", override)

    if config.timezone:
        driver.execute_cdp_cmd("Emulation.setTimezoneOverride", {"timezoneId": config.timezone})

    if config.geolocation is not None:
        latitude, longitude = config.geolocation
        driver.execute_cdp_cmd(
            "Emulation.setGeolocationOverride",
            {
                "latitude": latitude,
                "longitude": longitude,
                "accuracy": 100,
            },
        )

    script = _build_chromium_fingerprint_script(config)
    if script:
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": script})


def _build_chromium_fingerprint_script(config: FingerprintConfig) -> str:
    patches: list[str] = []

    patches.extend(config.custom_js_before_load)
    patches.extend(_build_navigator_patches(config))

    if config.hide_headless:
        patches.append(_build_headless_patch())

    user_agent_patch = _build_user_agent_patch(config)
    if user_agent_patch:
        patches.append(user_agent_patch)

    if config.webgl_vendor or config.webgl_renderer:
        patches.append(_build_webgl_patch(config))

    features_detection_patch = _build_features_detection_patch(config)
    if features_detection_patch:
        patches.append(features_detection_patch)

    if config.canvas_mode in {"noise", "fixed"}:
        patches.append(_build_canvas_patch(config))

    if config.audio_noise:
        patches.append(_build_audio_patch(config))

    if config.font_list or config.font_spoof_count:
        patches.append(_build_font_patch(config))

    if config.hide_adblock_signs:
        patches.append(_build_content_filter_patch())

    if _needs_worker_fingerprint_patch(config):
        patches.append(_build_worker_fingerprint_patch(config))

    if not patches:
        return ""

    return (
        "'use strict';\n(() => {\n"
        "if (globalThis.__secureBrowserFingerprintPreloadApplied) return;\n"
        "Object.defineProperty(globalThis, '__secureBrowserFingerprintPreloadApplied', { value: true });\n"
        + "\n".join(patches)
        + "\n})();"
    )
