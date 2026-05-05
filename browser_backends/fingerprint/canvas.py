from __future__ import annotations

from models.fingerprint_config import FingerprintConfig

from .templates import _render_js_template


def _build_canvas_patch(config: FingerprintConfig) -> str:
    noise_level = 0.0 if config.canvas_mode == "fixed" else config.canvas_noise_level
    noise = max(1, int(round(noise_level * 255)))
    return _render_js_template("canvas.js", {"mode": config.canvas_mode, "noise": noise})
