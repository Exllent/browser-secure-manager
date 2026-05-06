from __future__ import annotations

from models.fingerprint_config import FingerprintConfig

from .templates import _render_js_template
from .utils import _stable_noise_seed


def _build_canvas_patch(config: FingerprintConfig) -> str:
    noise_level = 0.0 if config.canvas_mode == "fixed" else config.canvas_noise_level
    noise = max(1, int(round(noise_level * 255)))
    seed = getattr(config, "canvas_noise_seed", None) or _stable_noise_seed(
        config.user_agent or "",
        config.platform or "",
        config.webgl_vendor or "",
        config.webgl_renderer or "",
        ",".join(config.spoof_languages or config.locale),
        config.timezone or "",
    )
    return _render_js_template(
        "canvas.js",
        {
            "mode": config.canvas_mode,
            "noise": noise,
            "seed": seed,
        },
    )
