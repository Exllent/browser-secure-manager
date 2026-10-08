from __future__ import annotations

import json

from app_config import APP_CONFIG
from models.fingerprint_config import FingerprintConfig

from .templates import _read_js_template, _render_js_template
from .utils import _canvas_device_seed, _canvas_noise_level, _stable_noise_seed
from .webgpu import _build_webgpu_patch


def _needs_worker_fingerprint_patch(config: FingerprintConfig) -> bool:
    # Worker WebGPU protection is always enabled so pages cannot bypass it with WorkerNavigator.gpu.
    return True


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

    canvas_noise = max(1, int(round(_canvas_noise_level(config) * 255)))
    webgl_noise_seed = _stable_noise_seed(
        config.user_agent or "",
        config.platform or "",
        config.webgl_vendor or "",
        config.webgl_renderer or "",
    )
    languages = config.spoof_languages or config.locale
    worker_script = _render_js_template(
        "worker_fingerprint.js",
        {
            "canvasMode": config.canvas_mode,
            "canvasNoise": canvas_noise,
            "canvasNoiseSeed": _canvas_device_seed(config),
            "fonts": fonts,
            "patchCanvas": config.canvas_mode in {"noise", "fixed"},
            "patchFonts": bool(config.font_list or config.font_spoof_count),
            "patchWebGL": bool(config.webgl_vendor or config.webgl_renderer),
            "timezone": config.timezone,
            "webglNoiseSeed": webgl_noise_seed,
            "webglRenderer": config.webgl_renderer or "ANGLE",
            "webglVendor": config.webgl_vendor or "Google Inc.",
        },
    )
    navigator_values: dict[str, object] = {}
    if config.user_agent:
        navigator_values["userAgent"] = config.user_agent
        navigator_values["appVersion"] = config.user_agent.removeprefix("Mozilla/")
    if config.platform:
        navigator_values["platform"] = config.platform
    if languages:
        navigator_values["languages"] = languages
        navigator_values["language"] = languages[0]
    if config.hardware_concurrency is not None:
        navigator_values["hardwareConcurrency"] = config.hardware_concurrency
    if config.device_memory is not None:
        navigator_values["deviceMemory"] = config.device_memory
    navigator_script = (
        _render_js_template("navigator_properties.js", navigator_values) if navigator_values else ""
    )
    return "\n".join([_build_webgpu_patch(config), navigator_script, worker_script])
