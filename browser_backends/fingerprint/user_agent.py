from __future__ import annotations

import json
import re
from typing import Any

from models.fingerprint_config import FingerprintConfig


def _build_user_agent_metadata(config: FingerprintConfig) -> dict[str, Any] | None:
    if not config.user_agent:
        return None

    full_version = _chromium_full_version(config.user_agent)
    major_version = full_version.split(".", 1)[0]
    platform_name = _client_hint_platform(config)
    if platform_name is None:
        return None

    return {
        "brands": [
            {"brand": "Chromium", "version": major_version},
            {"brand": "Google Chrome", "version": major_version},
            {"brand": "Not.A/Brand", "version": "99"},
        ],
        "fullVersionList": [
            {"brand": "Chromium", "version": full_version},
            {"brand": "Google Chrome", "version": full_version},
            {"brand": "Not.A/Brand", "version": "99.0.0.0"},
        ],
        "fullVersion": full_version,
        "platform": platform_name,
        "platformVersion": _client_hint_platform_version(config.user_agent, platform_name),
        "architecture": _client_hint_architecture(config),
        "model": "",
        "mobile": False,
        "bitness": "64",
        "wow64": False,
    }


def _chromium_full_version(user_agent: str) -> str:
    match = re.search(r"(?:Chrome|Chromium)/([0-9]+(?:\.[0-9]+){0,3})", user_agent)
    if not match:
        return "134.0.0.0"

    parts = match.group(1).split(".")
    return ".".join((parts + ["0", "0", "0", "0"])[:4])


def _client_hint_platform(config: FingerprintConfig) -> str | None:
    user_agent = config.user_agent or ""
    if "Macintosh" in user_agent or config.platform == "MacIntel":
        return "macOS"
    if "Windows NT" in user_agent or config.platform in {"Win32", "Win64"}:
        return "Windows"
    if "Linux" in user_agent or "X11" in user_agent or (config.platform or "").startswith("Linux"):
        return "Linux"
    return None


def _client_hint_platform_version(user_agent: str, platform_name: str) -> str:
    if platform_name == "macOS":
        match = re.search(r"Mac OS X ([0-9_]+)", user_agent)
        if not match:
            return "14.0.0"
        parts = match.group(1).replace("_", ".").split(".")
        return ".".join((parts + ["0", "0"])[:3])

    if platform_name == "Windows":
        match = re.search(r"Windows NT ([0-9.]+)", user_agent)
        if not match:
            return "10.0.0"
        parts = match.group(1).split(".")
        return ".".join((parts + ["0"])[:3])

    return ""


def _client_hint_architecture(config: FingerprintConfig) -> str:
    renderer = config.webgl_renderer or ""
    if "Apple M" in renderer or "arm" in (config.platform or "").lower():
        return "arm"
    return "x86"


def _build_user_agent_patch(config: FingerprintConfig) -> str:
    if not config.user_agent:
        return ""

    metadata = _build_user_agent_metadata(config)
    if metadata is None:
        return ""

    metadata_json = json.dumps(metadata)
    user_agent = json.dumps(config.user_agent)
    app_version = json.dumps(config.user_agent.removeprefix("Mozilla/"))
    return f"""
    const secureBrowserUserAgent = {user_agent};
    const secureBrowserUserAgentData = {metadata_json};

    Object.defineProperty(Navigator.prototype, 'userAgent', {{
        get: () => secureBrowserUserAgent,
        configurable: true
    }});

    Object.defineProperty(Navigator.prototype, 'appVersion', {{
        get: () => {app_version},
        configurable: true
    }});

    Object.defineProperty(Navigator.prototype, 'vendor', {{
        get: () => 'Google Inc.',
        configurable: true
    }});

    const buildUserAgentData = () => {{
        const data = {{
            brands: secureBrowserUserAgentData.brands.map((brand) => ({{...brand}})),
            mobile: secureBrowserUserAgentData.mobile,
            platform: secureBrowserUserAgentData.platform,
            getHighEntropyValues: async (hints) => {{
                const allowed = new Set(Array.isArray(hints) ? hints : []);
                const values = {{
                    brands: secureBrowserUserAgentData.brands.map((brand) => ({{...brand}})),
                    mobile: secureBrowserUserAgentData.mobile,
                    platform: secureBrowserUserAgentData.platform
                }};
                for (const key of allowed) {{
                    if (Object.prototype.hasOwnProperty.call(secureBrowserUserAgentData, key)) {{
                        values[key] = Array.isArray(secureBrowserUserAgentData[key])
                            ? secureBrowserUserAgentData[key].map((item) => ({{...item}}))
                            : secureBrowserUserAgentData[key];
                    }}
                }}
                return values;
            }},
            toJSON: () => ({{
                brands: secureBrowserUserAgentData.brands.map((brand) => ({{...brand}})),
                mobile: secureBrowserUserAgentData.mobile,
                platform: secureBrowserUserAgentData.platform
            }})
        }};
        return Object.freeze(data);
    }};

    Object.defineProperty(Navigator.prototype, 'userAgentData', {{
        get: buildUserAgentData,
        configurable: true
    }});
    """
