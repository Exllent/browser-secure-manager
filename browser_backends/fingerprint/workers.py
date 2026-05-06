from __future__ import annotations

import json

from app_config import APP_CONFIG
from models.fingerprint_config import FingerprintConfig

from .templates import _read_js_template, _render_js_template
from .utils import _stable_noise_seed


def _needs_worker_fingerprint_patch(config: FingerprintConfig) -> bool:
    return (
        config.canvas_mode in {"noise", "fixed"}
        or bool(config.webgl_vendor or config.webgl_renderer)
        or bool(config.font_list or config.font_spoof_count)
    )


def _build_worker_fingerprint_patch(config: FingerprintConfig) -> str:
    worker_script = json.dumps(_build_worker_fingerprint_script(config))
    return _read_js_template("worker_wrapper.js").replace(
        "__SECURE_BROWSER_WORKER_SCRIPT__",
        worker_script,
    )


def _build_worker_fingerprint_script(config: FingerprintConfig) -> str:
    fonts = list(dict.fromkeys(config.font_list))
    for index in range(config.font_spoof_count):
        fonts.append(f"{APP_CONFIG.fingerprint_generation.fake_font_prefix}{index + 1}")

    noise_level = 0.0 if config.canvas_mode == "fixed" else config.canvas_noise_level
    canvas_noise = max(1, int(round(noise_level * 255)))
    webgl_noise_seed = _stable_noise_seed(
        config.user_agent or "",
        config.platform or "",
        config.webgl_vendor or "",
        config.webgl_renderer or "",
    )
    canvas_noise_seed = getattr(config, "canvas_noise_seed", None) or _stable_noise_seed(
        "canvas",
        config.user_agent or "",
        config.platform or "",
        config.webgl_vendor or "",
        config.webgl_renderer or "",
        ",".join(config.spoof_languages or config.locale),
        config.timezone or "",
    )
    return _render_js_template(
        "worker_fingerprint.js",
        {
            "canvasMode": config.canvas_mode,
            "canvasNoise": canvas_noise,
            "canvasNoiseSeed": canvas_noise_seed,
            "fonts": fonts,
            "patchCanvas": config.canvas_mode in {"noise", "fixed"},
            "patchFonts": bool(config.font_list or config.font_spoof_count),
            "patchWebGL": bool(config.webgl_vendor or config.webgl_renderer),
            "webglNoiseSeed": webgl_noise_seed,
            "webglRenderer": config.webgl_renderer or "ANGLE",
            "webglVendor": config.webgl_vendor or "Google Inc.",
        },
    )
