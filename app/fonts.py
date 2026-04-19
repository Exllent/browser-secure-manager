from __future__ import annotations

import logging

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

logger = logging.getLogger(__name__)

BASE_FONT_CANDIDATES = (
    "Noto Sans",
    "Segoe UI",
    "San Francisco",
    "Helvetica Neue",
    "Arial",
    "DejaVu Sans",
    "Ubuntu Sans",
)

FALLBACK_FONT_CANDIDATES = (
    "Noto Sans Arabic",
    "Noto Sans Hebrew",
    "Noto Sans Devanagari",
    "Noto Sans Bengali",
    "Noto Sans Thai",
    "Noto Sans CJK SC",
    "Noto Sans CJK TC",
    "Noto Sans CJK JP",
    "Noto Sans CJK KR",
    "Noto Color Emoji",
    "DejaVu Sans",
    "Segoe UI",
    "Arial",
)

SUBSTITUTED_FONT_FAMILIES = (
    "Ubuntu Sans",
    "Arial",
    "Helvetica",
    "Helvetica Neue",
    "Segoe UI",
    "Sans Serif",
    "sans-serif",
)

EMOJI_FONT_CANDIDATES = (
    "Noto Color Emoji",
    "Segoe UI Emoji",
    "Apple Color Emoji",
)


def configure_application_fonts(app: QApplication) -> None:
    families = set(QFontDatabase.families())
    base_family = _first_installed(families, BASE_FONT_CANDIDATES)
    fallback_families = _installed(families, FALLBACK_FONT_CANDIDATES)

    if base_family is not None:
        app.setFont(QFont(base_family, 10))

    if fallback_families:
        for family in SUBSTITUTED_FONT_FAMILIES:
            QFont.insertSubstitutions(family, fallback_families)

    _configure_emoji_font(families)

    logger.info(
        "Configured application font: base=%s fallbacks=%s",
        base_family or "system default",
        ", ".join(fallback_families) if fallback_families else "system default",
    )


def _configure_emoji_font(families: set[str]) -> None:
    emoji_family = _first_installed(families, EMOJI_FONT_CANDIDATES)
    if emoji_family is None:
        return

    add_emoji_family = getattr(QFontDatabase, "addApplicationEmojiFontFamily", None)
    if add_emoji_family is not None:
        add_emoji_family(emoji_family)


def _first_installed(families: set[str], candidates: tuple[str, ...]) -> str | None:
    for family in candidates:
        if family in families:
            return family
    return None


def _installed(families: set[str], candidates: tuple[str, ...]) -> list[str]:
    return [family for family in candidates if family in families]
