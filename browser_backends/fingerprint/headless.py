from __future__ import annotations

from .templates import _render_js_template


def _build_headless_patch() -> str:
    return _render_js_template("headless.js")
