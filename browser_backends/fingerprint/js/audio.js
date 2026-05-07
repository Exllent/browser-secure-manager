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
    if (AudioBuffer.prototype.copyFromChannel) {
        const originalCopyFromChannel = AudioBuffer.prototype.copyFromChannel;
        AudioBuffer.prototype.copyFromChannel = new Proxy(originalCopyFromChannel, {
            apply(target, thisArg, args) {
                const result = Reflect.apply(target, thisArg, args);
                secureBrowserWeakAudioNoise(args[0]);
                return result;
            }
        });
    }
}

const patchAnalyserPrototype = (prototype) => {
    if (!prototype || prototype.__secureBrowserAnalyserPatched) return;
    Object.defineProperty(prototype, '__secureBrowserAnalyserPatched', {value: true});
    for (const methodName of [
        'getFloatFrequencyData',
        'getFloatTimeDomainData',
        'getByteFrequencyData',
        'getByteTimeDomainData'
    ]) {
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

const patchOfflineAudioContextPrototype = (prototype) => {
    if (!prototype || prototype.__secureBrowserOfflineAudioPatched || !prototype.startRendering) return;
    Object.defineProperty(prototype, '__secureBrowserOfflineAudioPatched', {value: true});
    const originalStartRendering = prototype.startRendering;
    prototype.startRendering = new Proxy(originalStartRendering, {
        apply(target, thisArg, args) {
            const result = Reflect.apply(target, thisArg, args);
            if (!result || typeof result.then !== 'function') return result;
            return result.then((buffer) => {
                try {
                    for (let channel = 0; channel < buffer.numberOfChannels; channel += 1) {
                        secureBrowserWeakAudioNoise(buffer.getChannelData(channel));
                    }
                } catch (error) {
                }
                return buffer;
            });
        }
    });
};
patchOfflineAudioContextPrototype(window.OfflineAudioContext && OfflineAudioContext.prototype);
patchOfflineAudioContextPrototype(window.webkitOfflineAudioContext && webkitOfflineAudioContext.prototype);
