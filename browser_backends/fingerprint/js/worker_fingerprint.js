'use strict';
(() => {
    if (self.__secureBrowserWorkerFingerprintApplied) return;
    Object.defineProperty(self, '__secureBrowserWorkerFingerprintApplied', {value: true});

    const secureBrowserWorkerConfig = __SECURE_BROWSER_CONFIG__;
    const secureBrowserPatchWorkerCanvas = secureBrowserWorkerConfig.patchCanvas;
    const secureBrowserPatchWorkerWebGL = secureBrowserWorkerConfig.patchWebGL;
    const secureBrowserPatchWorkerFonts = secureBrowserWorkerConfig.patchFonts;
    const secureBrowserCanvasNoise = secureBrowserWorkerConfig.canvasNoise;
    const secureBrowserCanvasMode = secureBrowserWorkerConfig.canvasMode;
    const secureBrowserWorkerFonts = new Set(secureBrowserWorkerConfig.fonts);
    const secureBrowserCanvasNoiseSeed = secureBrowserWorkerConfig.canvasNoiseSeed >>> 0;
    const secureBrowserWebGLNoiseSeed = secureBrowserWorkerConfig.webglNoiseSeed;
    const fingerprintWebGLDebugInfo = {
        UNMASKED_VENDOR_WEBGL: 37445,
        UNMASKED_RENDERER_WEBGL: 37446
    };

    const applyCanvasFingerprint = (imageData) => {
        if (!imageData || !imageData.data) return imageData;
        const data = imageData.data;
        const pixelCount = Math.max(1, Math.floor(data.length / 4));
        const patchCount = secureBrowserCanvasMode === 'fixed'
            ? Math.max(1, Math.floor(pixelCount / 96))
            : Math.max(1, Math.floor(pixelCount / Math.max(24, 144 - secureBrowserCanvasNoise)));
        let state = secureBrowserCanvasNoiseSeed || 1;
        for (let i = 0; i < patchCount; i += 1) {
            state = (state * 1664525 + 1013904223) >>> 0;
            const pixelIndex = state % pixelCount;
            state = (state * 1664525 + 1013904223) >>> 0;
            const channel = (pixelIndex * 4) + (state % 3);
            if (channel >= data.length) continue;
            const direction = secureBrowserCanvasMode === 'fixed'
                ? 1
                : ((state >>> 8) & 1) ? 1 : -1;
            const delta = Math.max(1, secureBrowserCanvasNoise) * direction;
            data[channel] = Math.max(0, Math.min(255, data[channel] + delta));
        }
        return imageData;
    };

    const secureBrowserCanvasState = (...values) => {
        let state = secureBrowserCanvasNoiseSeed || 1;
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

    const secureBrowserStableImageData = (context, width, height, salt = '') => {
        const safeWidth = Math.max(1, Math.floor(Number(width) || 1));
        const safeHeight = Math.max(1, Math.floor(Number(height) || 1));
        const imageData = context && context.createImageData
            ? context.createImageData(safeWidth, safeHeight)
            : new ImageData(safeWidth, safeHeight);
        const data = imageData.data;
        let state = secureBrowserCanvasState(safeWidth, safeHeight, salt);
        for (let index = 0; index < data.length; index += 4) {
            state = secureBrowserNextCanvasState(state);
            data[index] = state & 255;
            state = secureBrowserNextCanvasState(state);
            data[index + 1] = state & 255;
            state = secureBrowserNextCanvasState(state);
            data[index + 2] = state & 255;
            data[index + 3] = 255;
        }
        return imageData;
    };

    const patchCanvas2DPrototype = (prototype, markerProperty) => {
        if (!prototype || prototype[markerProperty] || !prototype.getImageData) return;
        Object.defineProperty(prototype, markerProperty, {value: true});
        const originalGetImageData = prototype.getImageData;
        prototype.getImageData = new Proxy(originalGetImageData, {
            apply(target, thisArg, args) {
                const width = args.length > 2 ? args[2] : thisArg.canvas && thisArg.canvas.width;
                const height = args.length > 3 ? args[3] : thisArg.canvas && thisArg.canvas.height;
                return secureBrowserStableImageData(thisArg, width, height, 'worker-getImageData');
            }
        });
    };
    if (secureBrowserPatchWorkerCanvas) {
        patchCanvas2DPrototype(
            self.OffscreenCanvasRenderingContext2D && OffscreenCanvasRenderingContext2D.prototype,
            '__secureBrowserWorkerCanvas2DPatched'
        );
    }

    if (self.OffscreenCanvas && OffscreenCanvas.prototype.convertToBlob
        && secureBrowserPatchWorkerCanvas
        && !OffscreenCanvas.prototype.__secureBrowserWorkerConvertToBlobPatched) {
        Object.defineProperty(OffscreenCanvas.prototype, '__secureBrowserWorkerConvertToBlobPatched', {value: true});
        const originalConvertToBlob = OffscreenCanvas.prototype.convertToBlob;
        OffscreenCanvas.prototype.convertToBlob = new Proxy(originalConvertToBlob, {
            apply(target, thisArg, args) {
                try {
                    const context = thisArg.getContext('2d');
                    if (context) {
                        context.putImageData(
                            secureBrowserStableImageData(
                                context,
                                thisArg.width,
                                thisArg.height,
                                'worker-offscreen-export'
                            ),
                            0,
                            0
                        );
                    }
                } catch (error) {
                }
                return Reflect.apply(target, thisArg, args);
            }
        });
    }

    const secureBrowserWeakWebGLNoise = (pixels, width, height) => {
        if (!pixels || typeof pixels.length !== 'number') return pixels;
        const pixelCount = Math.max(1, Number(width || 0) * Number(height || 0));
        const step = Math.max(64, Math.floor(pixelCount / 96)) * 4;
        let state = secureBrowserWebGLNoiseSeed >>> 0;
        for (let index = 0; index < pixels.length; index += step) {
            state = (state * 1664525 + 1013904223) >>> 0;
            const channel = index + (state % 3);
            if (channel < pixels.length) {
                const delta = ((state >>> 8) % 3) - 1;
                pixels[channel] = Math.max(0, Math.min(255, pixels[channel] + delta));
            }
        }
        return pixels;
    };

    const patchWebGLPrototype = (prototype) => {
        if (!prototype || prototype.__secureBrowserWorkerWebGLPatched) return;
        Object.defineProperty(prototype, '__secureBrowserWorkerWebGLPatched', {value: true});

        const originalGetParameter = prototype.getParameter;
        prototype.getParameter = new Proxy(originalGetParameter, {
            apply(target, thisArg, args) {
                const parameter = args[0];
                if (parameter === 37445) return secureBrowserWorkerConfig.webglVendor;
                if (parameter === 37446) return secureBrowserWorkerConfig.webglRenderer;
                return Reflect.apply(target, thisArg, args);
            }
        });

        const originalGetExtension = prototype.getExtension;
        prototype.getExtension = new Proxy(originalGetExtension, {
            apply(target, thisArg, args) {
                if (String(args[0]).toLowerCase() === 'webgl_debug_renderer_info') {
                    return fingerprintWebGLDebugInfo;
                }
                return Reflect.apply(target, thisArg, args);
            }
        });

        const originalGetSupportedExtensions = prototype.getSupportedExtensions;
        prototype.getSupportedExtensions = new Proxy(originalGetSupportedExtensions, {
            apply(target, thisArg, args) {
                const result = Reflect.apply(target, thisArg, args) || [];
                return result.includes('WEBGL_debug_renderer_info')
                    ? result
                    : [...result, 'WEBGL_debug_renderer_info'];
            }
        });

        const originalReadPixels = prototype.readPixels;
        prototype.readPixels = new Proxy(originalReadPixels, {
            apply(target, thisArg, args) {
                const result = Reflect.apply(target, thisArg, args);
                const pixels = args[6];
                if (pixels && ArrayBuffer.isView(pixels)) {
                    secureBrowserWeakWebGLNoise(pixels, args[2], args[3]);
                }
                return result;
            }
        });
    };
    if (secureBrowserPatchWorkerWebGL) {
        patchWebGLPrototype(self.WebGLRenderingContext && WebGLRenderingContext.prototype);
        patchWebGLPrototype(self.WebGL2RenderingContext && WebGL2RenderingContext.prototype);
    }

    if (secureBrowserPatchWorkerFonts) {
        Object.defineProperty(self, 'queryLocalFonts', {
            value: async () => Array.from(secureBrowserWorkerFonts).map((family) => ({
                family,
                fullName: family,
                postscriptName: family.replace(/\s+/g, '-'),
                style: 'Regular'
            })),
            configurable: true
        });
    }
})();
