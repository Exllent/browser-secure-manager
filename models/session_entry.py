from __future__ import annotations

from dataclasses import dataclass

from app_config import APP_CONFIG


@dataclass(slots=True)
class SessionEntry:
    id: int | None
    name: str
    url: str
    browser: str
    profile_path: str
    proxy_id: int | None = None
    fingerprint_id: int | None = None
    proxy_label: str = ""
    custom_user_agent: str = ""
    notes: str = ""
    window_width: int = APP_CONFIG.storage.default_window_size[0]
    window_height: int = APP_CONFIG.storage.default_window_size[1]
    status: str = APP_CONFIG.storage.default_status

    def normalized_browser(self) -> str:
        return self.browser.strip().lower() or APP_CONFIG.storage.default_browser_key
