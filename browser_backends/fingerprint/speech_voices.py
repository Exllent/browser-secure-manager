from __future__ import annotations

from typing import Any

from models.fingerprint_config import FingerprintConfig

from .templates import _render_js_template


def _build_speech_voices_patch(config: FingerprintConfig) -> str:
    if not getattr(config, "spoof_speech_voices", False):
        return ""
    return _render_js_template(
        "speech_voices.js",
        {"voices": _speech_voices_for_config(config)},
    )


def _speech_voices_for_config(config: FingerprintConfig) -> list[dict[str, str | bool]]:
    voices = getattr(config, "speech_voices", None)
    if voices:
        return [_normalize_speech_voice(voice, index) for index, voice in enumerate(voices)]

    languages = getattr(config, "spoof_languages", None) or getattr(config, "locale", None) or []
    primary_language = str(languages[0] if languages else "en-US")
    platform = str(getattr(config, "platform", "") or "")
    language_name = _language_voice_name(primary_language)

    if platform == "MacIntel":
        names = (language_name, "Samantha", "Alex")
        prefix = "com.apple.speech.synthesis.voice"
    elif platform.startswith("Win"):
        names = (language_name, "Microsoft David Desktop", "Microsoft Zira Desktop")
        prefix = "Microsoft"
    elif platform.startswith("Linux"):
        names = (language_name, "Google US English", "English United States")
        prefix = "Google"
    else:
        names = (language_name, "Google US English", "English United States")
        prefix = "Google"

    return [
        _normalize_speech_voice(
            {
                "voiceURI": f"{prefix}.{name}".replace(" ", "-"),
                "name": name,
                "lang": primary_language if index == 0 else "en-US",
                "localService": index != 1,
                "default": index == 0,
            },
            index,
        )
        for index, name in enumerate(dict.fromkeys(names))
    ]


def _normalize_speech_voice(
    voice: dict[str, Any],
    index: int,
) -> dict[str, str | bool]:
    name = str(voice.get("name") or f"Secure Browser Voice {index + 1}")
    language = str(voice.get("lang") or "en-US")
    return {
        "voiceURI": str(voice.get("voiceURI") or name),
        "name": name,
        "lang": language,
        "localService": bool(voice.get("localService", True)),
        "default": bool(voice.get("default", index == 0)),
    }


def _language_voice_name(language: str) -> str:
    language_prefix = language.split("-", 1)[0].lower()
    if language_prefix == "ru":
        return "Google Russian"
    if language_prefix == "de":
        return "Google Deutsch"
    if language_prefix == "fr":
        return "Google French"
    if language_prefix == "ja":
        return "Google Japanese"
    if language.lower() == "en-gb":
        return "Google UK English Female"
    return "Google US English"
