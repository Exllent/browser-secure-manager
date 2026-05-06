from __future__ import annotations

from app_config import APP_CONFIG
from models.fingerprint_config import FingerprintConfig

from .templates import _render_js_template

KNOWN_FONT_FAMILIES = set(APP_CONFIG.fingerprint_generation.known_font_families)


def _build_font_patch(config: FingerprintConfig) -> str:
    fonts = list(dict.fromkeys(config.font_list))
    for index in range(config.font_spoof_count):
        fonts.append(f"{APP_CONFIG.fingerprint_generation.fake_font_prefix}{index + 1}")
    return _render_js_template(
        "fonts.js",
        {
            "fonts": fonts,
            "knownFonts": sorted(set(fonts) | KNOWN_FONT_FAMILIES),
        },
    )
