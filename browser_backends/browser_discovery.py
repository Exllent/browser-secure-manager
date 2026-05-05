from __future__ import annotations

import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

from models.browser_config import BrowserConfig


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
