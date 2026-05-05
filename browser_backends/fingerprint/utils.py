from __future__ import annotations

import hashlib


def _stable_noise_seed(*parts: str) -> int:
    digest = hashlib.sha256("\n".join(parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") or 1
