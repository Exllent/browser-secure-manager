const secureBrowserMediaDevicesConfig = __SECURE_BROWSER_CONFIG__;
const secureBrowserMediaPermissionState = {granted: false};

const secureBrowserBuildMediaDevice = (device) => {
    const prototype = window.MediaDeviceInfo && MediaDeviceInfo.prototype;
    const mediaDevice = prototype ? Object.create(prototype) : {};
    const values = Object.freeze({
        deviceId: String(device.deviceId || ''),
        groupId: String(device.groupId || ''),
        kind: String(device.kind || 'audioinput'),
        label: secureBrowserMediaPermissionState.granted ? String(device.label || '') : ''
    });

    for (const [property, value] of Object.entries(values)) {
        try {
            Object.defineProperty(mediaDevice, property, {
                get: () => value,
                enumerable: true,
                configurable: true
            });
        } catch (error) {
        }
    }
    try {
        Object.defineProperty(mediaDevice, 'toJSON', {
            value: () => ({
                deviceId: values.deviceId,
                groupId: values.groupId,
                kind: values.kind,
                label: values.label
            }),
            configurable: true
        });
    } catch (error) {
    }
    return Object.freeze(mediaDevice);
};

const secureBrowserEnumerateDevices = async () => secureBrowserMediaDevicesConfig.devices
    .map(secureBrowserBuildMediaDevice);

const secureBrowserGetUserMedia = async () => Promise.reject(
    new DOMException('Permission denied', 'NotAllowedError')
);

const secureBrowserGetSupportedConstraints = () => Object.freeze({
    aspectRatio: true,
    autoGainControl: true,
    channelCount: true,
    deviceId: true,
    echoCancellation: true,
    facingMode: true,
    frameRate: true,
    groupId: true,
    height: true,
    noiseSuppression: true,
    sampleRate: true,
    sampleSize: true,
    width: true
});

const secureBrowserMediaDevices = navigator.mediaDevices || {};
const secureBrowserPatchMediaDevices = (target) => {
    if (!target || target.__secureBrowserMediaDevicesPatched) return;
    try {
        Object.defineProperty(target, '__secureBrowserMediaDevicesPatched', {value: true});
    } catch (error) {
    }
    try {
        Object.defineProperty(target, 'enumerateDevices', {
            value: secureBrowserEnumerateDevices,
            configurable: true
        });
    } catch (error) {
    }
    try {
        Object.defineProperty(target, 'getUserMedia', {
            value: secureBrowserGetUserMedia,
            configurable: true
        });
    } catch (error) {
    }
    try {
        Object.defineProperty(target, 'getSupportedConstraints', {
            value: secureBrowserGetSupportedConstraints,
            configurable: true
        });
    } catch (error) {
    }
};

secureBrowserPatchMediaDevices(secureBrowserMediaDevices);
const secureBrowserMediaDevicesPrototype = Object.getPrototypeOf(secureBrowserMediaDevices);
if (secureBrowserMediaDevicesPrototype && secureBrowserMediaDevicesPrototype !== Object.prototype) {
    secureBrowserPatchMediaDevices(secureBrowserMediaDevicesPrototype);
}
try {
    Object.defineProperty(Navigator.prototype, 'mediaDevices', {
        get: () => secureBrowserMediaDevices,
        configurable: true
    });
} catch (error) {
}
