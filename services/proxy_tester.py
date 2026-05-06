from __future__ import annotations

import base64
import logging
import socket
import ssl
import time
from dataclasses import dataclass

from app_config import APP_CONFIG
from models.proxy_config import ProxyConfig

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ProxyTestResult:
    ok: bool
    elapsed_ms: int | None
    message: str


def test_proxy(
    proxy: ProxyConfig,
    *,
    timeout: float = APP_CONFIG.proxies.test_timeout_seconds,
) -> ProxyTestResult:
    started = time.perf_counter()
    logger.info("Testing proxy %s", proxy.display_name())
    try:
        proxy_type = proxy.normalized_type()
        target_host = APP_CONFIG.proxies.test_target_host
        target_port = APP_CONFIG.proxies.test_target_port
        if proxy_type == "socks5":
            sock = _open_socks5_tunnel(
                proxy,
                target_host=target_host,
                target_port=target_port,
                timeout=timeout,
            )
        elif proxy_type == "socks4":
            sock = _open_socks4_tunnel(
                proxy,
                target_host=target_host,
                target_port=target_port,
                timeout=timeout,
            )
        else:
            sock = _open_http_tunnel(
                proxy,
                target_host=target_host,
                target_port=target_port,
                timeout=timeout,
            )

        with sock:
            _verify_tls(sock, server_hostname=target_host, timeout=timeout)
    except OSError as exc:
        logger.warning("Proxy test failed for %s: %s", proxy.display_name(), exc)
        return ProxyTestResult(False, None, str(exc))
    except ValueError as exc:
        logger.warning("Proxy test failed for %s: %s", proxy.display_name(), exc)
        return ProxyTestResult(False, None, str(exc))
    except ssl.SSLError as exc:
        logger.warning("Proxy TLS validation failed for %s: %s", proxy.display_name(), exc)
        return ProxyTestResult(False, None, f"TLS validation failed through proxy: {exc}")

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    logger.info("Proxy test passed for %s in %s ms", proxy.display_name(), elapsed_ms)
    return ProxyTestResult(True, elapsed_ms, "ok")


def _open_socks5_tunnel(
    proxy: ProxyConfig,
    *,
    target_host: str,
    target_port: int,
    timeout: float,
) -> socket.socket:
    sock = socket.create_connection((proxy.host.strip(), proxy.port), timeout=timeout)
    try:
        sock.settimeout(timeout)
        methods = [0x02, 0x00] if proxy.username or proxy.password else [0x00]

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

        target = target_host.encode("idna")
        request = bytes([0x05, 0x01, 0x00, 0x03, len(target)]) + target + target_port.to_bytes(2, "big")
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
        return sock
    except Exception:
        sock.close()
        raise


def _socks5_auth(sock: socket.socket, proxy: ProxyConfig) -> None:
    username = proxy.username.encode("utf-8")
    password = proxy.password.encode("utf-8")
    if len(username) > 255 or len(password) > 255:
        raise ValueError("SOCKS5 username/password is too long")

    sock.sendall(bytes([0x01, len(username)]) + username + bytes([len(password)]) + password)
    response = _recv_exact(sock, 2)
    if response[0] != 0x01 or response[1] != 0x00:
        raise ValueError("SOCKS5 username/password rejected")


def _open_socks4_tunnel(
    proxy: ProxyConfig,
    *,
    target_host: str,
    target_port: int,
    timeout: float,
) -> socket.socket:
    sock = socket.create_connection((proxy.host.strip(), proxy.port), timeout=timeout)
    try:
        sock.settimeout(timeout)
        target_ip = socket.gethostbyname(target_host)
        request = bytes([0x04, 0x01]) + target_port.to_bytes(2, "big") + socket.inet_aton(target_ip)
        request += proxy.username.encode("utf-8") + b"\x00"
        sock.sendall(request)
        response = _recv_exact(sock, 8)
        if response[0] != 0x00 or response[1] != 0x5A:
            raise ValueError(f"SOCKS4 connect failed with code {response[1]}")
        return sock
    except Exception:
        sock.close()
        raise


def _open_http_tunnel(
    proxy: ProxyConfig,
    *,
    target_host: str,
    target_port: int,
    timeout: float,
) -> socket.socket:
    sock = socket.create_connection((proxy.host.strip(), proxy.port), timeout=timeout)
    try:
        sock.settimeout(timeout)
        headers = [
            f"CONNECT {target_host}:{target_port} HTTP/1.1",
            f"Host: {target_host}:{target_port}",
            "Proxy-Connection: keep-alive",
        ]
        if proxy.username or proxy.password:
            credentials = f"{proxy.username}:{proxy.password}".encode("utf-8")
            token = base64.b64encode(credentials).decode("ascii")
            headers.append(f"Proxy-Authorization: Basic {token}")
        request = "\r\n".join(headers) + "\r\n\r\n"
        sock.sendall(request.encode("ascii"))
        response = sock.recv(256).decode("iso-8859-1", errors="replace")
        if " 200 " not in response.splitlines()[0]:
            raise ValueError(response.splitlines()[0] if response else "empty HTTP proxy response")
        return sock
    except Exception:
        sock.close()
        raise


def _verify_tls(sock: socket.socket, *, server_hostname: str, timeout: float) -> None:
    context = ssl.create_default_context()
    with context.wrap_socket(sock, server_hostname=server_hostname) as tls_sock:
        tls_sock.settimeout(timeout)
        tls_sock.sendall(
            (
                f"HEAD {APP_CONFIG.proxies.tls_probe_path} HTTP/1.1\r\n"
                f"Host: {server_hostname}\r\n"
                "Connection: close\r\n"
                "\r\n"
            ).encode("ascii")
        )
        response = tls_sock.recv(128).decode("iso-8859-1", errors="replace")
        if not response.startswith("HTTP/"):
            raise ValueError("TLS tunnel did not return a valid HTTPS response")


def _recv_exact(sock: socket.socket, size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        chunk = sock.recv(size - len(chunks))
        if not chunk:
            raise ValueError("connection closed by proxy")
        chunks.extend(chunk)
    return bytes(chunks)
