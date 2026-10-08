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
    };
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
                self.assertEqual(snapshot["headers"]["user-agent"], config.user_agent)
                self.assertEqual(snapshot["headers"]["sec-ch-ua-platform"], '"Windows"')
                self.assertEqual(snapshot["headers"]["sec-ch-ua-platform-version"], '"15.0.0"')
            finally:
                backend.close_all()
