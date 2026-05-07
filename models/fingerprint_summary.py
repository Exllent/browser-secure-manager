from __future__ import annotations

from dataclasses import dataclass

from models.fingerprint_config import FingerprintConfig
from models.fingerprint_profile import FingerprintProfile


@dataclass(frozen=True, slots=True)
class FingerprintSummarySection:
    title: str
    rows: tuple[tuple[str, str], ...]


def build_fingerprint_summary_sections(
    profile: FingerprintProfile,
) -> tuple[FingerprintSummarySection, ...]:
    config = profile.config
    return (
        FingerprintSummarySection(
            "Identity",
            (
                ("Name", profile.display_name()),
                ("Platform", _platform_label(config.platform)),
                ("Device", _device_label(profile.name)),
                ("Country", _country_code(config)),
            ),
        ),
        FingerprintSummarySection(
            "Locale and time",
            (
                ("Languages", _list_value(config.spoof_languages or config.locale)),
                ("Locale", _list_value(config.locale)),
                ("Timezone", config.timezone or "Not set"),
                ("Geolocation", _geolocation_value(config.geolocation)),
            ),
        ),
        FingerprintSummarySection(
            "Hardware",
            (
                ("CPU", _cpu_value(config)),
                ("Logical cores", _optional_value(config.hardware_concurrency)),
                ("Device memory", _memory_value(config.device_memory)),
                ("Touch points", _optional_value(config.max_touch_points)),
            ),
        ),
        FingerprintSummarySection(
            "Display",
            (
                ("Screen", _size_value(config.screen_width, config.screen_height)),
                (
                    "Available screen",
                    _size_value(config.screen_avail_width, config.screen_avail_height),
                ),
                ("Scale factor", _optional_value(config.device_scale_factor)),
                ("Color depth", _depth_value(config.color_depth, config.pixel_depth)),
            ),
        ),
        FingerprintSummarySection(
            "Graphics",
            (
                ("GPU", _gpu_value(config.webgl_renderer)),
                ("WebGL vendor", config.webgl_vendor or "Not set"),
                ("WebGL renderer", config.webgl_renderer or "Not set"),
            ),
        ),
        FingerprintSummarySection(
            "Browser APIs",
            (
                ("WebRTC", config.webrtc_mode),
                ("Canvas", config.canvas_mode),
                ("Audio noise", _bool_value(config.audio_noise)),
                ("Fonts", _fonts_value(config.font_list)),
                ("Media devices", _count_value(config.media_devices)),
                ("Speech voices", _count_value(config.speech_voices)),
                ("Do Not Track", config.do_not_track or "Not set"),
            ),
        ),
        FingerprintSummarySection(
            "User agent",
            (("User agent", config.user_agent or "Not set"),),
        ),
    )


def _platform_label(platform: str | None) -> str:
    if platform in {"Win32", "Win64"}:
        return "Windows"
    if platform == "MacIntel":
        return "macOS"
    if platform and platform.startswith("Linux"):
        return platform
    return platform or "Not set"


def _device_label(name: str) -> str:
    normalized = name.lower()
    if "desktop" in normalized:
        return "Desktop"
    if "surface" in normalized or "tablet" in normalized:
        return "2-in-1 / tablet"
    if "laptop" in normalized or "macbook" in normalized:
        return "Laptop"
    if "mini" in normalized:
        return "Desktop"
    return "Not set"


def _country_code(config: FingerprintConfig) -> str:
    for language in (*config.locale, *config.spoof_languages):
        if "-" not in language:
            continue
        region = language.rsplit("-", 1)[-1].upper()
        return "UK" if region == "GB" else region
    return "Not set"


def _cpu_value(config: FingerprintConfig) -> str:
    parts: list[str] = []
    if config.client_hints_architecture:
        parts.append(config.client_hints_architecture)
    if config.client_hints_bitness:
        parts.append(f"{config.client_hints_bitness}-bit")
    if config.hardware_concurrency is not None:
        parts.append(f"{config.hardware_concurrency} logical cores")
    return ", ".join(parts) or "Not set"


def _gpu_value(renderer: str | None) -> str:
    if not renderer:
        return "Not set"
    cleaned = renderer
    for token in (
        "ANGLE (",
        "Google Inc.",
        "Direct3D11 vs_5_0 ps_5_0",
        "OpenGL 4.6",
        "OpenGL 4.1",
        "Unspecified Version",
    ):
        cleaned = cleaned.replace(token, "")
    return " ".join(cleaned.replace(")", "").replace(",", " ").split())


def _geolocation_value(value: tuple[float, float] | None) -> str:
    if value is None:
        return "Not set"
    latitude, longitude = value
    return f"{latitude:.5f}, {longitude:.5f}"


def _size_value(width: int | None, height: int | None) -> str:
    if width is None or height is None:
        return "Not set"
    return f"{width} x {height}"


def _depth_value(color_depth: int | None, pixel_depth: int | None) -> str:
    if color_depth is None and pixel_depth is None:
        return "Not set"
    return f"{_optional_value(color_depth)} / {_optional_value(pixel_depth)}"


def _memory_value(value: float | None) -> str:
    if value is None:
        return "Not set"
    return f"{value:g} GB"


def _fonts_value(fonts: list[str]) -> str:
    if not fonts:
        return "0"
    return f"{len(fonts)}: {', '.join(fonts[:8])}"


def _list_value(values: list[str]) -> str:
    return ", ".join(values) if values else "Not set"


def _count_value(values: list[object]) -> str:
    return str(len(values))


def _bool_value(value: bool) -> str:
    return "Yes" if value else "No"


def _optional_value(value: object | None) -> str:
    return str(value) if value is not None else "Not set"
