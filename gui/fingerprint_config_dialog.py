from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QLabel,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.i18n import _
from app_config import APP_CONFIG
from models.fingerprint_config import FingerprintConfig


class FingerprintConfigDialog(QDialog):
    def __init__(self, config: FingerprintConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(_("Fingerprint settings"))
        self.resize(*APP_CONFIG.gui.fingerprint_settings_size)
        self._config = FingerprintConfig.from_dict(config.to_dict())

        self.hide_automation_check = QCheckBox(_("Hide automation"))
        self.hide_automation_check.setChecked(config.hide_automation)
        self.hide_headless_check = QCheckBox(_("Hide headless"))
        self.hide_headless_check.setChecked(config.hide_headless)
        self.spoof_plugins_check = QCheckBox(_("Spoof plugins"))
        self.spoof_plugins_check.setChecked(config.spoof_plugins)

        self.user_agent_edit = QLineEdit(config.user_agent or "")
        self.user_agent_edit.setPlaceholderText("Mozilla/5.0 ...")

        self.languages_edit = QLineEdit(", ".join(config.spoof_languages))
        self.languages_edit.setPlaceholderText("en-US, en")
        self.locale_edit = QLineEdit(", ".join(config.locale))
        self.locale_edit.setPlaceholderText("en-US, en")

        self.canvas_mode_combo = QComboBox()
        for mode in APP_CONFIG.fingerprint_validation.canvas_modes:
            self.canvas_mode_combo.addItem(mode, mode)
        self.canvas_mode_combo.setCurrentIndex(max(self.canvas_mode_combo.findData(config.canvas_mode), 0))

        self.canvas_noise_spin = QDoubleSpinBox()
        self.canvas_noise_spin.setRange(
            APP_CONFIG.fingerprint_validation.canvas_noise_min,
            APP_CONFIG.fingerprint_validation.canvas_noise_max,
        )
        self.canvas_noise_spin.setSingleStep(0.01)
        self.canvas_noise_spin.setDecimals(3)
        self.canvas_noise_spin.setValue(config.canvas_noise_level)

        self.webgl_vendor_edit = QLineEdit(config.webgl_vendor or "")
        self.webgl_renderer_edit = QLineEdit(config.webgl_renderer or "")

        self.audio_noise_check = QCheckBox(_("Audio noise"))
        self.audio_noise_check.setChecked(config.audio_noise)
        self.font_list_edit = QLineEdit(", ".join(config.font_list))
        self.font_spoof_count_spin = QSpinBox()
        self.font_spoof_count_spin.setRange(
            APP_CONFIG.fingerprint_validation.font_spoof_min,
            APP_CONFIG.fingerprint_validation.font_spoof_max,
        )
        self.font_spoof_count_spin.setValue(config.font_spoof_count)

        self.timezone_edit = QLineEdit(config.timezone or "")
        self.timezone_edit.setPlaceholderText("Europe/Moscow")

        self.geolocation_check = QCheckBox(_("Override geolocation"))
        self.geolocation_check.setChecked(config.geolocation is not None)
        self.latitude_spin = QDoubleSpinBox()
        self.latitude_spin.setRange(-90, 90)
        self.latitude_spin.setDecimals(6)
        self.latitude_spin.setValue(config.geolocation[0] if config.geolocation else 0)
        self.longitude_spin = QDoubleSpinBox()
        self.longitude_spin.setRange(-180, 180)
        self.longitude_spin.setDecimals(6)
        self.longitude_spin.setValue(config.geolocation[1] if config.geolocation else 0)

        self.webrtc_mode_combo = QComboBox()
        for mode in APP_CONFIG.fingerprint_validation.webrtc_modes:
            self.webrtc_mode_combo.addItem(mode, mode)
        self.webrtc_mode_combo.setCurrentIndex(max(self.webrtc_mode_combo.findData(config.webrtc_mode), 0))

        self.hardware_spin = QSpinBox()
        self.hardware_spin.setRange(
            0,
            APP_CONFIG.fingerprint_validation.hardware_concurrency_max,
        )
        self.hardware_spin.setSpecialValueText(_("Browser default"))
        self.hardware_spin.setValue(config.hardware_concurrency or 0)

        self.device_memory_combo = QComboBox()
        self.device_memory_combo.addItem(_("Browser default"), None)
        for value in APP_CONFIG.fingerprint_validation.device_memory_values:
            self.device_memory_combo.addItem(str(value), value)
        self.device_memory_combo.setCurrentIndex(max(self.device_memory_combo.findData(config.device_memory), 0))

        self.platform_combo = QComboBox()
        self.platform_combo.addItem(_("Browser default"), None)
        for platform_name in APP_CONFIG.fingerprint_validation.platforms:
            self.platform_combo.addItem(platform_name, platform_name)
        self.platform_combo.setCurrentIndex(max(self.platform_combo.findData(config.platform), 0))

        self.tls_profile_combo = QComboBox()
        self.tls_profile_combo.addItem(_("No TLS profile"), None)
        for profile_name in APP_CONFIG.fingerprint_validation.tls_profiles:
            self.tls_profile_combo.addItem(profile_name, profile_name)
        self.tls_profile_combo.setCurrentIndex(max(self.tls_profile_combo.findData(config.tls_profile), 0))

        self.spoof_touch_check = QCheckBox(_("Spoof touch support"))
        self.spoof_touch_check.setChecked(config.spoof_touch_support)
        self.spoof_connection_check = QCheckBox(_("Spoof connection"))
        self.spoof_connection_check.setChecked(config.spoof_connection)
        self.spoof_permissions_check = QCheckBox(_("Spoof permissions"))
        self.spoof_permissions_check.setChecked(config.spoof_permissions)
        self.spoof_feature_detection_check = QCheckBox(_("Spoof feature detection"))
        self.spoof_feature_detection_check.setChecked(config.spoof_feature_detection)
        self.hide_adblock_check = QCheckBox(_("Hide adblock signs"))
        self.hide_adblock_check.setChecked(config.hide_adblock_signs)
        self.spoof_battery_check = QCheckBox(_("Spoof battery"))
        self.spoof_battery_check.setChecked(config.spoof_battery)

        self.before_js_edit = QLineEdit(" | ".join(config.custom_js_before_load))
        self.before_js_edit.setPlaceholderText(_("Separate scripts with |"))
        self.after_js_edit = QLineEdit(" | ".join(config.custom_js_after_load))
        self.after_js_edit.setPlaceholderText(_("Separate scripts with |"))

        content = QWidget()
        form = QFormLayout(content)
        self._add_section(form, _("Automation / Identity"))
        form.addRow(self.hide_automation_check)
        form.addRow(self.hide_headless_check)
        form.addRow(self.spoof_plugins_check)

        self._add_section(form, _("User-Agent / Locale"))
        form.addRow(_("User-Agent"), self.user_agent_edit)
        form.addRow(_("Languages"), self.languages_edit)
        form.addRow(_("Locale"), self.locale_edit)

        self._add_section(form, _("Canvas / WebGL"))
        form.addRow(_("Canvas mode"), self.canvas_mode_combo)
        form.addRow(_("Canvas noise"), self.canvas_noise_spin)
        form.addRow(_("WebGL vendor"), self.webgl_vendor_edit)
        form.addRow(_("WebGL renderer"), self.webgl_renderer_edit)

        self._add_section(form, _("Audio / Fonts"))
        form.addRow(self.audio_noise_check)
        form.addRow(_("Font list"), self.font_list_edit)
        form.addRow(_("Fake fonts count"), self.font_spoof_count_spin)

        self._add_section(form, _("Timezone / Geolocation"))
        form.addRow(_("Timezone"), self.timezone_edit)
        form.addRow(self.geolocation_check)
        form.addRow(_("Latitude"), self.latitude_spin)
        form.addRow(_("Longitude"), self.longitude_spin)

        self._add_section(form, _("WebRTC"))
        form.addRow(_("WebRTC mode"), self.webrtc_mode_combo)

        self._add_section(form, _("Hardware / Device"))
        form.addRow(_("Hardware concurrency"), self.hardware_spin)
        form.addRow(_("Device memory"), self.device_memory_combo)
        form.addRow(_("Platform"), self.platform_combo)

        self._add_section(form, _("TLS / Network"))
        form.addRow(_("TLS profile"), self.tls_profile_combo)
        self._add_note(
            form,
            _("TLS profile requires an external proxy or browser network stack support."),
        )

        self._add_section(form, _("Feature Detection"))
        form.addRow(self.spoof_touch_check)
        form.addRow(self.spoof_connection_check)
        form.addRow(self.spoof_permissions_check)
        form.addRow(self.spoof_feature_detection_check)
        form.addRow(self.spoof_battery_check)

        self._add_section(form, _("Content Filter"))
        form.addRow(self.hide_adblock_check)

        self._add_section(form, _("Custom JavaScript"))
        form.addRow(_("JS before load"), self.before_js_edit)
        form.addRow(_("JS after load"), self.after_js_edit)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(content)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(_("Save"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(_("Cancel"))
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(scroll_area, 1)
        layout.addWidget(buttons)

    def _add_section(self, form: QFormLayout, title: str) -> None:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        form.addRow(line)

        label = QLabel(title)
        font = label.font()
        font.setBold(True)
        label.setFont(font)
        form.addRow(label)

    def _add_note(self, form: QFormLayout, text: str) -> None:
        label = QLabel(text)
        label.setWordWrap(True)
        form.addRow("", label)

    def to_config(self) -> FingerprintConfig:
        hardware_concurrency = self.hardware_spin.value() or None
        geolocation = None
        if self.geolocation_check.isChecked():
            geolocation = (self.latitude_spin.value(), self.longitude_spin.value())

        return FingerprintConfig(
            hide_automation=self.hide_automation_check.isChecked(),
            hide_headless=self.hide_headless_check.isChecked(),
            spoof_plugins=self.spoof_plugins_check.isChecked(),
            spoof_languages=_split_csv(self.languages_edit.text()),
            user_agent=self.user_agent_edit.text().strip() or None,
            canvas_mode=str(self.canvas_mode_combo.currentData() or "noise"),
            canvas_noise_level=self.canvas_noise_spin.value(),
            canvas_noise_seed=getattr(self._config, "canvas_noise_seed", None),
            webgl_vendor=self.webgl_vendor_edit.text().strip() or None,
            webgl_renderer=self.webgl_renderer_edit.text().strip() or None,
            audio_noise=self.audio_noise_check.isChecked(),
            font_list=_split_csv(self.font_list_edit.text()),
            font_spoof_count=self.font_spoof_count_spin.value(),
            timezone=self.timezone_edit.text().strip() or None,
            geolocation=geolocation,
            locale=_split_csv(self.locale_edit.text()),
            webrtc_mode=str(self.webrtc_mode_combo.currentData() or "proxy_dns"),
            hardware_concurrency=hardware_concurrency,
            device_memory=self.device_memory_combo.currentData(),
            platform=self.platform_combo.currentData(),
            tls_profile=self.tls_profile_combo.currentData(),
            spoof_touch_support=self.spoof_touch_check.isChecked(),
            spoof_connection=self.spoof_connection_check.isChecked(),
            spoof_permissions=self.spoof_permissions_check.isChecked(),
            spoof_feature_detection=self.spoof_feature_detection_check.isChecked(),
            hide_adblock_signs=self.hide_adblock_check.isChecked(),
            spoof_battery=self.spoof_battery_check.isChecked(),
            custom_js_before_load=_split_pipe(self.before_js_edit.text()),
            custom_js_after_load=_split_pipe(self.after_js_edit.text()),
        ).ensure_canvas_noise_seed()

    def _accept_if_valid(self) -> None:
        errors = self.to_config().validate()
        if errors:
            QMessageBox.critical(self, _("Fingerprint validation error"), "\n".join(errors))
            return
        self.accept()



def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]



def _split_pipe(value: str) -> list[str]:
    return [item.strip() for item in value.split("|") if item.strip()]
