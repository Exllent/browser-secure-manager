from __future__ import annotations

from .templates import _render_js_template


def _build_content_filter_patch() -> str:
    return _render_js_template("content_filter.js")
