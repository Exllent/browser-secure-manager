from __future__ import annotations

from dataclasses import dataclass, field

from models.fingerprint_config import FingerprintConfig


@dataclass(slots=True)
class FingerprintProfile:
    id: int | None
    name: str
    config: FingerprintConfig = field(default_factory=FingerprintConfig)
    enabled: bool = True

    def display_name(self) -> str:
        return self.name.strip() or "Untitled fingerprint"
