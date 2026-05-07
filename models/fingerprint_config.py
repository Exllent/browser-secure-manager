from __future__ import annotations

import zoneinfo
from dataclasses import asdict, dataclass, field
from numbers import Real
from typing import Any, Literal, get_args

from app_config import APP_CONFIG

CanvasMode = Literal["noise", "fixed", "passthrough", "captured"]
WebRTCMode = Literal["disable", "public_ip_only", "proxy_dns", "passthrough"]
TLSProfile = Literal["chrome_134", "chromium_134", "random"]

_VALIDATION_CONFIG = APP_CONFIG.fingerprint_validation
VALID_CANVAS_MODES = set(_VALIDATION_CONFIG.canvas_modes)
VALID_WEBRTC_MODES = set(_VALIDATION_CONFIG.webrtc_modes)
VALID_TLS_PROFILES = set(_VALIDATION_CONFIG.tls_profiles)
VALID_PLATFORMS = set(_VALIDATION_CONFIG.platforms)
VALID_DEVICE_MEMORY_VALUES = set(_VALIDATION_CONFIG.device_memory_values)
VALID_CLIENT_HINT_ARCHITECTURES = set(_VALIDATION_CONFIG.client_hint_architectures)
VALID_CLIENT_HINT_BITNESS_VALUES = set(_VALIDATION_CONFIG.client_hint_bitness_values)
VALID_CONNECTION_EFFECTIVE_TYPES = set(_VALIDATION_CONFIG.connection_effective_types)
VALID_CONNECTION_TYPES = set(_VALIDATION_CONFIG.connection_types)
VALID_DO_NOT_TRACK_VALUES = set(_VALIDATION_CONFIG.do_not_track_values)
VALID_MEDIA_DEVICE_KINDS = set(_VALIDATION_CONFIG.media_device_kinds)
TIMEZONE_LANGUAGE_PREFIXES = dict(_VALIDATION_CONFIG.timezone_language_prefixes)
BOOLEAN_FIELDS = _VALIDATION_CONFIG.boolean_fields
LIST_FIELDS = _VALIDATION_CONFIG.list_fields
OPTIONAL_STRING_FIELDS = _VALIDATION_CONFIG.optional_string_fields

assert VALID_CANVAS_MODES == set(get_args(CanvasMode))
assert VALID_WEBRTC_MODES == set(get_args(WebRTCMode))
assert VALID_TLS_PROFILES == set(get_args(TLSProfile))


@dataclass(slots=True)
class FingerprintConfig:
    # === Скрытие автоматизации ===
    hide_automation: bool = True  # navigator.webdriver, CDP артефакты
    hide_headless: bool = True  # признаки headless-режима
    spoof_plugins: bool = True  # navigator.plugins (не пустой список)
    spoof_languages: list[str] = field(default_factory=list)  # navigator.languages
    user_agent: str | None = None
    client_hints_platform_version: str | None = None
    client_hints_architecture: str | None = None
    client_hints_bitness: str | None = None
    client_hints_model: str | None = None

    # === Canvas / WebGL ===
    canvas_mode: CanvasMode = "noise"
    canvas_noise_level: float = 0.02  # 0.0 - 0.1, микро-шум для уникальности
    canvas_noise_seed: int | None = None  # legacy field; canvas seed is derived from device data
    canvas_capture_data_url: str | None = None
    canvas_capture_width: int | None = None
    canvas_capture_height: int | None = None
    webgl_vendor: str | None = None  # например, "Google Inc. (NVIDIA)"
    webgl_renderer: str | None = None  # например, "ANGLE (NVIDIA, ...)"

    # === Аудио / Fonts ===
    audio_noise: bool = True  # микро-вариации в AudioContext
    font_list: list[str] = field(default_factory=list)  # явный список шрифтов
    font_spoof_count: int = 0  # добавить случайные "фейковые" шрифты (0-5)

    # === Геолокация / Время ===
    timezone: str | None = None  # "Europe/Moscow", "America/New_York"
    geolocation: tuple[float, float] | None = None  # (lat, lon)
    locale: list[str] = field(default_factory=list)  # ["ru-RU", "ru", "en-US"]

    # === WebRTC ===
    webrtc_mode: WebRTCMode = "proxy_dns"

    # === Hardware / Device ===
    hardware_concurrency: int | None = None  # navigator.hardwareConcurrency
    device_memory: float | None = None  # navigator.deviceMemory (GB)
    platform: str | None = None  # navigator.platform: "Win32", "MacIntel", etc.
    screen_width: int | None = None
    screen_height: int | None = None
    screen_avail_width: int | None = None
    screen_avail_height: int | None = None
    color_depth: int | None = None
    pixel_depth: int | None = None
    device_scale_factor: float | None = None
    max_touch_points: int | None = None

    # === TLS / Network (требует внешнего прокси) ===
    # Примечание: Selenium не управляет TLS-стеком.
    # Для смены JA3/JA4 используйте резидентные прокси с кастомным стеком.
    tls_profile: TLSProfile | None = None

    # === Feature Detection ===
    spoof_touch_support: bool = True  # navigator.maxTouchPoints
    spoof_connection: bool = True  # navigator.connection
    spoof_permissions: bool = True  # navigator.permissions.query
    spoof_feature_detection: bool = True  # стабильный профиль feature-detection API
    spoof_media_devices: bool = True  # navigator.mediaDevices.enumerateDevices()
    media_devices: list[dict[str, str]] = field(default_factory=list)
    do_not_track: str | None = None
    global_privacy_control: bool = False
    connection_downlink: float | None = None
    connection_effective_type: str | None = None
    connection_rtt: int | None = None
    connection_save_data: bool = False
    connection_type: str | None = None

    # === Content Filter / AdBlock ===
    hide_adblock_signs: bool = False  # скрыть признаки блокировщиков
    spoof_battery: bool = True  # navigator.getBattery()
    battery_charging: bool = True
    battery_level: float = 1.0
    battery_charging_time: int | None = 0
    battery_discharging_time: int | None = None

    # === Дополнительные скрипты ===
    custom_js_before_load: list[str] = field(default_factory=list)
    custom_js_after_load: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FingerprintConfig:
        """Создает конфигурацию из словаря и нормализует JSON-friendly значения."""
        values = dict(data)
        for field_name in LIST_FIELDS:
            if values.get(field_name) is None:
                values[field_name] = []
        if values.get("media_devices") is None:
            values["media_devices"] = []

        if isinstance(values.get("geolocation"), list | tuple):
            values["geolocation"] = tuple(values["geolocation"])
        if values.get("tls_profile") == "firefox_125":
            values["tls_profile"] = "chrome_134"

        return cls(**values)

    def to_dict(self) -> dict[str, Any]:
        """Возвращает конфигурацию в виде словаря для сохранения в JSON/YAML."""
        return asdict(self)

    def ensure_canvas_noise_seed(self) -> FingerprintConfig:
        return self

    def validate(self) -> list[str]:
        """Возвращает список ошибок конфигурации."""
        errors: list[str] = []

        self._validate_boolean_fields(errors)
        self._validate_optional_string_fields(errors)

        if self.canvas_mode not in VALID_CANVAS_MODES:
            errors.append(f"Invalid canvas_mode: {self.canvas_mode}")

        if self.canvas_mode == "captured" and not self.canvas_capture_data_url:
            errors.append("captured canvas mode requires canvas_capture_data_url")

        if (
            self.canvas_capture_data_url is not None
            and not self.canvas_capture_data_url.startswith("data:image/png;base64,")
        ):
            errors.append("canvas_capture_data_url must be a PNG data URL")

        for field_name in ("canvas_capture_width", "canvas_capture_height"):
            value = getattr(self, field_name)
            if value is None:
                continue
            if not isinstance(value, int) or isinstance(value, bool):
                errors.append(f"{field_name} must be an integer")
            elif not (
                _VALIDATION_CONFIG.canvas_capture_size_min
                <= value
                <= _VALIDATION_CONFIG.canvas_capture_size_max
            ):
                errors.append(f"{field_name} must be between 1 and 16384")

        if not self._is_number(self.canvas_noise_level):
            errors.append("canvas_noise_level must be a number")
        elif not (
            _VALIDATION_CONFIG.canvas_noise_min
            <= self.canvas_noise_level
            <= _VALIDATION_CONFIG.canvas_noise_max
        ):
            errors.append("canvas_noise_level must be between 0.0 and 0.1")

        if self.canvas_noise_seed is not None:
            if not isinstance(self.canvas_noise_seed, int) or isinstance(
                self.canvas_noise_seed,
                bool,
            ):
                errors.append("canvas_noise_seed must be an integer")
            elif not (
                _VALIDATION_CONFIG.canvas_seed_min
                <= self.canvas_noise_seed
                <= _VALIDATION_CONFIG.canvas_seed_max
            ):
                errors.append("canvas_noise_seed must be between 1 and 4294967295")

        if not isinstance(self.font_spoof_count, int) or isinstance(self.font_spoof_count, bool):
            errors.append("font_spoof_count must be an integer")
        elif not (
            _VALIDATION_CONFIG.font_spoof_min
            <= self.font_spoof_count
            <= _VALIDATION_CONFIG.font_spoof_max
        ):
            errors.append("font_spoof_count must be between 0 and 5")

        if isinstance(self.timezone, str) and self.timezone:
            try:
                zoneinfo.ZoneInfo(self.timezone)
            except zoneinfo.ZoneInfoNotFoundError:
                errors.append(f"Invalid timezone: {self.timezone}")

        if self.geolocation is not None:
            errors.extend(self._validate_geolocation())

        if self.webrtc_mode not in VALID_WEBRTC_MODES:
            errors.append(f"Invalid webrtc_mode: {self.webrtc_mode}")

        if self.do_not_track is not None and self.do_not_track not in VALID_DO_NOT_TRACK_VALUES:
            errors.append(f"Invalid do_not_track: {self.do_not_track}")

        if self.hardware_concurrency is not None:
            if not isinstance(self.hardware_concurrency, int) or isinstance(
                self.hardware_concurrency, bool
            ):
                errors.append("hardware_concurrency must be an integer")
            elif not (
                _VALIDATION_CONFIG.hardware_concurrency_min
                <= self.hardware_concurrency
                <= _VALIDATION_CONFIG.hardware_concurrency_max
            ):
                errors.append("hardware_concurrency must be between 1 and 128")

        if self.device_memory is not None:
            if not self._is_number(self.device_memory):
                errors.append("device_memory must be a number")
            elif self.device_memory not in VALID_DEVICE_MEMORY_VALUES:
                values = ", ".join(str(value) for value in sorted(VALID_DEVICE_MEMORY_VALUES))
                errors.append(f"device_memory must be one of: {values}")

        if self.platform and self.platform not in VALID_PLATFORMS:
            errors.append(f"Invalid platform: {self.platform}")

        if self.tls_profile is not None and self.tls_profile not in VALID_TLS_PROFILES:
            errors.append(f"Invalid tls_profile: {self.tls_profile}")

        self._validate_client_hints(errors)
        self._validate_screen(errors)
        self._validate_connection(errors)
        self._validate_battery(errors)
        self._validate_media_devices(errors)

        for field_name in LIST_FIELDS:
            self._validate_str_list(field_name, getattr(self, field_name), errors)

        self._validate_consistency(errors)

        return errors

    def raise_if_invalid(self) -> None:
        """Выбрасывает ValueError, если конфигурация некорректна."""
        errors = self.validate()
        if errors:
            raise ValueError("; ".join(errors))

    def _validate_geolocation(self) -> list[str]:
        errors: list[str] = []

        if not isinstance(self.geolocation, tuple) or len(self.geolocation) != 2:
            return ["geolocation must be a tuple with latitude and longitude"]

        latitude, longitude = self.geolocation
        if not self._is_number(latitude) or not self._is_number(longitude):
            return ["geolocation latitude and longitude must be numbers"]

        if not (-90 <= latitude <= 90):
            errors.append("geolocation latitude must be between -90 and 90")
        if not (-180 <= longitude <= 180):
            errors.append("geolocation longitude must be between -180 and 180")

        return errors

    @staticmethod
    def _validate_str_list(name: str, value: list[str], errors: list[str]) -> None:
        if not isinstance(value, list):
            errors.append(f"{name} must be a list")
            return

        if any(not isinstance(item, str) for item in value):
            errors.append(f"{name} must contain only strings")

    def _validate_boolean_fields(self, errors: list[str]) -> None:
        for field_name in BOOLEAN_FIELDS:
            if not isinstance(getattr(self, field_name), bool):
                errors.append(f"{field_name} must be a boolean")

    def _validate_optional_string_fields(self, errors: list[str]) -> None:
        for field_name in OPTIONAL_STRING_FIELDS:
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, str):
                errors.append(f"{field_name} must be a string or None")

    def _validate_client_hints(self, errors: list[str]) -> None:
        if (
            self.client_hints_architecture is not None
            and self.client_hints_architecture not in VALID_CLIENT_HINT_ARCHITECTURES
        ):
            errors.append(f"Invalid client_hints_architecture: {self.client_hints_architecture}")
        if (
            self.client_hints_bitness is not None
            and self.client_hints_bitness not in VALID_CLIENT_HINT_BITNESS_VALUES
        ):
            errors.append(f"Invalid client_hints_bitness: {self.client_hints_bitness}")

    def _validate_screen(self, errors: list[str]) -> None:
        for field_name in (
            "screen_width",
            "screen_height",
            "screen_avail_width",
            "screen_avail_height",
            "color_depth",
            "pixel_depth",
            "max_touch_points",
        ):
            value = getattr(self, field_name)
            if value is None:
                continue
            if not isinstance(value, int) or isinstance(value, bool):
                errors.append(f"{field_name} must be an integer")
                continue

            if field_name.startswith("screen_") and not (
                _VALIDATION_CONFIG.screen_size_min <= value <= _VALIDATION_CONFIG.screen_size_max
            ):
                errors.append(f"{field_name} must be between 1 and 16384")
            elif field_name in {"color_depth", "pixel_depth"} and not (
                _VALIDATION_CONFIG.color_depth_min <= value <= _VALIDATION_CONFIG.color_depth_max
            ):
                errors.append(f"{field_name} must be between 1 and 64")
            elif field_name == "max_touch_points" and not (
                _VALIDATION_CONFIG.max_touch_points_min
                <= value
                <= _VALIDATION_CONFIG.max_touch_points_max
            ):
                errors.append("max_touch_points must be between 0 and 16")

        if self.device_scale_factor is not None:
            if not self._is_number(self.device_scale_factor):
                errors.append("device_scale_factor must be a number")
            elif not (
                _VALIDATION_CONFIG.device_scale_factor_min
                <= self.device_scale_factor
                <= _VALIDATION_CONFIG.device_scale_factor_max
            ):
                errors.append("device_scale_factor must be between 0.5 and 4.0")

    def _validate_connection(self, errors: list[str]) -> None:
        if self.connection_downlink is not None:
            if not self._is_number(self.connection_downlink):
                errors.append("connection_downlink must be a number")
            elif not (
                _VALIDATION_CONFIG.connection_downlink_min
                <= self.connection_downlink
                <= _VALIDATION_CONFIG.connection_downlink_max
            ):
                errors.append("connection_downlink must be between 0.0 and 10000.0")

        if self.connection_rtt is not None:
            if not isinstance(self.connection_rtt, int) or isinstance(self.connection_rtt, bool):
                errors.append("connection_rtt must be an integer")
            elif not (
                _VALIDATION_CONFIG.connection_rtt_min
                <= self.connection_rtt
                <= _VALIDATION_CONFIG.connection_rtt_max
            ):
                errors.append("connection_rtt must be between 0 and 10000")

        if (
            self.connection_effective_type is not None
            and self.connection_effective_type not in VALID_CONNECTION_EFFECTIVE_TYPES
        ):
            errors.append(f"Invalid connection_effective_type: {self.connection_effective_type}")

        if self.connection_type is not None and self.connection_type not in VALID_CONNECTION_TYPES:
            errors.append(f"Invalid connection_type: {self.connection_type}")

    def _validate_battery(self, errors: list[str]) -> None:
        if not self._is_number(self.battery_level):
            errors.append("battery_level must be a number")
        elif not (
            _VALIDATION_CONFIG.battery_level_min
            <= self.battery_level
            <= _VALIDATION_CONFIG.battery_level_max
        ):
            errors.append("battery_level must be between 0.0 and 1.0")

        for field_name in ("battery_charging_time", "battery_discharging_time"):
            value = getattr(self, field_name)
            if value is None:
                continue
            if not isinstance(value, int) or isinstance(value, bool):
                errors.append(f"{field_name} must be an integer or None")
            elif not (
                _VALIDATION_CONFIG.battery_time_min <= value <= _VALIDATION_CONFIG.battery_time_max
            ):
                errors.append(f"{field_name} must be between 0 and 86400")

    def _validate_media_devices(self, errors: list[str]) -> None:
        if not isinstance(self.media_devices, list):
            errors.append("media_devices must be a list")
            return

        allowed_keys = {"kind", "label", "deviceId", "groupId"}
        for index, device in enumerate(self.media_devices, start=1):
            if not isinstance(device, dict):
                errors.append(f"media_devices item {index} must be an object")
                continue

            unknown_keys = set(device) - allowed_keys
            if unknown_keys:
                keys = ", ".join(sorted(unknown_keys))
                errors.append(f"media_devices item {index} has unknown keys: {keys}")

            kind = device.get("kind")
            if not isinstance(kind, str) or kind not in VALID_MEDIA_DEVICE_KINDS:
                errors.append(f"media_devices item {index} has invalid kind: {kind}")

            for key in ("label", "deviceId", "groupId"):
                value = device.get(key, "")
                if not isinstance(value, str):
                    errors.append(f"media_devices item {index} {key} must be a string")

    def _validate_consistency(self, errors: list[str]) -> None:
        if not self.user_agent:
            return

        user_agent = self.user_agent
        renderer = self.webgl_renderer or ""
        languages = self.spoof_languages or self.locale
        validation = APP_CONFIG.fingerprint_validation

        if "Macintosh" in user_agent:
            if self.platform != validation.mac_platform:
                errors.append("Macintosh User-Agent requires platform MacIntel")
            if renderer and "Direct3D" in renderer:
                errors.append("Macintosh User-Agent must not use Direct3D WebGL renderer")
            if self.max_touch_points not in {None, 0}:
                errors.append("Macintosh desktop User-Agent requires max_touch_points 0")
        elif "Windows NT" in user_agent:
            if self.platform not in validation.windows_platforms:
                errors.append("Windows User-Agent requires Win32 or Win64 platform")
            if "Apple M" in renderer or "ANGLE Metal Renderer: Apple" in renderer:
                errors.append("Windows User-Agent must not use Apple WebGL renderer")
            if self.max_touch_points not in {None, 0}:
                errors.append("Windows desktop User-Agent requires max_touch_points 0")
        elif "Linux" in user_agent or "X11" in user_agent:
            if self.platform not in validation.linux_platforms:
                errors.append("Linux User-Agent requires Linux platform")
            if "Direct3D" in renderer or "Apple" in renderer:
                errors.append("Linux User-Agent must not use Direct3D or Apple WebGL renderer")
            if self.max_touch_points not in {None, 0}:
                errors.append("Linux desktop User-Agent requires max_touch_points 0")

        if self.timezone in TIMEZONE_LANGUAGE_PREFIXES and languages:
            allowed_prefixes = TIMEZONE_LANGUAGE_PREFIXES[self.timezone]
            primary_language = languages[0].split("-", 1)[0].lower()
            if primary_language not in allowed_prefixes:
                errors.append(
                    f"timezone {self.timezone} is inconsistent with primary language {languages[0]}"
                )

    @staticmethod
    def _is_number(value: object) -> bool:
        return isinstance(value, Real) and not isinstance(value, bool)
