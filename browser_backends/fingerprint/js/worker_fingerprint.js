'use strict';
(() => {
    if (self.__secureBrowserWorkerFingerprintApplied) return;
    Object.defineProperty(self, '__secureBrowserWorkerFingerprintApplied', { value: true });

    const secureBrowserWorkerConfig = __SECURE_BROWSER_CONFIG__;
    const secureBrowserPatchWorkerCanvas = secureBrowserWorkerConfig.patchCanvas;
    const secureBrowserPatchWorkerWebGL = secureBrowserWorkerConfig.patchWebGL;
    const secureBrowserPatchWorkerFonts = secureBrowserWorkerConfig.patchFonts;
    const secureBrowserCanvasNoise = secureBrowserWorkerConfig.canvasNoise;
    const secureBrowserCanvasMode = secureBrowserWorkerConfig.canvasMode;
    const secureBrowserWorkerFonts = new Set(secureBrowserWorkerConfig.fonts);
    const secureBrowserWebGLNoiseSeed = secureBrowserWorkerConfig.webglNoiseSeed;
    const fingerprintWebGLDebugInfo = {
        UNMASKED_VENDOR_WEBGL: 37445,
        UNMASKED_RENDERER_WEBGL: 37446
    };

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
                return applyCanvasFingerprint(Reflect.apply(target, thisArg, args));
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
        Object.defineProperty(OffscreenCanvas.prototype, '__secureBrowserWorkerConvertToBlobPatched', { value: true });
        const originalConvertToBlob = OffscreenCanvas.prototype.convertToBlob;
        OffscreenCanvas.prototype.convertToBlob = new Proxy(originalConvertToBlob, {
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
        Object.defineProperty(prototype, '__secureBrowserWorkerWebGLPatched', { value: true });

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
