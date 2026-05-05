const secureBrowserFeatureDetectionConfig = __SECURE_BROWSER_CONFIG__;
const secureBrowserFeatureDetectionProfile = Object.freeze({
    batteryapi: true,
    cookieEnabled: true,
    doNotTrack: null,
    globalPrivacyControl: false,
    javaEnabled: false,
    lowbattery: false,
    pdfViewerEnabled: true,
    webrtc: secureBrowserFeatureDetectionConfig.webrtcSupported
});
const defineSecureBrowserFeature = (target, property, value) => {
    try {
        Object.defineProperty(target, property, {
            get: () => value,
            configurable: true
        });
    } catch (error) {}
};
const defineSecureBrowserValue = (target, property, value) => {
    try {
        Object.defineProperty(target, property, {
            value,
            configurable: true,
            writable: true
        });
    } catch (error) {}
};

defineSecureBrowserFeature(
    Navigator.prototype,
    'cookieEnabled',
    secureBrowserFeatureDetectionProfile.cookieEnabled
);
defineSecureBrowserFeature(
    Navigator.prototype,
    'doNotTrack',
    secureBrowserFeatureDetectionProfile.doNotTrack
);
defineSecureBrowserFeature(
    Navigator.prototype,
    'globalPrivacyControl',
    secureBrowserFeatureDetectionProfile.globalPrivacyControl
);
defineSecureBrowserFeature(
    Navigator.prototype,
    'pdfViewerEnabled',
    secureBrowserFeatureDetectionProfile.pdfViewerEnabled
);
try {
    Navigator.prototype.javaEnabled = () => secureBrowserFeatureDetectionProfile.javaEnabled;
} catch (error) {}

const patchSecureBrowserMediaSupport = (prototype, fallbackSupport) => {
    if (!prototype || prototype.__secureBrowserFeatureMediaPatched || !prototype.canPlayType) return;
    Object.defineProperty(prototype, '__secureBrowserFeatureMediaPatched', { value: true });
    const originalCanPlayType = prototype.canPlayType;
    prototype.canPlayType = new Proxy(originalCanPlayType, {
        apply(target, thisArg, args) {
            const mimeType = String(args[0] || '').toLowerCase();
            if (mimeType.includes('audio/ogg') || mimeType.includes('vorbis')) return 'probably';
            if (mimeType.includes('audio/mpeg') || mimeType.includes('audio/mp3')) return 'probably';
            if (mimeType.includes('audio/wav') || mimeType.includes('audio/x-wav')) return 'probably';
            if (mimeType.includes('audio/mp4') || mimeType.includes('audio/aac')) return 'probably';
            if (mimeType.includes('audio/opus')) return 'probably';
            if (mimeType.includes('video/mp4') || mimeType.includes('avc1')) return 'probably';
            if (mimeType.includes('video/webm') || mimeType.includes('vp8') || mimeType.includes('vp9')) return 'probably';
            if (mimeType.includes('application/vnd.apple.mpegurl')) return '';
            const result = Reflect.apply(target, thisArg, args);
            return result || fallbackSupport;
        }
    });
};
patchSecureBrowserMediaSupport(window.HTMLAudioElement && HTMLAudioElement.prototype, 'maybe');
patchSecureBrowserMediaSupport(window.HTMLVideoElement && HTMLVideoElement.prototype, 'maybe');

if (window.CSS && CSS.supports && !CSS.__secureBrowserFeatureSupportsPatched) {
    Object.defineProperty(CSS, '__secureBrowserFeatureSupportsPatched', { value: true });
    const originalCssSupports = CSS.supports.bind(CSS);
    CSS.supports = (...args) => {
        const query = args.length === 1
            ? String(args[0] || '').toLowerCase()
            : `${String(args[0] || '').toLowerCase()}: ${String(args[1] || '').toLowerCase()}`;
        if (query.includes('display: grid')) return true;
        if (query.includes('display: flex')) return true;
        if (query.includes('gap:') || query.includes('row-gap:') || query.includes('column-gap:')) return true;
        if (query.includes('backdrop-filter')) return true;
        if (query.includes('aspect-ratio')) return true;
        if (query.includes('--secure-browser-test')) return true;
        if (query.includes('position: sticky')) return true;
        if (query.includes('font-variation-settings')) return true;
        if (query.includes('selector(') && query.includes(':focus-within')) return true;
        return originalCssSupports(...args);
    };
}

try {
    if (!window.localStorage) defineSecureBrowserValue(window, 'localStorage', {});
} catch (error) {}
try {
    if (!window.sessionStorage) defineSecureBrowserValue(window, 'sessionStorage', {});
} catch (error) {}
if (!navigator.storage) {
    defineSecureBrowserValue(navigator, 'storage', Object.freeze({
        estimate: async () => ({ quota: 10737418240, usage: 0 }),
        persisted: async () => false
    }));
}
if (!window.indexedDB) defineSecureBrowserValue(window, 'indexedDB', Object.freeze({}));
if (!window.openDatabase) defineSecureBrowserValue(window, 'openDatabase', undefined);
if (!window.applicationCache) defineSecureBrowserValue(window, 'applicationCache', undefined);

if (!navigator.geolocation) {
    defineSecureBrowserValue(navigator, 'geolocation', Object.freeze({
        clearWatch: () => undefined,
        getCurrentPosition: () => undefined,
        watchPosition: () => 0
    }));
}
if (!window.Notification) {
    defineSecureBrowserValue(window, 'Notification', function Notification() {});
    defineSecureBrowserValue(window.Notification, 'permission', 'default');
}
if (!window.PublicKeyCredential) {
    defineSecureBrowserValue(window, 'PublicKeyCredential', function PublicKeyCredential() {});
}
if (!window.TextEncoder) {
    defineSecureBrowserValue(window, 'TextEncoder', function TextEncoder() {});
}
if (!window.TextDecoder) {
    defineSecureBrowserValue(window, 'TextDecoder', function TextDecoder() {});
}
if (secureBrowserFeatureDetectionProfile.webrtc) {
    if (!window.RTCPeerConnection && window.webkitRTCPeerConnection) {
        defineSecureBrowserValue(window, 'RTCPeerConnection', window.webkitRTCPeerConnection);
    }
    if (!navigator.mediaDevices) {
        defineSecureBrowserValue(navigator, 'mediaDevices', {});
    }
    if (navigator.mediaDevices && !navigator.mediaDevices.getUserMedia) {
        defineSecureBrowserValue(
            navigator.mediaDevices,
            'getUserMedia',
            async () => Promise.reject(new DOMException('Permission denied', 'NotAllowedError'))
        );
    }
} else {
    defineSecureBrowserValue(window, 'RTCPeerConnection', undefined);
    defineSecureBrowserValue(window, 'webkitRTCPeerConnection', undefined);
    if (navigator.mediaDevices) {
        defineSecureBrowserValue(navigator.mediaDevices, 'getUserMedia', undefined);
    }
}

const patchModernizrResults = (modernizr) => {
    if (!modernizr || modernizr.__secureBrowserFeatureDetectionPatched) return modernizr;
    try {
        Object.defineProperty(modernizr, '__secureBrowserFeatureDetectionPatched', { value: true });
    } catch (error) {}
    const stableResults = {
        applicationcache: false,
        audio: true,
        audioloop: true,
        batteryapi: secureBrowserFeatureDetectionProfile.batteryapi,
        beacon: true,
        blobconstructor: true,
        cookies: true,
        cors: true,
        cssall: true,
        cssanimations: true,
        csscalc: true,
        cssgridlegacy: false,
        cssgrid: true,
        csspositionsticky: true,
        csssupports: true,
        customprotocolhandler: true,
        dataview: true,
        eventlistener: true,
        fetch: true,
        filereader: true,
        filesystem: false,
        flexbox: true,
        flexboxlegacy: false,
        flexboxtweener: false,
        flexgap: true,
        fullscreen: true,
        gamepads: true,
        geolocation: true,
        getrandomvalues: true,
        getusermedia: true,
        indexeddb: true,
        intl: true,
        json: true,
        localstorage: true,
        lowbattery: secureBrowserFeatureDetectionProfile.lowbattery,
        mediaqueries: true,
        mediasource: true,
        notification: true,
        peerconnection: secureBrowserFeatureDetectionProfile.webrtc,
        postmessage: true,
        promises: true,
        queryselector: true,
        requestanimationframe: true,
        serviceworker: true,
        sessionstorage: true,
        sharedworkers: true,
        svg: true,
        templatestrings: true,
        typedarrays: true,
        websockets: true,
        websqldatabase: false,
        webworkers: true
    };
    for (const [feature, value] of Object.entries(stableResults)) {
        try {
            modernizr[feature] = value;
        } catch (error) {}
    }
    try {
        modernizr.audio = Object.assign(new Boolean(true), {
            m4a: 'probably',
            mp3: 'probably',
            ogg: 'probably',
            opus: 'probably',
            wav: 'probably'
        });
    } catch (error) {}
    try {
        modernizr.video = Object.assign(new Boolean(true), {
            h264: 'probably',
            hls: '',
            ogg: 'probably',
            vp9: 'probably',
            webm: 'probably'
        });
    } catch (error) {}
    return modernizr;
};
let secureBrowserModernizrValue = window.Modernizr;
if (secureBrowserModernizrValue) patchModernizrResults(secureBrowserModernizrValue);
try {
    Object.defineProperty(window, 'Modernizr', {
        get: () => secureBrowserModernizrValue,
        set: (value) => {
            secureBrowserModernizrValue = value;
            patchModernizrResults(value);
            queueMicrotask(() => patchModernizrResults(value));
            setTimeout(() => patchModernizrResults(value), 0);
        },
        configurable: true
    });
} catch (error) {}

if (!window.chrome) {
    Object.defineProperty(window, 'chrome', {
        value: Object.freeze({
            app: Object.freeze({
                InstallState: Object.freeze({
                    DISABLED: 'disabled',
                    INSTALLED: 'installed',
                    NOT_INSTALLED: 'not_installed'
                }),
                RunningState: Object.freeze({
                    CANNOT_RUN: 'cannot_run',
                    READY_TO_RUN: 'ready_to_run',
                    RUNNING: 'running'
                }),
                getDetails: () => null,
                getIsInstalled: () => false,
                installState: () => 'not_installed',
                isInstalled: false,
                runningState: () => 'cannot_run'
            }),
            csi: () => ({}),
            loadTimes: () => ({}),
            runtime: Object.freeze({})
        }),
        configurable: true
    });
}
