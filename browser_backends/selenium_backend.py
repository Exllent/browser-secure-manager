from __future__ import annotations

import logging
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.safari.options import Options as SafariOptions
from selenium.webdriver.safari.service import Service as SafariService

from models.browser_config import BrowserConfig
from models.proxy_config import ProxyConfig
from models.session_entry import SessionEntry

logger = logging.getLogger(__name__)


class SeleniumBrowserBackend:
    def __init__(self) -> None:
        self._drivers: dict[int, webdriver.Chrome | webdriver.Firefox | webdriver.Safari] = {}

    def open_session(
        self,
        session: SessionEntry,
        browser_config: BrowserConfig,
        proxy_config: ProxyConfig | None = None,
    ) -> None:
        if session.id is None:
            raise ValueError("Session must be saved before opening a browser")

        self.close_session(session.id)
        profile_dir = Path(session.profile_path).expanduser()
        profile_dir.mkdir(parents=True, exist_ok=True)

        browser_type = browser_config.normalized_type()
        logger.info(
            "Opening %s session %s with %s profile %s",
            browser_type,
            session.id,
            browser_config.display_name,
            profile_dir,
        )

        try:
            if browser_type == "safari":
                driver = self._open_safari(session, browser_config, profile_dir)
            elif browser_type == "firefox":
                driver = self._open_firefox(session, browser_config, profile_dir, proxy_config)
            else:
                driver = self._open_chromium(session, browser_config, profile_dir, proxy_config)
        except Exception:
            logger.exception("Failed to open browser for session %s", session.id)
            raise

        self._drivers[session.id] = driver
        driver.get(session.url)

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
    ) -> webdriver.Chrome:
        options = ChromeOptions()
        browser_binary = _browser_binary_from_config(
            browser_config,
            default_browser_name="Chrome / Chromium",
            default_env_var="CHROME_BINARY",
            command_names=("google-chrome", "chrome", "chromium", "chromium-browser"),
            candidates=_chromium_candidates(),
            version_keywords=("Google Chrome", "Chromium", "Chrome", "Opera"),
            required=False,
        )
        if browser_binary is not None:
            options.binary_location = str(browser_binary)
        options.add_argument(f"--user-data-dir={profile_dir}")
        options.add_argument(f"--window-size={session.window_width},{session.window_height}")
        if session.custom_user_agent.strip():
            options.add_argument(f"--user-agent={session.custom_user_agent.strip()}")
        if proxy_config is not None:
            options.add_argument(f"--proxy-server={proxy_config.browser_proxy_url()}")
        return webdriver.Chrome(options=options)

    @staticmethod
    def _open_firefox(
        session: SessionEntry,
        browser_config: BrowserConfig,
        profile_dir: Path,
        proxy_config: ProxyConfig | None,
    ) -> webdriver.Firefox:
        browser_binary = _browser_binary_from_config(
            browser_config,
            default_browser_name="Firefox",
            default_env_var="FIREFOX_BINARY",
            command_names=("firefox", "firefox-esr"),
            candidates=_firefox_candidates(),
            version_keywords=("Firefox",),
            required=True,
        )
        if browser_binary is None:
            raise RuntimeError("Firefox executable was not found")

        options = FirefoxOptions()
        options.binary_location = str(browser_binary)
        if session.custom_user_agent.strip():
            options.set_preference("general.useragent.override", session.custom_user_agent.strip())
        if proxy_config is not None:
            options.set_preference("network.proxy.type", 1)
            if proxy_config.normalized_type() in {"socks4", "socks5"}:
                options.set_preference("network.proxy.socks", proxy_config.host.strip())
                options.set_preference("network.proxy.socks_port", proxy_config.port)
                socks_version = 4 if proxy_config.normalized_type() == "socks4" else 5
                options.set_preference("network.proxy.socks_version", socks_version)
                options.set_preference("network.proxy.socks_remote_dns", True)
            else:
                options.set_preference("network.proxy.http", proxy_config.host.strip())
                options.set_preference("network.proxy.http_port", proxy_config.port)
                options.set_preference("network.proxy.ssl", proxy_config.host.strip())
                options.set_preference("network.proxy.ssl_port", proxy_config.port)
        options.add_argument("-profile")
        options.add_argument(str(profile_dir))
        driver = webdriver.Firefox(options=options)
        driver.set_window_size(session.window_width, session.window_height)
        return driver

    @staticmethod
    def _open_safari(
        session: SessionEntry,
        browser_config: BrowserConfig,
        profile_dir: Path,
    ) -> webdriver.Safari:
        if sys.platform != "darwin":
            raise RuntimeError("Safari WebDriver is available only on macOS.")

        logger.warning(
            "Safari does not support per-session user-data-dir/profile_path via safaridriver. "
            "Ignoring profile path for session %s: %s",
            session.id,
            profile_dir,
        )

        options = SafariOptions()
        if session.custom_user_agent.strip():
            logger.warning(
                "Safari WebDriver does not support per-session User-Agent launch settings. "
                "Ignoring custom User-Agent for session %s.",
                session.id,
            )
        executable_path = browser_config.executable_path.strip()
        if executable_path:
            path = Path(executable_path).expanduser()
            _validate_driver_binary(path=path, driver_name=browser_config.display_name)
            driver = webdriver.Safari(service=SafariService(executable_path=str(path)), options=options)
        else:
            driver = webdriver.Safari(options=options)

        driver.set_window_size(session.window_width, session.window_height)
        return driver


def discover_installed_browsers() -> list[BrowserConfig]:
    discovered: list[BrowserConfig] = []
    seen_paths: set[str] = set()
    known_browsers = (
        ("chrome", "Chrome / Chromium", "chromium", _chromium_candidates()),
        ("firefox", "Firefox", "firefox", _firefox_candidates()),
        ("opera", "Opera", "chromium", _opera_candidates()),
        ("safari", "Safari", "safari", _safari_driver_candidates()),
    )

    for key, display_name, browser_type, candidates in known_browsers:
        version_keywords = _version_keywords_for_type(browser_type)
        for candidate in candidates:
            path = Path(candidate).expanduser()
            path_key = str(path)
            if path_key in seen_paths or not path.is_file() or not _looks_like_native_binary(path):
                continue
            try:
                if browser_type == "safari":
                    _validate_driver_binary(path=path, driver_name=display_name)
                else:
                    _validate_browser_binary(
                        path=path,
                        browser_name=display_name,
                        version_keywords=version_keywords,
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


def _firefox_candidates() -> tuple[str, ...]:
    if sys.platform == "darwin":
        return (
            "/Applications/Firefox.app/Contents/MacOS/firefox",
            str(Path.home() / "Applications/Firefox.app/Contents/MacOS/firefox"),
        )
    if sys.platform == "win32":
        return _windows_browser_candidates(
            "Mozilla Firefox",
            "firefox.exe",
            extra_env_vars=("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"),
        )
    return (
        "/snap/firefox/current/usr/lib/firefox/firefox",
        "/snap/firefox/current/usr/lib/firefox/firefox-bin",
        "/usr/lib/firefox/firefox",
        "/usr/lib/firefox/firefox-bin",
        "/usr/bin/firefox",
        "/usr/bin/firefox-esr",
        "/opt/firefox/firefox",
    )


def _chromium_candidates() -> tuple[str, ...]:
    if sys.platform == "darwin":
        return (
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Opera.app/Contents/MacOS/Opera",
            str(Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            str(Path.home() / "Applications/Opera.app/Contents/MacOS/Opera"),
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
            *_opera_candidates(),
        )
    return (
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/snap/chromium/current/usr/lib/chromium-browser/chrome",
        "/snap/bin/chromium",
        "/opt/google/chrome/chrome",
        *_opera_candidates(),
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


def _safari_driver_candidates() -> tuple[str, ...]:
    if sys.platform == "darwin":
        return ("/usr/bin/safaridriver",)
    return ()


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


def _validate_driver_binary(*, path: Path, driver_name: str) -> None:
    if not path.is_file():
        raise RuntimeError(f"{driver_name}: driver executable file was not found: {path}")
    if not _looks_like_native_binary(path):
        raise RuntimeError(f"{driver_name}: selected file is not a native executable: {path}")

    try:
        result = _run_version_command(path)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"{driver_name}: cannot run driver executable: {path}\n{exc}") from exc

    output = f"{result.stdout}\n{result.stderr}".strip()
    if result.returncode != 0:
        raise RuntimeError(
            f"{driver_name}: selected driver executable is not usable.\n"
            f"Path: {path}\n"
            f"Output: {output or f'exit code {result.returncode}'}"
        )


def _version_keywords_for_type(browser_type: str) -> tuple[str, ...]:
    if browser_type == "safari":
        return ("Safari", "safaridriver")
    return ("Firefox",) if browser_type == "firefox" else (
        "Google Chrome",
        "Chromium",
        "Chrome",
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


def _find_firefox_binary() -> Path:
    firefox_binary = _find_browser_binary(
        browser_name="Firefox",
        env_var="FIREFOX_BINARY",
        command_names=("firefox", "firefox-esr"),
        candidates=_firefox_candidates(),
        version_keywords=("Firefox",),
        required=True,
    )
    if firefox_binary is None:
        raise RuntimeError("Firefox executable was not found")
    return firefox_binary
