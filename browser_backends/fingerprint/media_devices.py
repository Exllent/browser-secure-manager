from __future__ import annotations

from typing import Any

from models.fingerprint_config import FingerprintConfig

from .templates import _render_js_template


def _build_media_devices_patch(config: FingerprintConfig) -> str:
    if not getattr(config, "spoof_media_devices", False):
        return ""
    return _render_js_template(
        "media_devices.js",
        {"devices": _media_devices_for_config(config)},
    )


def _media_devices_for_config(config: FingerprintConfig) -> list[dict[str, str]]:
    devices = getattr(config, "media_devices", None)
    if devices:
        return [_normalize_media_device(device, index) for index, device in enumerate(devices)]

    platform = str(getattr(config, "platform", "") or "")
    if platform == "MacIntel":
        labels = (
            ("audioinput", "MacBook Pro Microphone"),
            ("videoinput", "FaceTime HD Camera"),
            ("audiooutput", "MacBook Pro Speakers"),
        )
    elif platform.startswith("Win"):
        labels = (
            ("audioinput", "Microphone Array (Realtek(R) Audio)"),
            ("videoinput", "Integrated Camera"),
            ("audiooutput", "Speakers (Realtek(R) Audio)"),
        )
    elif platform.startswith("Linux"):
        labels = (
            ("audioinput", "Built-in Audio Analog Stereo"),
            ("videoinput", "Integrated Camera"),
            ("audiooutput", "Built-in Audio Analog Stereo"),
        )
    else:
        labels = (
            ("audioinput", "Default Microphone"),
            ("videoinput", "Default Camera"),
            ("audiooutput", "Default Speakers"),
        )

    return [
        _normalize_media_device(
            {
                "kind": kind,
                "label": label,
                "deviceId": f"secure-{kind}-{index}",
                "groupId": f"secure-group-{'audio' if kind.startswith('audio') else 'video'}",
            },
            index,
        )
        for index, (kind, label) in enumerate(labels)
    ]


def _normalize_media_device(device: dict[str, Any], index: int) -> dict[str, str]:
    kind = str(device.get("kind") or "audioinput")
    return {
        "kind": kind,
        "label": str(device.get("label") or ""),
        "deviceId": str(device.get("deviceId") or f"secure-{kind}-{index}"),
        "groupId": str(device.get("groupId") or f"secure-group-{index}"),
    }
