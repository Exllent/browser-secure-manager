from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

JS_DIR = Path(__file__).resolve().parent / "js"
CONFIG_PLACEHOLDER = "__SECURE_BROWSER_CONFIG__"


@lru_cache(maxsize=None)
def _read_js_template(name: str) -> str:
    return (JS_DIR / name).read_text(encoding="utf-8")


def _render_js_template(name: str, config: dict[str, Any] | None = None) -> str:
    source = _read_js_template(name)
    if config is None:
        return source
    return source.replace(
        CONFIG_PLACEHOLDER,
        json.dumps(config, ensure_ascii=False, sort_keys=True),
    )
