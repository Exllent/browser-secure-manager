from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SessionEntry:
    id: int | None
    name: str
    url: str
    browser: str
    profile_path: str
    proxy_id: int | None = None
    proxy_label: str = ""
    custom_user_agent: str = ""
    notes: str = ""
    window_width: int = 1280
    window_height: int = 800
    status: str = "idle"

    def normalized_browser(self) -> str:
        browser = self.browser.strip().lower()
        return browser if browser in {"chrome", "firefox"} else "chrome"
