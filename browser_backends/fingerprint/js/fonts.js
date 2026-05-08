const secureBrowserFontConfig = __SECURE_BROWSER_CONFIG__;
const secureBrowserFonts = new Set(secureBrowserFontConfig.fonts);
const secureBrowserKnownFonts = new Set(secureBrowserFontConfig.knownFonts);
const secureBrowserFontPlatform = String(secureBrowserFontConfig.platform || '');
const secureBrowserKnownFontList = Array.from(secureBrowserKnownFonts)
    .sort((first, second) => second.length - first.length);
const secureBrowserFontPlatformSalt = (() => {
    if (secureBrowserFontPlatform === 'MacIntel') return 29;
    if (secureBrowserFontPlatform.startsWith('Win')) return 17;
    if (secureBrowserFontPlatform.startsWith('Linux')) return 23;
    return 19;
})();
const splitFontFamilyList = (value) => {
    const families = [];
    let current = '';
    let quote = '';
    for (const char of String(value || '')) {
        if (quote) {
            current += char;
            if (char === quote) quote = '';
            continue;
        }
        if (char === '"' || char === "'") {
            quote = char;
            current += char;
            continue;
        }
        if (char === ',') {
            families.push(current);
            current = '';
            continue;
        }
        current += char;
    }
    families.push(current);
    return families;
};
const stripFontShorthand = (value) => {
    const source = String(value || '').trim();
    const sizePattern = /(?:^|\s)(?:xx-small|x-small|small|medium|large|x-large|xx-large|xxx-large|smaller|larger|[0-9]*\.?[0-9]+(?:px|pt|pc|in|cm|mm|q|em|rem|ex|ch|lh|rlh|vw|vh|vmin|vmax|%))(?:\s*\/\s*(?:normal|[0-9]*\.?[0-9]+(?:px|pt|pc|in|cm|mm|q|em|rem|ex|ch|lh|rlh|vw|vh|vmin|vmax|%)?|[0-9]*\.?[0-9]+))?\s*/i;
    const match = source.match(sizePattern);
    if (!match || match.index === undefined) return source;
    return source.slice(match.index + match[0].length).trim();
};
const normalizeFontFamily = (value) => splitFontFamilyList(stripFontShorthand(value))
    .map((part) => part.trim().replace(/^['"]|['"]$/g, ''))
    .filter((family) => family && !/^(serif|sans-serif|monospace|cursive|fantasy|system-ui|emoji|math|fangsong|ui-serif|ui-sans-serif|ui-monospace|ui-rounded)$/i.test(family));
const familiesFromElement = (element) => {
    try {
        const inlineFamily = element && element.style && element.style.fontFamily;
        const computedFamily = window.getComputedStyle ? getComputedStyle(element).fontFamily : '';
        return normalizeFontFamily(inlineFamily || computedFamily);
    } catch (error) {
        return [];
    }
};
const profileHasFont = (families) => families.some((family) => secureBrowserFonts.has(family));
const hasMaskedSystemFont = (families) => families.some((family) =>
    secureBrowserKnownFonts.has(family) && !secureBrowserFonts.has(family)
);
const replaceMaskedFonts = (fontValue) => {
    let result = String(fontValue || '');
    for (const family of secureBrowserKnownFontList) {
        if (secureBrowserFonts.has(family)) continue;
        const escapedFamily = family.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        result = result.replace(new RegExp(`(["'])?${escapedFamily}\\1`, 'g'), 'sans-serif');
    }
    return result;
};
const fontSignal = (families) => {
    const profileFamily = families.find((family) => secureBrowserFonts.has(family));
    if (!profileFamily) return 0;
    let total = 0;
    for (const char of profileFamily) total += char.charCodeAt(0);
    return (total % 9) + 3;
};
const fontMetricHash = (text, family, axis) => {
    let state = secureBrowserFontPlatformSalt + axis;
    for (const char of `${text}|${family}|${axis}`) {
        state = (Math.imul(state ^ char.charCodeAt(0), 16777619)) >>> 0;
    }
    return state;
};
const fontMetricFamilies = (element) => {
    try {
        if (!element || !element.style || !element.style.fontFamily) return [];
        return normalizeFontFamily(element.style.fontFamily);
    } catch (error) {
        return [];
    }
};
const fontMetricSize = (element) => {
    try {
        const inlineSize = String(element.style && element.style.fontSize || '');
        const computedSize = window.getComputedStyle ? getComputedStyle(element).fontSize : '';
        const parsed = parseFloat(inlineSize || computedSize);
        return Number.isFinite(parsed) && parsed > 0 ? parsed : 16;
    } catch (error) {
        return 16;
    }
};
const fontMetricText = (element) => {
    const text = String(element && element.textContent || '');
    return text || 'A';
};
const fallbackFontMetric = (element, axis) => {
    const size = fontMetricSize(element);
    const text = fontMetricText(element);
    if (axis === 'width') {
        return Math.max(1, Math.round(text.length * size * (0.51 + secureBrowserFontPlatformSalt / 1000)));
    }
    return Math.max(1, Math.round(size * (1.08 + secureBrowserFontPlatformSalt / 1000)));
};
const profileFontMetric = (element, family, axis) => {
    const size = fontMetricSize(element);
    const text = fontMetricText(element);
    const signal = fontSignal([family]);
    const hash = fontMetricHash(text, family, axis);
    if (axis === 'width') {
        const ratio = 0.48 + ((hash % 23) / 100) + (signal / 100);
        return Math.max(1, Math.round(text.length * size * ratio));
    }
    const ratio = 1.0 + (((hash >>> 8) % 18) / 100) + (signal / 120);
    return Math.max(1, Math.round(size * ratio));
};
const fontMetricValue = (element, axis, nativeValue) => {
    const families = fontMetricFamilies(element);
    if (!families.length) return nativeValue;
    const profileFamily = families.find((family) => secureBrowserFonts.has(family));
    if (profileFamily) return profileFontMetric(element, profileFamily, axis);
    return fallbackFontMetric(element, axis);
};
const withMaskedFontsReplaced = (element, callback) => {
    const families = familiesFromElement(element);
    if (!hasMaskedSystemFont(families)) return callback();

    const previousInlineFont = element.style.font;
    const previousInlineFamily = element.style.fontFamily;
    try {
        if (previousInlineFont) element.style.font = replaceMaskedFonts(previousInlineFont);
        element.style.fontFamily = replaceMaskedFonts(previousInlineFamily || getComputedStyle(element).fontFamily);
        return callback();
    } finally {
        element.style.font = previousInlineFont;
        element.style.fontFamily = previousInlineFamily;
    }
};
const secureBrowserBuildFontFace = (family) => {
    if (!window.FontFace) return {family, status: 'loaded'};
    try {
        const fontFace = new FontFace(family, `local("${family.replace(/"/g, '\\"')}")`);
        try {
            Object.defineProperty(fontFace, 'status', {get: () => 'loaded', configurable: true});
        } catch (error) {
        }
        return fontFace;
    } catch (error) {
        return {family, status: 'loaded'};
    }
};

const fontFaceSetPrototype = document.fonts && Object.getPrototypeOf(document.fonts);
if (fontFaceSetPrototype && fontFaceSetPrototype.check && !fontFaceSetPrototype.__secureBrowserFontCheckPatched) {
    Object.defineProperty(fontFaceSetPrototype, '__secureBrowserFontCheckPatched', {value: true});
    const originalFontCheck = fontFaceSetPrototype.check;
    fontFaceSetPrototype.check = new Proxy(originalFontCheck, {
        apply(target, thisArg, args) {
            const font = args[0];
            const text = args[1];
            const families = normalizeFontFamily(font);
            if (profileHasFont(families)) return true;
            if (hasMaskedSystemFont(families)) return false;
            return Reflect.apply(target, thisArg, [font, text]);
        }
    });
    if (fontFaceSetPrototype.load) {
        const originalFontLoad = fontFaceSetPrototype.load;
        fontFaceSetPrototype.load = new Proxy(originalFontLoad, {
            apply(target, thisArg, args) {
                const families = normalizeFontFamily(args[0]);
                if (profileHasFont(families)) {
                    return Promise.resolve(families
                        .filter((family) => secureBrowserFonts.has(family))
                        .map(secureBrowserBuildFontFace));
                }
                if (hasMaskedSystemFont(families)) return Promise.resolve([]);
                return Reflect.apply(target, thisArg, args);
            }
        });
    }
    const secureBrowserProfileFontFaces = () => Array.from(secureBrowserFonts).map(secureBrowserBuildFontFace);
    for (const methodName of ['values', Symbol.iterator]) {
        const originalMethod = fontFaceSetPrototype[methodName];
        if (!originalMethod) continue;
        fontFaceSetPrototype[methodName] = new Proxy(originalMethod, {
            apply(target, thisArg, args) {
                return secureBrowserProfileFontFaces()[Symbol.iterator]();
            }
        });
    }
    if (fontFaceSetPrototype.entries) {
        const originalEntries = fontFaceSetPrototype.entries;
        fontFaceSetPrototype.entries = new Proxy(originalEntries, {
            apply(target, thisArg, args) {
                return secureBrowserProfileFontFaces()
                    .map((face) => [face, face])[Symbol.iterator]();
            }
        });
    }
    if (fontFaceSetPrototype.forEach) {
        const originalForEach = fontFaceSetPrototype.forEach;
        fontFaceSetPrototype.forEach = new Proxy(originalForEach, {
            apply(target, thisArg, args) {
                const callback = args[0];
                const thisValue = args[1];
                if (typeof callback !== 'function') return undefined;
                for (const face of secureBrowserProfileFontFaces()) {
                    callback.call(thisValue, face, face, thisArg);
                }
                return undefined;
            }
        });
    }
    const sizeDescriptor = Object.getOwnPropertyDescriptor(fontFaceSetPrototype, 'size');
    if (sizeDescriptor && sizeDescriptor.get) {
        Object.defineProperty(fontFaceSetPrototype, 'size', {
            get() {
                return secureBrowserFonts.size;
            },
            configurable: true
        });
    }
}

Object.defineProperty(window, 'queryLocalFonts', {
    value: async () => Array.from(secureBrowserFonts).map((family) => ({
        family,
        fullName: family,
        postscriptName: family.replace(/\s+/g, '-'),
        style: 'Regular'
    })),
    configurable: true
});

if (window.CanvasRenderingContext2D) {
    const originalMeasureText = CanvasRenderingContext2D.prototype.measureText;
    CanvasRenderingContext2D.prototype.measureText = new Proxy(originalMeasureText, {
        apply(target, thisArg, args) {
            const families = normalizeFontFamily(thisArg.font);
            if (hasMaskedSystemFont(families)) {
                const originalFont = thisArg.font;
                try {
                    thisArg.font = replaceMaskedFonts(originalFont);
                    return Reflect.apply(target, thisArg, args);
                } finally {
                    thisArg.font = originalFont;
                }
            }

            const metrics = Reflect.apply(target, thisArg, args);
            if (!profileHasFont(families)) return metrics;
            const widthOffset = families.join('').length % 7 / 100;
            return new Proxy(metrics, {
                get(metricTarget, property, receiver) {
                    if (property === 'width') return Reflect.get(metricTarget, property, metricTarget) + widthOffset;
                    return Reflect.get(metricTarget, property, metricTarget);
                }
            });
        }
    });
}

const patchFontMetric = (prototype, property, axis) => {
    if (!prototype) return;
    const descriptor = Object.getOwnPropertyDescriptor(prototype, property);
    if (!descriptor || !descriptor.get) return;
    Object.defineProperty(prototype, property, {
        get() {
            return fontMetricValue(this, axis, descriptor.get.call(this));
        },
        configurable: true
    });
};
patchFontMetric(HTMLElement.prototype, 'offsetWidth', 'width');
patchFontMetric(HTMLElement.prototype, 'offsetHeight', 'height');
