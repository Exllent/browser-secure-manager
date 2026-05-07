const secureBrowserClientRectsConfig = __SECURE_BROWSER_CONFIG__;

const secureBrowserBuildClientRect = (rect) => {
    const width = Math.max(0, Number(rect.width || 0) + secureBrowserClientRectsConfig.widthDelta);
    const height = Math.max(0, Number(rect.height || 0) + secureBrowserClientRectsConfig.heightDelta);
    const x = Number(rect.x ?? rect.left ?? 0) + secureBrowserClientRectsConfig.xDelta;
    const y = Number(rect.y ?? rect.top ?? 0) + secureBrowserClientRectsConfig.yDelta;
    const data = {
        x,
        y,
        width,
        height,
        top: y,
        left: x,
        right: x + width,
        bottom: y + height
    };
    if (globalThis.DOMRect && DOMRect.fromRect) return DOMRect.fromRect(data);
    return Object.freeze(data);
};

const secureBrowserBuildClientRectList = (rects) => {
    const list = Array.from(rects || [], secureBrowserBuildClientRect);
    try {
        Object.defineProperty(list, 'item', {
            value: (index) => list[index] || null,
            configurable: true
        });
    } catch (error) {
    }
    return list;
};

if (globalThis.Element && Element.prototype.getBoundingClientRect
    && !Element.prototype.__secureBrowserClientBoundingRectPatched) {
    Object.defineProperty(Element.prototype, '__secureBrowserClientBoundingRectPatched', {value: true});
    const originalGetBoundingClientRect = Element.prototype.getBoundingClientRect;
    Element.prototype.getBoundingClientRect = new Proxy(originalGetBoundingClientRect, {
        apply(target, thisArg, args) {
            return secureBrowserBuildClientRect(Reflect.apply(target, thisArg, args));
        }
    });
}

if (globalThis.Element && Element.prototype.getClientRects
    && !Element.prototype.__secureBrowserClientRectsPatched) {
    Object.defineProperty(Element.prototype, '__secureBrowserClientRectsPatched', {value: true});
    const originalGetClientRects = Element.prototype.getClientRects;
    Element.prototype.getClientRects = new Proxy(originalGetClientRects, {
        apply(target, thisArg, args) {
            return secureBrowserBuildClientRectList(Reflect.apply(target, thisArg, args));
        }
    });
}
