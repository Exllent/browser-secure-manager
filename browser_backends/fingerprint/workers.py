from __future__ import annotations

import json

from models.fingerprint_config import FingerprintConfig

from .utils import _stable_noise_seed


def _needs_worker_fingerprint_patch(config: FingerprintConfig) -> bool:
    return (
        config.canvas_mode in {"noise", "fixed"}
        or bool(config.webgl_vendor or config.webgl_renderer)
        or bool(config.font_list or config.font_spoof_count)
    )


def _build_worker_fingerprint_patch(config: FingerprintConfig) -> str:
    worker_script = json.dumps(_build_worker_fingerprint_script(config))
    return f"""
    const secureBrowserWorkerFingerprintScript = {worker_script};
    const secureBrowserWrapWorkerUrl = (workerUrl, workerOptions) => {{
        try {{
            const originalUrl = new URL(String(workerUrl), location.href).href;
            const options = workerOptions && typeof workerOptions === 'object' ? workerOptions : {{}};
            const isModule = String(options.type || '').toLowerCase() === 'module';
            const wrapperSource = isModule
                ? secureBrowserWorkerFingerprintScript + '\\nimport ' + JSON.stringify(originalUrl) + ';'
                : secureBrowserWorkerFingerprintScript + '\\nimportScripts(' + JSON.stringify(originalUrl) + ');';
            return URL.createObjectURL(new Blob([wrapperSource], {{ type: 'application/javascript' }}));
        }} catch (error) {{
            return workerUrl;
        }}
    }};
    const secureBrowserPatchWorkerConstructor = (globalName) => {{
        const OriginalWorkerConstructor = window[globalName];
        if (!OriginalWorkerConstructor || OriginalWorkerConstructor.__secureBrowserWorkerPatched) return;
        const PatchedWorkerConstructor = new Proxy(OriginalWorkerConstructor, {{
            construct(target, args, newTarget) {{
                const originalArgs = Array.from(args);
                const workerUrl = originalArgs[0];
                if (typeof workerUrl === 'string' || workerUrl instanceof URL) {{
                    originalArgs[0] = secureBrowserWrapWorkerUrl(workerUrl, originalArgs[1]);
                    try {{
                        return Reflect.construct(target, originalArgs, newTarget);
                    }} catch (error) {{
                        return Reflect.construct(target, args, newTarget);
                    }}
                }}
                return Reflect.construct(target, args, newTarget);
            }}
        }});
        Object.defineProperty(PatchedWorkerConstructor, '__secureBrowserWorkerPatched', {{ value: true }});
        Object.defineProperty(window, globalName, {{
            value: PatchedWorkerConstructor,
            configurable: true,
            writable: true
        }});
    }};
    secureBrowserPatchWorkerConstructor('Worker');
    secureBrowserPatchWorkerConstructor('SharedWorker');
    """


def _build_worker_fingerprint_script(config: FingerprintConfig) -> str:
    fonts = list(dict.fromkeys(config.font_list))
    for index in range(config.font_spoof_count):
        fonts.append(f"Secure UI {index + 1}")

    noise_level = 0.0 if config.canvas_mode == "fixed" else config.canvas_noise_level
    canvas_noise = max(1, int(round(noise_level * 255)))
    webgl_vendor = json.dumps(config.webgl_vendor or "Google Inc.")
    webgl_renderer = json.dumps(config.webgl_renderer or "ANGLE")
    fonts_json = json.dumps(fonts)
    noise_seed = _stable_noise_seed(
        config.user_agent or "",
        config.platform or "",
        config.webgl_vendor or "",
        config.webgl_renderer or "",
    )
    patch_canvas = json.dumps(config.canvas_mode in {"noise", "fixed"})
    patch_webgl = json.dumps(bool(config.webgl_vendor or config.webgl_renderer))
    patch_fonts = json.dumps(bool(config.font_list or config.font_spoof_count))

    return f"""'use strict';
(() => {{
    if (self.__secureBrowserWorkerFingerprintApplied) return;
    Object.defineProperty(self, '__secureBrowserWorkerFingerprintApplied', {{ value: true }});

    const secureBrowserPatchWorkerCanvas = {patch_canvas};
    const secureBrowserPatchWorkerWebGL = {patch_webgl};
    const secureBrowserPatchWorkerFonts = {patch_fonts};
    const secureBrowserCanvasNoise = {canvas_noise};
    const secureBrowserCanvasMode = {json.dumps(config.canvas_mode)};
    const secureBrowserWorkerFonts = new Set({fonts_json});
    const secureBrowserWebGLNoiseSeed = {noise_seed};
    const fingerprintWebGLDebugInfo = {{
        UNMASKED_VENDOR_WEBGL: 37445,
        UNMASKED_RENDERER_WEBGL: 37446
    }};

    const applyCanvasFingerprint = (imageData) => {{
        if (!imageData || !imageData.data) return imageData;
        const data = imageData.data;
        const step = secureBrowserCanvasMode === 'fixed'
            ? 32
            : Math.max(4, Math.floor(96 / Math.max(secureBrowserCanvasNoise, 1)));
        for (let i = 0; i < data.length; i += step * 4) {{
            data[i] = (data[i] + secureBrowserCanvasNoise) & 255;
            data[i + 1] = (data[i + 1] + 1) & 255;
            data[i + 2] = (data[i + 2] + 2) & 255;
        }}
        return imageData;
    }};

    const patchCanvas2DPrototype = (prototype, markerProperty) => {{
        if (!prototype || prototype[markerProperty] || !prototype.getImageData) return;
        Object.defineProperty(prototype, markerProperty, {{ value: true }});
        const originalGetImageData = prototype.getImageData;
        prototype.getImageData = new Proxy(originalGetImageData, {{
            apply(target, thisArg, args) {{
                return applyCanvasFingerprint(Reflect.apply(target, thisArg, args));
            }}
        }});
    }};
    if (secureBrowserPatchWorkerCanvas) {{
        patchCanvas2DPrototype(
            self.OffscreenCanvasRenderingContext2D && OffscreenCanvasRenderingContext2D.prototype,
            '__secureBrowserWorkerCanvas2DPatched'
        );
    }}

    if (self.OffscreenCanvas && OffscreenCanvas.prototype.convertToBlob
        && secureBrowserPatchWorkerCanvas
        && !OffscreenCanvas.prototype.__secureBrowserWorkerConvertToBlobPatched) {{
        Object.defineProperty(OffscreenCanvas.prototype, '__secureBrowserWorkerConvertToBlobPatched', {{ value: true }});
        const originalConvertToBlob = OffscreenCanvas.prototype.convertToBlob;
        OffscreenCanvas.prototype.convertToBlob = new Proxy(originalConvertToBlob, {{
            apply(target, thisArg, args) {{
                try {{
                    const context = thisArg.getContext('2d');
                    if (context) {{
                        const imageData = context.getImageData(0, 0, thisArg.width, thisArg.height);
                        context.putImageData(applyCanvasFingerprint(imageData), 0, 0);
                    }}
                }} catch (error) {{}}
                return Reflect.apply(target, thisArg, args);
            }}
        }});
    }}

    const secureBrowserWeakWebGLNoise = (pixels, width, height) => {{
        if (!pixels || typeof pixels.length !== 'number') return pixels;
        const pixelCount = Math.max(1, Number(width || 0) * Number(height || 0));
        const step = Math.max(64, Math.floor(pixelCount / 96)) * 4;
        let state = secureBrowserWebGLNoiseSeed >>> 0;
        for (let index = 0; index < pixels.length; index += step) {{
            state = (state * 1664525 + 1013904223) >>> 0;
            const channel = index + (state % 3);
            if (channel < pixels.length) {{
                const delta = ((state >>> 8) % 3) - 1;
                pixels[channel] = Math.max(0, Math.min(255, pixels[channel] + delta));
            }}
        }}
        return pixels;
    }};

    const patchWebGLPrototype = (prototype) => {{
        if (!prototype || prototype.__secureBrowserWorkerWebGLPatched) return;
        Object.defineProperty(prototype, '__secureBrowserWorkerWebGLPatched', {{ value: true }});

        const originalGetParameter = prototype.getParameter;
        prototype.getParameter = new Proxy(originalGetParameter, {{
            apply(target, thisArg, args) {{
                const parameter = args[0];
                if (parameter === 37445) return {webgl_vendor};
                if (parameter === 37446) return {webgl_renderer};
                return Reflect.apply(target, thisArg, args);
            }}
        }});

        const originalGetExtension = prototype.getExtension;
        prototype.getExtension = new Proxy(originalGetExtension, {{
            apply(target, thisArg, args) {{
                if (String(args[0]).toLowerCase() === 'webgl_debug_renderer_info') {{
                    return fingerprintWebGLDebugInfo;
                }}
                return Reflect.apply(target, thisArg, args);
            }}
        }});

        const originalGetSupportedExtensions = prototype.getSupportedExtensions;
        prototype.getSupportedExtensions = new Proxy(originalGetSupportedExtensions, {{
            apply(target, thisArg, args) {{
                const result = Reflect.apply(target, thisArg, args) || [];
                return result.includes('WEBGL_debug_renderer_info')
                    ? result
                    : [...result, 'WEBGL_debug_renderer_info'];
            }}
        }});

        const originalReadPixels = prototype.readPixels;
        prototype.readPixels = new Proxy(originalReadPixels, {{
            apply(target, thisArg, args) {{
                const result = Reflect.apply(target, thisArg, args);
                const pixels = args[6];
                if (pixels && ArrayBuffer.isView(pixels)) {{
                    secureBrowserWeakWebGLNoise(pixels, args[2], args[3]);
                }}
                return result;
            }}
        }});
    }};
    if (secureBrowserPatchWorkerWebGL) {{
        patchWebGLPrototype(self.WebGLRenderingContext && WebGLRenderingContext.prototype);
        patchWebGLPrototype(self.WebGL2RenderingContext && WebGL2RenderingContext.prototype);
    }}

    if (secureBrowserPatchWorkerFonts) {{
        Object.defineProperty(self, 'queryLocalFonts', {{
            value: async () => Array.from(secureBrowserWorkerFonts).map((family) => ({{
                family,
                fullName: family,
                postscriptName: family.replace(/\\s+/g, '-'),
                style: 'Regular'
            }})),
            configurable: true
        }});
    }}
}})();
"""
