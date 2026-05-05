from __future__ import annotations

import logging
from pathlib import Path

from selenium.webdriver.chrome.options import Options as ChromeOptions

logger = logging.getLogger(__name__)


def _webrtc_leak_prevent_extension_path() -> Path:
    return Path(__file__).resolve().parents[1] / "browser_extensions" / "webrtc_leak_prevent"


def _configure_default_extensions(options: ChromeOptions) -> None:
    extension_dir = _webrtc_leak_prevent_extension_path()
    manifest_path = extension_dir / "manifest.json"
    if not manifest_path.is_file():
        logger.warning("WebRTC Leak Prevent extension is missing: %s", extension_dir)
        return

    _add_chromium_extension(options, extension_dir)
    options.add_argument("--force-webrtc-ip-handling-policy=disable_non_proxied_udp")


def _add_chromium_extension(options: ChromeOptions, extension_dir: Path) -> None:
    argument_prefix = "--load-extension="
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
