const secureBrowserStripHeadless = (value) => String(value || '')
    .replace(/HeadlessChrome/gi, 'Chrome')
    .replace(/HeadlessChromium/gi, 'Chromium');
const secureBrowserOriginalUserAgent = secureBrowserStripHeadless(navigator.userAgent);
const secureBrowserOriginalAppVersion = secureBrowserStripHeadless(navigator.appVersion);

for (const [property, value] of [
    ['userAgent', secureBrowserOriginalUserAgent],
    ['appVersion', secureBrowserOriginalAppVersion]
]) {
    if (navigator[property] === value) continue;
    const descriptor = Object.getOwnPropertyDescriptor(Navigator.prototype, property);
    if (!descriptor || typeof descriptor.get !== 'function') continue;
    Object.defineProperty(Navigator.prototype, property, {
        ...descriptor,
        get: new Proxy(descriptor.get, {
            apply(target, receiver, args) {
                Reflect.apply(target, receiver, args);
                return value;
            }
        })
    });
}

if (!window.chrome) {
    Object.defineProperty(window, 'chrome', {
        value: Object.freeze({
            app: Object.freeze({}),
            csi: () => ({}),
            loadTimes: () => ({}),
            runtime: Object.freeze({})
        }),
        configurable: true
    });
}
