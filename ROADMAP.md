# Secure Browser Roadmap

## Fingerprint Surfaces Status

- [x] Media devices: success. `navigator.mediaDevices.enumerateDevices()` now returns deterministic profile devices with stable `deviceId` / `groupId`; labels remain permission-aware and hidden before media permission.
- [ ] SpeechVoices: implement deterministic `speechSynthesis.getVoices()` and `voiceschanged` behavior per OS/browser preset.
- [ ] MAC address: browser JavaScript normally cannot read MAC addresses; document the boundary and only address it if a native helper or network-layer requirement appears.
- [ ] WebGPU deep spoofing: current protection should prevent host WebGPU exposure from JavaScript. Full adapter/limits/features spoofing requires a browser-engine or DevTools-level strategy.
