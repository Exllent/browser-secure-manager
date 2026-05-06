from __future__ import annotations

from dataclasses import dataclass

from app_config import APP_CONFIG

SUPPORTED_BROWSER_TYPES = set(APP_CONFIG.storage.supported_browser_types)


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
        return (
            browser_type
            if browser_type in SUPPORTED_BROWSER_TYPES
            else APP_CONFIG.storage.default_browser_type
        )
