const secureBrowserAudioConfig = __SECURE_BROWSER_CONFIG__;
const secureBrowserAudioNoiseSeed = secureBrowserAudioConfig.noiseSeed;
const secureBrowserWeakAudioNoise = (data) => {
    if (!data || typeof data.length !== 'number') return data;
    let state = secureBrowserAudioNoiseSeed >>> 0;
    const step = Math.max(16, Math.floor(data.length / 64));
    for (let index = 0; index < data.length; index += step) {
        state = (state * 1664525 + 1013904223) >>> 0;
        const delta = (((state >>> 8) % 7) - 3) / 1000000;
        data[index] = data[index] + delta;
    }
    return data;
};

if (window.AudioBuffer && AudioBuffer.prototype.getChannelData
    && !AudioBuffer.prototype.__secureBrowserAudioBufferPatched) {
    Object.defineProperty(AudioBuffer.prototype, '__secureBrowserAudioBufferPatched', {value: true});
    const originalGetChannelData = AudioBuffer.prototype.getChannelData;
    AudioBuffer.prototype.getChannelData = new Proxy(originalGetChannelData, {
        apply(target, thisArg, args) {
            return secureBrowserWeakAudioNoise(Reflect.apply(target, thisArg, args));
        }
    });
}

const patchAnalyserPrototype = (prototype) => {
    if (!prototype || prototype.__secureBrowserAnalyserPatched) return;
    Object.defineProperty(prototype, '__secureBrowserAnalyserPatched', {value: true});
    for (const methodName of ['getFloatFrequencyData', 'getFloatTimeDomainData']) {
        const originalMethod = prototype[methodName];
        if (!originalMethod) continue;
        prototype[methodName] = new Proxy(originalMethod, {
            apply(target, thisArg, args) {
                const result = Reflect.apply(target, thisArg, args);
                secureBrowserWeakAudioNoise(args[0]);
                return result;
            }
        });
    }
};
patchAnalyserPrototype(window.AnalyserNode && AnalyserNode.prototype);
