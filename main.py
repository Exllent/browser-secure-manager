from __future__ import annotations

import logging
import os
import sys

from PySide6.QtWidgets import QApplication

from app.app_service import AppService
from app.fonts import configure_application_fonts
from app.i18n import load_language
from browser_backends.selenium_backend import SeleniumBrowserBackend
from gui.main_window import MainWindow


def configure_qt_logging() -> None:
    existing_rules = os.environ.get("QT_LOGGING_RULES", "").strip()
    font_rule = "qt.text.font.db=false"
    if font_rule in existing_rules:
        return

    os.environ["QT_LOGGING_RULES"] = (
        f"{existing_rules};{font_rule}" if existing_rules else font_rule
    )


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def main() -> int:
    configure_qt_logging()
    configure_logging()
    app_service = AppService(SeleniumBrowserBackend())
    app_service.init_storage()

    app = QApplication(sys.argv)
    configure_application_fonts(app)
    load_language(app_service.get_setting("language", "en"))
    window = MainWindow(app_service)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
