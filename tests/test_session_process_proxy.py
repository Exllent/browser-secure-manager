from __future__ import annotations

import logging
import queue
import unittest
from dataclasses import replace
from unittest import mock

from app import session_process
from app_config import APP_CONFIG
from models.browser_config import BrowserConfig
from models.proxy_config import ProxyConfig
from models.session_entry import SessionEntry
from services.proxy_tester import ProxyTestResult


class SessionProcessProxyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.session = SessionEntry(
            id=149, name="Test", browser="chrome", url="about:blank", profile_path="unused-profile"
        )
        self.browser = BrowserConfig(None, "chrome", "Chrome", "chromium")
        self.proxy = ProxyConfig(118, "Test proxy", "proxy.invalid", 1080, "socks5", "u", "p")
        self.events = queue.Queue()
        self.backend = mock.Mock()
        self.bridge = mock.Mock()
        self.local = replace(
            self.proxy, id=None, host="127.0.0.1", port=43210, username="", password=""
        )
        self.bridge.start.return_value = self.local
        self.bridge.is_running.return_value = True
        patches = (
            mock.patch.object(session_process, "_configure_child_logging"),
            mock.patch.object(session_process, "SeleniumBrowserBackend", return_value=self.backend),
            mock.patch.object(session_process, "Socks5Bridge", return_value=self.bridge),
            mock.patch.object(
                session_process, "test_proxy", return_value=ProxyTestResult(True, 1, "ok")
            ),
            mock.patch.object(session_process, "_process_session_loop"),
        )
        self.logging_patch, self.backend_class, self.bridge_class, self.test_proxy, self.loop = (
            self.enterContext(patch) for patch in patches
        )

    def run_session(self, proxy: ProxyConfig | None) -> None:
        session_process._run_browser_session_process(
            self.session, self.browser, proxy, None, queue.Queue(), self.events, "unused.log"
        )

    def test_authenticated_socks5_uses_local_config_and_cleans_up(self) -> None:
        original = replace(self.proxy)
        self.run_session(self.proxy)
        self.test_proxy.assert_called_once_with(self.proxy)
        self.bridge_class.assert_called_once_with(self.proxy)
        self.backend.open_session.assert_called_once_with(
            self.session, self.browser, self.local, None
        )
        self.assertEqual(self.proxy, original)
        self.assertIs(self.loop.call_args.args[-1], self.bridge)
        self.backend.close_all.assert_called_once()
        self.bridge.close.assert_called_once()
        self.assertEqual(self.events.get_nowait()["type"], "started")

    def test_existing_proxy_paths_bypass_bridge(self) -> None:
        for proxy in (
            None,
            replace(self.proxy, username="", password=""),
            replace(self.proxy, proxy_type="http"),
            replace(self.proxy, proxy_type="socks4"),
        ):
            with self.subTest(proxy_type=proxy.proxy_type if proxy else None):
                self.backend.reset_mock()
                self.run_session(proxy)
                self.backend.open_session.assert_called_once_with(
                    self.session, self.browser, proxy, None
                )
        self.bridge_class.assert_not_called()

    def test_proxy_validation_failure_does_not_launch_bridge_or_browser(self) -> None:
        self.test_proxy.return_value = ProxyTestResult(False, None, "refused")
        with self.assertLogs("app.session_process", level="ERROR"):
            self.run_session(self.proxy)
        self.bridge_class.assert_not_called()
        self.backend.open_session.assert_not_called()
        self.assertEqual(self.events.get_nowait()["type"], "failed")

    def test_startup_failures_close_bridge(self) -> None:
        for component in (self.bridge.start, self.backend.open_session):
            with self.subTest(component=component):
                self.bridge.close.reset_mock()
                component.side_effect = RuntimeError("startup failed")
                with self.assertLogs("app.session_process", level="ERROR"):
                    self.run_session(self.proxy)
                self.bridge.close.assert_called_once()
                self.assertEqual(self.events.get_nowait()["type"], "failed")
                component.side_effect = None

    def test_browser_cleanup_exception_still_closes_bridge(self) -> None:
        self.backend.close_all.side_effect = RuntimeError("cleanup failed")
        with self.assertRaisesRegex(RuntimeError, "cleanup failed"):
            self.run_session(self.proxy)
        self.bridge.close.assert_called_once()

    def test_listener_failure_reports_session_error(self) -> None:
        self.bridge.is_running.return_value = False
        with mock.patch.object(session_process, "_process_session_loop", self.loop_original):
            with self.assertLogs("app.session_process", level="ERROR"):
                self.run_session(self.proxy)
        self.assertEqual(self.events.get_nowait()["type"], "started")
        self.assertEqual(self.events.get_nowait()["type"], "failed")
        self.bridge.close.assert_called_once()

    loop_original = staticmethod(session_process._process_session_loop)

    def test_stop_command_keeps_existing_browser_stop_path(self) -> None:
        commands = queue.Queue()
        commands.put({"type": APP_CONFIG.session_process.stop_command})
        self.loop_original(149, self.backend, commands, logging.getLogger(__name__), self.bridge)
        self.backend.close_session.assert_called_once_with(149)
