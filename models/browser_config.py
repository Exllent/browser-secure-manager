from __future__ import annotations

from dataclasses import dataclass

SUPPORTED_BROWSER_TYPES = {"chromium"}


@dataclass(slots=True)
class BrowserConfig:
    id: int | None
    key: str
    display_name: str
    browser_type: str
    executable_path: str = ""
    enabled: bool = True

    def normalized_type(self) -> str:
        browser_type = self.browser_type.strip().lower()
        return browser_type if browser_type in SUPPORTED_BROWSER_TYPES else "chromium"
