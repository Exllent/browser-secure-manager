from __future__ import annotations

import ipaddress
import socket
import time
from collections.abc import Callable

from models.proxy_config import ProxyConfig


class Socks5Error(ValueError):
    def __init__(self, message: str, reply_code: int = 1) -> None:
        super().__init__(message)
        self.reply_code = reply_code


def recv_exact(sock: socket.socket, size: int, *, deadline: float | None = None) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("SOCKS5 handshake timed out")
            sock.settimeout(remaining)
        chunk = sock.recv(size - len(chunks))
        if not chunk:
            raise ValueError("connection closed by proxy")
        chunks.extend(chunk)
    return bytes(chunks)


def read_address(sock: socket.socket, atyp: int, *, deadline: float) -> bytes:
    if atyp == 1:
        return recv_exact(sock, 4, deadline=deadline)
    if atyp == 4:
        return recv_exact(sock, 16, deadline=deadline)
    if atyp == 3:
        length = recv_exact(sock, 1, deadline=deadline)
        if length[0] == 0:
            raise Socks5Error("empty SOCKS5 domain", 8)
        return length + recv_exact(sock, length[0], deadline=deadline)
    raise Socks5Error("unsupported SOCKS5 address type", 8)


def encode_address(host: str) -> tuple[int, bytes]:
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        domain = host.encode("idna")
        if not 1 <= len(domain) <= 255:
            raise ValueError("invalid SOCKS5 domain length") from None
        return 3, bytes([len(domain)]) + domain
    return (1 if address.version == 4 else 4), address.packed


def open_socks5_tunnel(
    proxy: ProxyConfig,
    *,
    target_host: str = "",
    target_port: int,
    timeout: float,
    target_address: tuple[int, bytes] | None = None,
    on_socket: Callable[[socket.socket], None] | None = None,
) -> socket.socket:
    # Only the proxy endpoint is resolved locally. Browser target bytes are forwarded unchanged.
    atyp, address = target_address if target_address is not None else encode_address(target_host)
    deadline = time.monotonic() + timeout
    sock = socket.create_connection((proxy.host.strip(), proxy.port), timeout=timeout)
    try:
        if on_socket is not None:
            on_socket(sock)
        sock.settimeout(timeout)
        methods = [2, 0] if proxy.username or proxy.password else [0]
        sock.sendall(bytes([5, len(methods), *methods]))
        response = recv_exact(sock, 2, deadline=deadline)
        if response[0] != 5:
            raise ValueError("server did not respond as SOCKS5")
        if response[1] == 255:
            raise ValueError("SOCKS5 auth method rejected")
        if response[1] not in methods:
            raise ValueError(f"unsupported SOCKS5 auth method: {response[1]}")
        if response[1] == 2:
            username = proxy.username.encode("utf-8")
            password = proxy.password.encode("utf-8")
            if len(username) > 255 or len(password) > 255:
                raise ValueError("SOCKS5 username/password is too long")
            sock.sendall(bytes([1, len(username)]) + username + bytes([len(password)]) + password)
            response = recv_exact(sock, 2, deadline=deadline)
            if response != bytes([1, 0]):
                raise ValueError("SOCKS5 username/password rejected")

        sock.sendall(bytes([5, 1, 0, atyp]) + address + target_port.to_bytes(2, "big"))
        header = recv_exact(sock, 4, deadline=deadline)
        if header[0] != 5 or header[2] != 0:
            raise ValueError("invalid SOCKS5 connect response")
        if header[1] != 0:
            code = header[1] if 1 <= header[1] <= 8 else 1
            raise Socks5Error(f"SOCKS5 connect failed with code {header[1]}", code)
        read_address(sock, header[3], deadline=deadline)
        recv_exact(sock, 2, deadline=deadline)
        sock.settimeout(timeout)
        return sock
    except Exception:
        sock.close()
        raise
