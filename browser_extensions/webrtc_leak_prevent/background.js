const WEBRTC_POLICY = "disable_non_proxied_udp";

function setPrivacySetting(setting, value) {
  return new Promise((resolve) => {
    if (!setting || !setting.set) {
      resolve();
      return;
    }
    setting.set({ value, scope: "regular" }, () => resolve());
  });
}

async function applyWebRTCLeakPrevention() {
  await setPrivacySetting(chrome.privacy.network.webRTCIPHandlingPolicy, WEBRTC_POLICY);
  await setPrivacySetting(chrome.privacy.network.webRTCMultipleRoutesEnabled, false);
  await setPrivacySetting(chrome.privacy.network.webRTCNonProxiedUdpEnabled, false);
}

chrome.runtime.onInstalled.addListener(applyWebRTCLeakPrevention);
chrome.runtime.onStartup.addListener(applyWebRTCLeakPrevention);
applyWebRTCLeakPrevention();
