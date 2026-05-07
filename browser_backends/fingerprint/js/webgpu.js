const secureBrowserWebGPUConfig = __SECURE_BROWSER_CONFIG__;

const secureBrowserFreezeWithTag = (value, tag) => {
    try {
        Object.defineProperty(value, Symbol.toStringTag, {
            value: tag,
            configurable: true
        });
    } catch (error) {
    }
    return Object.freeze(value);
};

const secureBrowserBuildSupportedSet = (values, tag) => {
    const items = Object.freeze(Array.from(new Set(values)));
    const supportedSet = {
        get size() {
            return items.length;
        },
        has: (value) => items.includes(value),
        keys: () => items[Symbol.iterator](),
        values: () => items[Symbol.iterator](),
        entries: () => items.map((value) => [value, value])[Symbol.iterator](),
        forEach(callback, thisArg) {
            if (typeof callback !== 'function') return;
            for (const value of items) callback.call(thisArg, value, value, supportedSet);
        },
        [Symbol.iterator]: () => items[Symbol.iterator]()
    };
    try {
        Object.defineProperty(supportedSet, Symbol.toStringTag, {
            value: tag,
            configurable: true
        });
    } catch (error) {
    }
    return Object.freeze(supportedSet);
};

const secureBrowserCloneWebGPUInfo = () => Object.freeze({
    vendor: secureBrowserWebGPUConfig.adapterInfo.vendor,
    architecture: secureBrowserWebGPUConfig.adapterInfo.architecture,
    device: secureBrowserWebGPUConfig.adapterInfo.device,
    description: secureBrowserWebGPUConfig.adapterInfo.description
});

const secureBrowserCloneWebGPULimits = () => secureBrowserFreezeWithTag(
    {...secureBrowserWebGPUConfig.limits},
    'GPUSupportedLimits'
);

const secureBrowserBuildGPUResource = (tag, methods = {}) => secureBrowserFreezeWithTag({
    label: '',
    destroy: () => undefined,
    ...methods
}, tag);

const secureBrowserBuildGPUQueue = () => secureBrowserFreezeWithTag({
    label: '',
    submit: () => undefined,
    onSubmittedWorkDone: async () => undefined,
    writeBuffer: () => undefined,
    writeTexture: () => undefined,
    copyExternalImageToTexture: () => undefined
}, 'GPUQueue');

const secureBrowserBuildGPUDevice = (adapter) => secureBrowserFreezeWithTag({
    label: '',
    features: secureBrowserBuildSupportedSet(Array.from(adapter.features), 'GPUSupportedFeatures'),
    limits: secureBrowserCloneWebGPULimits(),
    queue: secureBrowserBuildGPUQueue(),
    lost: new Promise(() => undefined),
    pushErrorScope: () => undefined,
    popErrorScope: async () => null,
    destroy: () => undefined,
    createBuffer: () => secureBrowserBuildGPUResource('GPUBuffer', {
        mapAsync: async () => undefined,
        getMappedRange: () => new ArrayBuffer(0),
        unmap: () => undefined
    }),
    createTexture: () => secureBrowserBuildGPUResource('GPUTexture', {
        createView: () => secureBrowserBuildGPUResource('GPUTextureView')
    }),
    createSampler: () => secureBrowserBuildGPUResource('GPUSampler'),
    createBindGroupLayout: () => secureBrowserBuildGPUResource('GPUBindGroupLayout'),
    createPipelineLayout: () => secureBrowserBuildGPUResource('GPUPipelineLayout'),
    createBindGroup: () => secureBrowserBuildGPUResource('GPUBindGroup'),
    createShaderModule: () => secureBrowserBuildGPUResource('GPUShaderModule', {
        getCompilationInfo: async () => ({messages: []})
    }),
    createComputePipeline: () => secureBrowserBuildGPUResource('GPUComputePipeline'),
    createRenderPipeline: () => secureBrowserBuildGPUResource('GPURenderPipeline'),
    createComputePipelineAsync: async () => secureBrowserBuildGPUResource('GPUComputePipeline'),
    createRenderPipelineAsync: async () => secureBrowserBuildGPUResource('GPURenderPipeline'),
    createCommandEncoder: () => secureBrowserBuildGPUResource('GPUCommandEncoder', {
        beginRenderPass: () => secureBrowserBuildGPUResource('GPURenderPassEncoder', {
            end: () => undefined
        }),
        beginComputePass: () => secureBrowserBuildGPUResource('GPUComputePassEncoder', {
            end: () => undefined
        }),
        copyBufferToBuffer: () => undefined,
        copyBufferToTexture: () => undefined,
        copyTextureToBuffer: () => undefined,
        copyTextureToTexture: () => undefined,
        finish: () => secureBrowserBuildGPUResource('GPUCommandBuffer')
    }),
    createRenderBundleEncoder: () => secureBrowserBuildGPUResource('GPURenderBundleEncoder', {
        finish: () => secureBrowserBuildGPUResource('GPURenderBundle')
    }),
    createQuerySet: () => secureBrowserBuildGPUResource('GPUQuerySet')
}, 'GPUDevice');

const secureBrowserValidateRequiredFeatures = (features) => {
    const supportedFeatures = new Set(secureBrowserWebGPUConfig.features);
    for (const feature of Array.from(features || [])) {
        if (!supportedFeatures.has(feature)) {
            throw new DOMException(`Unsupported WebGPU feature: ${feature}`, 'NotSupportedError');
        }
    }
};

const secureBrowserBuildGPUAdapter = () => {
    const features = secureBrowserBuildSupportedSet(
        secureBrowserWebGPUConfig.features,
        'GPUSupportedFeatures'
    );
    const adapter = secureBrowserFreezeWithTag({
        name: secureBrowserWebGPUConfig.adapterName,
        info: secureBrowserCloneWebGPUInfo(),
        features,
        limits: secureBrowserCloneWebGPULimits(),
        isFallbackAdapter: false,
        requestAdapterInfo: async () => secureBrowserCloneWebGPUInfo(),
        requestDevice: async (descriptor = {}) => {
            secureBrowserValidateRequiredFeatures(descriptor.requiredFeatures);
            return secureBrowserBuildGPUDevice(adapter);
        }
    }, 'GPUAdapter');
    return adapter;
};

const secureBrowserGPUAdapter = secureBrowserBuildGPUAdapter();
const secureBrowserGPU = secureBrowserFreezeWithTag({
    requestAdapter: async () => secureBrowserGPUAdapter,
    getPreferredCanvasFormat: () => secureBrowserWebGPUConfig.canvasFormat,
    wgslLanguageFeatures: secureBrowserBuildSupportedSet([], 'WGSLLanguageFeatures')
}, 'GPU');

const secureBrowserPatchWebGPUPrototype = (prototype) => {
    if (!prototype) return;
    try {
        Object.defineProperty(prototype, 'gpu', {
            get: () => secureBrowserGPU,
            configurable: true
        });
    } catch (error) {
    }
};

secureBrowserPatchWebGPUPrototype(globalThis.Navigator && Navigator.prototype);
secureBrowserPatchWebGPUPrototype(globalThis.WorkerNavigator && WorkerNavigator.prototype);
if (globalThis.navigator) {
    secureBrowserPatchWebGPUPrototype(Object.getPrototypeOf(globalThis.navigator));
}
