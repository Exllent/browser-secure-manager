const secureBrowserWorkerFingerprintScript = __SECURE_BROWSER_WORKER_SCRIPT__;
const secureBrowserWrapWorkerUrl = (workerUrl, workerOptions) => {
    try {
        const originalUrl = new URL(String(workerUrl), location.href).href;
        const options = workerOptions && typeof workerOptions === 'object' ? workerOptions : {};
        const isModule = String(options.type || '').toLowerCase() === 'module';
        const wrapperSource = isModule
            ? secureBrowserWorkerFingerprintScript + '\nimport ' + JSON.stringify(originalUrl) + ';'
            : secureBrowserWorkerFingerprintScript + '\nimportScripts(' + JSON.stringify(originalUrl) + ');';
        return URL.createObjectURL(new Blob([wrapperSource], { type: 'application/javascript' }));
    } catch (error) {
        return workerUrl;
    }
};
const secureBrowserPatchWorkerConstructor = (globalName) => {
    const OriginalWorkerConstructor = window[globalName];
    if (!OriginalWorkerConstructor || OriginalWorkerConstructor.__secureBrowserWorkerPatched) return;
    const PatchedWorkerConstructor = new Proxy(OriginalWorkerConstructor, {
        construct(target, args, newTarget) {
            const originalArgs = Array.from(args);
            const workerUrl = originalArgs[0];
            if (typeof workerUrl === 'string' || workerUrl instanceof URL) {
                originalArgs[0] = secureBrowserWrapWorkerUrl(workerUrl, originalArgs[1]);
                try {
                    return Reflect.construct(target, originalArgs, newTarget);
                } catch (error) {
                    return Reflect.construct(target, args, newTarget);
                }
            }
            return Reflect.construct(target, args, newTarget);
        }
    });
    Object.defineProperty(PatchedWorkerConstructor, '__secureBrowserWorkerPatched', { value: true });
    Object.defineProperty(window, globalName, {
        value: PatchedWorkerConstructor,
        configurable: true,
        writable: true
    });
};
secureBrowserPatchWorkerConstructor('Worker');
secureBrowserPatchWorkerConstructor('SharedWorker');
