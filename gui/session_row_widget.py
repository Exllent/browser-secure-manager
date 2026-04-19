from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.app_service import AppService
from models.browser_config import BrowserConfig
from models.session_entry import SessionEntry

SESSION_TABLE_COLUMNS = (
    ("id", 64),
    ("Название", 360),
    ("Статус", 110),
    ("Открыть", 72),
    ("Настройки", 92),
    ("Сохранить", 92),
    ("Удалить", 72),
)


class SessionRowWidget(QWidget):
    open_requested = Signal(object)
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
        self._proxy_label = session.proxy_label
        self._custom_user_agent = session.custom_user_agent
        self._notes = session.notes
        self._window_width = session.window_width
        self._window_height = session.window_height

        self.id_label = QLabel(str(session.id or "new"))
        self.id_label.setFixedWidth(48)

        self.name_edit = QLineEdit(session.name)
        self.name_edit.setPlaceholderText("Название")
        self.name_edit.setFixedWidth(SESSION_TABLE_COLUMNS[1][1])
        self._browser_configs = browser_configs

        self.status_label = QLabel(session.status)
        self.status_label.setFixedWidth(SESSION_TABLE_COLUMNS[2][1])

        self.open_button = self._make_action_button("▶", "Открыть", "#1f9d55")
        self.settings_button = self._make_action_button("⚙", "Настройки", "#9ca3af")
        self.save_button = self._make_action_button("✓", "Сохранить", "#60a5fa")
        self.delete_button = self._make_action_button("✖", "Удалить", "#f87171")

        layout = QGridLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)
        widgets = (
            self.id_label,
            self.name_edit,
            self.status_label,
            self.open_button,
            self.settings_button,
            self.save_button,
            self.delete_button,
        )
        for column, (widget, (_label, width)) in enumerate(zip(widgets, SESSION_TABLE_COLUMNS)):
            widget.setFixedWidth(width)
            layout.addWidget(widget, 0, column)
            layout.setColumnMinimumWidth(column, width)

        self.open_button.clicked.connect(lambda: self.open_requested.emit(self.to_session()))
        self.settings_button.clicked.connect(self.open_settings_dialog)
        self.save_button.clicked.connect(lambda: self.save_requested.emit(self.to_session()))
        self.delete_button.clicked.connect(lambda: self.delete_requested.emit(self.to_session()))

    @staticmethod
    def _make_action_button(text: str, tooltip: str, color: str) -> QPushButton:
        button = QPushButton(text)
        button.setToolTip(tooltip)
        button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        button.setFixedSize(32, 32)
        button.setStyleSheet(
            f"""
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
            """
        )
        return button

    def to_session(self) -> SessionEntry:
        return SessionEntry(
            id=self._session_id,
            name=self.name_edit.text().strip() or "Untitled session",
            url=self._url.strip() or "about:blank",
            browser=self._browser.strip() or "chrome",
            profile_path=self._profile_path.strip(),
            proxy_id=self._proxy_id,
            proxy_label=self._proxy_label.strip(),
            custom_user_agent=self._custom_user_agent.strip(),
            notes=self._notes.strip(),
            window_width=self._window_width,
            window_height=self._window_height,
            status=self.status_label.text(),
        )

    def set_session(self, session: SessionEntry) -> None:
        self._session_id = session.id
        self.id_label.setText(str(session.id or "new"))
        self._url = session.url
        self._browser = session.browser
        self._profile_path = session.profile_path
        self._proxy_id = session.proxy_id
        self._proxy_label = session.proxy_label
        self._custom_user_agent = session.custom_user_agent
        self._notes = session.notes
        self._window_width = session.window_width
        self._window_height = session.window_height
        self.set_status(session.status)

    def set_status(self, status: str) -> None:
        self.status_label.setText(status)

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
        self._proxy_label = updated.proxy_label
        self._custom_user_agent = updated.custom_user_agent
        self._notes = updated.notes
        self._window_width = updated.window_width
        self._window_height = updated.window_height


class SessionSettingsDialog(QDialog):
    def __init__(
        self,
        session: SessionEntry,
        app_service: AppService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Настройки записи {session.id or 'new'}")
        self.resize(720, 520)
        self._session = session
        self.app_service = app_service

        self.url_edit = QLineEdit(session.url)
        self.url_edit.setPlaceholderText("https://example.com")

        self.browser_combo = QComboBox()
        self._load_browsers(session.browser)

        self.profile_path_edit = QLineEdit(session.profile_path)
        self.profile_path_edit.setPlaceholderText("profiles/session_<id>")

        self.proxy_combo = QComboBox()
        self._load_proxies(session.proxy_id)

        self.proxy_label_edit = QLineEdit(session.proxy_label)
        self.proxy_label_edit.setPlaceholderText("Свободная заметка по прокси")

        self.user_agent_edit = QTextEdit(session.custom_user_agent)
        self.user_agent_edit.setPlaceholderText("Оставьте пустым, чтобы использовать User-Agent браузера")
        self.user_agent_edit.setMinimumHeight(80)

        self.notes_edit = QTextEdit(session.notes)
        self.notes_edit.setPlaceholderText("Комментарий")
        self.notes_edit.setMinimumHeight(120)

        self.width_spin = QSpinBox()
        self.width_spin.setRange(320, 7680)
        self.width_spin.setValue(session.window_width)

        self.height_spin = QSpinBox()
        self.height_spin.setRange(240, 4320)
        self.height_spin.setValue(session.window_height)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        nav_layout = QHBoxLayout()
        self.general_button = QPushButton("Основное")
        self.profile_button = QPushButton("Профиль")
        self.proxy_button = QPushButton("Прокси")
        self.window_button = QPushButton("Окно")
        self.user_agent_button = QPushButton("User-Agent")
        self.notes_button = QPushButton("Заметки")
        for button in (
            self.general_button,
            self.profile_button,
            self.proxy_button,
            self.window_button,
            self.user_agent_button,
            self.notes_button,
        ):
            nav_layout.addWidget(button)
        nav_layout.addStretch(1)

        self.stack = QStackedWidget()
        self.general_page = self._build_general_page()
        self.profile_page = self._build_profile_page()
        self.proxy_page = self._build_proxy_page()
        self.window_page = self._build_window_page()
        self.user_agent_page = self._build_user_agent_page()
        self.notes_page = self._build_notes_page()
        for page in (
            self.general_page,
            self.profile_page,
            self.proxy_page,
            self.window_page,
            self.user_agent_page,
            self.notes_page,
        ):
            self.stack.addWidget(page)

        self.general_button.clicked.connect(lambda: self.stack.setCurrentWidget(self.general_page))
        self.profile_button.clicked.connect(lambda: self.stack.setCurrentWidget(self.profile_page))
        self.proxy_button.clicked.connect(lambda: self.stack.setCurrentWidget(self.proxy_page))
        self.window_button.clicked.connect(lambda: self.stack.setCurrentWidget(self.window_page))
        self.user_agent_button.clicked.connect(lambda: self.stack.setCurrentWidget(self.user_agent_page))
        self.notes_button.clicked.connect(lambda: self.stack.setCurrentWidget(self.notes_page))

        layout = QVBoxLayout(self)
        layout.addLayout(nav_layout)
        layout.addWidget(self.stack, 1)
        layout.addWidget(buttons)

    def _load_browsers(self, selected_browser_key: str) -> None:
        self.browser_combo.clear()
        for config in self.app_service.get_browser_configs(enabled_only=True):
            self.browser_combo.addItem(config.display_name, config.key)

        if self.browser_combo.count() == 0:
            self.browser_combo.addItem("Chrome / Chromium", "chrome")

        index = self.browser_combo.findData(selected_browser_key)
        if index < 0:
            index = self.browser_combo.findData("chrome")
        self.browser_combo.setCurrentIndex(max(index, 0))

    def _load_proxies(self, selected_proxy_id: int | None) -> None:
        self.proxy_combo.clear()
        self.proxy_combo.addItem("Без прокси", None)
        for proxy in self.app_service.get_proxy_configs(enabled_only=True):
            self.proxy_combo.addItem(proxy.display_name(), proxy.id)

        if selected_proxy_id is None:
            self.proxy_combo.setCurrentIndex(0)
            return

        index = self.proxy_combo.findData(selected_proxy_id)
        self.proxy_combo.setCurrentIndex(max(index, 0))

    def _scroll_page(self, content: QWidget) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(content)
        layout.addWidget(scroll_area, 1)
        return page

    def _build_general_page(self) -> QWidget:
        content = QWidget()
        form = QFormLayout(content)
        form.addRow("Стартовый URL", self.url_edit)
        form.addRow("Браузер", self.browser_combo)
        return self._scroll_page(content)

    def _build_profile_page(self) -> QWidget:
        content = QWidget()
        form = QFormLayout(content)
        form.addRow("Путь профиля", self.profile_path_edit)
        return self._scroll_page(content)

    def _build_proxy_page(self) -> QWidget:
        content = QWidget()
        form = QFormLayout(content)
        form.addRow("Выбранный прокси", self.proxy_combo)
        form.addRow("Заметка", self.proxy_label_edit)
        return self._scroll_page(content)

    def _build_window_page(self) -> QWidget:
        content = QWidget()
        form = QFormLayout(content)
        form.addRow("Ширина", self.width_spin)
        form.addRow("Высота", self.height_spin)
        return self._scroll_page(content)

    def _build_user_agent_page(self) -> QWidget:
        content = QWidget()
        form = QFormLayout(content)
        form.addRow("Custom User-Agent", self.user_agent_edit)
        return self._scroll_page(content)

    def _build_notes_page(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.addWidget(self.notes_edit)
        return self._scroll_page(content)

    def to_session(self) -> SessionEntry:
        return SessionEntry(
            id=self._session.id,
            name=self._session.name,
            url=self.url_edit.text().strip() or "about:blank",
            browser=str(self.browser_combo.currentData() or "chrome"),
            profile_path=self.profile_path_edit.text().strip(),
            proxy_id=self.proxy_combo.currentData(),
            proxy_label=self.proxy_label_edit.text().strip(),
            custom_user_agent=self.user_agent_edit.toPlainText().strip(),
            notes=self.notes_edit.toPlainText().strip(),
            window_width=self.width_spin.value(),
            window_height=self.height_spin.value(),
            status=self._session.status,
        )
