from __future__ import annotations

from models.fingerprint_config import FingerprintConfig

from .templates import _render_js_template


def _build_features_detection_patch(config: FingerprintConfig) -> str:
    patches: list[str] = []

    if config.spoof_feature_detection:
        patches.append(_build_core_features_patch(config))
    if config.spoof_touch_support:
        patches.append(_build_touch_support_patch())
    if config.spoof_connection:
        patches.append(_build_connection_patch())
    if config.spoof_permissions:
        patches.append(_build_permissions_patch(config))
    if config.spoof_battery:
        patches.append(_build_battery_patch())

    return "\n".join(patches)


def _build_core_features_patch(config: FingerprintConfig) -> str:
    return _render_js_template(
        "features_core.js",
        {"webrtcSupported": config.webrtc_mode != "disable"},
    )


def _build_touch_support_patch() -> str:
    return """
    Object.defineProperty(Navigator.prototype, 'maxTouchPoints', {
        get: () => 0,
        configurable: true
    });
    """


def _build_connection_patch() -> str:
    return """
    Object.defineProperty(Navigator.prototype, 'connection', {
        get: () => ({
            downlink: 10,
            effectiveType: '4g',
            rtt: 50,
            saveData: false
        }),
        configurable: true
    });
    """


def _build_battery_patch() -> str:
    return """
    Navigator.prototype.getBattery = () => Promise.resolve({
        charging: true,
        chargingTime: 0,
        dischargingTime: Infinity,
        level: 1,
        addEventListener: () => undefined,
        removeEventListener: () => undefined
    });
    """


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
