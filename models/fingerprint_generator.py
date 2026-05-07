from __future__ import annotations

import hashlib
from random import SystemRandom

from app_config import APP_CONFIG, FingerprintPresetConfig
from models.fingerprint_config import FingerprintConfig
from models.fingerprint_profile import FingerprintProfile

_RANDOM = SystemRandom()

FINGERPRINT_PRESETS: tuple[FingerprintPresetConfig, ...] = APP_CONFIG.fingerprint_generation.presets


def generate_fingerprint_config(
    preset: FingerprintPresetConfig | None = None,
) -> FingerprintConfig:
    generation_config = APP_CONFIG.fingerprint_generation
    selected_preset = preset or _RANDOM.choice(FINGERPRINT_PRESETS)
    return FingerprintConfig(
        hide_automation=True,
        hide_headless=True,
        spoof_plugins=True,
        spoof_languages=list(selected_preset.languages),
        user_agent=selected_preset.user_agent,
        client_hints_platform_version=selected_preset.client_hints_platform_version,
        client_hints_architecture=selected_preset.client_hints_architecture,
        client_hints_bitness=selected_preset.client_hints_bitness,
        client_hints_model=selected_preset.client_hints_model,
        canvas_mode="fixed",
        canvas_noise_level=_device_canvas_noise_level(selected_preset),
        canvas_noise_seed=None,
        webgl_vendor=selected_preset.webgl_vendor,
        webgl_renderer=selected_preset.webgl_renderer,
        audio_noise=True,
        font_list=list(selected_preset.fonts),
        font_spoof_count=_RANDOM.choice(generation_config.font_spoof_count_choices),
        timezone=selected_preset.timezone,
        geolocation=selected_preset.geolocation,
        locale=list(selected_preset.languages),
        webrtc_mode="proxy_dns",
        hardware_concurrency=selected_preset.hardware_concurrency,
        device_memory=selected_preset.device_memory,
        platform=selected_preset.platform,
        screen_width=selected_preset.screen_width,
        screen_height=selected_preset.screen_height,
        screen_avail_width=selected_preset.screen_avail_width,
        screen_avail_height=selected_preset.screen_avail_height,
        color_depth=selected_preset.color_depth,
        pixel_depth=selected_preset.pixel_depth,
        device_scale_factor=selected_preset.device_scale_factor,
        max_touch_points=selected_preset.max_touch_points,
        tls_profile="chrome_134",
        spoof_touch_support=True,
        spoof_connection=True,
        spoof_permissions=True,
        spoof_feature_detection=True,
        do_not_track=None,
        global_privacy_control=False,
        connection_downlink=selected_preset.connection_downlink,
        connection_effective_type=selected_preset.connection_effective_type,
        connection_rtt=selected_preset.connection_rtt,
        connection_save_data=selected_preset.connection_save_data,
        connection_type=selected_preset.connection_type,
        hide_adblock_signs=False,
        spoof_battery=True,
        battery_charging=selected_preset.battery_charging,
        battery_level=selected_preset.battery_level,
        battery_charging_time=selected_preset.battery_charging_time,
        battery_discharging_time=selected_preset.battery_discharging_time,
    )


def generate_fingerprint_profile(name: str | None = None) -> FingerprintProfile:
    preset = _RANDOM.choice(FINGERPRINT_PRESETS)
    config = generate_fingerprint_config(preset)
    return FingerprintProfile(
        id=None,
        name=name or preset.label,
        config=config,
        enabled=True,
    )


def _device_canvas_noise_level(preset: FingerprintPresetConfig) -> float:
    choices = APP_CONFIG.fingerprint_generation.canvas_noise_choices
    return choices[_device_canvas_seed(preset) % len(choices)]


def _device_canvas_seed(preset: FingerprintPresetConfig) -> int:
    digest = hashlib.sha256(
        "|".join(
            (
                preset.user_agent,
                preset.platform,
                preset.client_hints_architecture,
                preset.client_hints_bitness,
                preset.webgl_vendor,
                preset.webgl_renderer,
                ",".join(preset.fonts),
                str(preset.screen_width),
                str(preset.screen_height),
                str(preset.device_scale_factor),
                ",".join(preset.languages),
                preset.timezone,
            )
        ).encode("utf-8")
    ).digest()
    return int.from_bytes(digest[:4], "big") or 1
