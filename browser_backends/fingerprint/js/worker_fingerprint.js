'use strict';
(() => {
    if (self.__secureBrowserWorkerFingerprintApplied) return;
    Object.defineProperty(self, '__secureBrowserWorkerFingerprintApplied', {value: true});

    const secureBrowserWorkerConfig = __SECURE_BROWSER_CONFIG__;
    const secureBrowserPatchWorkerCanvas = secureBrowserWorkerConfig.patchCanvas;
    const secureBrowserPatchWorkerWebGL = secureBrowserWorkerConfig.patchWebGL;
    const secureBrowserPatchWorkerFonts = secureBrowserWorkerConfig.patchFonts;
    const secureBrowserPatchWorkerNavigator = secureBrowserWorkerConfig.patchNavigator;
    const secureBrowserCanvasNoise = secureBrowserWorkerConfig.canvasNoise;
    const secureBrowserCanvasMode = secureBrowserWorkerConfig.canvasMode;
    const secureBrowserWorkerFonts = new Set(secureBrowserWorkerConfig.fonts);
    const secureBrowserCanvasNoiseSeed = secureBrowserWorkerConfig.canvasNoiseSeed >>> 0;
    const secureBrowserWebGLNoiseSeed = secureBrowserWorkerConfig.webglNoiseSeed;
    const secureBrowserWorkerUserAgentData = secureBrowserWorkerConfig.userAgentData;
    const secureBrowserWorkerTimezone = secureBrowserWorkerConfig.timezone;
    const fingerprintWebGLDebugInfo = {
        UNMASKED_VENDOR_WEBGL: 37445,
        UNMASKED_RENDERER_WEBGL: 37446
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
            const alphaIndex = (pixelIndex * 4) + 3;
            if (alphaIndex >= data.length || data[alphaIndex] === 0) continue;
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

    const patchWorkerNavigatorProperty = (target, property, value) => {
        if (!target || value === null || value === undefined) return;
        try {
            Object.defineProperty(target, property, {
                get: () => value,
                configurable: true
            });
        } catch (error) {
        }
    };

    const buildWorkerUserAgentData = () => {
        if (!secureBrowserWorkerUserAgentData) return undefined;
        const data = {
            brands: secureBrowserWorkerUserAgentData.brands.map((brand) => ({...brand})),
            mobile: secureBrowserWorkerUserAgentData.mobile,
            platform: secureBrowserWorkerUserAgentData.platform,
            getHighEntropyValues: async (hints) => {
                const allowed = new Set(Array.isArray(hints) ? hints : []);
                const values = {
                    brands: secureBrowserWorkerUserAgentData.brands.map((brand) => ({...brand})),
                    mobile: secureBrowserWorkerUserAgentData.mobile,
                    platform: secureBrowserWorkerUserAgentData.platform
                };
                for (const key of allowed) {
                    if (Object.prototype.hasOwnProperty.call(secureBrowserWorkerUserAgentData, key)) {
                        values[key] = Array.isArray(secureBrowserWorkerUserAgentData[key])
                            ? secureBrowserWorkerUserAgentData[key].map((item) => ({...item}))
                            : secureBrowserWorkerUserAgentData[key];
                    }
                }
                return values;
            },
            toJSON: () => ({
                brands: secureBrowserWorkerUserAgentData.brands.map((brand) => ({...brand})),
                mobile: secureBrowserWorkerUserAgentData.mobile,
                platform: secureBrowserWorkerUserAgentData.platform
            })
        };
        return Object.freeze(data);
    };

    if (secureBrowserPatchWorkerNavigator && self.navigator) {
        const navigatorPrototype = Object.getPrototypeOf(self.navigator);
        patchWorkerNavigatorProperty(navigatorPrototype, 'userAgent', secureBrowserWorkerConfig.userAgent);
        patchWorkerNavigatorProperty(navigatorPrototype, 'appVersion', secureBrowserWorkerConfig.appVersion);
        patchWorkerNavigatorProperty(navigatorPrototype, 'platform', secureBrowserWorkerConfig.platform);
        patchWorkerNavigatorProperty(navigatorPrototype, 'languages', secureBrowserWorkerConfig.languages);
        patchWorkerNavigatorProperty(navigatorPrototype, 'language', secureBrowserWorkerConfig.language);
        patchWorkerNavigatorProperty(
            navigatorPrototype,
            'hardwareConcurrency',
            secureBrowserWorkerConfig.hardwareConcurrency
        );
        patchWorkerNavigatorProperty(
            navigatorPrototype,
            'deviceMemory',
            secureBrowserWorkerConfig.deviceMemory
        );
        try {
            Object.defineProperty(navigatorPrototype, 'oscpu', {
                get: () => undefined,
                configurable: true
            });
        } catch (error) {
        }
        if (secureBrowserWorkerUserAgentData) {
            try {
                Object.defineProperty(navigatorPrototype, 'userAgentData', {
                    get: buildWorkerUserAgentData,
                    configurable: true
                });
            } catch (error) {
            }
        }
    }

    if (secureBrowserWorkerTimezone && self.Intl && Intl.DateTimeFormat) {
        const originalResolvedOptions = Intl.DateTimeFormat.prototype.resolvedOptions;
        if (originalResolvedOptions && !Intl.DateTimeFormat.prototype.__secureBrowserTimezonePatched) {
            Object.defineProperty(Intl.DateTimeFormat.prototype, '__secureBrowserTimezonePatched', {value: true});
            Intl.DateTimeFormat.prototype.resolvedOptions = new Proxy(originalResolvedOptions, {
                apply(target, thisArg, args) {
                    return {
                        ...Reflect.apply(target, thisArg, args),
                        timeZone: secureBrowserWorkerTimezone
                    };
                }
            });
        }
    }

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
    let originalWorkerGetImageData = null;
    if (secureBrowserPatchWorkerCanvas) {
        originalWorkerGetImageData = patchCanvas2DPrototype(
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
                        const imageData = Reflect.apply(
                            originalWorkerGetImageData || context.getImageData,
                            context,
                            [0, 0, Math.max(1, thisArg.width), Math.max(1, thisArg.height)]
                        );
                        context.putImageData(applyCanvasFingerprint(imageData), 0, 0);
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
