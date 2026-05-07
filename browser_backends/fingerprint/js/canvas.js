const secureBrowserCanvasConfig = __SECURE_BROWSER_CONFIG__;
const secureBrowserCanvasNoise = secureBrowserCanvasConfig.noise;
const secureBrowserCanvasMode = secureBrowserCanvasConfig.mode;
const secureBrowserCanvasSeed = secureBrowserCanvasConfig.seed >>> 0;
const secureBrowserCanvasState = (...values) => {
    let state = secureBrowserCanvasSeed || 1;
    for (const value of values) {
        const text = String(value ?? '');
        for (let index = 0; index < text.length; index += 1) {
            state ^= text.charCodeAt(index);
            state = Math.imul(state, 16777619) >>> 0;
        }
    }
    return state || 1;
};
const secureBrowserNextCanvasState = (state) => (
    (Math.imul(state >>> 0, 1664525) + 1013904223) >>> 0
);
const applyCanvasFingerprint = (imageData) => {
    if (!imageData || !imageData.data) return imageData;
    const width = Math.max(1, Math.floor(Number(imageData.width) || 1));
    const height = Math.max(1, Math.floor(Number(imageData.height) || 1));
    const data = imageData.data;
    const pixelCount = Math.max(1, Math.floor(data.length / 4));
    const patchRatio = Math.max(0.002, Math.min(0.12, secureBrowserCanvasNoise / 255));
    const patchCount = Math.max(1, Math.floor(pixelCount * patchRatio));
    let state = secureBrowserCanvasState(width, height, secureBrowserCanvasMode, secureBrowserCanvasNoise);
    for (let index = 0; index < patchCount; index += 1) {
        state = secureBrowserNextCanvasState(state);
        const pixelIndex = state % pixelCount;
        state = secureBrowserNextCanvasState(state);
        const channel = (pixelIndex * 4) + (state % 3);
        if (channel >= data.length) continue;
        const direction = ((state >>> 8) & 1) ? 1 : -1;
        state = secureBrowserNextCanvasState(state);
        const delta = 1 + (state % secureBrowserCanvasNoise);
        data[channel] = Math.max(0, Math.min(255, data[channel] + (direction * delta)));
        state = secureBrowserNextCanvasState(state);
    }
    return imageData;
};

const patchCanvas2DPrototype = (prototype, markerProperty) => {
    if (!prototype || prototype[markerProperty] || !prototype.getImageData) return null;
    Object.defineProperty(prototype, markerProperty, {value: true});
    const originalGetImageData = prototype.getImageData;
    prototype.getImageData = new Proxy(originalGetImageData, {
        apply(target, thisArg, args) {
            const imageData = Reflect.apply(target, thisArg, args);
            return applyCanvasFingerprint(imageData);
        }
    });
    return originalGetImageData;
};

const originalCanvas2DGetImageData = patchCanvas2DPrototype(
    window.CanvasRenderingContext2D && CanvasRenderingContext2D.prototype,
    '__secureBrowserCanvas2DPatched'
);
const originalOffscreen2DGetImageData = patchCanvas2DPrototype(
    window.OffscreenCanvasRenderingContext2D && OffscreenCanvasRenderingContext2D.prototype,
    '__secureBrowserOffscreenCanvas2DPatched'
);

const copyCanvasWithNoise = (canvas, offscreen = false) => {
    const clone = offscreen
        ? new OffscreenCanvas(canvas.width, canvas.height)
        : document.createElement('canvas');
    clone.width = canvas.width;
    clone.height = canvas.height;
    const cloneContext = clone.getContext('2d');
    if (!cloneContext) return null;
    cloneContext.drawImage(canvas, 0, 0);
    const originalGetImageData = offscreen
        ? originalOffscreen2DGetImageData
        : originalCanvas2DGetImageData;
    const imageData = Reflect.apply(
        originalGetImageData || cloneContext.getImageData,
        cloneContext,
        [0, 0, Math.max(1, clone.width), Math.max(1, clone.height)]
    );
    cloneContext.putImageData(applyCanvasFingerprint(imageData), 0, 0);
    return clone;
};

if (!HTMLCanvasElement.prototype.__secureBrowserCanvasExportPatched) {
    Object.defineProperty(HTMLCanvasElement.prototype, '__secureBrowserCanvasExportPatched', {value: true});
    const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = new Proxy(originalToDataURL, {
        apply(target, thisArg, args) {
            try {
                const clone = copyCanvasWithNoise(thisArg);
                if (clone) return Reflect.apply(target, clone, args);
            } catch (error) {
            }
            return Reflect.apply(target, thisArg, args);
        }
    });
}

const originalToBlob = HTMLCanvasElement.prototype.toBlob;
if (originalToBlob && !HTMLCanvasElement.prototype.__secureBrowserCanvasBlobPatched) {
    Object.defineProperty(HTMLCanvasElement.prototype, '__secureBrowserCanvasBlobPatched', {value: true});
    HTMLCanvasElement.prototype.toBlob = new Proxy(originalToBlob, {
        apply(target, thisArg, args) {
            try {
                const clone = copyCanvasWithNoise(thisArg);
                if (clone) return Reflect.apply(target, clone, args);
            } catch (error) {
            }
            return Reflect.apply(target, thisArg, args);
        }
    });
}

if (window.OffscreenCanvas && OffscreenCanvas.prototype.convertToBlob) {
    const originalCanvasConvertToBlob = OffscreenCanvas.prototype.convertToBlob;
    if (!OffscreenCanvas.prototype.__secureBrowserCanvasConvertToBlobPatched) {
        Object.defineProperty(OffscreenCanvas.prototype, '__secureBrowserCanvasConvertToBlobPatched', {value: true});
        OffscreenCanvas.prototype.convertToBlob = new Proxy(originalCanvasConvertToBlob, {
            apply(target, thisArg, args) {
                try {
                    const clone = copyCanvasWithNoise(thisArg, true);
                    if (clone) return Reflect.apply(target, clone, args);
                } catch (error) {
                }
                return Reflect.apply(target, thisArg, args);
            }
        });
    }
}
