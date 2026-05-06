from __future__ import annotations

from PySide6.QtCore import QCoreApplication, Qt, QTranslator

from app_config import APP_CONFIG

_CONTEXT = APP_CONFIG.i18n.context
_TRANSLATOR: QTranslator | None = None


def _(text: str) -> str:
    return QCoreApplication.translate(_CONTEXT, text)


def load_language(language_code: str) -> bool:
    global _TRANSLATOR

    app = QCoreApplication.instance()
    if app is None:
        return False

    app.setLayoutDirection(
        Qt.LayoutDirection.RightToLeft
        if language_code in {"ar", "fa", "he"}
        else Qt.LayoutDirection.LeftToRight
    )

    if _TRANSLATOR is not None:
        app.removeTranslator(_TRANSLATOR)
        _TRANSLATOR = None

    if language_code == "en":
        return True

    qm_path = (
        APP_CONFIG.paths.translations_dir
        / f"{APP_CONFIG.i18n.translation_prefix}{language_code}{APP_CONFIG.i18n.translation_suffix}"
    )

    translator = QTranslator()
    if not translator.load(str(qm_path)):
        return False

    app.installTranslator(translator)
    _TRANSLATOR = translator
    return True
