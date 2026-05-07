# Secure Browser Roadmap

## Fingerprint Surfaces Not Covered Yet

- Media devices: implement deterministic `navigator.mediaDevices.enumerateDevices()`, stable fake `deviceId` / `groupId`, and permission-aware camera/microphone labels.
- SpeechVoices: implement deterministic `speechSynthesis.getVoices()` and `voiceschanged` behavior per OS/browser preset.
- MAC address: browser JavaScript normally cannot read MAC addresses; document the boundary and only address it if a native helper or network-layer requirement appears.
- WebGPU deep spoofing: current protection should prevent host WebGPU exposure from JavaScript. Full adapter/limits/features spoofing requires a browser-engine or DevTools-level strategy.
