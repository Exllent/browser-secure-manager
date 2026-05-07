from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QWidget,
)

from app.i18n import _
from models.fingerprint_config import FingerprintConfig
from models.fingerprint_generator import generate_fingerprint_profile
from models.fingerprint_profile import FingerprintProfile

from .fingerprint_config_dialog import FingerprintConfigDialog


class FingerprintProfileRow(QWidget):
    delete_requested = Signal()

    def __init__(self, profile: FingerprintProfile, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._profile_id = profile.id
        self._config = FingerprintConfig.from_dict(profile.config.to_dict())

        self.selected_check = QCheckBox(_("Selected"))
        self.selected_check.setToolTip(_("Selected"))

        self.enabled_check = QCheckBox(_("Enabled"))
        self.enabled_check.setChecked(profile.enabled)
        self.enabled_check.setToolTip(_("Enabled"))

        self.name_edit = QLineEdit(profile.name)
        self.name_edit.setPlaceholderText(_("Name"))
        self.name_edit.setMinimumWidth(180)

        self.generate_button = QPushButton(_("Generate"))
        self.edit_button = QPushButton(_("Edit"))
        self.delete_button = QPushButton(_("Delete"))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(self.selected_check)
        layout.addWidget(self.enabled_check)
        layout.addWidget(self.name_edit, 1)
        layout.addWidget(self.generate_button)
        layout.addWidget(self.edit_button)
        layout.addWidget(self.delete_button)

        self.generate_button.clicked.connect(self.generate_profile)
        self.edit_button.clicked.connect(self.edit_profile)
        self.delete_button.clicked.connect(self.delete_requested.emit)

    def generate_profile(self) -> None:
        profile = generate_fingerprint_profile()
        self._config = profile.config
        if not self.name_edit.text().strip():
            self.name_edit.setText(profile.name)

    def edit_profile(self) -> None:
        dialog = FingerprintConfigDialog(self._config, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        self._config = dialog.to_config()

    def to_profile(self) -> FingerprintProfile:
        return FingerprintProfile(
            id=self._profile_id,
            name=self.name_edit.text().strip(),
            config=FingerprintConfig.from_dict(
                self._config.to_dict(),
            ),
            enabled=self.enabled_check.isChecked(),
        )

    def set_selected(self, selected: bool) -> None:
        self.selected_check.setChecked(selected)

    def is_selected(self) -> bool:
        return self.selected_check.isChecked()
