(() => {
    const secureBrowserNavigatorValues = __SECURE_BROWSER_CONFIG__;
    const navigatorObject = globalThis.navigator;
    if (!navigatorObject) return;
    const prototype = Object.getPrototypeOf(navigatorObject);
    const sameValue = (actual, expected) => (
        Array.isArray(expected)
            ? Array.isArray(actual) && actual.length === expected.length
                && expected.every((value, index) => actual[index] === value)
            : actual === expected
    );
    for (const [property, configuredValue] of Object.entries(secureBrowserNavigatorValues)) {
        const descriptor = Object.getOwnPropertyDescriptor(prototype, property);
        // Do not introduce APIs absent in this browser or security context.
        if (!descriptor || typeof descriptor.get !== 'function') continue;
        try {
            const actual = Reflect.apply(descriptor.get, navigatorObject, []);
            // CDP and Chromium preferences already supply many configured values.
            if (sameValue(actual, configuredValue)) continue;
            const value = Array.isArray(configuredValue)
                ? Object.freeze([...configuredValue]) : configuredValue;
            Object.defineProperty(prototype, property, {
                ...descriptor,
                get: new Proxy(descriptor.get, {
                    apply(target, receiver, args) {
                        // Preserve native receiver validation and getter metadata.
                        Reflect.apply(target, receiver, args);
                        return value;
                    }
                })
            });
        } catch (error) {
            // An unavailable or non-configurable property keeps its native API.
        }
    }
})();
