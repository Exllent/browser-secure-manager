from __future__ import annotations

import json

from models.fingerprint_config import FingerprintConfig


def _build_font_patch(config: FingerprintConfig) -> str:
    fonts = list(dict.fromkeys(config.font_list))
    for index in range(config.font_spoof_count):
        fonts.append(f"Secure UI {index + 1}")
    fonts_json = json.dumps(fonts)
    known_fonts_json = json.dumps(
        sorted(
            set(fonts)
            | {
                "Arial",
                "Calibri",
                "Cambria",
                "Courier New",
                "Geneva",
                "DejaVu Sans",
                "DejaVu Sans Mono",
                "DejaVu Serif",
                "Georgia",
                "Helvetica",
                "Hiragino Sans",
                "Liberation Sans",
                "Liberation Serif",
                "Menlo",
                "Monaco",
                "Noto Sans",
                "Osaka",
                "Roboto",
                "Segoe UI",
                "Tahoma",
                "Times",
                "Times New Roman",
                "Ubuntu",
                "Verdana",
                "Yu Gothic",
            }
        )
    )
    return f"""
    const secureBrowserFonts = new Set({fonts_json});
    const secureBrowserKnownFonts = new Set({known_fonts_json});
    const secureBrowserKnownFontList = Array.from(secureBrowserKnownFonts)
        .sort((first, second) => second.length - first.length);
    const splitFontFamilyList = (value) => {{
        const families = [];
        let current = '';
        let quote = '';
        for (const char of String(value || '')) {{
            if (quote) {{
                current += char;
                if (char === quote) quote = '';
                continue;
            }}
            if (char === '"' || char === "'") {{
                quote = char;
                current += char;
                continue;
            }}
            if (char === ',') {{
                families.push(current);
                current = '';
                continue;
            }}
            current += char;
        }}
        families.push(current);
        return families;
    }};
    const stripFontShorthand = (value) => {{
        const source = String(value || '').trim();
        const sizePattern = /(?:^|\\s)(?:xx-small|x-small|small|medium|large|x-large|xx-large|xxx-large|smaller|larger|[0-9]*\\.?[0-9]+(?:px|pt|pc|in|cm|mm|q|em|rem|ex|ch|lh|rlh|vw|vh|vmin|vmax|%))(?:\\s*\\/\\s*(?:normal|[0-9]*\\.?[0-9]+(?:px|pt|pc|in|cm|mm|q|em|rem|ex|ch|lh|rlh|vw|vh|vmin|vmax|%)?|[0-9]*\\.?[0-9]+))?\\s*/i;
        const match = source.match(sizePattern);
        if (!match || match.index === undefined) return source;
        return source.slice(match.index + match[0].length).trim();
    }};
    const normalizeFontFamily = (value) => splitFontFamilyList(stripFontShorthand(value))
        .map((part) => part.trim().replace(/^['"]|['"]$/g, ''))
        .filter((family) => family && !/^(serif|sans-serif|monospace|cursive|fantasy|system-ui|emoji|math|fangsong|ui-serif|ui-sans-serif|ui-monospace|ui-rounded)$/i.test(family));
    const familiesFromElement = (element) => {{
        try {{
            const inlineFamily = element && element.style && element.style.fontFamily;
            const computedFamily = window.getComputedStyle ? getComputedStyle(element).fontFamily : '';
            return normalizeFontFamily(inlineFamily || computedFamily);
        }} catch (error) {{
            return [];
        }}
    }};
    const profileHasFont = (families) => families.some((family) => secureBrowserFonts.has(family));
    const hasMaskedSystemFont = (families) => families.some((family) =>
        secureBrowserKnownFonts.has(family) && !secureBrowserFonts.has(family)
    );
    const replaceMaskedFonts = (fontValue) => {{
        let result = String(fontValue || '');
        for (const family of secureBrowserKnownFontList) {{
            if (secureBrowserFonts.has(family)) continue;
            const escapedFamily = family.replace(/[.*+?^${{}}()|[\\]\\\\]/g, '\\\\$&');
            result = result.replace(new RegExp(`(["'])?${{escapedFamily}}\\\\1`, 'g'), 'sans-serif');
        }}
        return result;
    }};
    const fontSignal = (families) => {{
        const profileFamily = families.find((family) => secureBrowserFonts.has(family));
        if (!profileFamily) return 0;
        let total = 0;
        for (const char of profileFamily) total += char.charCodeAt(0);
        return (total % 9) + 3;
    }};
    const withMaskedFontsReplaced = (element, callback) => {{
        const families = familiesFromElement(element);
        if (!hasMaskedSystemFont(families)) return callback();

        const previousInlineFont = element.style.font;
        const previousInlineFamily = element.style.fontFamily;
        try {{
            if (previousInlineFont) element.style.font = replaceMaskedFonts(previousInlineFont);
            element.style.fontFamily = replaceMaskedFonts(previousInlineFamily || getComputedStyle(element).fontFamily);
            return callback();
        }} finally {{
            element.style.font = previousInlineFont;
            element.style.fontFamily = previousInlineFamily;
        }}
    }};
    const buildRect = (rect, widthDelta, heightDelta) => {{
        const nextWidth = Math.max(0, rect.width + widthDelta);
        const nextHeight = Math.max(0, rect.height + heightDelta);
        const data = {{
            x: rect.x,
            y: rect.y,
            width: nextWidth,
            height: nextHeight,
            top: rect.top,
            left: rect.left,
            right: rect.left + nextWidth,
            bottom: rect.top + nextHeight
        }};
        if (window.DOMRect && DOMRect.fromRect) return DOMRect.fromRect(data);
        return data;
    }};

    const fontFaceSetPrototype = document.fonts && Object.getPrototypeOf(document.fonts);
    if (fontFaceSetPrototype && fontFaceSetPrototype.check && !fontFaceSetPrototype.__secureBrowserFontCheckPatched) {{
        Object.defineProperty(fontFaceSetPrototype, '__secureBrowserFontCheckPatched', {{ value: true }});
        const originalFontCheck = fontFaceSetPrototype.check;
        fontFaceSetPrototype.check = new Proxy(originalFontCheck, {{
            apply(target, thisArg, args) {{
                const font = args[0];
                const text = args[1];
                const families = normalizeFontFamily(font);
                if (profileHasFont(families)) return true;
                if (hasMaskedSystemFont(families)) return false;
                return Reflect.apply(target, thisArg, [font, text]);
            }}
        }});
    }}

    Object.defineProperty(window, 'queryLocalFonts', {{
        value: async () => Array.from(secureBrowserFonts).map((family) => ({{
            family,
            fullName: family,
            postscriptName: family.replace(/\\s+/g, '-'),
            style: 'Regular'
        }})),
        configurable: true
    }});

    if (window.CanvasRenderingContext2D) {{
        const originalMeasureText = CanvasRenderingContext2D.prototype.measureText;
        CanvasRenderingContext2D.prototype.measureText = new Proxy(originalMeasureText, {{
            apply(target, thisArg, args) {{
                const families = normalizeFontFamily(thisArg.font);
                if (hasMaskedSystemFont(families)) {{
                    const originalFont = thisArg.font;
                    try {{
                        thisArg.font = replaceMaskedFonts(originalFont);
                        return Reflect.apply(target, thisArg, args);
                    }} finally {{
                        thisArg.font = originalFont;
                    }}
                }}

                const metrics = Reflect.apply(target, thisArg, args);
                if (!profileHasFont(families)) return metrics;
                const widthOffset = families.join('').length % 7 / 100;
                return new Proxy(metrics, {{
                    get(metricTarget, property, receiver) {{
                        if (property === 'width') return Reflect.get(metricTarget, property, metricTarget) + widthOffset;
                        return Reflect.get(metricTarget, property, metricTarget);
                    }}
                }});
            }}
        }});
    }}

    const patchElementMetric = (prototype, property, deltaAxis) => {{
        if (!prototype) return;
        const descriptor = Object.getOwnPropertyDescriptor(prototype, property);
        if (!descriptor || !descriptor.get) return;
        Object.defineProperty(prototype, property, {{
            get() {{
                const families = familiesFromElement(this);
                const readMetric = () => descriptor.get.call(this);
                if (hasMaskedSystemFont(families)) return withMaskedFontsReplaced(this, readMetric);
                const value = readMetric();
                const signal = fontSignal(families);
                if (!signal) return value;
                return value + (deltaAxis === 'width' ? signal : Math.max(1, Math.floor(signal / 2)));
            }},
            configurable: true
        }});
    }};

    patchElementMetric(HTMLElement.prototype, 'offsetWidth', 'width');
    patchElementMetric(HTMLElement.prototype, 'offsetHeight', 'height');

    if (window.Element && Element.prototype.getBoundingClientRect) {{
        const originalGetBoundingClientRect = Element.prototype.getBoundingClientRect;
        Element.prototype.getBoundingClientRect = new Proxy(originalGetBoundingClientRect, {{
            apply(target, thisArg, args) {{
                const families = familiesFromElement(thisArg);
                const readRect = () => Reflect.apply(target, thisArg, args);
                if (hasMaskedSystemFont(families)) return withMaskedFontsReplaced(thisArg, readRect);
                const rect = readRect();
                const signal = fontSignal(families);
                if (!signal) return rect;
                return buildRect(rect, signal, Math.max(1, Math.floor(signal / 2)));
            }}
        }});
    }}

    if (window.Element && Element.prototype.getClientRects) {{
        const originalGetClientRects = Element.prototype.getClientRects;
        Element.prototype.getClientRects = new Proxy(originalGetClientRects, {{
            apply(target, thisArg, args) {{
                const families = familiesFromElement(thisArg);
                const readRects = () => Reflect.apply(target, thisArg, args);
                if (hasMaskedSystemFont(families)) return withMaskedFontsReplaced(thisArg, readRects);
                const rects = readRects();
                const signal = fontSignal(families);
                if (!signal) return rects;
                return Array.from(rects).map((rect) =>
                    buildRect(rect, signal, Math.max(1, Math.floor(signal / 2)))
                );
            }}
        }});
    }}
    """
