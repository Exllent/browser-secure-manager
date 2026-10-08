from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from selenium.webdriver.chrome.service import Service

from browser_backends import selenium_backend
from browser_backends.browser_discovery import discover_installed_browsers
from models.browser_config import BrowserConfig
from models.fingerprint_config import FingerprintConfig
from models.session_entry import SessionEntry

_PROBE = """
async function probeUserAgent() {
    const data = navigator.userAgentData;
    let missingArgumentError = null;
    try { await data.getHighEntropyValues(); }
    catch (error) { missingArgumentError = error.name; }
    return {
        nativeType: Object.prototype.toString.call(data),
        nativeInstance: data instanceof NavigatorUAData,
        missingArgumentError,
        userAgent: navigator.userAgent,
        platform: navigator.platform,
        low: data.toJSON(),
        high: await data.getHighEntropyValues([
            'architecture', 'bitness', 'platformVersion', 'fullVersionList', 'formFactors'
        ]),
        navigatorApis: probeNavigatorApis(),
    };
}

function probeNavigatorApis() {
    const prototype = Object.getPrototypeOf(navigator);
    const fields = ['platform', 'language', 'languages', 'hardwareConcurrency', 'deviceMemory', 'userAgent', 'appVersion', 'cookieEnabled', 'doNotTrack', 'pdfViewerEnabled', 'maxTouchPoints', 'globalPrivacyControl'];
    const getters = {};
    for (const field of fields) {
        const descriptor = Object.getOwnPropertyDescriptor(prototype, field);
        if (!descriptor || !descriptor.get) continue;
        let invalidThisError = null;
        try { descriptor.get.call({}); }
        catch (error) { invalidThisError = error.name; }
        getters[field] = {invalidThisError, name: descriptor.get.name};
    }
    let invalidJavaReceiver = 'absent';
    if (navigator.javaEnabled) {
        invalidJavaReceiver = null;
        try { navigator.javaEnabled.call({}); }
        catch (error) { invalidJavaReceiver = error.name; }
    }
    let screenApis = null;
    if (typeof window !== 'undefined') {
        const getter = Object.getOwnPropertyDescriptor(Screen.prototype, 'width').get;
        let invalidScreenReceiver = null;
        try { getter.call({}); } catch (error) { invalidScreenReceiver = error.name; }
        screenApis = {width: screen.width, height: screen.height, invalidScreenReceiver, getterName: getter.name};
    }
    return {
        getters,
        invalidJavaReceiver,
        screenApis,
        languages: navigator.languages,
        frozenLanguages: Object.isFrozen(navigator.languages),
        hardwareConcurrency: navigator.hardwareConcurrency,
        deviceMemory: navigator.deviceMemory,
        hasOscpu: 'oscpu' in navigator,
        webdriver: 'webdriver' in navigator ? navigator.webdriver : 'absent',
        nativePlatformGetter: Function.prototype.toString.call(Object.getOwnPropertyDescriptor(prototype, 'platform').get),
    };
}

function probePluginApis() {
    const plugins = navigator.plugins;
    const mimeTypes = navigator.mimeTypes;
    try {
        const plugin = PluginArray.prototype.item.call(plugins, 0);
        const mimeType = MimeTypeArray.prototype.item.call(mimeTypes, 0);
        return {
            pluginCount: Object.getOwnPropertyDescriptor(PluginArray.prototype, 'length').get.call(plugins),
            mimeTypeCount: Object.getOwnPropertyDescriptor(MimeTypeArray.prototype, 'length').get.call(mimeTypes),
            pluginName: plugin && Object.getOwnPropertyDescriptor(Plugin.prototype, 'name').get.call(plugin),
            mimeType: mimeType && Object.getOwnPropertyDescriptor(MimeType.prototype, 'type').get.call(mimeType),
            pluginItemMatches: plugin === plugins.item(0),
            mimeTypeItemMatches: mimeType === mimeTypes.item(0),
            pluginNamedItemMatches: plugin === PluginArray.prototype.namedItem.call(plugins, plugin.name),
            mimeTypeNamedItemMatches: mimeType === MimeTypeArray.prototype.namedItem.call(mimeTypes, mimeType.type),
        };
    } catch (error) {
        return {error: error.name + ': ' + error.message};
    }
}

async function probePermissionApis() {
    const values = {};
    for (const name of ['notifications', 'geolocation']) {
        const status = await navigator.permissions.query({name});
        let prototypeState;
        try {
            prototypeState = Object.getOwnPropertyDescriptor(PermissionStatus.prototype, 'state').get.call(status);
        } catch (error) { prototypeState = error.name; }
        values[name] = {
            nativeType: Object.prototype.toString.call(status),
            nativeInstance: status instanceof PermissionStatus,
            state: status.state,
            prototypeState,
            eventTarget: status instanceof EventTarget,
            hasOnchange: 'onchange' in status,
        };
    }
    let invalidReceiver;
    try { await navigator.permissions.query.call({}, {name: 'notifications'}); }
    catch (error) { invalidReceiver = error.name; }
    return {values, invalidReceiver};
}
"""


class _ProbeHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path.startswith("/worker.js"):
            content = (_PROBE + "probeUserAgent().then(postMessage);").encode()
            content_type = "application/javascript"
        elif self.path == "/headers":
            content = json.dumps(
                {key.lower(): value for key, value in self.headers.items()}
            ).encode()
            content_type = "application/json"
        else:
            content = (
                b"<!doctype html><title>User-Agent API test</title><body>Local API test</body>"
            )
            content_type = "text/html"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header(
            "Accept-CH",
            "Sec-CH-UA-Full-Version-List, Sec-CH-UA-Platform-Version, Sec-CH-UA-Arch",
        )
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, *_args) -> None:
        pass


@unittest.skipUnless(
    os.environ.get("SECURE_BROWSER_LIVE_API") == "1",
    "set SECURE_BROWSER_LIVE_API=1 to test native APIs in a temporary headless Chromium",
)
class LiveUserAgentApiTest(unittest.TestCase):
    def test_client_hints_preserve_native_api_and_selected_identity(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", 0), _ProbeHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            self._check_browser(f"http://127.0.0.1:{server.server_address[1]}/")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(2)

    def _check_browser(self, url: str) -> None:
        explicit = os.environ.get("SECURE_BROWSER_LIVE_BROWSER")
        browser = (
            BrowserConfig(None, "live", "Live Chromium", "chromium", explicit)
            if explicit
            else discover_installed_browsers()[0]
        )
        config = FingerprintConfig(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
            ),
            platform="Win32",
            client_hints_platform_version="15.0.0",
            client_hints_architecture="x86",
            client_hints_bitness="64",
            spoof_languages=["en-US", "en"],
            hardware_concurrency=3,
            device_memory=0.5,
            screen_width=1366,
            screen_height=768,
            screen_avail_width=1366,
            screen_avail_height=728,
        )
        original_driver = selenium_backend.webdriver.Chrome

        def headless_driver(*, options):
            options.add_argument("--headless=new")
            driver_path = os.environ.get("SECURE_BROWSER_LIVE_DRIVER")
            service = Service(driver_path) if driver_path else Service()
            driver = original_driver(options=options, service=service)
            driver.set_page_load_timeout(10)
            driver.set_script_timeout(10)
            return driver

        with tempfile.TemporaryDirectory(prefix="secure-browser-native-ua-") as directory:
            session = SessionEntry(
                1, "API test", url, browser.key, str(Path(directory) / "profile")
            )
            backend = selenium_backend.SeleniumBrowserBackend()
            try:
                with mock.patch.object(
                    selenium_backend.webdriver, "Chrome", side_effect=headless_driver
                ):
                    backend.open_session(session, browser, None, config)
                driver = backend._drivers[1]
                snapshot = driver.execute_async_script(_PROBE + """
                    const done = arguments[0];
                    (async () => ({
                        page: await probeUserAgent(),
                        plugins: probePluginApis(),
                        permissions: await probePermissionApis(),
                        headers: await fetch('/headers').then(response => response.json()),
                        classic: await workerProbe('classic'),
                        module: await workerProbe('module'),
                        iframe: await frameProbe(),
                    }))().then(done, error => done({error: error.name + ': ' + error.message}));
                    function workerProbe(type) {
                        return new Promise((resolve, reject) => {
                            const worker = new Worker('/worker.js?type=' + type, {type});
                            worker.onmessage = event => { worker.terminate(); resolve(event.data); };
                            worker.onerror = event => { worker.terminate(); reject(new Error(event.message)); };
                        });
                    }
                    function frameProbe() {
                        return new Promise(resolve => {
                            const frame = document.createElement('iframe');
                            frame.onload = async () => {
                                const data = frame.contentWindow.navigator.userAgentData;
                                const result = {
                                    nativeType: Object.prototype.toString.call(data),
                                    low: data.toJSON(),
                                    high: await data.getHighEntropyValues(['fullVersionList']),
                                };
                                frame.remove(); resolve(result);
                            };
                            frame.src = '/frame'; document.body.append(frame);
                        });
                    }
                    """)
                self.assertNotIn("error", snapshot, snapshot)
                permissions = snapshot["permissions"]
                self.assertEqual(permissions["invalidReceiver"], "TypeError")
                for name, status in permissions["values"].items():
                    with self.subTest(permission=name):
                        self.assertEqual(status["nativeType"], "[object PermissionStatus]")
                        self.assertTrue(status["nativeInstance"])
                        self.assertTrue(status["eventTarget"])
                        self.assertTrue(status["hasOnchange"])
                        self.assertIn(status["state"], ("prompt", "denied", "granted"))
                        self.assertEqual(status["state"], status["prototypeState"])
                plugins = snapshot["plugins"]
                self.assertNotIn("error", plugins, plugins)
                self.assertGreater(plugins["pluginCount"], 0)
                self.assertGreater(plugins["mimeTypeCount"], 0)
                self.assertEqual(plugins["pluginName"], "PDF Viewer")
                self.assertEqual(plugins["mimeType"], "application/pdf")
                for field in (
                    "pluginItemMatches",
                    "mimeTypeItemMatches",
                    "pluginNamedItemMatches",
                    "mimeTypeNamedItemMatches",
                ):
                    self.assertTrue(plugins[field], plugins)
                for surface in ("page", "classic", "module", "iframe"):
                    with self.subTest(surface=surface):
                        value = snapshot[surface]
                        self.assertEqual(value["nativeType"], "[object NavigatorUAData]")
                        self.assertEqual(value["low"]["platform"], "Windows")
                        self.assertIn(
                            {"brand": "Chromium", "version": "134.0.0.0"},
                            value["high"]["fullVersionList"],
                        )
                        if surface != "iframe":
                            self.assertTrue(value["nativeInstance"])
                            self.assertEqual(value["missingArgumentError"], "TypeError")
                            self.assertEqual(value["userAgent"], config.user_agent)
                            self.assertEqual(value["platform"], "Win32")
                            self.assertEqual(value["high"]["platformVersion"], "15.0.0")
                            self.assertIn("formFactors", value["high"])
                            navigator_apis = value["navigatorApis"]
                            self.assertEqual(navigator_apis["hardwareConcurrency"], 3)
                            self.assertEqual(navigator_apis["deviceMemory"], 0.5)
                            self.assertEqual(navigator_apis["languages"], ["en-US", "en"])
                            self.assertTrue(navigator_apis["frozenLanguages"])
                            self.assertFalse(navigator_apis["hasOscpu"])
                            self.assertIn("[native code]", navigator_apis["nativePlatformGetter"])
                            expected_webdriver = False if surface == "page" else "absent"
                            self.assertEqual(navigator_apis["webdriver"], expected_webdriver)
                            if surface == "page":
                                self.assertEqual(navigator_apis["invalidJavaReceiver"], "TypeError")
                                screen_apis = navigator_apis["screenApis"]
                                self.assertEqual(screen_apis["width"], 1366)
                                self.assertEqual(screen_apis["height"], 768)
                                self.assertEqual(screen_apis["invalidScreenReceiver"], "TypeError")
                                self.assertEqual(screen_apis["getterName"], "get width")
                            for field, getter in navigator_apis["getters"].items():
                                with self.subTest(surface=surface, getter=field):
                                    self.assertEqual(getter["invalidThisError"], "TypeError")
                                    self.assertEqual(getter["name"], "get " + field)
                self.assertEqual(snapshot["headers"]["user-agent"], config.user_agent)
                self.assertEqual(snapshot["headers"]["sec-ch-ua-platform"], '"Windows"')
                self.assertEqual(snapshot["headers"]["sec-ch-ua-platform-version"], '"15.0.0"')
            finally:
                backend.close_all()
