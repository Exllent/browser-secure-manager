from __future__ import annotations

from models.fingerprint_config import FingerprintConfig

from .templates import _render_js_template


def _build_device_patch(config: FingerprintConfig) -> str:
    if not _has_screen_patch(config):
        return ""

    width = getattr(config, "screen_width", None) or 1920
    height = getattr(config, "screen_height", None) or 1080
    return _render_js_template(
        "device.js",
        {
            "screenWidth": width,
            "screenHeight": height,
            "screenAvailWidth": getattr(config, "screen_avail_width", None) or width,
            "screenAvailHeight": getattr(config, "screen_avail_height", None) or height,
            "colorDepth": getattr(config, "color_depth", None) or 24,
            "pixelDepth": getattr(config, "pixel_depth", None)
            or getattr(config, "color_depth", None)
            or 24,
            "devicePixelRatio": getattr(config, "device_scale_factor", None) or 1.0,
        },
    )


def _has_screen_patch(config: FingerprintConfig) -> bool:
    return any(
        value is not None
        for value in (
            getattr(config, "screen_width", None),
            getattr(config, "screen_height", None),
            getattr(config, "screen_avail_width", None),
            getattr(config, "screen_avail_height", None),
            getattr(config, "color_depth", None),
            getattr(config, "pixel_depth", None),
            getattr(config, "device_scale_factor", None),
        )
    )
