from __future__ import annotations

import logging
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options as ChromeOptions

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
from .chromium_extensions import (
    _configure_default_extensions,
    _webrtc_leak_prevent_extension_path,
)
from .fingerprint import (
    _apply_chromium_fingerprint,
    _build_chromium_fingerprint_script,
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
    "_build_user_agent_metadata",
    "_configure_chromium_fingerprint_extension",
    "_configure_default_extensions",
    "_webrtc_leak_prevent_extension_path",
]


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
        user_agent = _effective_user_agent(fingerprint_config)
        if user_agent:
            options.add_argument(f"--user-agent={user_agent}")
        if proxy_config is not None:
            options.add_argument(f"--proxy-server={proxy_config.browser_proxy_url()}")
        _configure_default_extensions(options)
        if fingerprint_config is not None:
            _configure_chromium_options(options, fingerprint_config)
            _configure_chromium_fingerprint_extension(options, profile_dir, fingerprint_config)

        driver = webdriver.Chrome(options=options)
        if fingerprint_config is not None:
            _apply_chromium_fingerprint(driver, fingerprint_config)
        return driver


SeleniumBrowserManager = SeleniumBrowserBackend


def _effective_user_agent(
    fingerprint_config: FingerprintConfig | None,
) -> str:
    if fingerprint_config is not None and fingerprint_config.user_agent:
        return fingerprint_config.user_agent.strip()
    return ""
