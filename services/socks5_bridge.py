from __future__ import annotations

import logging
import selectors
import socket
import threading
import time
from dataclasses import replace

from app_config import APP_CONFIG
from models.proxy_config import ProxyConfig
from services.socks5_transport import Socks5Error, open_socks5_tunnel, read_address, recv_exact

logger = logging.getLogger(__name__)


class Socks5Bridge:
    """Session-owned TCP bridge; all sockets and threads belong to the session process."""

    def __init__(self, upstream: ProxyConfig) -> None:
        self._upstream = replace(upstream)
        self._config = APP_CONFIG.socks5_bridge
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._sockets: set[socket.socket] = set()
        self._workers: set[threading.Thread] = set()
        self._listener: socket.socket | None = None
        self._accept_thread: threading.Thread | None = None
        self._port: int | None = None

    def start(self) -> ProxyConfig:
        if self._listener is not None or self._stop.is_set():
            raise RuntimeError("SOCKS5 bridge cannot be started twice")
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            listener.bind((self._config.listen_host, 0))
            listener.listen(self._config.max_connections)
            listener.settimeout(self._config.poll_seconds)
            self._port = listener.getsockname()[1]
            self._listener = listener
            self._accept_thread = threading.Thread(
                target=self._accept_connections, name="socks5-bridge-listener", daemon=True
            )
            self._accept_thread.start()
        except Exception:
            listener.close()
            self.close()
            raise
        logger.info("SOCKS5 bridge listening on %s:%s", self._config.listen_host, self._port)
        return replace(
            self._upstream,
            id=None,
            host=self._config.listen_host,
            port=self._port,
            proxy_type="socks5",
            username="",
            password="",
        )

    def is_running(self) -> bool:
        return bool(
            not self._stop.is_set() and self._accept_thread and self._accept_thread.is_alive()
        )

    def close(self) -> None:
        self._stop.set()
        if self._listener is not None:
            self._close_socket(self._listener)
        with self._lock:
            sockets = list(self._sockets)
            threads = list(self._workers)
        for sock in sockets:
            self._close_socket(sock)
        if self._accept_thread is not None:
            threads.append(self._accept_thread)
        deadline = time.monotonic() + self._config.shutdown_seconds
        for thread in threads:
            if thread.ident is not None and thread is not threading.current_thread():
                thread.join(max(0, deadline - time.monotonic()))

    @staticmethod
    def _close_socket(sock: socket.socket) -> None:
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        sock.close()

    def _track_socket(self, sock: socket.socket) -> None:
        with self._lock:
            if self._stop.is_set():
                self._close_socket(sock)
                raise OSError("SOCKS5 bridge is stopping")
            self._sockets.add(sock)

    def _accept_connections(self) -> None:
        assert self._listener is not None
        while not self._stop.is_set():
            try:
                client, _ = self._listener.accept()
            except TimeoutError:
                continue
            except OSError:
                if not self._stop.is_set():
                    logger.error("SOCKS5 bridge listener failed")
                return
            with self._lock:
                if self._stop.is_set() or len(self._workers) >= self._config.max_connections:
                    client.close()
                    continue
                self._sockets.add(client)
                worker = threading.Thread(
                    target=self._serve_client,
                    args=(client,),
                    name="socks5-bridge-client",
                    daemon=True,
                )
                self._workers.add(worker)
                try:
                    worker.start()
                except RuntimeError:
                    self._workers.discard(worker)
                    self._sockets.discard(client)
                    client.close()
                    logger.error("SOCKS5 bridge could not start connection worker")

    def _serve_client(self, client: socket.socket) -> None:
        upstream: socket.socket | None = None
        request_received = False
        connected = False
        try:
            deadline = time.monotonic() + self._config.handshake_seconds
            version, count = recv_exact(client, 2, deadline=deadline)
            if version != 5 or count == 0:
                raise ValueError("invalid SOCKS5 greeting")
            methods = recv_exact(client, count, deadline=deadline)
            if 0 not in methods:
                client.sendall(bytes([5, 255]))
                return
            client.sendall(bytes([5, 0]))
            version, command, reserved, atyp = recv_exact(client, 4, deadline=deadline)
            request_received = True
            if version != 5 or reserved != 0:
                raise Socks5Error("invalid SOCKS5 request")
            if command != 1:
                raise Socks5Error("only SOCKS5 CONNECT is supported", 7)
            address = read_address(client, atyp, deadline=deadline)
            port = int.from_bytes(recv_exact(client, 2, deadline=deadline), "big")
            upstream = open_socks5_tunnel(
                self._upstream,
                target_address=(atyp, address),
                target_port=port,
                timeout=self._config.connect_seconds,
                on_socket=self._track_socket,
            )
            self._reply(client, 0)
            connected = True
            self._relay(client, upstream)
        except (OSError, ValueError) as exc:
            if not self._stop.is_set():
                if not connected:
                    logger.warning("SOCKS5 bridge connection failed: %s", exc)
                if request_received and not connected:
                    code = exc.reply_code if isinstance(exc, Socks5Error) else 1
                    try:
                        self._reply(client, code)
                    except OSError:
                        pass
        finally:
            for sock in (client, upstream):
                if sock is not None:
                    self._close_socket(sock)
                    with self._lock:
                        self._sockets.discard(sock)
            with self._lock:
                # A transport handshake may have failed after registering its socket.
                self._sockets = {sock for sock in self._sockets if sock.fileno() != -1}
                self._workers.discard(threading.current_thread())

    @staticmethod
    def _reply(client: socket.socket, code: int) -> None:
        client.sendall(bytes([5, code, 0, 1, 0, 0, 0, 0, 0, 0]))

    def _relay(self, client: socket.socket, upstream: socket.socket) -> None:
        peers = {client: upstream, upstream: client}
        pending = {client: bytearray(), upstream: bytearray()}
        readable = {client: True, upstream: True}
        write_closed: set[socket.socket] = set()
        for sock in peers:
            sock.setblocking(False)
        with selectors.DefaultSelector() as selector:
            while not self._stop.is_set():
                for sock, peer in peers.items():
                    if not readable[peer] and not pending[sock] and sock not in write_closed:
                        sock.shutdown(socket.SHUT_WR)
                        write_closed.add(sock)
                    events = 0
                    if readable[sock] and len(pending[peer]) < self._config.buffer_bytes:
                        events |= selectors.EVENT_READ
                    if pending[sock]:
                        events |= selectors.EVENT_WRITE
                    try:
                        key = selector.get_key(sock)
                    except KeyError:
                        if events:
                            selector.register(sock, events)
                    else:
                        if not events:
                            selector.unregister(sock)
                        elif key.events != events:
                            selector.modify(sock, events)
                if not any(readable.values()) and not any(pending.values()):
                    return
                for key, events in selector.select(self._config.poll_seconds):
                    sock = key.fileobj
                    peer = peers[sock]
                    if events & selectors.EVENT_READ:
                        try:
                            data = sock.recv(self._config.buffer_bytes - len(pending[peer]))
                        except BlockingIOError:
                            pass
                        else:
                            if data:
                                pending[peer].extend(data)
                            else:
                                readable[sock] = False
                    if events & selectors.EVENT_WRITE:
                        try:
                            sent = sock.send(pending[sock])
                        except BlockingIOError:
                            pass
                        else:
                            if sent == 0:
                                return
                            del pending[sock][:sent]
