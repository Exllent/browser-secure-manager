from __future__ import annotations

from models.fingerprint_config import FingerprintConfig

from .templates import _read_js_template


def _build_webgpu_patch(config: FingerprintConfig) -> str:
    return _read_js_template("webgpu.js")
