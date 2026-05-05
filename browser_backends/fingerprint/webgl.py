from __future__ import annotations

from models.fingerprint_config import FingerprintConfig

from .templates import _render_js_template
from .utils import _stable_noise_seed


def _build_webgl_patch(config: FingerprintConfig) -> str:
    noise_seed = _stable_noise_seed(
        config.user_agent or "",
        config.platform or "",
        config.webgl_vendor or "",
        config.webgl_renderer or "",
    )
    return _render_js_template(
        "webgl.js",
        {
            "noiseSeed": noise_seed,
            "renderer": config.webgl_renderer or "ANGLE",
            "vendor": config.webgl_vendor or "Google Inc.",
        },
    )
