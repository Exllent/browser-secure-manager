from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication

from app.app_service import AppService
from browser_backends.selenium_backend import SeleniumBrowserBackend
from gui.main_window import MainWindow


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def main() -> int:
    configure_logging()
    app_service = AppService(SeleniumBrowserBackend())
    app_service.init_storage()

    app = QApplication(sys.argv)
    window = MainWindow(app_service)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
