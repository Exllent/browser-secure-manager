const secureBrowserPatchWebGPUPrototype = (prototype) => {
    if (!prototype) return;
    try {
        Object.defineProperty(prototype, 'gpu', {
            get: () => undefined,
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
