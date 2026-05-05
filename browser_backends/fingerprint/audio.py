from __future__ import annotations

from models.fingerprint_config import FingerprintConfig

from .templates import _render_js_template
from .utils import _stable_noise_seed


def _build_audio_patch(config: FingerprintConfig) -> str:
    noise_seed = _stable_noise_seed(
        config.user_agent or "",
        config.platform or "",
        ",".join(config.locale),
        "audio",
    )
    return _render_js_template("audio.js", {"noiseSeed": noise_seed})
