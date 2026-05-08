from __future__ import annotations

import json

from models.fingerprint_config import FingerprintConfig


def _build_navigator_patches(config: FingerprintConfig) -> list[str]:
    patches: list[str] = []

    if config.hide_automation:
        patches.append("""
            Object.defineProperty(Navigator.prototype, 'webdriver', {
                get: () => undefined,
                configurable: true
            });
            """)

    if config.platform:
        patches.append(f"""
            Object.defineProperty(Navigator.prototype, 'platform', {{
                get: () => {json.dumps(config.platform)},
                configurable: true
            }});
            """)

    languages = config.spoof_languages or config.locale
    if languages:
        patches.append(f"""
            Object.defineProperty(Navigator.prototype, 'languages', {{
                get: () => {json.dumps(languages)},
                configurable: true
            }});
            Object.defineProperty(Navigator.prototype, 'language', {{
                get: () => {json.dumps(languages[0])},
                configurable: true
            }});
            """)

    if config.hardware_concurrency is not None:
        patches.append(f"""
            Object.defineProperty(Navigator.prototype, 'hardwareConcurrency', {{
                get: () => {config.hardware_concurrency},
                configurable: true
            }});
            """)

    if config.device_memory is not None:
        patches.append(f"""
            Object.defineProperty(Navigator.prototype, 'deviceMemory', {{
                get: () => {config.device_memory},
                configurable: true
            }});
            """)

    if config.spoof_plugins:
        patches.append("""
            const secureBrowserDefineReadonly = (target, key, value) => {
                Object.defineProperty(target, key, {
                    value,
                    enumerable: false,
                    configurable: true
                });
            };

            const secureBrowserMakeMimeType = (type, suffixes, description, plugin) => {
                const mimeType = typeof MimeType !== 'undefined' && MimeType.prototype
                    ? Object.create(MimeType.prototype)
                    : {};
                secureBrowserDefineReadonly(mimeType, 'type', type);
                secureBrowserDefineReadonly(mimeType, 'suffixes', suffixes);
                secureBrowserDefineReadonly(mimeType, 'description', description);
                secureBrowserDefineReadonly(mimeType, 'enabledPlugin', plugin);
                return mimeType;
            };

            const secureBrowserMakePlugin = (definition) => {
                const plugin = typeof Plugin !== 'undefined' && Plugin.prototype
                    ? Object.create(Plugin.prototype)
                    : {};
                const mimeTypes = definition.mimeTypes.map((mimeTypeDefinition) => (
                    secureBrowserMakeMimeType(
                        mimeTypeDefinition.type,
                        mimeTypeDefinition.suffixes,
                        mimeTypeDefinition.description,
                        plugin
                    )
                ));

                secureBrowserDefineReadonly(plugin, 'name', definition.name);
                secureBrowserDefineReadonly(plugin, 'filename', definition.filename);
                secureBrowserDefineReadonly(plugin, 'description', definition.description);
                secureBrowserDefineReadonly(plugin, 'length', mimeTypes.length);
                secureBrowserDefineReadonly(plugin, 'item', (index) => mimeTypes[index] || null);
                secureBrowserDefineReadonly(plugin, 'namedItem', (name) => (
                    mimeTypes.find((mimeType) => mimeType.type === name) || null
                ));

                mimeTypes.forEach((mimeType, index) => {
                    secureBrowserDefineReadonly(plugin, index, mimeType);
                    secureBrowserDefineReadonly(plugin, mimeType.type, mimeType);
                });

                return plugin;
            };

            const secureBrowserPluginDefinitions = [
                {
                    name: 'PDF Viewer',
                    filename: 'internal-pdf-viewer',
                    description: 'Portable Document Format',
                    mimeTypes: [
                        {
                            type: 'application/pdf',
                            suffixes: 'pdf',
                            description: 'Portable Document Format'
                        },
                        {
                            type: 'text/pdf',
                            suffixes: 'pdf',
                            description: 'Portable Document Format'
                        }
                    ]
                },
                {
                    name: 'Chrome PDF Viewer',
                    filename: 'internal-pdf-viewer',
                    description: 'Portable Document Format',
                    mimeTypes: []
                },
                {
                    name: 'Chromium PDF Viewer',
                    filename: 'internal-pdf-viewer',
                    description: 'Portable Document Format',
                    mimeTypes: []
                },
                {
                    name: 'Microsoft Edge PDF Viewer',
                    filename: 'internal-pdf-viewer',
                    description: 'Portable Document Format',
                    mimeTypes: []
                },
                {
                    name: 'WebKit built-in PDF',
                    filename: 'internal-pdf-viewer',
                    description: 'Portable Document Format',
                    mimeTypes: []
                }
            ];

            const secureBrowserPlugins = secureBrowserPluginDefinitions.map(
                secureBrowserMakePlugin
            );
            const secureBrowserMimeTypes = secureBrowserPlugins.flatMap((plugin) => {
                const values = [];
                for (let index = 0; index < plugin.length; index += 1) {
                    values.push(plugin.item(index));
                }
                return values;
            });

            const secureBrowserPluginArray = typeof PluginArray !== 'undefined'
                && PluginArray.prototype
                ? Object.create(PluginArray.prototype)
                : [];
            const secureBrowserMimeTypeArray = typeof MimeTypeArray !== 'undefined'
                && MimeTypeArray.prototype
                ? Object.create(MimeTypeArray.prototype)
                : [];

            secureBrowserDefineReadonly(
                secureBrowserPluginArray,
                'length',
                secureBrowserPlugins.length
            );
            secureBrowserDefineReadonly(
                secureBrowserPluginArray,
                'item',
                (index) => secureBrowserPlugins[index] || null
            );
            secureBrowserDefineReadonly(
                secureBrowserPluginArray,
                'namedItem',
                (name) => secureBrowserPlugins.find((plugin) => plugin.name === name) || null
            );
            secureBrowserDefineReadonly(secureBrowserPluginArray, 'refresh', () => undefined);
            secureBrowserPlugins.forEach((plugin, index) => {
                secureBrowserDefineReadonly(secureBrowserPluginArray, index, plugin);
                secureBrowserDefineReadonly(secureBrowserPluginArray, plugin.name, plugin);
            });

            secureBrowserDefineReadonly(
                secureBrowserMimeTypeArray,
                'length',
                secureBrowserMimeTypes.length
            );
            secureBrowserDefineReadonly(
                secureBrowserMimeTypeArray,
                'item',
                (index) => secureBrowserMimeTypes[index] || null
            );
            secureBrowserDefineReadonly(
                secureBrowserMimeTypeArray,
                'namedItem',
                (name) => (
                    secureBrowserMimeTypes.find((mimeType) => mimeType.type === name) || null
                )
            );
            secureBrowserMimeTypes.forEach((mimeType, index) => {
                secureBrowserDefineReadonly(secureBrowserMimeTypeArray, index, mimeType);
                secureBrowserDefineReadonly(secureBrowserMimeTypeArray, mimeType.type, mimeType);
            });

            Object.defineProperty(Navigator.prototype, 'plugins', {
                get: () => secureBrowserPluginArray,
                configurable: true
            });
            Object.defineProperty(Navigator.prototype, 'mimeTypes', {
                get: () => secureBrowserMimeTypeArray,
                configurable: true
            });
            """)

    return patches
