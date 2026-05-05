const secureBrowserStripHeadless = (value) => String(value || '')
    .replace(/HeadlessChrome/gi, 'Chrome')
    .replace(/HeadlessChromium/gi, 'Chromium');
const secureBrowserOriginalUserAgent = secureBrowserStripHeadless(navigator.userAgent);
const secureBrowserOriginalAppVersion = secureBrowserStripHeadless(navigator.appVersion);

Object.defineProperty(Navigator.prototype, 'userAgent', {
    get: () => secureBrowserOriginalUserAgent,
    configurable: true
});
Object.defineProperty(Navigator.prototype, 'appVersion', {
    get: () => secureBrowserOriginalAppVersion,
    configurable: true
});

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
