from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.app_service import AppService
from app.i18n import _
from gui.app_settings_dialog import AppSettingsDialog
from gui.session_row_widget import SESSION_TABLE_COLUMNS, SessionRowWidget
from models.browser_config import BrowserConfig
from models.session_entry import SessionEntry

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, app_service: AppService) -> None:
        super().__init__()
        self.setWindowTitle(_("Isolated Browser Sessions"))
        self.resize(1050, 720)

        self.app_service = app_service
        self.rows: dict[int, SessionRowWidget] = {}
        self.header_labels: list[QLabel] = []

        root = QWidget()
        root_layout = QVBoxLayout(root)

        toolbar = QHBoxLayout()
        self.add_button = QPushButton(_("Add session"))
        self.app_settings_button = QPushButton(_("Application settings"))
        self.save_all_button = QPushButton(_("Save all"))
        self.refresh_button = QPushButton(_("Refresh"))
        self.stop_all_button = QPushButton(_("Stop all"))
        toolbar.addWidget(self.add_button)
        toolbar.addWidget(self.app_settings_button)
        toolbar.addWidget(self.save_all_button)
        toolbar.addWidget(self.refresh_button)
        toolbar.addWidget(self.stop_all_button)
        toolbar.addStretch(1)
        root_layout.addLayout(toolbar)
        self.session_header = self._build_session_header()
        root_layout.addWidget(self.session_header)

        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.list_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.list_container)
        root_layout.addWidget(scroll_area, 1)

        self.setCentralWidget(root)

        self.add_button.clicked.connect(self.add_session)
        self.app_settings_button.clicked.connect(self.open_app_settings)
        self.save_all_button.clicked.connect(self.save_all)
        self.refresh_button.clicked.connect(self.refresh_sessions)
        self.stop_all_button.clicked.connect(self.stop_all)

        self.refresh_sessions()

    def _build_session_header(self) -> QWidget:
        header = QWidget()
        layout = QGridLayout(header)
        layout.setContentsMargins(6, 6, 6, 2)
        layout.setSpacing(6)

        for column, (label_text, width) in enumerate(SESSION_TABLE_COLUMNS):
            label = QLabel(_(label_text))
            label.setFixedWidth(width)
            label.setStyleSheet("font-weight: 600;")
            layout.addWidget(label, 0, column)
            layout.setColumnMinimumWidth(column, width)
            self.header_labels.append(label)

        return header

    def refresh_sessions(self) -> None:
        self._clear_rows()
        browser_configs = self.app_service.get_browser_configs(enabled_only=True)
        for session in self.app_service.get_sessions():
            self._add_row(session, browser_configs)

    def add_session(self) -> None:
        session = self.app_service.create_session(
            SessionEntry(
                id=None,
                name=_("New session"),
                url="about:blank",
                browser="chrome",
                profile_path="",
            )
        )
        self._add_row(session, self.app_service.get_browser_configs(enabled_only=True))

    def save_all(self) -> None:
        for row in list(self.rows.values()):
            self._save_row(row)

    def stop_all(self) -> None:
        self.app_service.close_all_sessions()
        for row in self.rows.values():
            saved = self.app_service.save_session(row.to_session())
            row.set_session(saved)

    def _add_row(
        self,
        session: SessionEntry,
        browser_configs: list[BrowserConfig],
    ) -> None:
        row = SessionRowWidget(session, browser_configs, self.app_service)
        row.open_requested.connect(lambda entry, widget=row: self.open_session(entry, widget))
        row.save_requested.connect(lambda _entry, widget=row: self._save_row(widget))
        row.delete_requested.connect(lambda entry, widget=row: self.delete_row(entry, widget))
        self.list_layout.addWidget(row)
        if session.id is not None:
            self.rows[session.id] = row

    def _save_row(self, row: SessionRowWidget) -> SessionEntry | None:
        try:
            saved = self.app_service.save_session(row.to_session())
        except Exception as exc:
            logger.exception("Failed to save session")
            QMessageBox.critical(self, _("Save error"), str(exc))
            return None

        row.set_session(saved)
        if saved.id is not None:
            self.rows[saved.id] = row
        return saved

    def open_session(self, session: SessionEntry, row: SessionRowWidget) -> None:
        result = self.app_service.open_session(row.to_session())
        row.set_session(result.session)
        if not result.ok:
            QMessageBox.critical(self, _(result.error_title or "Error"), result.error_message or "")
            return

    def delete_row(self, session: SessionEntry, row: SessionRowWidget) -> None:
        if self.app_service.confirm_before_delete() and not _confirm_delete(
            self,
            _("Delete session"),
            _("Are you sure you want to delete this session?"),
        ):
            return

        if session.id is not None:
            self.app_service.delete_session(session.id)
            self.rows.pop(session.id, None)

        self.list_layout.removeWidget(row)
        row.deleteLater()

    def _clear_rows(self) -> None:
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.rows.clear()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.app_service.close_all_sessions()
        super().closeEvent(event)

    def open_app_settings(self) -> None:
        dialog = AppSettingsDialog(self.app_service, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        browser_configs = self.app_service.get_browser_configs(enabled_only=True)
        for row in self.rows.values():
            row.set_browser_configs(browser_configs)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(_("Isolated Browser Sessions"))
        self.add_button.setText(_("Add session"))
        self.app_settings_button.setText(_("Application settings"))
        self.save_all_button.setText(_("Save all"))
        self.refresh_button.setText(_("Refresh"))
        self.stop_all_button.setText(_("Stop all"))

        for label, (label_text, _width) in zip(self.header_labels, SESSION_TABLE_COLUMNS):
            label.setText(_(label_text))

        for row in self.rows.values():
            row.retranslate_ui()


def _confirm_delete(parent: QWidget, title: str, text: str) -> bool:
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(text)
    box.setIcon(QMessageBox.Icon.Question)
    yes_button = box.addButton(_("Yes"), QMessageBox.ButtonRole.YesRole)
    no_button = box.addButton(_("No"), QMessageBox.ButtonRole.NoRole)
    box.setDefaultButton(no_button)
    box.exec()
    return box.clickedButton() == yes_button
