from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QDialog, QGridLayout, QLabel, QLineEdit, QPushButton, QWidget

from app.app_service import AppService
from app.i18n import _
from app_config import APP_CONFIG
from models.browser_config import BrowserConfig
from models.session_entry import SessionEntry

from .session_settings_dialog import SessionSettingsDialog
from .session_status import _status_label

SESSION_TABLE_COLUMNS = APP_CONFIG.gui.session_table_columns


class SessionRowWidget(QWidget):
    open_requested = Signal(object)
    stop_requested = Signal(object)
    save_requested = Signal(object)
    delete_requested = Signal(object)

    def __init__(
        self,
        session: SessionEntry,
        browser_configs: list[BrowserConfig],
        app_service: AppService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.app_service = app_service
        self._session_id = session.id
        self._url = session.url
        self._browser = session.browser
        self._profile_path = session.profile_path
        self._proxy_id = session.proxy_id
        self._fingerprint_id = session.fingerprint_id
        self._proxy_label = session.proxy_label
        self._notes = session.notes
        self._window_width = session.window_width
        self._window_height = session.window_height
        self._status = session.status

        self.id_label = QLabel(str(session.id) if session.id is not None else _("new"))
        self.id_label.setFixedWidth(48)

        self.name_edit = QLineEdit(session.name)
        self.name_edit.setPlaceholderText(_("Name"))
        self.name_edit.setFixedWidth(SESSION_TABLE_COLUMNS[1][1])
        self._browser_configs = browser_configs

        self.status_label = QLabel(_status_label(session.status))
        self.status_label.setFixedWidth(SESSION_TABLE_COLUMNS[2][1])
        self._process_logs: list[str] = []

        self.open_button = self._make_action_button("▶", _("Open"), "#1f9d55")
        self.stop_button = self._make_action_button("■", _("Stop"), "#f59e0b")
        self.settings_button = self._make_action_button("⚙", _("Settings"), "#9ca3af")
        self.save_button = self._make_action_button("✓", _("Save"), "#60a5fa")
        self.delete_button = self._make_action_button("✖", _("Delete"), "#f87171")

        layout = QGridLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)
        widgets = (
            self.id_label,
            self.name_edit,
            self.status_label,
            self.open_button,
            self.stop_button,
            self.settings_button,
            self.save_button,
            self.delete_button,
        )
        for column, (widget, (_label, width)) in enumerate(zip(widgets, SESSION_TABLE_COLUMNS)):
            widget.setFixedWidth(width)
            layout.addWidget(widget, 0, column)
            layout.setColumnMinimumWidth(column, width)

        self.open_button.clicked.connect(lambda: self.open_requested.emit(self.to_session()))
        self.stop_button.clicked.connect(lambda: self.stop_requested.emit(self.to_session()))
        self.settings_button.clicked.connect(self.open_settings_dialog)
        self.save_button.clicked.connect(lambda: self.save_requested.emit(self.to_session()))
        self.delete_button.clicked.connect(lambda: self.delete_requested.emit(self.to_session()))
        self._update_process_buttons()

    @staticmethod
    def _make_action_button(text: str, tooltip: str, color: str) -> QPushButton:
        button = QPushButton(text)
        button.setToolTip(tooltip)
        button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        button.setFixedSize(32, 32)
        button.setStyleSheet(f"""
            QPushButton {{
                color: {color};
                border: 1px solid #374151;
                border-radius: 6px;
                background: #111827;
                font-size: 17px;
                font-weight: 900;
            }}
            QPushButton:hover {{
                background: #1f2937;
                border-color: {color};
            }}
            QPushButton:pressed {{
                background: #030712;
            }}
            """)
        return button

    def to_session(self) -> SessionEntry:
        return SessionEntry(
            id=self._session_id,
            name=self.name_edit.text().strip() or _("Untitled session"),
            url=self._url.strip() or "about:blank",
            browser=self._browser.strip() or "chrome",
            profile_path=self._profile_path.strip(),
            proxy_id=self._proxy_id,
            fingerprint_id=self._fingerprint_id,
            proxy_label=self._proxy_label.strip(),
            custom_user_agent="",
            notes=self._notes.strip(),
            window_width=self._window_width,
            window_height=self._window_height,
            status=self._status,
        )

    def set_session(self, session: SessionEntry) -> None:
        self._session_id = session.id
        self.id_label.setText(str(session.id) if session.id is not None else _("new"))
        self._url = session.url
        self._browser = session.browser
        self._profile_path = session.profile_path
        self._proxy_id = session.proxy_id
        self._fingerprint_id = session.fingerprint_id
        self._proxy_label = session.proxy_label
        self._notes = session.notes
        self._window_width = session.window_width
        self._window_height = session.window_height
        self.set_status(session.status)

    def set_status(self, status: str) -> None:
        self._status = status
        self.status_label.setText(_status_label(status))
        self._update_process_buttons()

    def append_process_log(self, message: str) -> None:
        if not message:
            return
        self._process_logs.append(message)
        self._process_logs = self._process_logs[-20:]
        self.status_label.setToolTip("\n".join(self._process_logs))

    def retranslate_ui(self) -> None:
        if self._session_id is None:
            self.id_label.setText(_("new"))
        self.name_edit.setPlaceholderText(_("Name"))
        self.status_label.setText(_status_label(self._status))
        self.open_button.setToolTip(_("Open"))
        self.stop_button.setToolTip(_("Stop"))
        self.settings_button.setToolTip(_("Settings"))
        self.save_button.setToolTip(_("Save"))
        self.delete_button.setToolTip(_("Delete"))

    def set_browser_configs(
        self,
        browser_configs: list[BrowserConfig],
        *,
        selected_key: str | None = None,
    ) -> None:
        self._browser_configs = browser_configs
        if selected_key is not None:
            self._browser = selected_key

    def open_settings_dialog(self) -> None:
        dialog = SessionSettingsDialog(self.to_session(), self.app_service, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        updated = dialog.to_session()
        self._url = updated.url
        self._browser = updated.browser
        self._profile_path = updated.profile_path
        self._proxy_id = updated.proxy_id
        self._fingerprint_id = updated.fingerprint_id
        self._proxy_label = updated.proxy_label
        self._notes = updated.notes
        self._window_width = updated.window_width
        self._window_height = updated.window_height

    def _update_process_buttons(self) -> None:
        is_active = self._status in {"starting", "running"}
        self.open_button.setEnabled(not is_active)
        self.stop_button.setEnabled(is_active)
