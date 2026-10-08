from __future__ import annotations

import multiprocessing
import queue
import socket
import socketserver
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from unittest import mock

from app_config import APP_CONFIG
from models.proxy_config import ProxyConfig
from services import proxy_tester
from services.socks5_bridge import Socks5Bridge
from services.socks5_transport import encode_address, open_socks5_tunnel, read_address, recv_exact


class FakeSocks5Server(socketserver.ThreadingTCPServer):
    daemon_threads = True
    block_on_close = False

    def __init__(
        self, *, mode: str = "auth", marker: bytes = b"", username: str = "u", password: str = "p"
    ) -> None:
        super().__init__(("127.0.0.1", 0), FakeSocks5Handler)
        self.mode = mode
        self.marker = marker
        self.username = username
        self.password = password
        self.greeted = threading.Event()
        self.records: queue.Queue = queue.Queue()
        self.connections: set[socket.socket] = set()
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self.serve_forever, kwargs={"poll_interval": 0.02})
        self.thread.start()

    def proxy(self) -> ProxyConfig:
        return ProxyConfig(
            None,
            "Test proxy",
            "127.0.0.1",
            self.server_address[1],
            "socks5",
            self.username,
            self.password,
        )

    def close(self) -> None:
        self.shutdown()
        self.server_close()
        with self.lock:
            for sock in self.connections:
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
        self.thread.join(2)


class FakeSocks5Handler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        server = self.server
        sock = self.request
        with server.lock:
            server.connections.add(sock)
        try:
            sock.settimeout(3)
            version, count = recv_exact(sock, 2)
            methods = recv_exact(sock, count)
            if version != 5:
                return
            server.greeted.set()
            if server.mode == "timeout":
                sock.recv(1)
                return
            if server.mode == "malformed":
                sock.sendall(bytes([4, 0]))
                return
            method = 0 if server.mode == "noauth" else 2
            if method not in methods:
                sock.sendall(bytes([5, 255]))
                return
            # Split packets deliberately to exercise exact reads.
            sock.sendall(bytes([5]))
            sock.sendall(bytes([method]))
            credentials = None
            if method == 2:
                _, length = recv_exact(sock, 2)
                username = recv_exact(sock, length)
                length = recv_exact(sock, 1)[0]
                password = recv_exact(sock, length)
                credentials = (username, password)
                if credentials != (server.username.encode(), server.password.encode()):
                    sock.sendall(bytes([1, 1]))
                    return
                sock.sendall(bytes([1, 0]))
            version, command, reserved, atyp = recv_exact(sock, 4)
            address = read_address(sock, atyp, deadline=time.monotonic() + 3)
            port = int.from_bytes(recv_exact(sock, 2), "big")
            server.records.put((credentials, atyp, address, port, command))
            if server.mode == "refused":
                sock.sendall(bytes([5, 2, 0, 1, 0, 0, 0, 0, 0, 0]))
                return
            sock.sendall(bytes([5, 0, 0, 1, 127, 0, 0, 1, 0, 1]))
            if server.marker:
                sock.sendall(server.marker)
            while True:
                data = sock.recv(65536)
                if not data:
                    sock.sendall(b"done")
                    return
                sock.sendall(data)
        except (OSError, ValueError):
            pass
        finally:
            with server.lock:
                server.connections.discard(sock)


def _start_bridge_process(upstream: ProxyConfig, result: object, stop: object) -> None:
    bridge = Socks5Bridge(upstream)
    try:
        result.put(bridge.start())
        stop.wait()
    finally:
        bridge.close()


class Socks5BridgeTest(unittest.TestCase):
    def server(self, **kwargs) -> FakeSocks5Server:
        server = FakeSocks5Server(**kwargs)
        self.addCleanup(server.close)
        return server

    def bridge(self, proxy: ProxyConfig, **settings) -> tuple[Socks5Bridge, ProxyConfig]:
        bridge = Socks5Bridge(proxy)
        bridge._config = replace(APP_CONFIG.socks5_bridge, **settings)
        self.addCleanup(bridge.close)
        return bridge, bridge.start()

    def tunnel(self, proxy: ProxyConfig, target: str = "example.invalid") -> socket.socket:
        return open_socks5_tunnel(proxy, target_host=target, target_port=443, timeout=3)

    def test_transport_auth_and_noauth_and_proxy_tester(self) -> None:
        for mode in ("auth", "noauth"):
            with self.subTest(mode=mode):
                server = self.server(mode=mode)
                proxy = server.proxy()
                if mode == "noauth":
                    proxy = replace(proxy, username="", password="")
                with mock.patch.object(proxy_tester, "_verify_tls") as verify:
                    result = proxy_tester.test_proxy(proxy)
                self.assertTrue(result.ok, result.message)
                verify.assert_called_once()
                record = server.records.get(timeout=2)
                self.assertEqual(record[0], (b"u", b"p") if mode == "auth" else None)
                self.assertEqual(record[1:4], (3, b"\x10browserleaks.com", 443))

    def test_other_proxy_test_paths_are_preserved(self) -> None:
        for kind, helper in (("http", "_open_http_tunnel"), ("socks4", "_open_socks4_tunnel")):
            with self.subTest(kind=kind):
                with (
                    mock.patch.object(proxy_tester, helper) as tunnel,
                    mock.patch.object(proxy_tester, "_verify_tls"),
                    mock.patch.object(proxy_tester, "_open_socks5_tunnel") as socks5,
                ):
                    result = proxy_tester.test_proxy(ProxyConfig(None, "", "localhost", 1, kind))
                self.assertTrue(result.ok)
                tunnel.assert_called_once()
                socks5.assert_not_called()

    def test_targets_are_forwarded_without_local_dns(self) -> None:
        server = self.server()
        proxy = server.proxy()
        original = replace(proxy)
        bridge, local = self.bridge(proxy)
        self.assertEqual(proxy, original)
        self.assertEqual((local.host, local.username, local.password), ("127.0.0.1", "", ""))
        self.assertIsNone(local.id)
        self.assertTrue(bridge.is_running())
        for target in ("does-not-exist.invalid", "192.0.2.7", "2001:db8::7"):
            with self.subTest(target=target):
                with mock.patch("socket.getaddrinfo", wraps=socket.getaddrinfo) as resolve:
                    with self.tunnel(local, target) as sock:
                        sock.sendall(b"payload")
                        self.assertEqual(recv_exact(sock, 7), b"payload")
                self.assertTrue(all(call.args[0] == "127.0.0.1" for call in resolve.call_args_list))
                record = server.records.get(timeout=2)
                self.assertEqual(record, ((b"u", b"p"), *encode_address(target), 443, 1))

    def test_large_payload_and_half_close(self) -> None:
        _, local = self.bridge(self.server().proxy(), buffer_bytes=1024)
        with self.tunnel(local) as sock:
            payload = bytes(range(256)) * 8192

            def send() -> None:
                sock.sendall(payload)
                sock.shutdown(socket.SHUT_WR)

            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(send)
                received = bytearray()
                while chunk := sock.recv(65536):
                    received.extend(chunk)
                future.result(timeout=3)
            self.assertEqual(received, payload + b"done")

    def test_idle_tunnel_survives_handshake_timeout(self) -> None:
        _, local = self.bridge(self.server().proxy(), handshake_seconds=0.1, connect_seconds=0.1)
        with self.tunnel(local) as sock:
            threading.Event().wait(0.25)
            sock.sendall(b"still alive")
            self.assertEqual(recv_exact(sock, 11), b"still alive")

    def test_five_bridges_route_independently_and_stop_independently(self) -> None:
        servers = [
            self.server(marker=bytes([index]), username=f"user-{index}", password=f"secret-{index}")
            for index in range(5)
        ]
        configs = [self.bridge(server.proxy()) for server in servers]
        self.assertEqual(len({local.port for _, local in configs}), 5)

        def check(index: int) -> None:
            with self.tunnel(configs[index][1]) as sock:
                self.assertEqual(recv_exact(sock, 1), bytes([index]))
                payload = f"session-{index}".encode() * 10000
                sock.sendall(payload)
                self.assertEqual(recv_exact(sock, len(payload)), payload)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(check, index) for index in range(5) for _ in range(2)]
            for future in futures:
                future.result(timeout=5)
        configs[0][0].close()
        configs[0][0].close()
        with self.assertRaises(OSError):
            self.tunnel(configs[0][1])
        for index in range(1, 5):
            check(index)
        for index, server in enumerate(servers):
            self.assertEqual(
                server.records.get(timeout=2)[0],
                (f"user-{index}".encode(), f"secret-{index}".encode()),
            )

    def test_upstream_handshake_timeout_fails_closed(self) -> None:
        _, local = self.bridge(self.server(mode="timeout").proxy(), connect_seconds=0.15)
        with self.assertLogs("services.socks5_bridge", level="WARNING"):
            with self.assertRaisesRegex(ValueError, "SOCKS5 connect failed"):
                self.tunnel(local)

    def test_close_interrupts_upstream_handshake(self) -> None:
        server = self.server(mode="timeout")
        bridge, local = self.bridge(server.proxy())
        with socket.create_connection((local.host, local.port), timeout=2) as sock:
            sock.sendall(bytes([5, 1, 0]))
            self.assertEqual(recv_exact(sock, 2), bytes([5, 0]))
            sock.sendall(bytes([5, 1, 0, 3, 7]) + b"invalid" + bytes([1, 187]))
            self.assertTrue(server.greeted.wait(2))
            bridge.close()
            self.assertEqual(sock.recv(1), b"")
            self.assertFalse(bridge._workers)
            self.assertFalse(bridge._sockets)

    def test_authentication_and_upstream_failures_fail_closed(self) -> None:
        for mode, password in (("auth", "wrong"), ("refused", "p"), ("malformed", "p")):
            with self.subTest(mode=mode):
                server = self.server(mode=mode)
                _, local = self.bridge(replace(server.proxy(), password=password))
                with self.assertLogs("services.socks5_bridge", level="WARNING") as logs:
                    with self.assertRaisesRegex(ValueError, "SOCKS5 connect failed"):
                        self.tunnel(local)
                self.assertNotIn("wrong", " ".join(logs.output))

    def test_udp_and_invalid_address_are_rejected(self) -> None:
        server = self.server()
        _, local = self.bridge(server.proxy())
        for request, expected in ((bytes([5, 3, 0, 1]), 7), (bytes([5, 1, 0, 9]), 8)):
            with socket.create_connection((local.host, local.port), timeout=2) as sock:
                sock.sendall(bytes([5, 1, 0]))
                self.assertEqual(recv_exact(sock, 2), bytes([5, 0]))
                with self.assertLogs("services.socks5_bridge", level="WARNING"):
                    sock.sendall(request)
                    self.assertEqual(recv_exact(sock, 10)[1], expected)
        self.assertTrue(server.records.empty())

    def test_handshake_timeout_and_connection_limit(self) -> None:
        bridge, local = self.bridge(
            self.server().proxy(), handshake_seconds=0.15, max_connections=1
        )
        with socket.create_connection((local.host, local.port), timeout=2) as first:
            first.sendall(bytes([5, 1, 0]))
            self.assertEqual(recv_exact(first, 2), bytes([5, 0]))
            with socket.create_connection((local.host, local.port), timeout=2) as second:
                self.assertEqual(second.recv(1), b"")
            with self.assertLogs("services.socks5_bridge", level="WARNING"):
                self.assertEqual(first.recv(1), b"")
        self.assertTrue(bridge.is_running())

    def test_close_interrupts_active_connections_and_releases_port(self) -> None:
        bridge, local = self.bridge(self.server().proxy())
        with self.tunnel(local) as sock:
            start = time.monotonic()
            bridge.close()
            self.assertLess(time.monotonic() - start, 1)
            self.assertEqual(sock.recv(1), b"")
        self.assertFalse(bridge.is_running())
        with self.assertRaises(OSError):
            socket.create_connection((local.host, local.port), timeout=0.5)

    def test_process_exit_and_forced_termination_release_listener(self) -> None:
        server = self.server()
        context = multiprocessing.get_context("spawn")
        for force in (False, True):
            with self.subTest(force=force):
                result = context.Queue()
                stop = context.Event()
                process = context.Process(
                    target=_start_bridge_process, args=(server.proxy(), result, stop)
                )
                process.start()
                try:
                    local = result.get(timeout=10)
                    with self.tunnel(local) as sock:
                        sock.sendall(b"test")
                        self.assertEqual(recv_exact(sock, 4), b"test")
                        if force:
                            process.terminate()
                        else:
                            stop.set()
                        process.join(5)
                        self.assertFalse(process.is_alive())
                        self.assertEqual(sock.recv(1), b"")
                    with self.assertRaises(OSError):
                        socket.create_connection((local.host, local.port), timeout=0.5)
                finally:
                    if process.is_alive():
                        process.kill()
                        process.join(5)
                    process.close()
                    result.close()
                    result.join_thread()
