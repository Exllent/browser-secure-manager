from __future__ import annotations

from random import SystemRandom

from app_config import APP_CONFIG, FingerprintPresetConfig
from models.fingerprint_config import FingerprintConfig
from models.fingerprint_profile import FingerprintProfile

_RANDOM = SystemRandom()

FINGERPRINT_PRESETS: tuple[FingerprintPresetConfig, ...] = APP_CONFIG.fingerprint_generation.presets


def generate_fingerprint_config() -> FingerprintConfig:
    generation_config = APP_CONFIG.fingerprint_generation
    preset = _RANDOM.choice(FINGERPRINT_PRESETS)
    return FingerprintConfig(
        hide_automation=True,
        hide_headless=True,
        spoof_plugins=True,
        spoof_languages=list(preset.languages),
        user_agent=preset.user_agent,
        canvas_mode="noise",
        canvas_noise_level=_RANDOM.choice(generation_config.canvas_noise_choices),
        canvas_noise_seed=None,
        webgl_vendor=preset.webgl_vendor,
        webgl_renderer=preset.webgl_renderer,
        audio_noise=True,
        font_list=list(preset.fonts),
        font_spoof_count=_RANDOM.choice(generation_config.font_spoof_count_choices),
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
        spoof_feature_detection=True,
        hide_adblock_signs=True,
        spoof_battery=True,
    ).ensure_canvas_noise_seed()


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
