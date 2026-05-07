const secureBrowserSpeechVoicesConfig = __SECURE_BROWSER_CONFIG__;

const secureBrowserBuildSpeechVoice = (voice) => {
    const prototype = window.SpeechSynthesisVoice && SpeechSynthesisVoice.prototype;
    const speechVoice = prototype ? Object.create(prototype) : {};
    const values = Object.freeze({
        voiceURI: String(voice.voiceURI || voice.name || ''),
        name: String(voice.name || voice.voiceURI || ''),
        lang: String(voice.lang || 'en-US'),
        localService: Boolean(voice.localService),
        default: Boolean(voice.default)
    });
    for (const [property, value] of Object.entries(values)) {
        try {
            Object.defineProperty(speechVoice, property, {
                get: () => value,
                enumerable: true,
                configurable: true
            });
        } catch (error) {
        }
    }
    return Object.freeze(speechVoice);
};

const secureBrowserSpeechVoices = Object.freeze(
    secureBrowserSpeechVoicesConfig.voices.map(secureBrowserBuildSpeechVoice)
);
const secureBrowserGetVoices = () => Array.from(secureBrowserSpeechVoices);

const secureBrowserCreateSpeechSynthesisFallback = () => {
    const target = new EventTarget();
    Object.assign(target, {
        cancel: () => undefined,
        getVoices: secureBrowserGetVoices,
        pause: () => undefined,
        paused: false,
        pending: false,
        resume: () => undefined,
        speak: () => undefined,
        speaking: false
    });
    return target;
};

const secureBrowserSpeechSynthesis = window.speechSynthesis || secureBrowserCreateSpeechSynthesisFallback();
let secureBrowserOnVoicesChanged = null;

const secureBrowserDispatchVoicesChanged = () => {
    const event = new Event('voiceschanged');
    try {
        secureBrowserSpeechSynthesis.dispatchEvent(event);
    } catch (error) {
    }
    if (typeof secureBrowserOnVoicesChanged === 'function') {
        try {
            secureBrowserOnVoicesChanged.call(secureBrowserSpeechSynthesis, event);
        } catch (error) {
        }
    }
};

const secureBrowserScheduleVoicesChanged = () => {
    queueMicrotask(secureBrowserDispatchVoicesChanged);
    setTimeout(secureBrowserDispatchVoicesChanged, 0);
};

const secureBrowserPatchSpeechSynthesis = (target) => {
    if (!target || target.__secureBrowserSpeechVoicesPatched) return;
    try {
        Object.defineProperty(target, '__secureBrowserSpeechVoicesPatched', {value: true});
    } catch (error) {
    }
    try {
        Object.defineProperty(target, 'getVoices', {
            value: secureBrowserGetVoices,
            configurable: true
        });
    } catch (error) {
    }
};

secureBrowserPatchSpeechSynthesis(secureBrowserSpeechSynthesis);
const secureBrowserSpeechSynthesisPrototype = Object.getPrototypeOf(secureBrowserSpeechSynthesis);
if (secureBrowserSpeechSynthesisPrototype && secureBrowserSpeechSynthesisPrototype !== Object.prototype) {
    secureBrowserPatchSpeechSynthesis(secureBrowserSpeechSynthesisPrototype);
}

try {
    const originalAddEventListener = secureBrowserSpeechSynthesis.addEventListener;
    if (originalAddEventListener) {
        secureBrowserSpeechSynthesis.addEventListener = new Proxy(originalAddEventListener, {
            apply(target, thisArg, args) {
                const result = Reflect.apply(target, thisArg, args);
                if (args[0] === 'voiceschanged') secureBrowserScheduleVoicesChanged();
                return result;
            }
        });
    }
} catch (error) {
}

try {
    Object.defineProperty(secureBrowserSpeechSynthesis, 'onvoiceschanged', {
        get: () => secureBrowserOnVoicesChanged,
        set: (handler) => {
            secureBrowserOnVoicesChanged = handler;
            if (typeof handler === 'function') secureBrowserScheduleVoicesChanged();
        },
        configurable: true
    });
} catch (error) {
}

try {
    Object.defineProperty(window, 'speechSynthesis', {
        get: () => secureBrowserSpeechSynthesis,
        configurable: true
    });
} catch (error) {
}

secureBrowserScheduleVoicesChanged();
