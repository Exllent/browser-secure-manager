from __future__ import annotations

import re

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLineEdit, QPushButton, QWidget

from app.i18n import _
from app_config import APP_CONFIG
from models.browser_config import BrowserConfig


class BrowserConfigRow(QWidget):
    delete_requested = Signal()

    def __init__(self, config: BrowserConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config_id = config.id

        self.enabled_check = QCheckBox()
        self.enabled_check.setChecked(config.enabled)

        self.name_edit = QLineEdit(config.display_name)
        self.name_edit.setPlaceholderText(_("Name"))
        self.name_edit.setMinimumWidth(140)

        self.key_edit = QLineEdit(config.key)
        self.key_edit.setPlaceholderText(_("Key"))
        self.key_edit.setMinimumWidth(110)

        self.type_combo = QComboBox()
        self.type_combo.addItem(_("Chromium-based"), APP_CONFIG.storage.default_browser_type)
        index = self.type_combo.findData(config.normalized_type())
        self.type_combo.setCurrentIndex(max(index, 0))

        self.path_edit = QLineEdit(config.executable_path)
        self.path_edit.setPlaceholderText(_("Executable path"))
        self.path_edit.setMinimumWidth(260)

        self.browse_button = QPushButton(_("Choose"))
        self.delete_button = QPushButton(_("Delete"))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(self.enabled_check)
        layout.addWidget(self.name_edit)
        layout.addWidget(self.key_edit)
        layout.addWidget(self.type_combo)
        layout.addWidget(self.path_edit, 1)
        layout.addWidget(self.browse_button)
        layout.addWidget(self.delete_button)

        self.browse_button.clicked.connect(self.pick_executable)
        self.delete_button.clicked.connect(self.delete_requested.emit)

    def pick_executable(self) -> None:
        path, selected_filter = QFileDialog.getOpenFileName(
            self,
            _("Choose browser executable"),
            self.path_edit.text().strip(),
        )
        if path:
            self.path_edit.setText(path)

    def to_config(self) -> BrowserConfig:
        display_name = self.name_edit.text().strip()
        return BrowserConfig(
            id=self._config_id,
            key=self.key_edit.text().strip() or _make_browser_key(display_name),
            display_name=display_name,
            browser_type=str(self.type_combo.currentData()),
            executable_path=self.path_edit.text().strip(),
            enabled=self.enabled_check.isChecked(),
        )



def _make_browser_key(display_name: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", display_name.strip().lower())
    return key.strip("_") or "browser"
