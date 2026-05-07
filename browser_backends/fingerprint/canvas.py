from __future__ import annotations

from models.fingerprint_config import FingerprintConfig

from .templates import _render_js_template
from .utils import _canvas_device_seed, _canvas_noise_level


def _build_canvas_patch(config: FingerprintConfig) -> str:
    if config.canvas_mode == "captured":
        return _render_js_template(
            "canvas_capture.js",
            {
                "dataUrl": config.canvas_capture_data_url,
                "height": config.canvas_capture_height,
                "width": config.canvas_capture_width,
            },
        )

    noise = max(1, int(round(_canvas_noise_level(config) * 255)))
    return _render_js_template(
        "canvas.js",
        {
            "mode": config.canvas_mode,
            "noise": noise,
            "seed": _canvas_device_seed(config),
        },
    )
