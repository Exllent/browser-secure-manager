from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ProxyConfig:
    id: int | None
    label: str
    host: str
    port: int
    proxy_type: str = "socks5"
    username: str = ""
    password: str = ""
    enabled: bool = True

    def normalized_type(self) -> str:
        proxy_type = self.proxy_type.strip().lower()
        return proxy_type if proxy_type in {"http", "socks4", "socks5"} else "socks5"

    def display_name(self) -> str:
        label = self.label.strip()
        endpoint = f"{self.normalized_type()}://{self.host.strip()}:{self.port}"
        return f"{label} ({endpoint})" if label else endpoint

    def endpoint(self) -> str:
        return f"{self.host.strip()}:{self.port}"

    def browser_proxy_url(self) -> str:
        return f"{self.normalized_type()}://{self.endpoint()}"
