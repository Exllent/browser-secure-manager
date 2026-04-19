from __future__ import annotations

import socket
import time
from dataclasses import dataclass

from models.proxy_config import ProxyConfig


@dataclass(slots=True)
class ProxyTestResult:
    ok: bool
    elapsed_ms: int | None
    message: str


def test_proxy(proxy: ProxyConfig, *, timeout: float = 5.0) -> ProxyTestResult:
    started = time.perf_counter()
    try:
        proxy_type = proxy.normalized_type()
        if proxy_type == "socks5":
            _test_socks5(proxy, timeout=timeout)
        elif proxy_type == "socks4":
            _test_socks4(proxy, timeout=timeout)
        else:
            _test_http_connect(proxy, timeout=timeout)
    except OSError as exc:
        return ProxyTestResult(False, None, str(exc))
    except ValueError as exc:
        return ProxyTestResult(False, None, str(exc))

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return ProxyTestResult(True, elapsed_ms, "ok")


def _test_socks5(proxy: ProxyConfig, *, timeout: float) -> None:
    with socket.create_connection((proxy.host.strip(), proxy.port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        methods = [0x00]
        if proxy.username or proxy.password:
            methods.append(0x02)

        sock.sendall(bytes([0x05, len(methods), *methods]))
        response = _recv_exact(sock, 2)
        if response[0] != 0x05:
            raise ValueError("server did not respond as SOCKS5")
        if response[1] == 0xFF:
            raise ValueError("SOCKS5 auth method rejected")
        if response[1] == 0x02:
            _socks5_auth(sock, proxy)
        elif response[1] != 0x00:
            raise ValueError(f"unsupported SOCKS5 auth method: {response[1]}")

        target = b"example.com"
        port = 80
        request = bytes([0x05, 0x01, 0x00, 0x03, len(target)]) + target + port.to_bytes(2, "big")
        sock.sendall(request)
        header = _recv_exact(sock, 4)
        if header[0] != 0x05:
            raise ValueError("invalid SOCKS5 connect response")
        if header[1] != 0x00:
            raise ValueError(f"SOCKS5 connect failed with code {header[1]}")

        atyp = header[3]
        if atyp == 0x01:
            _recv_exact(sock, 4)
        elif atyp == 0x03:
            length = _recv_exact(sock, 1)[0]
            _recv_exact(sock, length)
        elif atyp == 0x04:
            _recv_exact(sock, 16)
        else:
            raise ValueError(f"invalid SOCKS5 address type: {atyp}")
        _recv_exact(sock, 2)


def _socks5_auth(sock: socket.socket, proxy: ProxyConfig) -> None:
    username = proxy.username.encode("utf-8")
    password = proxy.password.encode("utf-8")
    if len(username) > 255 or len(password) > 255:
        raise ValueError("SOCKS5 username/password is too long")

    sock.sendall(bytes([0x01, len(username)]) + username + bytes([len(password)]) + password)
    response = _recv_exact(sock, 2)
    if response[0] != 0x01 or response[1] != 0x00:
        raise ValueError("SOCKS5 username/password rejected")


def _test_socks4(proxy: ProxyConfig, *, timeout: float) -> None:
    with socket.create_connection((proxy.host.strip(), proxy.port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        target_ip = socket.gethostbyname("example.com")
        port = 80
        request = bytes([0x04, 0x01]) + port.to_bytes(2, "big") + socket.inet_aton(target_ip)
        request += proxy.username.encode("utf-8") + b"\x00"
        sock.sendall(request)
        response = _recv_exact(sock, 8)
        if response[0] != 0x00 or response[1] != 0x5A:
            raise ValueError(f"SOCKS4 connect failed with code {response[1]}")


def _test_http_connect(proxy: ProxyConfig, *, timeout: float) -> None:
    with socket.create_connection((proxy.host.strip(), proxy.port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        request = (
            "CONNECT example.com:443 HTTP/1.1\r\n"
            "Host: example.com:443\r\n"
            "Proxy-Connection: keep-alive\r\n"
            "\r\n"
        )
        sock.sendall(request.encode("ascii"))
        response = sock.recv(256).decode("iso-8859-1", errors="replace")
        if " 200 " not in response.splitlines()[0]:
            raise ValueError(response.splitlines()[0] if response else "empty HTTP proxy response")


def _recv_exact(sock: socket.socket, size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        chunk = sock.recv(size - len(chunks))
        if not chunk:
            raise ValueError("connection closed by proxy")
        chunks.extend(chunk)
    return bytes(chunks)
