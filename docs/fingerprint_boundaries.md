# Fingerprint Boundaries

## MAC Address

Status: success, explicitly bounded.

Chromium does not expose a network adapter MAC address to page JavaScript, content scripts, or Selenium CDP fingerprint overrides. A website should not be able to read the host MAC address through normal browser APIs, so Secure Browser must not add a fake `mac_address` fingerprint setting that appears configurable but is never applied.

If a real MAC-address requirement appears later, it belongs outside the browser fingerprint script: native helper, OS/network namespace, VM/container network adapter, or another upstream network layer.

## WebGPU Deep Spoofing

Status: success, explicitly bounded.

Chromium WebGPU exposes adapter, feature, limit, and device behavior from the browser engine. Secure Browser prevents page and worker JavaScript from reaching the host WebGPU adapter by neutralizing `navigator.gpu` at fingerprint preload time.

Full WebGPU adapter/limits/features spoofing is not implemented as a JavaScript-only shim. If that requirement appears later, it belongs in a browser-engine patch or a DevTools-level strategy that can control the real WebGPU stack before JavaScript observes it.
