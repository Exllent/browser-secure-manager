from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
from typing import Any

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options as ChromeOptions

from models.browser_config import BrowserConfig
from models.fingerprint_config import FingerprintConfig
from models.proxy_config import ProxyConfig
from models.session_entry import SessionEntry

logger = logging.getLogger(__name__)


def _webrtc_leak_prevent_extension_path() -> Path:
    return Path(__file__).resolve().parents[1] / "browser_extensions" / "webrtc_leak_prevent"


class SeleniumBrowserBackend:
    def __init__(self) -> None:
        self._drivers: dict[int, webdriver.Chrome] = {}

    def open_session(
        self,
        session: SessionEntry,
        browser_config: BrowserConfig,
        proxy_config: ProxyConfig | None = None,
        fingerprint_config: FingerprintConfig | None = None,
    ) -> None:
        if session.id is None:
            raise ValueError("Session must be saved before opening a browser")

        self.close_session(session.id)
        profile_dir = Path(session.profile_path).expanduser()
        profile_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "Opening Chromium session %s with %s profile %s",
            session.id,
            browser_config.display_name,
            profile_dir,
        )

        try:
            driver = self._open_chromium(
                session,
                browser_config,
                profile_dir,
                proxy_config,
                fingerprint_config,
            )
        except Exception:
            logger.exception("Failed to open browser for session %s", session.id)
            raise

        self._drivers[session.id] = driver
        driver.get(session.url)
        if fingerprint_config is not None:
            for script in fingerprint_config.custom_js_after_load:
                driver.execute_script(script)

    def close_session(self, session_id: int) -> None:
        driver = self._drivers.pop(session_id, None)
        if driver is None:
            return

        logger.info("Closing browser for session %s", session_id)
        try:
            driver.quit()
        except WebDriverException:
            logger.exception("Failed to close browser for session %s", session_id)

    def close_all(self) -> None:
        for session_id in list(self._drivers):
            self.close_session(session_id)

    def discover_installed_browsers(self) -> list[BrowserConfig]:
        return discover_installed_browsers()

    @staticmethod
    def _open_chromium(
        session: SessionEntry,
        browser_config: BrowserConfig,
        profile_dir: Path,
        proxy_config: ProxyConfig | None,
        fingerprint_config: FingerprintConfig | None,
    ) -> webdriver.Chrome:
        options = ChromeOptions()
        browser_binary = _browser_binary_from_config(
            browser_config,
            default_browser_name="Chrome / Chromium",
            default_env_var="CHROME_BINARY",
            command_names=(
                "google-chrome",
                "chrome",
                "chromium",
                "chromium-browser",
                "brave-browser",
                "microsoft-edge",
                "vivaldi",
                "opera",
            ),
            candidates=_chromium_candidates(),
            version_keywords=_chromium_version_keywords(),
            required=False,
        )
        if browser_binary is not None:
            options.binary_location = str(browser_binary)
        options.add_argument(f"--user-data-dir={profile_dir}")
        options.add_argument(f"--window-size={session.window_width},{session.window_height}")
        user_agent = _effective_user_agent(session, fingerprint_config)
        if user_agent:
            options.add_argument(f"--user-agent={user_agent}")
        if proxy_config is not None:
            options.add_argument(f"--proxy-server={proxy_config.browser_proxy_url()}")
        _configure_default_extensions(options)
        if fingerprint_config is not None:
            _configure_chromium_options(options, fingerprint_config)

        driver = webdriver.Chrome(options=options)
        if fingerprint_config is not None:
            _apply_chromium_fingerprint(driver, fingerprint_config)
        return driver


def discover_installed_browsers() -> list[BrowserConfig]:
    discovered: list[BrowserConfig] = []
    seen_paths: set[str] = set()
    known_browsers = (
        ("chrome", "Chrome / Chromium", "chromium", _chromium_candidates()),
        ("brave", "Brave", "chromium", _brave_candidates()),
        ("edge", "Microsoft Edge", "chromium", _edge_candidates()),
        ("vivaldi", "Vivaldi", "chromium", _vivaldi_candidates()),
        ("opera", "Opera", "chromium", _opera_candidates()),
    )

    for key, display_name, browser_type, candidates in known_browsers:
        for candidate in candidates:
            path = Path(candidate).expanduser()
            path_key = str(path)
            if path_key in seen_paths or not path.is_file() or not _looks_like_native_binary(path):
                continue
            try:
                _validate_browser_binary(
                    path=path,
                    browser_name=display_name,
                    version_keywords=_chromium_version_keywords(),
                )
            except RuntimeError:
                continue

            seen_paths.add(path_key)
            discovered.append(
                BrowserConfig(
                    id=None,
                    key=key,
                    display_name=display_name,
                    browser_type=browser_type,
                    executable_path=str(path),
                    enabled=True,
                )
            )
            break

    return discovered


SeleniumBrowserManager = SeleniumBrowserBackend


def _effective_user_agent(
    session: SessionEntry,
    fingerprint_config: FingerprintConfig | None,
) -> str:
    if fingerprint_config is not None and fingerprint_config.user_agent:
        return fingerprint_config.user_agent.strip()
    return session.custom_user_agent.strip()


def _build_user_agent_metadata(config: FingerprintConfig) -> dict[str, Any] | None:
    if not config.user_agent:
        return None

    full_version = _chromium_full_version(config.user_agent)
    major_version = full_version.split(".", 1)[0]
    platform_name = _client_hint_platform(config)
    if platform_name is None:
        return None

    return {
        "brands": [
            {"brand": "Chromium", "version": major_version},
            {"brand": "Google Chrome", "version": major_version},
            {"brand": "Not.A/Brand", "version": "99"},
        ],
        "fullVersionList": [
            {"brand": "Chromium", "version": full_version},
            {"brand": "Google Chrome", "version": full_version},
            {"brand": "Not.A/Brand", "version": "99.0.0.0"},
        ],
        "fullVersion": full_version,
        "platform": platform_name,
        "platformVersion": _client_hint_platform_version(config.user_agent, platform_name),
        "architecture": _client_hint_architecture(config),
        "model": "",
        "mobile": False,
        "bitness": "64",
        "wow64": False,
    }


def _chromium_full_version(user_agent: str) -> str:
    match = re.search(r"(?:Chrome|Chromium)/([0-9]+(?:\.[0-9]+){0,3})", user_agent)
    if not match:
        return "134.0.0.0"

    parts = match.group(1).split(".")
    return ".".join((parts + ["0", "0", "0", "0"])[:4])


def _client_hint_platform(config: FingerprintConfig) -> str | None:
    user_agent = config.user_agent or ""
    if "Macintosh" in user_agent or config.platform == "MacIntel":
        return "macOS"
    if "Windows NT" in user_agent or config.platform in {"Win32", "Win64"}:
        return "Windows"
    if "Linux" in user_agent or "X11" in user_agent or (config.platform or "").startswith("Linux"):
        return "Linux"
    return None


def _client_hint_platform_version(user_agent: str, platform_name: str) -> str:
    if platform_name == "macOS":
        match = re.search(r"Mac OS X ([0-9_]+)", user_agent)
        if not match:
            return "14.0.0"
        parts = match.group(1).replace("_", ".").split(".")
        return ".".join((parts + ["0", "0"])[:3])

    if platform_name == "Windows":
        match = re.search(r"Windows NT ([0-9.]+)", user_agent)
        if not match:
            return "10.0.0"
        parts = match.group(1).split(".")
        return ".".join((parts + ["0"])[:3])

    return ""


def _client_hint_architecture(config: FingerprintConfig) -> str:
    renderer = config.webgl_renderer or ""
    if "Apple M" in renderer or "arm" in (config.platform or "").lower():
        return "arm"
    return "x86"


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


def _configure_default_extensions(options: ChromeOptions) -> None:
    extension_dir = _webrtc_leak_prevent_extension_path()
    manifest_path = extension_dir / "manifest.json"
    if not manifest_path.is_file():
        logger.warning("WebRTC Leak Prevent extension is missing: %s", extension_dir)
        return

    options.add_argument(f"--load-extension={extension_dir}")
    options.add_argument("--force-webrtc-ip-handling-policy=disable_non_proxied_udp")


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

    if config.hide_automation:
        patches.append(
            """
            Object.defineProperty(Navigator.prototype, 'webdriver', {
                get: () => undefined,
                configurable: true
            });
            """
        )

    patches.extend(config.custom_js_before_load)

    if config.platform:
        patches.append(
            f"""
            Object.defineProperty(Navigator.prototype, 'platform', {{
                get: () => {json.dumps(config.platform)},
                configurable: true
            }});
            """
        )

    user_agent_patch = _build_user_agent_patch(config)
    if user_agent_patch:
        patches.append(user_agent_patch)

    languages = config.spoof_languages or config.locale
    if languages:
        patches.append(
            f"""
            Object.defineProperty(Navigator.prototype, 'languages', {{
                get: () => {json.dumps(languages)},
                configurable: true
            }});
            Object.defineProperty(Navigator.prototype, 'language', {{
                get: () => {json.dumps(languages[0])},
                configurable: true
            }});
            """
        )

    if config.hardware_concurrency is not None:
        patches.append(
            f"""
            Object.defineProperty(Navigator.prototype, 'hardwareConcurrency', {{
                get: () => {config.hardware_concurrency},
                configurable: true
            }});
            """
        )

    if config.device_memory is not None:
        patches.append(
            f"""
            Object.defineProperty(Navigator.prototype, 'deviceMemory', {{
                get: () => {config.device_memory},
                configurable: true
            }});
            """
        )

    if config.spoof_plugins:
        patches.append(
            """
            Object.defineProperty(Navigator.prototype, 'plugins', {
                get: () => [
                    {name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer'},
                    {name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai'},
                    {name: 'Native Client', filename: 'internal-nacl-plugin'}
                ],
                configurable: true
            });
            """
        )

    if config.webgl_vendor or config.webgl_renderer:
        patches.append(_build_webgl_patch(config))

    if config.spoof_touch_support:
        patches.append(
            """
            Object.defineProperty(Navigator.prototype, 'maxTouchPoints', {
                get: () => 0,
                configurable: true
            });
            """
        )

    if config.spoof_connection:
        patches.append(
            """
            Object.defineProperty(Navigator.prototype, 'connection', {
                get: () => ({
                    downlink: 10,
                    effectiveType: '4g',
                    rtt: 50,
                    saveData: false
                }),
                configurable: true
            });
            """
        )

    if config.spoof_battery:
        patches.append(
            """
            Navigator.prototype.getBattery = () => Promise.resolve({
                charging: true,
                chargingTime: 0,
                dischargingTime: Infinity,
                level: 1,
                addEventListener: () => undefined,
                removeEventListener: () => undefined
            });
            """
        )

    if config.spoof_permissions:
        patches.append(
            """
            if (navigator.permissions && navigator.permissions.query) {
                const originalPermissionsQuery = navigator.permissions.query.bind(navigator.permissions);
                navigator.permissions.query = (parameters) => {
                    if (parameters && parameters.name === 'notifications') {
                        return Promise.resolve({state: Notification.permission});
                    }
                    return originalPermissionsQuery(parameters);
                };
            }
            """
        )

    if config.canvas_mode in {"noise", "fixed"}:
        patches.append(_build_canvas_patch(config))

    if config.font_list or config.font_spoof_count:
        patches.append(_build_font_patch(config))

    if not patches:
        return ""

    return "'use strict';\n(() => {\n" + "\n".join(patches) + "\n})();"


def _build_user_agent_patch(config: FingerprintConfig) -> str:
    if not config.user_agent:
        return ""

    metadata = _build_user_agent_metadata(config)
    if metadata is None:
        return ""

    metadata_json = json.dumps(metadata)
    user_agent = json.dumps(config.user_agent)
    app_version = json.dumps(config.user_agent.removeprefix("Mozilla/"))
    return f"""
    const secureBrowserUserAgent = {user_agent};
    const secureBrowserUserAgentData = {metadata_json};

    Object.defineProperty(Navigator.prototype, 'userAgent', {{
        get: () => secureBrowserUserAgent,
        configurable: true
    }});

    Object.defineProperty(Navigator.prototype, 'appVersion', {{
        get: () => {app_version},
        configurable: true
    }});

    Object.defineProperty(Navigator.prototype, 'vendor', {{
        get: () => 'Google Inc.',
        configurable: true
    }});

    const buildUserAgentData = () => {{
        const data = {{
            brands: secureBrowserUserAgentData.brands.map((brand) => ({{...brand}})),
            mobile: secureBrowserUserAgentData.mobile,
            platform: secureBrowserUserAgentData.platform,
            getHighEntropyValues: async (hints) => {{
                const allowed = new Set(Array.isArray(hints) ? hints : []);
                const values = {{
                    brands: secureBrowserUserAgentData.brands.map((brand) => ({{...brand}})),
                    mobile: secureBrowserUserAgentData.mobile,
                    platform: secureBrowserUserAgentData.platform
                }};
                for (const key of allowed) {{
                    if (Object.prototype.hasOwnProperty.call(secureBrowserUserAgentData, key)) {{
                        values[key] = Array.isArray(secureBrowserUserAgentData[key])
                            ? secureBrowserUserAgentData[key].map((item) => ({{...item}}))
                            : secureBrowserUserAgentData[key];
                    }}
                }}
                return values;
            }},
            toJSON: () => ({{
                brands: secureBrowserUserAgentData.brands.map((brand) => ({{...brand}})),
                mobile: secureBrowserUserAgentData.mobile,
                platform: secureBrowserUserAgentData.platform
            }})
        }};
        return Object.freeze(data);
    }};

    Object.defineProperty(Navigator.prototype, 'userAgentData', {{
        get: buildUserAgentData,
        configurable: true
    }});
    """


def _build_webgl_patch(config: FingerprintConfig) -> str:
    vendor = json.dumps(config.webgl_vendor or "Google Inc.")
    renderer = json.dumps(config.webgl_renderer or "ANGLE")
    return f"""
    const fingerprintWebGLDebugInfo = {{
        UNMASKED_VENDOR_WEBGL: 37445,
        UNMASKED_RENDERER_WEBGL: 37446
    }};
    const patchWebGLPrototype = (prototype) => {{
        if (!prototype || prototype.__secureBrowserWebGLPatched) return;
        Object.defineProperty(prototype, '__secureBrowserWebGLPatched', {{ value: true }});

        const originalGetParameter = prototype.getParameter;
        prototype.getParameter = new Proxy(originalGetParameter, {{
            apply(target, thisArg, args) {{
                const parameter = args[0];
                if (parameter === 37445) return {vendor};
                if (parameter === 37446) return {renderer};
                return Reflect.apply(target, thisArg, args);
            }}
        }});

        const originalGetExtension = prototype.getExtension;
        prototype.getExtension = new Proxy(originalGetExtension, {{
            apply(target, thisArg, args) {{
                const name = args[0];
                if (String(name).toLowerCase() === 'webgl_debug_renderer_info') {{
                    return fingerprintWebGLDebugInfo;
                }}
                return Reflect.apply(target, thisArg, args);
            }}
        }});

        const originalGetSupportedExtensions = prototype.getSupportedExtensions;
        prototype.getSupportedExtensions = new Proxy(originalGetSupportedExtensions, {{
            apply(target, thisArg, args) {{
                const result = Reflect.apply(target, thisArg, args) || [];
                return result.includes('WEBGL_debug_renderer_info')
                    ? result
                    : [...result, 'WEBGL_debug_renderer_info'];
            }}
        }});
    }};
    patchWebGLPrototype(window.WebGLRenderingContext && WebGLRenderingContext.prototype);
    patchWebGLPrototype(window.WebGL2RenderingContext && WebGL2RenderingContext.prototype);
    """


def _build_canvas_patch(config: FingerprintConfig) -> str:
    noise_level = 0.0 if config.canvas_mode == "fixed" else config.canvas_noise_level
    noise = max(1, int(round(noise_level * 255)))
    return f"""
    const secureBrowserCanvasNoise = {noise};
    const secureBrowserCanvasMode = {json.dumps(config.canvas_mode)};
    const applyCanvasFingerprint = (imageData) => {{
        if (!imageData || !imageData.data) return imageData;
        const data = imageData.data;
        const step = secureBrowserCanvasMode === 'fixed'
            ? 32
            : Math.max(4, Math.floor(96 / Math.max(secureBrowserCanvasNoise, 1)));
        for (let i = 0; i < data.length; i += step * 4) {{
            data[i] = (data[i] + secureBrowserCanvasNoise) & 255;
            data[i + 1] = (data[i + 1] + 1) & 255;
            data[i + 2] = (data[i + 2] + 2) & 255;
        }}
        return imageData;
    }};

    if (window.CanvasRenderingContext2D) {{
        const originalGetImageData = CanvasRenderingContext2D.prototype.getImageData;
        CanvasRenderingContext2D.prototype.getImageData = new Proxy(originalGetImageData, {{
            apply(target, thisArg, args) {{
                const imageData = Reflect.apply(target, thisArg, args);
                return applyCanvasFingerprint(imageData);
            }}
        }});
    }}

    const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = new Proxy(originalToDataURL, {{
        apply(target, thisArg, args) {{
            try {{
                const context = thisArg.getContext('2d');
                if (context) {{
                    const imageData = context.getImageData(0, 0, thisArg.width, thisArg.height);
                    context.putImageData(applyCanvasFingerprint(imageData), 0, 0);
                }}
            }} catch (error) {{}}
            return Reflect.apply(target, thisArg, args);
        }}
    }});

    const originalToBlob = HTMLCanvasElement.prototype.toBlob;
    if (originalToBlob) {{
        HTMLCanvasElement.prototype.toBlob = new Proxy(originalToBlob, {{
            apply(target, thisArg, args) {{
                try {{
                    const context = thisArg.getContext('2d');
                    if (context) {{
                        const imageData = context.getImageData(0, 0, thisArg.width, thisArg.height);
                        context.putImageData(applyCanvasFingerprint(imageData), 0, 0);
                    }}
                }} catch (error) {{}}
                return Reflect.apply(target, thisArg, args);
            }}
        }});
    }}
    """


def _build_font_patch(config: FingerprintConfig) -> str:
    fonts = list(dict.fromkeys(config.font_list))
    for index in range(config.font_spoof_count):
        fonts.append(f"Secure UI {index + 1}")
    fonts_json = json.dumps(fonts)
    known_fonts_json = json.dumps(
        sorted(
            set(fonts)
            | {
                "Arial",
                "Calibri",
                "Cambria",
                "Courier New",
                "DejaVu Sans",
                "DejaVu Serif",
                "Helvetica",
                "Hiragino Sans",
                "Liberation Sans",
                "Menlo",
                "Monaco",
                "Noto Sans",
                "Osaka",
                "Segoe UI",
                "Tahoma",
                "Times",
                "Times New Roman",
                "Ubuntu",
                "Verdana",
                "Yu Gothic",
            }
        )
    )
    return f"""
    const secureBrowserFonts = new Set({fonts_json});
    const secureBrowserKnownFonts = new Set({known_fonts_json});
    const normalizeFontFamily = (value) => String(value || '')
        .split(',')
        .map((part) => part.trim().replace(/^['"]|['"]$/g, ''))
        .filter(Boolean);
    const profileHasFont = (families) => families.some((family) => secureBrowserFonts.has(family));
    const hasMaskedSystemFont = (families) => families.some((family) =>
        secureBrowserKnownFonts.has(family) && !secureBrowserFonts.has(family)
    );
    const replaceMaskedFonts = (fontValue) => {{
        let result = String(fontValue || '');
        for (const family of secureBrowserKnownFonts) {{
            if (secureBrowserFonts.has(family)) continue;
            const escaped = family.replace(/[.*+?^${{}}()|[\\]\\\\]/g, '\\\\$&');
            result = result.replace(new RegExp(`(["']?)${{escaped}}\\\\1`, 'g'), 'sans-serif');
        }}
        return result;
    }};

    if (document.fonts && document.fonts.check) {{
        const originalFontCheck = document.fonts.check.bind(document.fonts);
        document.fonts.check = (font, text) => {{
            const families = normalizeFontFamily(font);
            if (profileHasFont(families)) return true;
            if (hasMaskedSystemFont(families)) return false;
            return originalFontCheck(font, text);
        }};
    }}

    window.queryLocalFonts = async () => Array.from(secureBrowserFonts).map((family) => ({{
        family,
        fullName: family,
        postscriptName: family.replace(/\\s+/g, '-'),
        style: 'Regular'
    }}));

    if (window.CanvasRenderingContext2D) {{
        const originalMeasureText = CanvasRenderingContext2D.prototype.measureText;
        CanvasRenderingContext2D.prototype.measureText = new Proxy(originalMeasureText, {{
            apply(target, thisArg, args) {{
                const families = normalizeFontFamily(thisArg.font);
                if (hasMaskedSystemFont(families)) {{
                    const originalFont = thisArg.font;
                    try {{
                        thisArg.font = replaceMaskedFonts(originalFont);
                        return Reflect.apply(target, thisArg, args);
                    }} finally {{
                        thisArg.font = originalFont;
                    }}
                }}

                const metrics = Reflect.apply(target, thisArg, args);
                if (!profileHasFont(families)) return metrics;
                const widthOffset = families.join('').length % 7 / 100;
                return new Proxy(metrics, {{
                    get(metricTarget, property, receiver) {{
                        if (property === 'width') return Reflect.get(metricTarget, property, receiver) + widthOffset;
                        return Reflect.get(metricTarget, property, receiver);
                    }}
                }});
            }}
        }});
    }}
    """


def _browser_binary_from_config(
    browser_config: BrowserConfig,
    *,
    default_browser_name: str,
    default_env_var: str,
    command_names: tuple[str, ...],
    candidates: tuple[str, ...],
    version_keywords: tuple[str, ...],
    required: bool,
) -> Path | None:
    executable_path = browser_config.executable_path.strip()
    if executable_path:
        path = Path(executable_path).expanduser()
        _validate_browser_binary(
            path=path,
            browser_name=browser_config.display_name,
            version_keywords=(),
        )
        return path

    return _find_browser_binary(
        browser_name=default_browser_name,
        env_var=default_env_var,
        command_names=command_names,
        candidates=candidates,
        version_keywords=version_keywords,
        required=required,
    )


def _find_browser_binary(
    *,
    browser_name: str,
    env_var: str,
    command_names: tuple[str, ...],
    candidates: tuple[str, ...],
    version_keywords: tuple[str, ...],
    required: bool,
) -> Path | None:
    browser_candidates: list[str] = []

    env_binary = os.environ.get(env_var)
    if env_binary:
        browser_candidates.append(env_binary)

    browser_candidates.extend(candidates)

    for command_name in command_names:
        browser_from_path = shutil.which(command_name)
        if browser_from_path:
            browser_candidates.append(browser_from_path)

    checked: list[str] = []
    for candidate in dict.fromkeys(browser_candidates):
        path = Path(candidate).expanduser()
        if not path.is_file():
            checked.append(f"{path} (not found)")
            continue
        if not _looks_like_native_binary(path):
            checked.append(f"{path} (not a native browser binary)")
            continue

        try:
            _validate_browser_binary(
                path=path,
                browser_name=browser_name,
                version_keywords=version_keywords,
            )
        except RuntimeError as exc:
            checked.append(str(exc))
            continue

        return path

    if not required and not env_binary:
        return None

    details = "\n".join(f"- {item}" for item in checked)
    raise RuntimeError(
        f"{browser_name} executable was not found or is not usable by Selenium.\n"
        f"Install {browser_name}, or set {env_var} to the real browser executable.\n"
        "On Linux, Snap launchers can be rejected by webdriver; use the real binary path.\n\n"
        f"Checked:\n{details}"
    )


def _chromium_candidates() -> tuple[str, ...]:
    if sys.platform == "darwin":
        return (
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            str(Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        )
    if sys.platform == "win32":
        return (
            *_windows_browser_candidates(
                "Google/Chrome/Application",
                "chrome.exe",
                extra_env_vars=("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"),
            ),
            *_windows_browser_candidates(
                "Chromium/Application",
                "chrome.exe",
                extra_env_vars=("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"),
            ),
        )
    return (
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/snap/chromium/current/usr/lib/chromium-browser/chrome",
        "/snap/bin/chromium",
        "/opt/google/chrome/chrome",
    )


def _brave_candidates() -> tuple[str, ...]:
    if sys.platform == "darwin":
        return (
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            str(Path.home() / "Applications/Brave Browser.app/Contents/MacOS/Brave Browser"),
        )
    if sys.platform == "win32":
        return _windows_browser_candidates(
            "BraveSoftware/Brave-Browser/Application",
            "brave.exe",
            extra_env_vars=("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"),
        )
    return (
        "/usr/bin/brave-browser",
        "/usr/bin/brave",
        "/snap/bin/brave",
        "/opt/brave.com/brave/brave-browser",
    )


def _edge_candidates() -> tuple[str, ...]:
    if sys.platform == "darwin":
        return (
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            str(Path.home() / "Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
        )
    if sys.platform == "win32":
        return _windows_browser_candidates(
            "Microsoft/Edge/Application",
            "msedge.exe",
            extra_env_vars=("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"),
        )
    return (
        "/usr/bin/microsoft-edge",
        "/usr/bin/microsoft-edge-stable",
        "/opt/microsoft/msedge/msedge",
    )


def _vivaldi_candidates() -> tuple[str, ...]:
    if sys.platform == "darwin":
        return (
            "/Applications/Vivaldi.app/Contents/MacOS/Vivaldi",
            str(Path.home() / "Applications/Vivaldi.app/Contents/MacOS/Vivaldi"),
        )
    if sys.platform == "win32":
        return _windows_browser_candidates(
            "Vivaldi/Application",
            "vivaldi.exe",
            extra_env_vars=("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"),
        )
    return (
        "/usr/bin/vivaldi",
        "/usr/bin/vivaldi-stable",
        "/opt/vivaldi/vivaldi",
    )


def _opera_candidates() -> tuple[str, ...]:
    if sys.platform == "darwin":
        return (
            "/Applications/Opera.app/Contents/MacOS/Opera",
            str(Path.home() / "Applications/Opera.app/Contents/MacOS/Opera"),
        )
    if sys.platform == "win32":
        return (
            *_windows_browser_candidates(
                "Opera",
                "launcher.exe",
                extra_env_vars=("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"),
            ),
            *_windows_browser_candidates(
                "Programs/Opera",
                "launcher.exe",
                extra_env_vars=("LOCALAPPDATA",),
            ),
        )
    return (
        "/usr/bin/opera",
        "/snap/opera/current/usr/lib/x86_64-linux-gnu/opera/opera",
        "/snap/bin/opera",
        "/opt/opera/opera",
    )


def _windows_browser_candidates(
    app_subdir: str,
    executable_name: str,
    *,
    extra_env_vars: tuple[str, ...],
) -> tuple[str, ...]:
    paths: list[str] = []
    for env_var in extra_env_vars:
        base_dir = os.environ.get(env_var)
        if base_dir:
            paths.append(str(Path(base_dir) / app_subdir / executable_name))
    return tuple(paths)


def _looks_like_native_binary(path: Path) -> bool:
    try:
        with path.open("rb") as file:
            header = file.read(4)
    except OSError:
        return False

    if header.startswith((b"\x7fELF", b"MZ")):
        return True

    return header in {b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xfe\xed\xfa\xcf"}


def _validate_browser_binary(
    *,
    path: Path,
    browser_name: str,
    version_keywords: tuple[str, ...],
) -> None:
    if not path.is_file():
        raise RuntimeError(f"{browser_name}: executable file was not found: {path}")
    if not _looks_like_native_binary(path):
        raise RuntimeError(f"{browser_name}: selected file is not a native executable: {path}")

    try:
        result = _run_version_command(path)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"{browser_name}: cannot run executable: {path}\n{exc}") from exc

    output = f"{result.stdout}\n{result.stderr}".strip()
    keyword_mismatch = version_keywords and not any(keyword in output for keyword in version_keywords)
    if result.returncode != 0 or keyword_mismatch:
        raise RuntimeError(
            f"{browser_name}: selected executable does not look like a supported browser.\n"
            f"Path: {path}\n"
            f"Output: {output or f'exit code {result.returncode}'}"
        )


def _chromium_version_keywords() -> tuple[str, ...]:
    return (
        "Google Chrome",
        "Chromium",
        "Chrome",
        "Brave",
        "Microsoft Edge",
        "Vivaldi",
        "Opera",
    )


def _run_version_command(path: Path) -> subprocess.CompletedProcess[str]:
    kwargs: dict[str, object] = {
        "capture_output": True,
        "check": False,
        "text": True,
        "timeout": 5,
    }
    if platform.system() == "Windows":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        kwargs["startupinfo"] = startupinfo

    return subprocess.run([str(path), "--version"], **kwargs)
