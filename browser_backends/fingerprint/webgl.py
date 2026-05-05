from __future__ import annotations

import json

from models.fingerprint_config import FingerprintConfig

from .utils import _stable_noise_seed


def _build_webgl_patch(config: FingerprintConfig) -> str:
    vendor = json.dumps(config.webgl_vendor or "Google Inc.")
    renderer = json.dumps(config.webgl_renderer or "ANGLE")
    noise_seed = _stable_noise_seed(
        config.user_agent or "",
        config.platform or "",
        config.webgl_vendor or "",
        config.webgl_renderer or "",
    )
    return f"""
    const secureBrowserWebGLCanvases = new WeakMap();
    const secureBrowserWebGLNoiseSeed = {noise_seed};
    const fingerprintWebGLDebugInfo = {{
        UNMASKED_VENDOR_WEBGL: 37445,
        UNMASKED_RENDERER_WEBGL: 37446
    }};
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

    const patchWebGLCanvasGetContext = (prototype, markerProperty) => {{
        if (!prototype || prototype[markerProperty] || !prototype.getContext) return;
        Object.defineProperty(prototype, markerProperty, {{ value: true }});
        const originalCanvasGetContext = prototype.getContext;
        prototype.getContext = new Proxy(originalCanvasGetContext, {{
            apply(target, thisArg, args) {{
                const context = Reflect.apply(target, thisArg, args);
                const contextType = String(args[0] || '').toLowerCase();
                if (context && (contextType === 'webgl' || contextType === 'experimental-webgl' || contextType === 'webgl2')) {{
                    secureBrowserWebGLCanvases.set(thisArg, context);
                }}
                return context;
            }}
        }});
    }};
    patchWebGLCanvasGetContext(HTMLCanvasElement.prototype, '__secureBrowserWebGLGetContextPatched');
    patchWebGLCanvasGetContext(
        window.OffscreenCanvas && OffscreenCanvas.prototype,
        '__secureBrowserWebGLOffscreenGetContextPatched'
    );

    const noisyWebGLCanvasDataURL = (canvas, type, quality) => {{
        const context = secureBrowserWebGLCanvases.get(canvas);
        if (!context) return null;

        const width = context.drawingBufferWidth || canvas.width;
        const height = context.drawingBufferHeight || canvas.height;
        if (!width || !height) return null;

        const pixels = new Uint8Array(width * height * 4);
        context.readPixels(0, 0, width, height, context.RGBA, context.UNSIGNED_BYTE, pixels);

        const output = document.createElement('canvas');
        output.width = width;
        output.height = height;
        const outputContext = output.getContext('2d');
        if (!outputContext) return null;

        const imageData = outputContext.createImageData(width, height);
        const rowSize = width * 4;
        for (let row = 0; row < height; row += 1) {{
            const sourceStart = (height - row - 1) * rowSize;
            const targetStart = row * rowSize;
            imageData.data.set(pixels.subarray(sourceStart, sourceStart + rowSize), targetStart);
        }}
        outputContext.putImageData(imageData, 0, 0);
        return output.toDataURL(type, quality);
    }};

    if (!HTMLCanvasElement.prototype.__secureBrowserWebGLToDataURLPatched) {{
        Object.defineProperty(HTMLCanvasElement.prototype, '__secureBrowserWebGLToDataURLPatched', {{ value: true }});
        const originalWebGLToDataURL = HTMLCanvasElement.prototype.toDataURL;
        HTMLCanvasElement.prototype.toDataURL = new Proxy(originalWebGLToDataURL, {{
            apply(target, thisArg, args) {{
                try {{
                    const dataUrl = noisyWebGLCanvasDataURL(thisArg, args[0], args[1]);
                    if (dataUrl) return dataUrl;
                }} catch (error) {{}}
                return Reflect.apply(target, thisArg, args);
            }}
        }});
    }}

    if (!HTMLCanvasElement.prototype.__secureBrowserWebGLToBlobPatched && HTMLCanvasElement.prototype.toBlob) {{
        Object.defineProperty(HTMLCanvasElement.prototype, '__secureBrowserWebGLToBlobPatched', {{ value: true }});
        const originalWebGLToBlob = HTMLCanvasElement.prototype.toBlob;
        HTMLCanvasElement.prototype.toBlob = new Proxy(originalWebGLToBlob, {{
            apply(target, thisArg, args) {{
                const callback = args[0];
                if (typeof callback === 'function') {{
                    try {{
                        const dataUrl = noisyWebGLCanvasDataURL(thisArg, args[1], args[2]);
                        if (dataUrl) {{
                            fetch(dataUrl)
                                .then((response) => response.blob())
                                .then((blob) => callback(blob))
                                .catch(() => Reflect.apply(target, thisArg, args));
                            return undefined;
                        }}
                    }} catch (error) {{}}
                }}
                return Reflect.apply(target, thisArg, args);
            }}
        }});
    }}

    if (window.OffscreenCanvas && OffscreenCanvas.prototype.convertToBlob
        && !OffscreenCanvas.prototype.__secureBrowserWebGLConvertToBlobPatched) {{
        Object.defineProperty(OffscreenCanvas.prototype, '__secureBrowserWebGLConvertToBlobPatched', {{ value: true }});
        const originalWebGLConvertToBlob = OffscreenCanvas.prototype.convertToBlob;
        OffscreenCanvas.prototype.convertToBlob = new Proxy(originalWebGLConvertToBlob, {{
            apply(target, thisArg, args) {{
                try {{
                    const options = args[0] || {{}};
                    const dataUrl = noisyWebGLCanvasDataURL(thisArg, options.type, options.quality);
                    if (dataUrl) return fetch(dataUrl).then((response) => response.blob());
                }} catch (error) {{}}
                return Reflect.apply(target, thisArg, args);
            }}
        }});
    }}

    const patchWebGLPrototype = (prototype) => {{
        if (!prototype || prototype.__secureBrowserWebGLPatched) return;
        Object.defineProperty(prototype, '__secureBrowserWebGLPatched', {{ value: true }});

        const originalGetParameter = prototype.getParameter;
        prototype.getParameter = new Proxy(originalGetParameter, {{
            apply(target, thisArg, args) {{
                const parameter = args[0];
                if (parameter === 37445) return {vendor};
                if (parameter === 37446) return {renderer};
                return Reflect.apply(target, thisArg, args);
            }}
        }});

        const originalGetExtension = prototype.getExtension;
        prototype.getExtension = new Proxy(originalGetExtension, {{
            apply(target, thisArg, args) {{
                const name = args[0];
                if (String(name).toLowerCase() === 'webgl_debug_renderer_info') {{
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
    patchWebGLPrototype(window.WebGLRenderingContext && WebGLRenderingContext.prototype);
    patchWebGLPrototype(window.WebGL2RenderingContext && WebGL2RenderingContext.prototype);
    """
