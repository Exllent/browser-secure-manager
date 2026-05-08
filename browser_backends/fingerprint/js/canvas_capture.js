const secureBrowserCapturedCanvasConfig = __SECURE_BROWSER_CONFIG__;
const secureBrowserCapturedCanvasDataUrl = secureBrowserCapturedCanvasConfig.dataUrl;
const secureBrowserCapturedCanvasWidth = secureBrowserCapturedCanvasConfig.width;
const secureBrowserCapturedCanvasHeight = secureBrowserCapturedCanvasConfig.height;
const shouldUseCapturedCanvas = (canvas, type) => {
    if (!secureBrowserCapturedCanvasDataUrl) return false;
    if (type && String(type).toLowerCase() !== 'image/png') return false;
    if (secureBrowserCapturedCanvasWidth && canvas.width !== secureBrowserCapturedCanvasWidth) return false;
    if (secureBrowserCapturedCanvasHeight && canvas.height !== secureBrowserCapturedCanvasHeight) return false;
    return true;
};

const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
HTMLCanvasElement.prototype.toDataURL = new Proxy(originalToDataURL, {
    apply(target, thisArg, args) {
        if (shouldUseCapturedCanvas(thisArg, args[0])) return secureBrowserCapturedCanvasDataUrl;
        return Reflect.apply(target, thisArg, args);
    }
});

if (HTMLCanvasElement.prototype.toBlob) {
    const originalToBlob = HTMLCanvasElement.prototype.toBlob;
    HTMLCanvasElement.prototype.toBlob = new Proxy(originalToBlob, {
        apply(target, thisArg, args) {
            const callback = args[0];
            if (typeof callback === 'function' && shouldUseCapturedCanvas(thisArg, args[1])) {
                fetch(secureBrowserCapturedCanvasDataUrl)
                    .then((response) => response.blob())
                    .then((blob) => callback(blob))
                    .catch(() => Reflect.apply(target, thisArg, args));
                return undefined;
            }
            return Reflect.apply(target, thisArg, args);
        }
    });
}
