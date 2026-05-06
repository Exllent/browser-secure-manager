from __future__ import annotations

import logging
import os
import sys

from PySide6.QtWidgets import QApplication

from app.app_service import AppService
from app.fonts import configure_application_fonts
from app.i18n import load_language
from app.logging_config import configure_logging
from app_config import APP_CONFIG
from browser_backends.selenium_backend import SeleniumBrowserBackend
from gui.main_window import MainWindow

logger = logging.getLogger(__name__)


def configure_qt_logging() -> None:
    existing_rules = os.environ.get("QT_LOGGING_RULES", "").strip()
    font_rule = "qt.text.font.db=false"
    if font_rule in existing_rules:
        return

    os.environ["QT_LOGGING_RULES"] = (
        f"{existing_rules};{font_rule}" if existing_rules else font_rule
    )


def main() -> int:
    configure_qt_logging()
    configure_logging()
    logger.info("Secure Browser starting")
    try:
        app_service = AppService(SeleniumBrowserBackend())
        app_service.init_storage()

        app = QApplication(sys.argv)
        configure_application_fonts(app)
        language = app_service.get_setting(APP_CONFIG.settings_keys.language, "en")
        if not load_language(language):
            logger.warning("Failed to load language '%s'; using English", language)
        window = MainWindow(app_service)
        window.show()
        exit_code = app.exec()
        logger.info("Secure Browser stopped with exit code %s", exit_code)
        return exit_code
    except Exception:
        logger.critical("Secure Browser failed with an unhandled exception", exc_info=True)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
