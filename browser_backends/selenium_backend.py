from __future__ import annotations

import itertools
import json
import logging
import threading
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options as ChromeOptions

from app_config import APP_CONFIG
from models.browser_config import BrowserConfig
from models.fingerprint_config import FingerprintConfig
from models.proxy_config import ProxyConfig
from models.session_entry import SessionEntry

from .browser_discovery import (
    _browser_binary_from_config,
    _chromium_candidates,
    _chromium_version_keywords,
    discover_installed_browsers,
)
from .chromium_bookmarks import ensure_chromium_default_bookmarks
from .chromium_extensions import (
    _configure_default_extensions,
    _webrtc_leak_prevent_extension_path,
)
from .fingerprint import (
    _apply_chromium_fingerprint,
    _build_chromium_fingerprint_script,
    _build_chromium_worker_fingerprint_script,
    _build_user_agent_metadata,
    _configure_chromium_fingerprint_extension,
    _configure_chromium_options,
)

logger = logging.getLogger(__name__)

__all__ = [
    "SeleniumBrowserBackend",
    "SeleniumBrowserManager",
    "discover_installed_browsers",
    "_build_chromium_fingerprint_script",
    "_build_chromium_worker_fingerprint_script",
    "_build_user_agent_metadata",
    "_configure_chromium_fingerprint_extension",
    "_configure_default_extensions",
    "_webrtc_leak_prevent_extension_path",
]


class SeleniumBrowserBackend:
    def __init__(self) -> None:
        self._drivers: dict[int, webdriver.Chrome] = {}
        self._fingerprint_enforcers: dict[int, _FingerprintTargetEnforcer] = {}

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
        ensure_chromium_default_bookmarks(profile_dir)

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
        if fingerprint_config is not None:
            enforcer = _FingerprintTargetEnforcer(
                driver, fingerprint_config, session.url, session.id
            )
            enforcer.start()
            self._fingerprint_enforcers[session.id] = enforcer
        logger.info("Navigating session %s to %s", session.id, session.url)
        driver.get(session.url)
        if fingerprint_config is not None:
            _log_fingerprint_runtime_state(driver, session.id)
        if fingerprint_config is not None:
            for script in fingerprint_config.custom_js_after_load:
                logger.info("Executing post-load fingerprint script for session %s", session.id)
                driver.execute_script(script)

    def close_session(self, session_id: int) -> None:
        enforcer = self._fingerprint_enforcers.pop(session_id, None)
        if enforcer is not None:
            enforcer.close()
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

    def is_session_running(self, session_id: int) -> bool:
        driver = self._drivers.get(session_id)
        if driver is None:
            return False

        try:
            return bool(driver.window_handles)
        except WebDriverException:
            logger.info("Browser session %s is no longer reachable", session_id)
            self._drivers.pop(session_id, None)
            return False

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
            default_browser_name=APP_CONFIG.browser_discovery.default_browser_name,
            default_env_var=APP_CONFIG.browser_discovery.default_env_var,
            command_names=APP_CONFIG.browser_discovery.chromium_command_names,
            candidates=_chromium_candidates(),
            version_keywords=_chromium_version_keywords(),
            required=False,
        )
        if browser_binary is not None:
            options.binary_location = str(browser_binary)
        logger.info("Preparing Chromium options for session %s", session.id)
        options.add_argument(f"--user-data-dir={profile_dir}")
        options.add_argument(f"--window-size={session.window_width},{session.window_height}")
        user_agent = _effective_user_agent(fingerprint_config)
        if user_agent:
            logger.info("Applying User-Agent override for session %s", session.id)
            options.add_argument(f"--user-agent={user_agent}")
        if proxy_config is not None:
            logger.info("Applying proxy %s for session %s", proxy_config.display_name(), session.id)
            options.add_argument(f"--proxy-server={proxy_config.browser_proxy_url()}")
            _configure_proxy_dns_leak_prevention(options, proxy_config)
        _configure_default_extensions(options)
        if fingerprint_config is not None:
            logger.info("Applying fingerprint config for session %s", session.id)
            _configure_chromium_options(options, fingerprint_config)
            _configure_chromium_fingerprint_extension(options, profile_dir, fingerprint_config)

        logger.info("Starting webdriver for session %s", session.id)
        driver = webdriver.Chrome(options=options)
        if fingerprint_config is not None:
            _apply_chromium_fingerprint(driver, fingerprint_config, session.url)
        return driver


SeleniumBrowserManager = SeleniumBrowserBackend


def _effective_user_agent(
    fingerprint_config: FingerprintConfig | None,
) -> str:
    if fingerprint_config is not None and fingerprint_config.user_agent:
        return fingerprint_config.user_agent.strip()
    return ""


class _FingerprintTargetEnforcer:
    def __init__(
        self,
        driver: webdriver.Chrome,
        fingerprint_config: FingerprintConfig,
        session_url: str,
        session_id: int | None,
    ) -> None:
        self.driver = driver
        self.fingerprint_config = fingerprint_config
        self.session_url = session_url
        self.session_id = session_id
        self.script = _build_chromium_fingerprint_script(fingerprint_config)
        self.worker_script = _build_chromium_worker_fingerprint_script(fingerprint_config)
        self._counter = itertools.count(1)
        self._lock = threading.Lock()
        self._closed = threading.Event()
        self._socket: Any = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if not self.script:
            return
        debugger_address = _debugger_address(self.driver)
        if not debugger_address:
            logger.warning(
                "Could not start fingerprint target enforcer for session %s: no debugger address",
                self.session_id,
            )
            return

        try:
            import websocket  # type: ignore[import-not-found]

            version_url = f"http://{debugger_address}/json/version"
            with urllib.request.urlopen(version_url, timeout=2) as response:
                version = json.loads(response.read().decode("utf-8"))
            websocket_url = version["webSocketDebuggerUrl"]
            self._socket = websocket.create_connection(
                websocket_url,
                timeout=2,
                suppress_origin=True,
            )
            self._socket.settimeout(None)
        except Exception:
            logger.exception(
                "Could not connect fingerprint target enforcer for session %s",
                self.session_id,
            )
            self.close()
            return

        self._thread = threading.Thread(
            target=self._read_loop,
            name=f"secure-browser-fingerprint-cdp-{self.session_id}",
            daemon=True,
        )
        self._thread.start()
        self._send(
            "Target.setAutoAttach",
            {
                "autoAttach": True,
                "waitForDebuggerOnStart": True,
                "flatten": True,
            },
        )
        self._send("Target.setDiscoverTargets", {"discover": True})
        logger.info("Fingerprint target enforcer started for session %s", self.session_id)

    def close(self) -> None:
        self._closed.set()
        socket = self._socket
        self._socket = None
        if socket is not None:
            try:
                socket.close()
            except Exception:
                pass

    def _read_loop(self) -> None:
        while not self._closed.is_set():
            try:
                raw_message = self._socket.recv()
            except Exception:
                if not self._closed.is_set():
                    logger.info(
                        "Fingerprint target enforcer stopped for session %s",
                        self.session_id,
                    )
                return

            try:
                message = json.loads(raw_message)
            except Exception:
                continue

            if message.get("method") == "Target.attachedToTarget":
                params = message.get("params") or {}
                session_id = params.get("sessionId")
                target_info = params.get("targetInfo") or {}
                target_type = target_info.get("type")
                if not isinstance(session_id, str):
                    continue
                if target_type in {"page", "iframe"}:
                    self._configure_target(session_id)
                elif target_type in {"worker", "shared_worker"}:
                    self._configure_worker_target(session_id)

    def _configure_target(self, cdp_session_id: str) -> None:
        user_agent_override = _user_agent_override_payload(self.fingerprint_config)
        extra_headers = _extra_http_headers(self.fingerprint_config)
        if user_agent_override is not None or extra_headers:
            self._send("Network.enable", {}, session_id=cdp_session_id)
        if user_agent_override is not None:
            self._send(
                "Network.setUserAgentOverride",
                user_agent_override,
                session_id=cdp_session_id,
            )
        if extra_headers:
            self._send(
                "Network.setExtraHTTPHeaders",
                {"headers": extra_headers},
                session_id=cdp_session_id,
            )
        if self.fingerprint_config.timezone:
            self._send(
                "Emulation.setTimezoneOverride",
                {"timezoneId": self.fingerprint_config.timezone},
                session_id=cdp_session_id,
            )
        if self.fingerprint_config.geolocation is not None:
            latitude, longitude = self.fingerprint_config.geolocation
            self._send(
                "Emulation.setGeolocationOverride",
                {"latitude": latitude, "longitude": longitude, "accuracy": 100},
                session_id=cdp_session_id,
            )
        self._send("Page.enable", {}, session_id=cdp_session_id)
        self._send(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": self.script},
            session_id=cdp_session_id,
        )
        self._send(
            "Runtime.evaluate",
            {"expression": self.script, "includeCommandLineAPI": False},
            session_id=cdp_session_id,
        )
        self._send("Runtime.runIfWaitingForDebugger", {}, session_id=cdp_session_id)
        logger.info(
            "Fingerprint preload installed before target start for session %s",
            self.session_id,
        )

    def _configure_worker_target(self, cdp_session_id: str) -> None:
        if not self.worker_script:
            self._send("Runtime.runIfWaitingForDebugger", {}, session_id=cdp_session_id)
            return
        if self.fingerprint_config.timezone:
            self._send(
                "Emulation.setTimezoneOverride",
                {"timezoneId": self.fingerprint_config.timezone},
                session_id=cdp_session_id,
            )
        self._send("Runtime.enable", {}, session_id=cdp_session_id)
        self._send(
            "Runtime.evaluate",
            {"expression": self.worker_script, "includeCommandLineAPI": False},
            session_id=cdp_session_id,
        )
        self._send("Runtime.runIfWaitingForDebugger", {}, session_id=cdp_session_id)
        logger.info(
            "Fingerprint worker preload installed before target start for session %s",
            self.session_id,
        )

    def _send(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        session_id: str | None = None,
    ) -> None:
        socket = self._socket
        if socket is None:
            return
        message: dict[str, Any] = {
            "id": next(self._counter),
            "method": method,
            "params": params or {},
        }
        if session_id is not None:
            message["sessionId"] = session_id
        try:
            with self._lock:
                socket.send(json.dumps(message))
        except Exception:
            if not self._closed.is_set():
                logger.exception(
                    "Failed to send fingerprint CDP command %s for session %s",
                    method,
                    self.session_id,
                )


def _debugger_address(driver: webdriver.Chrome) -> str:
    chrome_options = driver.capabilities.get("goog:chromeOptions", {})
    if not isinstance(chrome_options, dict):
        return ""
    debugger_address = chrome_options.get("debuggerAddress", "")
    return str(debugger_address or "")


def _user_agent_override_payload(config: FingerprintConfig) -> dict[str, Any] | None:
    if not config.user_agent:
        return None
    override: dict[str, Any] = {
        "userAgent": config.user_agent,
        "platform": config.platform or "",
        "acceptLanguage": ",".join(config.spoof_languages or config.locale),
    }
    user_agent_metadata = _build_user_agent_metadata(config)
    if user_agent_metadata is not None:
        override["userAgentMetadata"] = user_agent_metadata
    return override


def _extra_http_headers(config: FingerprintConfig) -> dict[str, str]:
    headers: dict[str, str] = {}
    do_not_track = getattr(config, "do_not_track", None)
    if do_not_track is not None:
        headers["DNT"] = do_not_track
    return headers


def _configure_proxy_dns_leak_prevention(
    options: ChromeOptions,
    proxy_config: ProxyConfig,
) -> None:
    host = proxy_config.host.strip()
    excludes = ["localhost", "127.0.0.1", "::1"]
    if host:
        excludes.append(host)
        parsed_host = urlsplit(f"//{host}").hostname
        if parsed_host and parsed_host not in excludes:
            excludes.append(parsed_host)
    rules = ",".join(["MAP * ~NOTFOUND", *(f"EXCLUDE {item}" for item in excludes)])
    options.add_argument(f"--host-resolver-rules={rules}")
    options.add_argument("--disable-features=AsyncDns")


def _log_fingerprint_runtime_state(driver: webdriver.Chrome, session_id: int | None) -> None:
    try:
        state = driver.execute_script("""
            const canvas = document.createElement('canvas');
            canvas.width = 16;
            canvas.height = 16;
            const context = canvas.getContext('2d');
            if (context) {
                context.fillStyle = '#123456';
                context.fillRect(0, 0, 16, 16);
            }
            const canvasDataUrl = canvas.toDataURL();
            return {
                marker: globalThis.__secureBrowserFingerprintPreloadApplied === true,
                canvasDataUrlPrefix: canvasDataUrl.slice(0, 48),
                canvasDataUrlLength: canvasDataUrl.length,
                platform: navigator.platform,
                webdriver: navigator.webdriver,
                userAgent: navigator.userAgent
            };
            """)
    except Exception:
        logger.exception("Could not verify fingerprint runtime state for session %s", session_id)
        return

    logger.info("Fingerprint runtime state for session %s: %s", session_id, state)
    if not isinstance(state, dict) or not state.get("marker"):
        logger.error(
            "Fingerprint preload marker is missing for session %s; browser pages are not spoofed",
            session_id,
        )
