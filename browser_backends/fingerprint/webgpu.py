from __future__ import annotations

from models.fingerprint_config import FingerprintConfig

from .templates import _render_js_template


def _build_webgpu_patch(config: FingerprintConfig) -> str:
    return _render_js_template(
        "webgpu.js",
        {
            "renderer": config.webgl_renderer or "ANGLE",
            "vendor": config.webgl_vendor or "Google Inc.",
        },
    )
