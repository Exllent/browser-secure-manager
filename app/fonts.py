from __future__ import annotations

import logging

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from app_config import APP_CONFIG

logger = logging.getLogger(__name__)

BASE_FONT_CANDIDATES = APP_CONFIG.fonts.base_candidates
FALLBACK_FONT_CANDIDATES = APP_CONFIG.fonts.fallback_candidates
SUBSTITUTED_FONT_FAMILIES = APP_CONFIG.fonts.substituted_families
EMOJI_FONT_CANDIDATES = APP_CONFIG.fonts.emoji_candidates


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
