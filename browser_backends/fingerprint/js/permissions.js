(() => {
    if (!navigator.permissions || !navigator.permissions.query
        || typeof PermissionStatus === 'undefined') return;
    const secureBrowserPermissionStates = new Map(Object.entries(__SECURE_BROWSER_CONFIG__));
    const configuredStates = new WeakMap();
    const prototype = Object.getPrototypeOf(navigator.permissions);
    const queryDescriptor = Object.getOwnPropertyDescriptor(prototype, 'query');
    const stateDescriptor = Object.getOwnPropertyDescriptor(PermissionStatus.prototype, 'state');
    if (!queryDescriptor || typeof queryDescriptor.value !== 'function'
        || !stateDescriptor || typeof stateDescriptor.get !== 'function') return;
    let stateGetterPatched = false;
    Object.defineProperty(prototype, 'query', {
        ...queryDescriptor,
        value: new Proxy(queryDescriptor.value, {
            apply(target, receiver, args) {
                // Retain native argument validation and the real PermissionStatus.
                return Reflect.apply(target, receiver, args).then((status) => {
                    const parameters = args[0];
                    let wanted = parameters && secureBrowserPermissionStates.get(parameters.name);
                    if (parameters && parameters.name === 'notifications'
                        && typeof Notification !== 'undefined') {
                        wanted = Notification.permission === 'default'
                            ? 'prompt' : Notification.permission;
                    }
                    if (!wanted || status.state === wanted) return status;
                    configuredStates.set(status, wanted);
                    if (!stateGetterPatched) {
                        Object.defineProperty(PermissionStatus.prototype, 'state', {
                            ...stateDescriptor,
                            get: new Proxy(stateDescriptor.get, {
                                apply(getter, statusReceiver, getterArgs) {
                                    const nativeValue = Reflect.apply(getter, statusReceiver, getterArgs);
                                    return configuredStates.get(statusReceiver) || nativeValue;
                                }
                            })
                        });
                        stateGetterPatched = true;
                    }
                    return status;
                });
            }
        })
    });
})();
