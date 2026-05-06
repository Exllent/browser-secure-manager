from __future__ import annotations

import logging
from pathlib import Path

from selenium.webdriver.chrome.options import Options as ChromeOptions

from app_config import APP_CONFIG

logger = logging.getLogger(__name__)


def _webrtc_leak_prevent_extension_path() -> Path:
    return (
        APP_CONFIG.paths.browser_extensions_dir
        / APP_CONFIG.chromium_extensions.webrtc_extension_dirname
    )


def _configure_default_extensions(options: ChromeOptions) -> None:
    extension_dir = _webrtc_leak_prevent_extension_path()
    manifest_path = extension_dir / APP_CONFIG.chromium_extensions.manifest_filename
    if not manifest_path.is_file():
        logger.warning("WebRTC Leak Prevent extension is missing: %s", extension_dir)
        return

    _add_chromium_extension(options, extension_dir)
    options.add_argument(APP_CONFIG.chromium_extensions.disable_non_proxied_udp_argument)


def _add_chromium_extension(options: ChromeOptions, extension_dir: Path) -> None:
    _append_chromium_extension_argument(
        options,
        APP_CONFIG.chromium_extensions.load_extension_argument_prefix,
        extension_dir,
    )
    _append_chromium_extension_argument(
        options,
        APP_CONFIG.chromium_extensions.enable_only_extension_argument_prefix,
        extension_dir,
    )


def _append_chromium_extension_argument(
    options: ChromeOptions,
    argument_prefix: str,
    extension_dir: Path,
) -> None:
    extension_path = str(extension_dir)
    for index, argument in enumerate(options.arguments):
        if argument.startswith(argument_prefix):
            current_paths = [
                path for path in argument.removeprefix(argument_prefix).split(",") if path
            ]
            if extension_path not in current_paths:
                current_paths.append(extension_path)
                options.arguments[index] = argument_prefix + ",".join(current_paths)
            return

    options.add_argument(f"{argument_prefix}{extension_path}")
