const secureBrowserAdBlockBaitPattern = /(^|[-_\s])(ad|ads|advert|banner|sponsor|sponsored|doubleclick)([-_\s]|$)/i;
const secureBrowserIsAdBlockBait = (element) => {
    try {
        if (!element || element.nodeType !== 1) return false;
        const id = element.id || '';
        const className = typeof element.className === 'string' ? element.className : '';
        return secureBrowserAdBlockBaitPattern.test(id) || secureBrowserAdBlockBaitPattern.test(className);
    } catch (error) {
        return false;
    }
};

const originalSecureBrowserGetComputedStyle = window.getComputedStyle && window.getComputedStyle.bind(window);
if (originalSecureBrowserGetComputedStyle && !window.__secureBrowserAdBlockStylePatched) {
    Object.defineProperty(window, '__secureBrowserAdBlockStylePatched', {value: true});
    window.getComputedStyle = (element, pseudoElement) => {
        const style = originalSecureBrowserGetComputedStyle(element, pseudoElement);
        if (!secureBrowserIsAdBlockBait(element)) return style;
        return new Proxy(style, {
            get(target, property, receiver) {
                if (property === 'display') return 'block';
                if (property === 'visibility') return 'visible';
                if (property === 'opacity') return '1';
                if (property === 'height' || property === 'minHeight') return '1px';
                if (property === 'width' || property === 'minWidth') return '1px';
                if (property === 'getPropertyValue') {
                    return (name) => {
                        const normalized = String(name || '').toLowerCase();
                        if (normalized === 'display') return 'block';
                        if (normalized === 'visibility') return 'visible';
                        if (normalized === 'opacity') return '1';
                        if (normalized === 'height' || normalized === 'min-height') return '1px';
                        if (normalized === 'width' || normalized === 'min-width') return '1px';
                        return target.getPropertyValue(name);
                    };
                }
                return Reflect.get(target, property, receiver);
            }
        });
    };
}

const patchAdBlockMetric = (prototype, property) => {
    if (!prototype) return;
    const descriptor = Object.getOwnPropertyDescriptor(prototype, property);
    if (!descriptor || !descriptor.get) return;
    Object.defineProperty(prototype, property, {
        get() {
            if (secureBrowserIsAdBlockBait(this)) return Math.max(1, descriptor.get.call(this) || 1);
            return descriptor.get.call(this);
        },
        configurable: true
    });
};
patchAdBlockMetric(HTMLElement.prototype, 'offsetHeight');
patchAdBlockMetric(HTMLElement.prototype, 'offsetWidth');
