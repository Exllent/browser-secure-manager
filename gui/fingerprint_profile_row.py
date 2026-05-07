from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.i18n import _
from models.fingerprint_config import FingerprintConfig
from models.fingerprint_generator import generate_fingerprint_profile
from models.fingerprint_profile import FingerprintProfile
from models.fingerprint_summary import build_fingerprint_summary_sections

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
        self.info_button = QPushButton(_("Info"))
        self.edit_button = QPushButton(_("Edit"))
        self.delete_button = QPushButton(_("Delete"))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(self.selected_check)
        layout.addWidget(self.enabled_check)
        layout.addWidget(self.name_edit, 1)
        layout.addWidget(self.generate_button)
        layout.addWidget(self.info_button)
        layout.addWidget(self.edit_button)
        layout.addWidget(self.delete_button)

        self.generate_button.clicked.connect(self.generate_profile)
        self.info_button.clicked.connect(self.show_info)
        self.edit_button.clicked.connect(self.edit_profile)
        self.delete_button.clicked.connect(self.delete_requested.emit)

    def generate_profile(self) -> None:
        profile = generate_fingerprint_profile()
        self._config = profile.config
        self.name_edit.setText(profile.name)

    def edit_profile(self) -> None:
        dialog = FingerprintConfigDialog(self._config, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        self._config = dialog.to_config()

    def show_info(self) -> None:
        dialog = FingerprintInfoDialog(self.to_profile(), self)
        dialog.exec()

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


class FingerprintInfoDialog(QDialog):
    def __init__(self, profile: FingerprintProfile, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(_("Fingerprint information"))
        self.resize(720, 620)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(8, 8, 8, 8)

        for section in build_fingerprint_summary_sections(profile):
            group = QGroupBox(_(section.title))
            form = QFormLayout(group)
            form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
            for label, value in section.rows:
                value_label = QLabel(value)
                value_label.setWordWrap(True)
                value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                form.addRow(_(label), value_label)
            content_layout.addWidget(group)

        content_layout.addStretch(1)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(content)

        close_button = QPushButton(_("Close"))
        close_button.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(scroll_area, 1)
        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)
