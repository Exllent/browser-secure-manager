from __future__ import annotations

import logging
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

from app_config import APP_CONFIG, BrowserCandidateConfig
from models.browser_config import BrowserConfig

logger = logging.getLogger(__name__)


def discover_installed_browsers() -> list[BrowserConfig]:
    discovered: list[BrowserConfig] = []
    seen_paths: set[str] = set()
    for browser in APP_CONFIG.browser_discovery.candidates:
        for candidate in _candidate_paths(browser):
            path = Path(candidate).expanduser()
            path_key = str(path)
            if path_key in seen_paths or not path.is_file() or not _looks_like_native_binary(path):
                continue
            try:
                _validate_browser_binary(
                    path=path,
                    browser_name=browser.display_name,
                    version_keywords=_chromium_version_keywords(),
                )
            except RuntimeError as exc:
                logger.info("Skipping browser candidate %s: %s", path, exc)
                continue

            seen_paths.add(path_key)
            discovered.append(
                BrowserConfig(
                    id=None,
                    key=browser.key,
                    display_name=browser.display_name,
                    browser_type=browser.browser_type,
                    executable_path=str(path),
                    enabled=True,
                )
            )
            logger.info("Discovered %s browser at %s", browser.display_name, path)
            break

    return discovered


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
        logger.info("Using configured browser binary for %s: %s", browser_config.display_name, path)
        return path

    path = _find_browser_binary(
        browser_name=default_browser_name,
        env_var=default_env_var,
        command_names=command_names,
        candidates=candidates,
        version_keywords=version_keywords,
        required=required,
    )
    if path is None:
        logger.warning("No explicit browser binary configured for %s; Selenium will use driver defaults", default_browser_name)
    else:
        logger.info("Using detected browser binary for %s: %s", default_browser_name, path)
    return path


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
    return _candidate_paths(APP_CONFIG.browser_discovery.candidates[0])


def _brave_candidates() -> tuple[str, ...]:
    return _candidate_paths(APP_CONFIG.browser_discovery.candidates[1])


def _edge_candidates() -> tuple[str, ...]:
    return _candidate_paths(APP_CONFIG.browser_discovery.candidates[2])


def _vivaldi_candidates() -> tuple[str, ...]:
    return _candidate_paths(APP_CONFIG.browser_discovery.candidates[3])


def _opera_candidates() -> tuple[str, ...]:
    return _candidate_paths(APP_CONFIG.browser_discovery.candidates[4])


def _candidate_paths(browser: BrowserCandidateConfig) -> tuple[str, ...]:
    if sys.platform == "darwin":
        return tuple(
            str(Path.home() / path[2:])
            if path.startswith("~/")
            else path
            for path in browser.mac_paths
        )
    if sys.platform == "win32":
        paths: list[str] = []
        for app_subdir, executable_name, env_vars in browser.windows_subdirs:
            paths.extend(
                _windows_browser_candidates(
                    app_subdir,
                    executable_name,
                    extra_env_vars=env_vars,
                )
            )
        return tuple(paths)
    return browser.linux_paths


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
    return APP_CONFIG.browser_discovery.version_keywords


def _run_version_command(path: Path) -> subprocess.CompletedProcess[str]:
    kwargs: dict[str, object] = {
        "capture_output": True,
        "check": False,
        "text": True,
        "timeout": APP_CONFIG.browser_discovery.validate_timeout_seconds,
    }
    if platform.system() == "Windows":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        kwargs["startupinfo"] = startupinfo

    return subprocess.run([str(path), "--version"], **kwargs)
