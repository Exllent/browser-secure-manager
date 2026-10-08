const secureBrowserDeviceConfig = __SECURE_BROWSER_CONFIG__;
const defineSecureBrowserScreenGetter = (property, value) => {
    const target = window.Screen && Screen.prototype ? Screen.prototype : window.screen;
    if (!target) return;
    try {
        const descriptor = Object.getOwnPropertyDescriptor(target, property);
        if (!descriptor || typeof descriptor.get !== 'function') return;
        if (Reflect.apply(descriptor.get, window.screen, []) === value) return;
        Object.defineProperty(target, property, {
            ...descriptor,
            get: new Proxy(descriptor.get, {
                apply(nativeGetter, receiver, args) {
                    Reflect.apply(nativeGetter, receiver, args);
                    return value;
                }
            })
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
    const descriptor = Object.getOwnPropertyDescriptor(window, 'devicePixelRatio');
    if (descriptor && typeof descriptor.get === 'function'
        && window.devicePixelRatio !== secureBrowserDeviceConfig.devicePixelRatio) {
        Object.defineProperty(window, 'devicePixelRatio', {
            ...descriptor,
            get: new Proxy(descriptor.get, {
                apply(nativeGetter, receiver, args) {
                    Reflect.apply(nativeGetter, receiver, args);
                    return secureBrowserDeviceConfig.devicePixelRatio;
                }
            })
        });
    }
} catch (error) {
}
