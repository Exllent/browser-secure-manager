from __future__ import annotations

from dataclasses import dataclass
from random import SystemRandom

from models.fingerprint_config import FingerprintConfig
from models.fingerprint_profile import FingerprintProfile

_RANDOM = SystemRandom()


@dataclass(frozen=True, slots=True)
class FingerprintPreset:
    label: str
    user_agent: str
    languages: tuple[str, ...]
    timezone: str
    geolocation: tuple[float, float]
    platform: str
    hardware_concurrency: int
    device_memory: float
    webgl_vendor: str
    webgl_renderer: str
    fonts: tuple[str, ...]


FINGERPRINT_PRESETS = (
    FingerprintPreset(
        label="Windows Chrome RU Moscow",
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/134.0.0.0 Safari/537.36"
        ),
        languages=("ru-RU", "ru", "en-US", "en"),
        timezone="Europe/Moscow",
        geolocation=(55.755826, 37.6173),
        platform="Win32",
        hardware_concurrency=8,
        device_memory=8,
        webgl_vendor="Google Inc. (NVIDIA)",
        webgl_renderer="ANGLE (NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0)",
        fonts=("Arial", "Calibri", "Cambria", "Segoe UI", "Tahoma", "Times New Roman"),
    ),
    FingerprintPreset(
        label="macOS Chrome US New York",
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/134.0.0.0 Safari/537.36"
        ),
        languages=("en-US", "en"),
        timezone="America/New_York",
        geolocation=(40.712776, -74.005974),
        platform="MacIntel",
        hardware_concurrency=8,
        device_memory=8,
        webgl_vendor="Google Inc. (Apple)",
        webgl_renderer="ANGLE (Apple, ANGLE Metal Renderer: Apple M2 Pro, Unspecified Version)",
        fonts=("Arial", "Helvetica", "Menlo", "Monaco", "Times", "Verdana"),
    ),
    FingerprintPreset(
        label="macOS Chrome JP Tokyo",
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/133.0.0.0 Safari/537.36"
        ),
        languages=("ja-JP", "ja", "en-US", "en"),
        timezone="Asia/Tokyo",
        geolocation=(35.6762, 139.6503),
        platform="MacIntel",
        hardware_concurrency=10,
        device_memory=8,
        webgl_vendor="Google Inc. (Apple)",
        webgl_renderer="ANGLE (Apple, ANGLE Metal Renderer: Apple M3, Unspecified Version)",
        fonts=("Hiragino Sans", "Helvetica", "Menlo", "Osaka", "Times", "Yu Gothic"),
    ),
    FingerprintPreset(
        label="Windows Chrome DE Berlin",
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/133.0.0.0 Safari/537.36"
        ),
        languages=("de-DE", "de", "en-US", "en"),
        timezone="Europe/Berlin",
        geolocation=(52.52, 13.405),
        platform="Win32",
        hardware_concurrency=12,
        device_memory=8,
        webgl_vendor="Google Inc. (Intel)",
        webgl_renderer="ANGLE (Intel, Intel(R) Iris(R) Xe Graphics Direct3D11 vs_5_0 ps_5_0)",
        fonts=("Arial", "Calibri", "Segoe UI", "Tahoma", "Times New Roman", "Verdana"),
    ),
    FingerprintPreset(
        label="Windows Chrome FR Paris",
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/134.0.0.0 Safari/537.36"
        ),
        languages=("fr-FR", "fr", "en-US", "en"),
        timezone="Europe/Paris",
        geolocation=(48.856613, 2.352222),
        platform="Win32",
        hardware_concurrency=8,
        device_memory=8,
        webgl_vendor="Google Inc. (AMD)",
        webgl_renderer="ANGLE (AMD, AMD Radeon RX 6600 Direct3D11 vs_5_0 ps_5_0)",
        fonts=("Arial", "Calibri", "Segoe UI", "Tahoma", "Times New Roman", "Verdana"),
    ),
    FingerprintPreset(
        label="Linux Chrome US Los Angeles",
        user_agent=(
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/134.0.0.0 Safari/537.36"
        ),
        languages=("en-US", "en"),
        timezone="America/Los_Angeles",
        geolocation=(34.052235, -118.243683),
        platform="Linux x86_64",
        hardware_concurrency=8,
        device_memory=8,
        webgl_vendor="Google Inc. (Intel)",
        webgl_renderer="ANGLE (Intel, Mesa Intel(R) UHD Graphics 620, OpenGL 4.6)",
        fonts=("Arial", "DejaVu Sans", "Liberation Sans", "Noto Sans", "Ubuntu"),
    ),
)


def generate_fingerprint_config() -> FingerprintConfig:
    preset = _RANDOM.choice(FINGERPRINT_PRESETS)
    return FingerprintConfig(
        hide_automation=True,
        hide_headless=True,
        spoof_plugins=True,
        spoof_languages=list(preset.languages),
        user_agent=preset.user_agent,
        canvas_mode="noise",
        canvas_noise_level=_RANDOM.choice((0.01, 0.015, 0.02, 0.025)),
        webgl_vendor=preset.webgl_vendor,
        webgl_renderer=preset.webgl_renderer,
        audio_noise=True,
        font_list=list(preset.fonts),
        font_spoof_count=_RANDOM.choice((0, 1, 2)),
        timezone=preset.timezone,
        geolocation=preset.geolocation,
        locale=list(preset.languages),
        webrtc_mode="proxy_dns",
        hardware_concurrency=preset.hardware_concurrency,
        device_memory=preset.device_memory,
        platform=preset.platform,
        tls_profile="chrome_134",
        spoof_touch_support=True,
        spoof_connection=True,
        spoof_permissions=True,
        hide_adblock_signs=True,
        spoof_battery=True,
    )


def generate_fingerprint_profile(name: str | None = None) -> FingerprintProfile:
    config = generate_fingerprint_config()
    preset = next(
        preset for preset in FINGERPRINT_PRESETS if preset.user_agent == config.user_agent
    )
    return FingerprintProfile(
        id=None,
        name=name or preset.label,
        config=config,
        enabled=True,
    )
