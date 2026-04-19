from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QCoreApplication, Qt, QTranslator

_CONTEXT = "App"
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

    translations_dir = Path(__file__).resolve().parents[1] / "translations"
    qm_path = translations_dir / f"app_{language_code}.qm"

    translator = QTranslator()
    if not translator.load(str(qm_path)):
        return False

    app.installTranslator(translator)
    _TRANSLATOR = translator
    return True
