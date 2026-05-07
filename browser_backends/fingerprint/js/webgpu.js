const secureBrowserWebGPUConfig = __SECURE_BROWSER_CONFIG__;
const secureBrowserWebGPUAdapterInfo = Object.freeze({
    vendor: secureBrowserWebGPUConfig.vendor,
    architecture: '',
    device: '',
    description: secureBrowserWebGPUConfig.renderer
});

const secureBrowserBuildGPUAdapter = () => Object.freeze({
    name: secureBrowserWebGPUAdapterInfo.description,
    info: secureBrowserWebGPUAdapterInfo,
    isFallbackAdapter: false,
    features: Object.freeze(new Set()),
    limits: Object.freeze({}),
    requestDevice: async () => Promise.reject(
        new DOMException('WebGPU is unavailable for this fingerprint profile', 'NotSupportedError')
    )
});

const secureBrowserGPU = Object.freeze({
    requestAdapter: async () => secureBrowserBuildGPUAdapter(),
    getPreferredCanvasFormat: () => 'bgra8unorm',
    wgslLanguageFeatures: Object.freeze(new Set())
});

try {
    Object.defineProperty(Navigator.prototype, 'gpu', {
        get: () => secureBrowserGPU,
        configurable: true
    });
} catch (error) {
}
