from __future__ import annotations

import json

from models.fingerprint_config import FingerprintConfig


def _build_navigator_patches(config: FingerprintConfig) -> list[str]:
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

    if config.platform:
        patches.append(
            f"""
            Object.defineProperty(Navigator.prototype, 'platform', {{
                get: () => {json.dumps(config.platform)},
                configurable: true
            }});
            """
        )

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

    return patches
