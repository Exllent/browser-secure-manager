from __future__ import annotations

from models.fingerprint_config import FingerprintConfig

from .templates import _render_js_template


def _build_geolocation_patch(config: FingerprintConfig) -> str:
    if config.geolocation is None:
        return ""

    latitude, longitude = config.geolocation
    return _render_js_template(
        "geolocation.js",
        {
            "latitude": latitude,
            "longitude": longitude,
            "accuracy": 100,
            "watchIntervalMs": 1000,
        },
    )
