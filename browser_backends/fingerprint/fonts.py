from __future__ import annotations

from models.fingerprint_config import FingerprintConfig

from .templates import _render_js_template

KNOWN_FONT_FAMILIES = {
    "Arial",
    "Calibri",
    "Cambria",
    "Courier New",
    "Geneva",
    "DejaVu Sans",
    "DejaVu Sans Mono",
    "DejaVu Serif",
    "Georgia",
    "Helvetica",
    "Hiragino Sans",
    "Liberation Sans",
    "Liberation Serif",
    "Menlo",
    "Monaco",
    "Noto Sans",
    "Osaka",
    "Roboto",
    "Segoe UI",
    "Tahoma",
    "Times",
    "Times New Roman",
    "Ubuntu",
    "Verdana",
    "Yu Gothic",
}


def _build_font_patch(config: FingerprintConfig) -> str:
    fonts = list(dict.fromkeys(config.font_list))
    for index in range(config.font_spoof_count):
        fonts.append(f"Secure UI {index + 1}")
    return _render_js_template(
        "fonts.js",
        {
            "fonts": fonts,
            "knownFonts": sorted(set(fonts) | KNOWN_FONT_FAMILIES),
        },
    )
