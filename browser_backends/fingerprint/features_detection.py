from __future__ import annotations

import json

from models.fingerprint_config import FingerprintConfig

from .templates import _render_js_template


def _build_features_detection_patch(config: FingerprintConfig) -> str:
    patches: list[str] = []

    if config.spoof_feature_detection:
        patches.append(_build_core_features_patch(config))
    if config.spoof_touch_support:
        patches.append(_build_touch_support_patch(config))
    if config.spoof_connection:
        patches.append(_build_connection_patch(config))
    if config.spoof_permissions:
        patches.append(_build_permissions_patch(config))
    if config.spoof_battery:
        patches.append(_build_battery_patch(config))

    return "\n".join(patches)


def _build_core_features_patch(config: FingerprintConfig) -> str:
    return _render_js_template(
        "features_core.js",
        {
            "doNotTrack": getattr(config, "do_not_track", None),
            "globalPrivacyControl": getattr(config, "global_privacy_control", False),
            "modernizr": _modernizr_profile(config),
            "platformKind": _platform_kind(config),
            "webrtcMode": getattr(config, "webrtc_mode", "proxy_dns"),
            "webrtcSupported": getattr(config, "webrtc_mode", "proxy_dns") != "disable",
        },
    )


def _modernizr_profile(config: FingerprintConfig) -> dict[str, object]:
    platform_kind = _platform_kind(config)
    max_touch_points = int(getattr(config, "max_touch_points", None) or 0)
    connection_type = str(getattr(config, "connection_type", None) or "wifi")
    battery_level = float(getattr(config, "battery_level", 1.0) or 1.0)
    is_mobile_like = max_touch_points > 0
    is_battery_low = battery_level <= 0.2

    profile: dict[str, object] = {
        "batteryapi": _has_battery_api(config, platform_kind),
        "capture": is_mobile_like,
        "devicemotion": is_mobile_like,
        "deviceorientation": is_mobile_like,
        "effectiveType": True,
        "fileinputdirectory": platform_kind in {"windows", "macos"},
        "forcetouch": platform_kind == "macos",
        "hovermq": not is_mobile_like,
        "lowbandwidth": connection_type == "cellular",
        "lowbattery": is_battery_low,
        "pointermq": True,
        "quotamanagement": platform_kind != "linux",
        "speechrecognition": platform_kind in {"windows", "macos"},
        "vibrate": is_mobile_like,
        "websqldatabase": False,
    }

    if platform_kind == "macos":
        profile.update(
            {
                "audio": {
                    "m4a": "probably",
                    "mp3": "probably",
                    "ogg": "probably",
                    "opus": "probably",
                    "wav": "probably",
                },
                "video": {
                    "av1": "probably",
                    "h264": "probably",
                    "h265": "maybe",
                    "hls": "probably",
                    "ogg": "probably",
                    "vp9": "probably",
                    "webm": "probably",
                },
            }
        )
    elif platform_kind == "windows":
        profile.update(
            {
                "audio": {
                    "m4a": "probably",
                    "mp3": "probably",
                    "ogg": "probably",
                    "opus": "probably",
                    "wav": "probably",
                },
                "video": {
                    "av1": "probably",
                    "h264": "probably",
                    "h265": "",
                    "hls": "",
                    "ogg": "probably",
                    "vp9": "probably",
                    "webm": "probably",
                },
            }
        )
    else:
        profile.update(
            {
                "audio": {
                    "m4a": "maybe",
                    "mp3": "probably",
                    "ogg": "probably",
                    "opus": "probably",
                    "wav": "probably",
                },
                "video": {
                    "av1": "probably",
                    "h264": "probably",
                    "h265": "",
                    "hls": "",
                    "ogg": "probably",
                    "vp9": "probably",
                    "webm": "probably",
                },
            }
        )

    return profile


def _platform_kind(config: FingerprintConfig) -> str:
    platform = str(getattr(config, "platform", "") or "")
    user_agent = str(getattr(config, "user_agent", "") or "")
    if platform == "MacIntel" or "Macintosh" in user_agent:
        return "macos"
    if platform.startswith("Win") or "Windows NT" in user_agent:
        return "windows"
    if platform.startswith("Linux") or "Linux" in user_agent or "X11" in user_agent:
        return "linux"
    return "unknown"


def _has_battery_api(config: FingerprintConfig, platform_kind: str) -> bool:
    if getattr(config, "battery_discharging_time", None) is not None:
        return True
    if platform_kind == "macos":
        return True
    return bool(getattr(config, "battery_charging", True))


def _build_touch_support_patch(config: FingerprintConfig) -> str:
    max_touch_points = getattr(config, "max_touch_points", None) or 0
    return """
    Object.defineProperty(Navigator.prototype, 'maxTouchPoints', {
        get: () => %s,
        configurable: true
    });
    """ % max_touch_points


def _build_connection_patch(config: FingerprintConfig) -> str:
    connection = json.dumps(
        {
            "downlink": (
                getattr(config, "connection_downlink", None)
                if getattr(config, "connection_downlink", None) is not None
                else 10
            ),
            "effectiveType": getattr(config, "connection_effective_type", None) or "4g",
            "rtt": (
                getattr(config, "connection_rtt", None)
                if getattr(config, "connection_rtt", None) is not None
                else 50
            ),
            "saveData": getattr(config, "connection_save_data", False),
            "type": getattr(config, "connection_type", None) or "wifi",
        }
    )
    return """
    const secureBrowserConnectionInfo = Object.freeze(%s);
    const secureBrowserConnection = Object.freeze({
        downlink: secureBrowserConnectionInfo.downlink,
        effectiveType: secureBrowserConnectionInfo.effectiveType,
        rtt: secureBrowserConnectionInfo.rtt,
        saveData: secureBrowserConnectionInfo.saveData,
        type: secureBrowserConnectionInfo.type,
        onchange: null,
        addEventListener: () => undefined,
        removeEventListener: () => undefined,
        dispatchEvent: () => true
    });
    Object.defineProperty(Navigator.prototype, 'connection', {
        get: () => secureBrowserConnection,
        configurable: true
    });
    Object.defineProperty(Navigator.prototype, 'mozConnection', {
        get: () => secureBrowserConnection,
        configurable: true
    });
    Object.defineProperty(Navigator.prototype, 'webkitConnection', {
        get: () => secureBrowserConnection,
        configurable: true
    });
    """ % connection


def _build_battery_patch(config: FingerprintConfig) -> str:
    charging_time = (
        str(getattr(config, "battery_charging_time", 0))
        if getattr(config, "battery_charging_time", 0) is not None
        else "Infinity"
    )
    discharging_time = (
        str(getattr(config, "battery_discharging_time", None))
        if getattr(config, "battery_discharging_time", None) is not None
        else "Infinity"
    )
    charging = "true" if getattr(config, "battery_charging", True) else "false"
    return """
    const secureBrowserBattery = Object.freeze({
        charging: %s,
        chargingTime: %s,
        dischargingTime: %s,
        level: %s,
        addEventListener: () => undefined,
        removeEventListener: () => undefined,
        dispatchEvent: () => true
    });
    Navigator.prototype.getBattery = () => Promise.resolve(secureBrowserBattery);
    """ % (charging, charging_time, discharging_time, getattr(config, "battery_level", 1.0))


def _build_permissions_patch(config: FingerprintConfig) -> str:
    geolocation_state = "granted" if config.geolocation is not None else ""
    return """
    if (navigator.permissions && navigator.permissions.query) {
        const secureBrowserPermissionStates = new Map(Object.entries({
            geolocation: "%s"
        }).filter((entry) => entry[1]));
        const originalPermissionsQuery = navigator.permissions.query.bind(navigator.permissions);
        navigator.permissions.query = (parameters) => {
            if (parameters && secureBrowserPermissionStates.has(parameters.name)) {
                return Promise.resolve({state: secureBrowserPermissionStates.get(parameters.name)});
            }
            if (parameters && parameters.name === 'notifications') {
                return Promise.resolve({state: Notification.permission});
            }
            return originalPermissionsQuery(parameters);
        };
    }
    """ % geolocation_state
