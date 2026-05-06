from __future__ import annotations

import hashlib
import json
import logging
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions

from app_config import APP_CONFIG
from models.fingerprint_config import FingerprintConfig

from browser_backends.chromium_extensions import _add_chromium_extension

from .audio import _build_audio_patch
from .canvas import _build_canvas_patch
from .content_filter import _build_content_filter_patch
from .features_detection import _build_features_detection_patch
from .fonts import _build_font_patch
from .geolocation import _build_geolocation_patch
from .headless import _build_headless_patch
from .navigator import _build_navigator_patches
from .user_agent import _build_user_agent_metadata, _build_user_agent_patch
from .webgl import _build_webgl_patch
from .workers import _build_worker_fingerprint_patch, _needs_worker_fingerprint_patch

logger = logging.getLogger(__name__)


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
        logger.info("Configuring Chromium WebRTC disable mode")
        options.add_argument("--disable-webrtc")
    elif config.webrtc_mode in {"proxy_dns", "public_ip_only"}:
        logger.info("Configuring Chromium WebRTC IP handling policy: %s", config.webrtc_mode)
        options.add_argument(APP_CONFIG.chromium_extensions.disable_non_proxied_udp_argument)


def _configure_chromium_fingerprint_extension(
    options: ChromeOptions,
    profile_dir: Path,
    config: FingerprintConfig,
) -> None:
    script = _build_chromium_fingerprint_script(config)
    if not script:
        logger.info("Fingerprint extension was not created because no fingerprint script was generated")
        return

    extension_dir = _fingerprint_extension_dir(profile_dir, script)
    _cleanup_old_fingerprint_extensions(profile_dir, keep_dir=extension_dir)
    extension_dir.mkdir(parents=True, exist_ok=True)
    (extension_dir / APP_CONFIG.chromium_extensions.manifest_filename).write_text(
        json.dumps(
            {
                "manifest_version": 3,
                "name": APP_CONFIG.chromium_extensions.fingerprint_extension_name,
                "version": APP_CONFIG.chromium_extensions.fingerprint_extension_version,
                "permissions": ["scripting", "tabs", "webNavigation"],
                "host_permissions": ["<all_urls>"],
                "background": {
                    "service_worker": (
                        APP_CONFIG.chromium_extensions.fingerprint_background_filename
                    ),
                },
                "content_scripts": [
                    {
                        "matches": ["<all_urls>"],
                        "js": [APP_CONFIG.chromium_extensions.fingerprint_script_filename],
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
    (extension_dir / APP_CONFIG.chromium_extensions.fingerprint_script_filename).write_text(
        script,
        encoding="utf-8",
    )
    (extension_dir / APP_CONFIG.chromium_extensions.fingerprint_background_filename).write_text(
        _build_fingerprint_background_script(),
        encoding="utf-8",
    )
    _add_chromium_extension(options, extension_dir)
    logger.info(
        "Fingerprint extension prepared at %s with canvas seed %s",
        extension_dir,
        getattr(config, "canvas_noise_seed", None),
    )


def _build_fingerprint_background_script() -> str:
    script_filename = json.dumps(APP_CONFIG.chromium_extensions.fingerprint_script_filename)
    return f"""
const secureBrowserFingerprintScript = {script_filename};
const secureBrowserRegisteredScriptId = 'secure-browser-fingerprint-main-world';
const secureBrowserInjectableProtocols = new Set(['http:', 'https:', 'file:']);

const secureBrowserCanInject = (url) => {{
    if (!url) return false;
    try {{
        return secureBrowserInjectableProtocols.has(new URL(url).protocol);
    }} catch (error) {{
        return false;
    }}
}};

const secureBrowserInjectFingerprint = async (tabId) => {{
    try {{
        await chrome.scripting.executeScript({{
            target: {{ tabId, allFrames: true }},
            files: [secureBrowserFingerprintScript],
            world: 'MAIN',
            injectImmediately: true
        }});
    }} catch (error) {{
        // chrome://, extension pages, and closed tabs are expected to reject injection.
    }}
}};

const secureBrowserRegisterFingerprintScript = async () => {{
    try {{
        await chrome.scripting.unregisterContentScripts({{
            ids: [secureBrowserRegisteredScriptId]
        }});
    }} catch (error) {{
    }}

    try {{
        await chrome.scripting.registerContentScripts([{{
            id: secureBrowserRegisteredScriptId,
            matches: ['<all_urls>'],
            js: [secureBrowserFingerprintScript],
            runAt: 'document_start',
            allFrames: true,
            matchOriginAsFallback: true,
            world: 'MAIN',
            persistAcrossSessions: false
        }}]);
    }} catch (error) {{
    }}
}};

secureBrowserRegisterFingerprintScript();

chrome.runtime.onInstalled.addListener(() => {{
    secureBrowserRegisterFingerprintScript();
}});

chrome.runtime.onStartup.addListener(() => {{
    secureBrowserRegisterFingerprintScript();
}});

chrome.webNavigation.onCommitted.addListener((details) => {{
    if (details.frameId !== 0 || !secureBrowserCanInject(details.url)) return;
    secureBrowserInjectFingerprint(details.tabId);
}});

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {{
    const url = changeInfo.url || tab.pendingUrl || tab.url || '';
    if (!secureBrowserCanInject(url)) return;
    if (changeInfo.status === 'loading' || changeInfo.status === 'complete' || changeInfo.url) {{
        secureBrowserInjectFingerprint(tabId);
    }}
}});

chrome.tabs.onActivated.addListener(async (activeInfo) => {{
    try {{
        const tab = await chrome.tabs.get(activeInfo.tabId);
        if (secureBrowserCanInject(tab.url || tab.pendingUrl || '')) {{
            secureBrowserInjectFingerprint(activeInfo.tabId);
        }}
    }} catch (error) {{
    }}
}});
""".strip()


def _apply_chromium_fingerprint(
    driver: webdriver.Chrome,
    config: FingerprintConfig,
    session_url: str = "",
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
        logger.info("Applied CDP User-Agent override")

    if config.timezone:
        driver.execute_cdp_cmd("Emulation.setTimezoneOverride", {"timezoneId": config.timezone})
        logger.info("Applied CDP timezone override: %s", config.timezone)

    if config.geolocation is not None:
        latitude, longitude = config.geolocation
        _grant_geolocation_permission(driver, session_url)
        driver.execute_cdp_cmd(
            "Emulation.setGeolocationOverride",
            {
                "latitude": latitude,
                "longitude": longitude,
                "accuracy": 100,
            },
        )
        logger.info("Applied CDP geolocation override")

    script = _build_chromium_fingerprint_script(config)
    if script:
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": script})
        logger.info("Registered fingerprint preload script through CDP")


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

    geolocation_patch = _build_geolocation_patch(config)
    if geolocation_patch:
        patches.append(geolocation_patch)

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


def _grant_geolocation_permission(driver: webdriver.Chrome, session_url: str) -> None:
    origin = _origin_from_url(session_url)
    payload: dict[str, Any] = {"permissions": ["geolocation"]}
    if origin:
        payload["origin"] = origin

    try:
        driver.execute_cdp_cmd("Browser.grantPermissions", payload)
        logger.info("Granted geolocation permission%s", f" for {origin}" if origin else "")
    except Exception:
        logger.exception("Failed to grant geolocation permission")


def _origin_from_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}"


def _fingerprint_extension_dir(profile_dir: Path, script: str) -> Path:
    digest = hashlib.sha256(script.encode("utf-8")).hexdigest()[
        : APP_CONFIG.chromium_extensions.fingerprint_extension_digest_length
    ]
    dirname = f"{APP_CONFIG.chromium_extensions.fingerprint_extension_dirname}_{digest}"
    return profile_dir / dirname


def _cleanup_old_fingerprint_extensions(profile_dir: Path, *, keep_dir: Path) -> None:
    prefix = APP_CONFIG.chromium_extensions.fingerprint_extension_dirname
    if not profile_dir.exists():
        return

    for path in profile_dir.iterdir():
        if path == keep_dir or not path.is_dir():
            continue
        if path.name != prefix and not path.name.startswith(f"{prefix}_"):
            continue
        try:
            shutil.rmtree(path)
            logger.info("Removed stale fingerprint extension at %s", path)
        except OSError:
            logger.exception("Failed to remove stale fingerprint extension at %s", path)
