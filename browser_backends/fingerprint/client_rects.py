from __future__ import annotations

from models.fingerprint_config import FingerprintConfig

from .templates import _render_js_template
from .utils import _stable_noise_seed


def _build_client_rects_patch(config: FingerprintConfig) -> str:
    seed = _stable_noise_seed(
        getattr(config, "user_agent", None) or "",
        getattr(config, "platform", None) or "",
        str(getattr(config, "screen_width", None) or ""),
        str(getattr(config, "screen_height", None) or ""),
        ",".join(getattr(config, "font_list", None) or []),
        "client-rects",
    )
    return _render_js_template(
        "client_rects.js",
        {
            "heightDelta": _rect_delta(seed >> 8),
            "seed": seed,
            "widthDelta": _rect_delta(seed),
            "xDelta": _rect_delta(seed >> 16),
            "yDelta": _rect_delta(seed >> 24),
        },
    )


def _rect_delta(seed: int) -> float:
    value = ((seed & 0xFF) % 9) - 4
    if value == 0:
        value = 1
    return round(value / 100, 2)
