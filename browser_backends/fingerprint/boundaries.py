from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FingerprintSurfaceBoundary:
    name: str
    browser_exposed: bool
    status: str
    reason: str
    action: str


MAC_ADDRESS_BOUNDARY = FingerprintSurfaceBoundary(
    name="MAC address",
    browser_exposed=False,
    status="success",
    reason=(
        "Chromium does not expose a network adapter MAC address to page JavaScript, "
        "content scripts, or Selenium CDP fingerprint overrides."
    ),
    action=(
        "Do not add a fake browser fingerprint field for MAC address. If a future "
        "requirement appears, handle it in a native helper, OS/network namespace, "
        "or upstream network layer outside the browser fingerprint script."
    ),
)

WEBGPU_DEEP_SPOOFING_BOUNDARY = FingerprintSurfaceBoundary(
    name="WebGPU deep spoofing",
    browser_exposed=True,
    status="success",
    reason=(
        "Chromium WebGPU exposes adapter, feature, limit, and device behavior from the "
        "browser engine. Page and worker JavaScript can be prevented from reaching the "
        "host adapter, but reliable deep spoofing is not available through normal "
        "Selenium startup scripts."
    ),
    action=(
        "Neutralize navigator.gpu in page and worker JavaScript. If full adapter, "
        "limits, features, or device behavior must be spoofed later, implement it in a "
        "browser-engine patch or DevTools-level strategy instead of pretending a "
        "JavaScript-only shim is complete."
    ),
)

FINGERPRINT_SURFACE_BOUNDARIES = {
    "mac_address": MAC_ADDRESS_BOUNDARY,
    "webgpu_deep_spoofing": WEBGPU_DEEP_SPOOFING_BOUNDARY,
}
