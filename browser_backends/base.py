from __future__ import annotations

from typing import Protocol

from models.browser_config import BrowserConfig
from models.proxy_config import ProxyConfig
from models.session_entry import SessionEntry


class BrowserBackend(Protocol):
    def open_session(
        self,
        session: SessionEntry,
        browser_config: BrowserConfig,
        proxy_config: ProxyConfig | None = None,
    ) -> None:
        ...

    def close_session(self, session_id: int) -> None:
        ...

    def close_all(self) -> None:
        ...

    def discover_installed_browsers(self) -> list[BrowserConfig]:
        ...
