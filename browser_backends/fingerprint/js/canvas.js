const secureBrowserCanvasConfig = __SECURE_BROWSER_CONFIG__;
const secureBrowserCanvasNoise = secureBrowserCanvasConfig.noise;
const secureBrowserCanvasMode = secureBrowserCanvasConfig.mode;
const applyCanvasFingerprint = (imageData) => {
    if (!imageData || !imageData.data) return imageData;
    const data = imageData.data;
    const step = secureBrowserCanvasMode === 'fixed'
        ? 32
        : Math.max(4, Math.floor(96 / Math.max(secureBrowserCanvasNoise, 1)));
    for (let i = 0; i < data.length; i += step * 4) {
        data[i] = (data[i] + secureBrowserCanvasNoise) & 255;
        data[i + 1] = (data[i + 1] + 1) & 255;
        data[i + 2] = (data[i + 2] + 2) & 255;
    }
    return imageData;
};

const patchCanvas2DPrototype = (prototype, markerProperty) => {
    if (!prototype || prototype[markerProperty] || !prototype.getImageData) return;
    Object.defineProperty(prototype, markerProperty, { value: true });
    const originalGetImageData = prototype.getImageData;
    prototype.getImageData = new Proxy(originalGetImageData, {
        apply(target, thisArg, args) {
            const imageData = Reflect.apply(target, thisArg, args);
            return applyCanvasFingerprint(imageData);
        }
    });
};
patchCanvas2DPrototype(
    window.CanvasRenderingContext2D && CanvasRenderingContext2D.prototype,
    '__secureBrowserCanvas2DPatched'
);
patchCanvas2DPrototype(
    window.OffscreenCanvasRenderingContext2D && OffscreenCanvasRenderingContext2D.prototype,
    '__secureBrowserOffscreenCanvas2DPatched'
);

const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
HTMLCanvasElement.prototype.toDataURL = new Proxy(originalToDataURL, {
    apply(target, thisArg, args) {
        try {
            const context = thisArg.getContext('2d');
            if (context) {
                const imageData = context.getImageData(0, 0, thisArg.width, thisArg.height);
                context.putImageData(applyCanvasFingerprint(imageData), 0, 0);
            }
        } catch (error) {}
        return Reflect.apply(target, thisArg, args);
    }
});

const originalToBlob = HTMLCanvasElement.prototype.toBlob;
if (originalToBlob) {
    HTMLCanvasElement.prototype.toBlob = new Proxy(originalToBlob, {
        apply(target, thisArg, args) {
            try {
                const context = thisArg.getContext('2d');
                if (context) {
                    const imageData = context.getImageData(0, 0, thisArg.width, thisArg.height);
                    context.putImageData(applyCanvasFingerprint(imageData), 0, 0);
                }
            } catch (error) {}
            return Reflect.apply(target, thisArg, args);
        }
    });
}

if (window.OffscreenCanvas && OffscreenCanvas.prototype.convertToBlob) {
    const originalCanvasConvertToBlob = OffscreenCanvas.prototype.convertToBlob;
    OffscreenCanvas.prototype.convertToBlob = new Proxy(originalCanvasConvertToBlob, {
        apply(target, thisArg, args) {
            try {
                const context = thisArg.getContext('2d');
                if (context) {
                    const imageData = context.getImageData(0, 0, thisArg.width, thisArg.height);
                    context.putImageData(applyCanvasFingerprint(imageData), 0, 0);
                }
            } catch (error) {}
            return Reflect.apply(target, thisArg, args);
        }
    });
}
