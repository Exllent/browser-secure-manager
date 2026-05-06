const secureBrowserGeolocationConfig = __SECURE_BROWSER_CONFIG__;
const secureBrowserGeolocationWatchers = new Map();
let secureBrowserGeolocationWatchId = 1;

const secureBrowserBuildGeolocationPosition = () => ({
    coords: Object.freeze({
        latitude: secureBrowserGeolocationConfig.latitude,
        longitude: secureBrowserGeolocationConfig.longitude,
        accuracy: secureBrowserGeolocationConfig.accuracy,
        altitude: null,
        altitudeAccuracy: null,
        heading: null,
        speed: null
    }),
    timestamp: Date.now()
});

const secureBrowserAsyncGeolocationCallback = (callback) => {
    if (typeof callback !== 'function') return;
    queueMicrotask(() => callback(secureBrowserBuildGeolocationPosition()));
};

const secureBrowserGeolocation = Object.freeze({
    getCurrentPosition(successCallback) {
        secureBrowserAsyncGeolocationCallback(successCallback);
    },
    watchPosition(successCallback) {
        const watchId = secureBrowserGeolocationWatchId++;
        secureBrowserAsyncGeolocationCallback(successCallback);
        const intervalId = setInterval(
            () => secureBrowserAsyncGeolocationCallback(successCallback),
            secureBrowserGeolocationConfig.watchIntervalMs
        );
        secureBrowserGeolocationWatchers.set(watchId, intervalId);
        return watchId;
    },
    clearWatch(watchId) {
        const intervalId = secureBrowserGeolocationWatchers.get(watchId);
        if (intervalId === undefined) return;
        clearInterval(intervalId);
        secureBrowserGeolocationWatchers.delete(watchId);
    }
});

try {
    Object.defineProperty(Navigator.prototype, 'geolocation', {
        get: () => secureBrowserGeolocation,
        configurable: true
    });
} catch (error) {
    try {
        Object.defineProperty(navigator, 'geolocation', {
            value: secureBrowserGeolocation,
            configurable: true
        });
    } catch (nestedError) {
    }
}
