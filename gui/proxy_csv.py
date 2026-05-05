from __future__ import annotations

import csv
from pathlib import Path

from models.proxy_config import ProxyConfig


def parse_proxy_csv(path: Path) -> list[ProxyConfig]:
    proxies: list[ProxyConfig] = []
    with path.open("r", encoding="utf-8-sig", newline="", errors="replace") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None:
            raise ValueError("CSV must contain a header row.")

        for index, row in enumerate(reader, start=2):
            host = _csv_value(row, "ip", "host", "address")
            port_text = _csv_value(row, "port")
            protocol = _csv_value(row, "protocols", "protocol", "type") or "socks5"

            if not host or not port_text:
                continue

            try:
                port = int(port_text)
            except ValueError:
                raise ValueError(f"Invalid port on row {index}: {port_text}") from None

            proxy_type = _normalize_csv_protocol(protocol)
            label = _csv_value(row, "country", "label", "name")
            username = _csv_value(row, "username", "user", "login")
            password = _csv_value(row, "password", "pass")

            proxies.append(
                ProxyConfig(
                    id=None,
                    label=label,
                    host=host,
                    port=port,
                    proxy_type=proxy_type,
                    username=username,
                    password=password,
                    enabled=True,
                )
            )

    return proxies



def _csv_value(row: dict[str, str], *names: str) -> str:
    lowered = {key.lower(): value for key, value in row.items() if key is not None}
    for name in names:
        value = lowered.get(name.lower())
        if value is not None:
            return value.strip()
    return ""



def _normalize_csv_protocol(value: str) -> str:
    protocol = value.strip().lower()
    if "," in protocol:
        protocol = protocol.split(",", 1)[0].strip()
    if protocol in {"socks4", "socks5", "http"}:
        return protocol
    if protocol == "https":
        return "http"
    return "socks5"
