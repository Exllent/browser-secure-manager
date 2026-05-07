from __future__ import annotations

import hashlib
from typing import Any


def _stable_noise_seed(*parts: str) -> int:
    digest = hashlib.sha256("\n".join(parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") or 1


def _canvas_device_seed(config: Any) -> int:
    languages = getattr(config, "spoof_languages", None) or getattr(config, "locale", None) or []
    font_list = getattr(config, "font_list", None) or []
    return _stable_noise_seed(
        "canvas-device",
        getattr(config, "user_agent", None) or "",
        getattr(config, "platform", None) or "",
        getattr(config, "webgl_vendor", None) or "",
        getattr(config, "webgl_renderer", None) or "",
        ",".join(languages),
        getattr(config, "timezone", None) or "",
        str(getattr(config, "hardware_concurrency", None) or ""),
        str(getattr(config, "device_memory", None) or ""),
        str(getattr(config, "screen_width", None) or ""),
        str(getattr(config, "screen_height", None) or ""),
        str(getattr(config, "screen_avail_width", None) or ""),
        str(getattr(config, "screen_avail_height", None) or ""),
        str(getattr(config, "color_depth", None) or ""),
        str(getattr(config, "pixel_depth", None) or ""),
        str(getattr(config, "device_scale_factor", None) or ""),
        str(getattr(config, "max_touch_points", None) or ""),
        ",".join(font_list),
        str(getattr(config, "font_spoof_count", None) or ""),
    )


def _canvas_noise_level(config: Any) -> float:
    noise_level = float(getattr(config, "canvas_noise_level", 0.02) or 0.0)
    if getattr(config, "canvas_mode", None) == "fixed":
        return max(noise_level, 0.04)
    return noise_level
