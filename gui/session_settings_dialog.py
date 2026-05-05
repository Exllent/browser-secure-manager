from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
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
from app.i18n import _
from models.session_entry import SessionEntry


class SessionSettingsDialog(QDialog):
    def __init__(
        self,
        session: SessionEntry,
        app_service: AppService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        session_label = str(session.id) if session.id is not None else _("new")
        self.setWindowTitle(f"{_('Session settings')} {session_label}")
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

        self.fingerprint_combo = QComboBox()
        self._load_fingerprints(session.fingerprint_id)

        self.proxy_label_edit = QLineEdit(session.proxy_label)
        self.proxy_label_edit.setPlaceholderText(_("Proxy note"))

        self.notes_edit = QTextEdit(session.notes)
        self.notes_edit.setPlaceholderText(_("Comment"))
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
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(_("Save"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(_("Cancel"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        nav_layout = QHBoxLayout()
        self.general_button = QPushButton(_("General"))
        self.profile_button = QPushButton(_("Profile"))
        self.proxy_button = QPushButton(_("Proxy"))
        self.fingerprint_button = QPushButton(_("Fingerprint"))
        self.window_button = QPushButton(_("Window"))
        self.notes_button = QPushButton(_("Notes"))
        for button in (
            self.general_button,
            self.profile_button,
            self.proxy_button,
            self.fingerprint_button,
            self.window_button,
            self.notes_button,
        ):
            nav_layout.addWidget(button)
        nav_layout.addStretch(1)

        self.stack = QStackedWidget()
        self.general_page = self._build_general_page()
        self.profile_page = self._build_profile_page()
        self.proxy_page = self._build_proxy_page()
        self.fingerprint_page = self._build_fingerprint_page()
        self.window_page = self._build_window_page()
        self.notes_page = self._build_notes_page()
        for page in (
            self.general_page,
            self.profile_page,
            self.proxy_page,
            self.fingerprint_page,
            self.window_page,
            self.notes_page,
        ):
            self.stack.addWidget(page)

        self.general_button.clicked.connect(lambda: self.stack.setCurrentWidget(self.general_page))
        self.profile_button.clicked.connect(lambda: self.stack.setCurrentWidget(self.profile_page))
        self.proxy_button.clicked.connect(lambda: self.stack.setCurrentWidget(self.proxy_page))
        self.fingerprint_button.clicked.connect(lambda: self.stack.setCurrentWidget(self.fingerprint_page))
        self.window_button.clicked.connect(lambda: self.stack.setCurrentWidget(self.window_page))
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
        self.proxy_combo.addItem(_("No proxy"), None)
        for proxy in self.app_service.get_proxy_configs(enabled_only=True):
            self.proxy_combo.addItem(proxy.display_name(), proxy.id)

        if selected_proxy_id is None:
            self.proxy_combo.setCurrentIndex(0)
            return

        index = self.proxy_combo.findData(selected_proxy_id)
        self.proxy_combo.setCurrentIndex(max(index, 0))

    def _load_fingerprints(self, selected_fingerprint_id: int | None) -> None:
        self.fingerprint_combo.clear()
        self.fingerprint_combo.addItem(_("No fingerprint"), None)
        for profile in self.app_service.get_fingerprint_profiles(enabled_only=True):
            self.fingerprint_combo.addItem(profile.display_name(), profile.id)

        if selected_fingerprint_id is None:
            self.fingerprint_combo.setCurrentIndex(0)
            return

        index = self.fingerprint_combo.findData(selected_fingerprint_id)
        self.fingerprint_combo.setCurrentIndex(max(index, 0))

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
        form.addRow(_("Start URL"), self.url_edit)
        form.addRow(_("Browser"), self.browser_combo)
        return self._scroll_page(content)

    def _build_profile_page(self) -> QWidget:
        content = QWidget()
        form = QFormLayout(content)
        form.addRow(_("Profile path"), self.profile_path_edit)
        return self._scroll_page(content)

    def _build_proxy_page(self) -> QWidget:
        content = QWidget()
        form = QFormLayout(content)
        form.addRow(_("Selected proxy"), self.proxy_combo)
        form.addRow(_("Proxy note"), self.proxy_label_edit)
        return self._scroll_page(content)

    def _build_fingerprint_page(self) -> QWidget:
        content = QWidget()
        form = QFormLayout(content)
        form.addRow(_("Selected fingerprint"), self.fingerprint_combo)
        note = QLabel(_("Create and edit fingerprints in Application settings."))
        note.setWordWrap(True)
        form.addRow("", note)
        return self._scroll_page(content)

    def _build_window_page(self) -> QWidget:
        content = QWidget()
        form = QFormLayout(content)
        form.addRow(_("Width"), self.width_spin)
        form.addRow(_("Height"), self.height_spin)
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
            fingerprint_id=self.fingerprint_combo.currentData(),
            proxy_label=self.proxy_label_edit.text().strip(),
            custom_user_agent="",
            notes=self.notes_edit.toPlainText().strip(),
            window_width=self.width_spin.value(),
            window_height=self.height_spin.value(),
            status=self._session.status,
        )
