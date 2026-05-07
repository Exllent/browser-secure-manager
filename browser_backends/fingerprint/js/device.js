const secureBrowserDeviceConfig = __SECURE_BROWSER_CONFIG__;
const defineSecureBrowserScreenGetter = (property, value) => {
    const target = window.Screen && Screen.prototype ? Screen.prototype : window.screen;
    if (!target) return;
    try {
        Object.defineProperty(target, property, {
            get: () => value,
            configurable: true
        });
    } catch (error) {
    }
};

defineSecureBrowserScreenGetter('width', secureBrowserDeviceConfig.screenWidth);
defineSecureBrowserScreenGetter('height', secureBrowserDeviceConfig.screenHeight);
defineSecureBrowserScreenGetter('availWidth', secureBrowserDeviceConfig.screenAvailWidth);
defineSecureBrowserScreenGetter('availHeight', secureBrowserDeviceConfig.screenAvailHeight);
defineSecureBrowserScreenGetter('colorDepth', secureBrowserDeviceConfig.colorDepth);
defineSecureBrowserScreenGetter('pixelDepth', secureBrowserDeviceConfig.pixelDepth);

try {
    Object.defineProperty(window, 'devicePixelRatio', {
        get: () => secureBrowserDeviceConfig.devicePixelRatio,
        configurable: true
    });
} catch (error) {
}
