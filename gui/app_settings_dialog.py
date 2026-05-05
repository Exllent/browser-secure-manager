from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, QThreadPool
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListView,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.app_service import AppService
from app.i18n import _, load_language
from models.browser_config import BrowserConfig
from models.fingerprint_config import FingerprintConfig
from models.fingerprint_generator import generate_fingerprint_profile
from models.fingerprint_profile import FingerprintProfile
from models.proxy_config import ProxyConfig

from .browser_config_row import BrowserConfigRow, _make_browser_key
from .fingerprint_config_dialog import FingerprintConfigDialog, _split_csv, _split_pipe
from .fingerprint_profile_row import FingerprintProfileRow
from .proxy_config_row import ProxyConfigRow, ProxyTestSignals, ProxyTestWorker
from .proxy_csv import _csv_value, _normalize_csv_protocol, parse_proxy_csv


class AppSettingsDialog(QDialog):
    def __init__(self, app_service: AppService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(_("Application settings"))
        self.resize(980, 620)

        self.app_service = app_service
        self.browser_rows: list[BrowserConfigRow] = []
        self.proxy_rows: list[ProxyConfigRow] = []
        self.fingerprint_rows: list[FingerprintProfileRow] = []
        self.deleted_browser_ids: list[int] = []
        self.deleted_proxy_ids: list[int] = []
        self.deleted_fingerprint_ids: list[int] = []
        self.thread_pool = QThreadPool.globalInstance()
        self.thread_pool.setMaxThreadCount(32)

        self.general_button = QPushButton(_("General"))
        self.browsers_button = QPushButton(_("Browsers"))
        self.proxies_button = QPushButton(_("Proxies"))
        self.fingerprints_button = QPushButton(_("Fingerprints"))
        self.language_button = QPushButton(_("Language"))
        nav_layout = QHBoxLayout()
        nav_layout.addWidget(self.general_button)
        nav_layout.addWidget(self.browsers_button)
        nav_layout.addWidget(self.proxies_button)
        nav_layout.addWidget(self.fingerprints_button)
        nav_layout.addWidget(self.language_button)
        nav_layout.addStretch(1)

        self.stack = QStackedWidget()
        self.general_page = self._build_general_page()
        self.browser_page = self._build_browser_page()
        self.proxy_page = self._build_proxy_page()
        self.fingerprint_page = self._build_fingerprint_page()
        self.language_page = self._build_language_page()
        self.stack.addWidget(self.general_page)
        self.stack.addWidget(self.browser_page)
        self.stack.addWidget(self.proxy_page)
        self.stack.addWidget(self.fingerprint_page)
        self.stack.addWidget(self.language_page)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(_("Save"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(_("Cancel"))

        layout = QVBoxLayout(self)
        layout.addLayout(nav_layout)
        layout.addWidget(self.stack, 1)
        layout.addWidget(buttons)

        self.general_button.clicked.connect(lambda: self.stack.setCurrentWidget(self.general_page))
        self.browsers_button.clicked.connect(lambda: self.stack.setCurrentWidget(self.browser_page))
        self.proxies_button.clicked.connect(lambda: self.stack.setCurrentWidget(self.proxy_page))
        self.fingerprints_button.clicked.connect(lambda: self.stack.setCurrentWidget(self.fingerprint_page))
        self.language_button.clicked.connect(lambda: self.stack.setCurrentWidget(self.language_page))
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)

        self.load()

    def _build_general_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.confirm_before_delete_check = QCheckBox(_("Ask before deleting"))
        self.confirm_before_delete_check.setChecked(self.app_service.confirm_before_delete())
        layout.addWidget(self.confirm_before_delete_check)
        layout.addStretch(1)
        return page

    def _build_browser_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        self.scan_browsers_button = QPushButton(_("Find browsers"))
        self.add_browser_button = QPushButton(_("Add manually"))
        top_layout = QHBoxLayout()
        top_layout.addWidget(self.scan_browsers_button)
        top_layout.addWidget(self.add_browser_button)
        top_layout.addStretch(1)

        self.browser_rows_container = QWidget()
        self.browser_rows_layout = QVBoxLayout(self.browser_rows_container)
        self.browser_rows_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.browser_rows_container)

        layout.addLayout(top_layout)
        layout.addWidget(scroll_area, 1)

        self.scan_browsers_button.clicked.connect(self.scan_browsers)
        self.add_browser_button.clicked.connect(self.add_manual_browser)
        return page

    def _build_proxy_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        self.add_proxy_button = QPushButton(_("Add proxy"))
        self.import_proxy_csv_button = QPushButton(_("Load CSV"))
        self.test_all_proxies_button = QPushButton(_("Test all"))
        self.select_all_proxies_button = QPushButton(_("Select all"))
        self.clear_all_proxies_button = QPushButton(_("Clear all"))
        self.delete_error_proxies_button = QPushButton(_("Remove errors"))
        self.delete_slow_proxies_button = QPushButton(_("Remove ping > 500"))
        top_layout = QHBoxLayout()
        top_layout.addWidget(self.add_proxy_button)
        top_layout.addWidget(self.import_proxy_csv_button)
        top_layout.addWidget(self.test_all_proxies_button)
        top_layout.addWidget(self.select_all_proxies_button)
        top_layout.addWidget(self.clear_all_proxies_button)
        top_layout.addWidget(self.delete_error_proxies_button)
        top_layout.addWidget(self.delete_slow_proxies_button)
        top_layout.addStretch(1)

        self.proxy_rows_container = QWidget()
        self.proxy_rows_layout = QVBoxLayout(self.proxy_rows_container)
        self.proxy_rows_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.proxy_rows_container)

        layout.addLayout(top_layout)
        layout.addWidget(scroll_area, 1)

        self.add_proxy_button.clicked.connect(self.add_proxy)
        self.import_proxy_csv_button.clicked.connect(self.import_proxy_csv)
        self.test_all_proxies_button.clicked.connect(self.test_all_proxies)
        self.select_all_proxies_button.clicked.connect(self.select_all_proxies)
        self.clear_all_proxies_button.clicked.connect(self.clear_all_proxies)
        self.delete_error_proxies_button.clicked.connect(self.delete_error_proxies)
        self.delete_slow_proxies_button.clicked.connect(self.delete_slow_proxies)
        self._update_proxy_cleanup_buttons()
        return page

    def _build_fingerprint_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        self.add_fingerprint_button = QPushButton(_("Add fingerprint"))
        self.generate_fingerprint_button = QPushButton(_("Generate fingerprint"))
        self.select_all_fingerprints_button = QPushButton(_("Select all"))
        self.clear_all_fingerprints_button = QPushButton(_("Clear all"))
        self.delete_selected_fingerprints_button = QPushButton(_("Delete selected"))
        top_layout = QHBoxLayout()
        top_layout.addWidget(self.add_fingerprint_button)
        top_layout.addWidget(self.generate_fingerprint_button)
        top_layout.addWidget(self.select_all_fingerprints_button)
        top_layout.addWidget(self.clear_all_fingerprints_button)
        top_layout.addWidget(self.delete_selected_fingerprints_button)
        top_layout.addStretch(1)

        self.fingerprint_rows_container = QWidget()
        self.fingerprint_rows_layout = QVBoxLayout(self.fingerprint_rows_container)
        self.fingerprint_rows_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.fingerprint_rows_container)

        layout.addLayout(top_layout)
        layout.addWidget(scroll_area, 1)

        self.add_fingerprint_button.clicked.connect(self.add_fingerprint)
        self.generate_fingerprint_button.clicked.connect(self.generate_fingerprint)
        self.select_all_fingerprints_button.clicked.connect(self.select_all_fingerprints)
        self.clear_all_fingerprints_button.clicked.connect(self.clear_all_fingerprints)
        self.delete_selected_fingerprints_button.clicked.connect(self.delete_selected_fingerprints)
        return page

    def _build_language_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.language_combo = QComboBox()
        self.language_combo.setStyleSheet("QComboBox { combobox-popup: 0; }")
        self.language_combo.setView(QListView())
        self.language_combo.setMaxVisibleItems(8)
        self.language_combo.setMinimumContentsLength(18)
        self.language_combo.view().setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.language_combo.view().setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.language_combo.view().setUniformItemSizes(True)
        self.language_combo.view().setMinimumHeight(216)
        self.language_combo.view().setMaximumHeight(216)
        self.language_combo.view().setBaseSize(QSize(0, 216))
        self.language_combo.addItem("English", "en")
        self.language_combo.addItem("Русский", "ru")
        language = self.app_service.get_setting("language", "en")
        index = self.language_combo.findData(language)
        self.language_combo.setCurrentIndex(max(index, 0))
        layout.addWidget(self.language_combo)
        self.language_note_label = QLabel(_("Language is applied after saving."))
        layout.addWidget(self.language_note_label)
        layout.addStretch(1)
        return page

    def load(self) -> None:
        self._clear_browser_rows()
        self._clear_proxy_rows()
        self._clear_fingerprint_rows()
        for config in self.app_service.get_browser_configs():
            self._add_browser_row(config)
        for proxy in self.app_service.get_proxy_configs():
            self._add_proxy_row(proxy)
        for profile in self.app_service.get_fingerprint_profiles():
            self._add_fingerprint_row(profile)

    def scan_browsers(self) -> None:
        discovered = self.app_service.discover_installed_browsers()
        if not discovered:
            QMessageBox.information(self, _("Find browsers"), _("No browsers were detected automatically."))
            return

        existing_paths = {row.to_config().executable_path for row in self.browser_rows}
        existing_keys = {row.to_config().key for row in self.browser_rows}
        added = 0

        for config in discovered:
            if config.executable_path in existing_paths:
                continue
            if config.key in existing_keys:
                config.key = self._unique_browser_key(config.key)
            self._add_browser_row(config)
            existing_paths.add(config.executable_path)
            existing_keys.add(config.key)
            added += 1

        QMessageBox.information(self, _("Find browsers"), _("Browsers added: {count}").format(count=added))

    def add_manual_browser(self) -> None:
        key = self._unique_browser_key("browser")
        self._add_browser_row(
            BrowserConfig(
                id=None,
                key=key,
                display_name="New browser",
                browser_type="chromium",
                executable_path="",
                enabled=True,
            )
        )

    def add_proxy(self) -> None:
        self._add_proxy_row(
            ProxyConfig(
                id=None,
                label="New proxy",
                host="",
                port=8080,
                proxy_type="socks5",
                username="",
                password="",
                enabled=True,
            )
        )

    def add_fingerprint(self) -> None:
        self._add_fingerprint_row(
            FingerprintProfile(
                id=None,
                name=self._unique_fingerprint_name(_("New fingerprint")),
                config=FingerprintConfig(),
                enabled=True,
            )
        )

    def generate_fingerprint(self) -> None:
        profile = generate_fingerprint_profile(self._unique_fingerprint_name(_("Generated fingerprint")))
        self._add_fingerprint_row(profile)

    def import_proxy_csv(self) -> None:
        path, selected_filter = QFileDialog.getOpenFileName(
            self,
            _("Choose proxy CSV file"),
            "",
            "CSV files (*.csv);;All files (*)",
        )
        if not path:
            return

        try:
            proxies = parse_proxy_csv(Path(path))
        except Exception as exc:
            QMessageBox.critical(self, _("CSV import error"), str(exc))
            return

        existing = {
            (row.to_config().host, row.to_config().port, row.to_config().normalized_type())
            for row in self.proxy_rows
        }
        added = 0
        imported_rows: list[ProxyConfigRow] = []
        for proxy in proxies:
            key = (proxy.host, proxy.port, proxy.normalized_type())
            if key in existing:
                continue
            imported_rows.append(self._add_proxy_row(proxy))
            existing.add(key)
            added += 1

        for row in imported_rows:
            row.test_proxy()

        QMessageBox.information(
            self,
            _("CSV import"),
            _("Added proxies: {count}. Tests started.").format(count=added),
        )

    def test_all_proxies(self) -> None:
        for row in self.proxy_rows:
            row.test_proxy()
        self._update_proxy_cleanup_buttons()

    def select_all_proxies(self) -> None:
        for row in self.proxy_rows:
            row.set_checked(True)

    def clear_all_proxies(self) -> None:
        for row in self.proxy_rows:
            row.set_checked(False)

    def delete_error_proxies(self) -> None:
        rows = [row for row in self.proxy_rows if row.has_test_error()]
        if rows and not self._confirm_delete_if_needed(
            _("Delete proxies"),
            _("Are you sure you want to delete selected proxies?"),
        ):
            return
        self._delete_proxy_rows(rows)
        QMessageBox.information(
            self,
            _("Proxies"),
            _("Proxies with errors removed: {count}").format(count=len(rows)),
        )

    def delete_slow_proxies(self) -> None:
        rows = [row for row in self.proxy_rows if row.has_ping_greater_than(500)]
        if rows and not self._confirm_delete_if_needed(
            _("Delete proxies"),
            _("Are you sure you want to delete selected proxies?"),
        ):
            return
        self._delete_proxy_rows(rows)
        QMessageBox.information(
            self,
            _("Proxies"),
            _("Proxies with ping > 500 removed: {count}").format(count=len(rows)),
        )

    def save(self) -> None:
        try:
            for config_id in self.deleted_browser_ids:
                self.app_service.delete_browser_config(config_id)
            for proxy_id in self.deleted_proxy_ids:
                self.app_service.delete_proxy_config(proxy_id)
            for fingerprint_id in self.deleted_fingerprint_ids:
                self.app_service.delete_fingerprint_profile(fingerprint_id)

            for row in self.browser_rows:
                config = row.to_config()
                if not config.display_name.strip():
                    raise ValueError(_("Every browser must have a name."))
                config.key = config.key.strip() or self.app_service.make_browser_key(config.display_name)
                self.app_service.save_browser_config(config)

            for row in self.proxy_rows:
                proxy = row.to_config()
                if not proxy.host.strip():
                    raise ValueError(_("Every proxy must have a host or IP."))
                if proxy.port <= 0:
                    raise ValueError(_("Every proxy must have a port."))
                self.app_service.save_proxy_config(proxy)

            for row in self.fingerprint_rows:
                profile = row.to_profile()
                if not profile.name.strip():
                    raise ValueError(_("Every fingerprint must have a name."))
                self.app_service.save_fingerprint_profile(profile)

            language = str(self.language_combo.currentData() or "en")
            self.app_service.set_setting("language", language)
            self.app_service.set_setting(
                "confirm_before_delete",
                "1" if self.confirm_before_delete_check.isChecked() else "0",
            )
            load_language(language)
        except Exception as exc:
            QMessageBox.critical(self, _("Settings save error"), str(exc))
            return

        self.accept()

    def _add_browser_row(self, config: BrowserConfig) -> None:
        row = BrowserConfigRow(config)
        row.delete_requested.connect(lambda widget=row: self._delete_browser_row(widget))
        self.browser_rows.append(row)
        self.browser_rows_layout.addWidget(row)

    def _delete_browser_row(self, row: "BrowserConfigRow") -> None:
        if not self._confirm_delete_if_needed(
            _("Delete browser"),
            _("Are you sure you want to delete this browser?"),
        ):
            return
        config = row.to_config()
        if config.id is not None:
            self.deleted_browser_ids.append(config.id)
        self.browser_rows.remove(row)
        self.browser_rows_layout.removeWidget(row)
        row.deleteLater()

    def _add_proxy_row(self, proxy: ProxyConfig) -> "ProxyConfigRow":
        row = ProxyConfigRow(proxy, self.app_service)
        row.delete_requested.connect(lambda widget=row: self._delete_proxy_row(widget))
        row.test_state_changed.connect(self._update_proxy_cleanup_buttons)
        self.proxy_rows.append(row)
        self.proxy_rows_layout.addWidget(row)
        self._renumber_proxy_rows()
        self._update_proxy_cleanup_buttons()
        return row

    def _delete_proxy_row(self, row: "ProxyConfigRow") -> None:
        if not self._confirm_delete_if_needed(
            _("Delete proxy"),
            _("Are you sure you want to delete this proxy?"),
        ):
            return
        row.mark_deleted()
        proxy = row.to_config()
        if proxy.id is not None:
            self.deleted_proxy_ids.append(proxy.id)
        self.proxy_rows.remove(row)
        self.proxy_rows_layout.removeWidget(row)
        row.deleteLater()
        self._renumber_proxy_rows()
        self._update_proxy_cleanup_buttons()

    def _add_fingerprint_row(self, profile: FingerprintProfile) -> "FingerprintProfileRow":
        row = FingerprintProfileRow(profile)
        row.delete_requested.connect(lambda widget=row: self._delete_fingerprint_row(widget))
        self.fingerprint_rows.append(row)
        self.fingerprint_rows_layout.addWidget(row)
        return row

    def _delete_fingerprint_row(self, row: "FingerprintProfileRow") -> None:
        if not self._confirm_delete_if_needed(
            _("Delete fingerprint"),
            _("Are you sure you want to delete this fingerprint?"),
        ):
            return
        profile = row.to_profile()
        if profile.id is not None:
            self.deleted_fingerprint_ids.append(profile.id)
        self.fingerprint_rows.remove(row)
        self.fingerprint_rows_layout.removeWidget(row)
        row.deleteLater()

    def select_all_fingerprints(self) -> None:
        for row in self.fingerprint_rows:
            row.set_selected(True)

    def clear_all_fingerprints(self) -> None:
        for row in self.fingerprint_rows:
            row.set_selected(False)

    def delete_selected_fingerprints(self) -> None:
        rows = [row for row in self.fingerprint_rows if row.is_selected()]
        if not rows:
            return
        if not self._confirm_delete_if_needed(
            _("Delete fingerprints"),
            _("Are you sure you want to delete selected fingerprints?"),
        ):
            return
        for row in list(rows):
            if row in self.fingerprint_rows:
                self._delete_fingerprint_row_without_confirmation(row)

    def _delete_fingerprint_row_without_confirmation(self, row: "FingerprintProfileRow") -> None:
        profile = row.to_profile()
        if profile.id is not None:
            self.deleted_fingerprint_ids.append(profile.id)
        self.fingerprint_rows.remove(row)
        self.fingerprint_rows_layout.removeWidget(row)
        row.deleteLater()

    def _delete_proxy_rows(self, rows: list["ProxyConfigRow"]) -> None:
        for row in list(rows):
            if row in self.proxy_rows:
                self._delete_proxy_row_without_confirmation(row)

    def _delete_proxy_row_without_confirmation(self, row: "ProxyConfigRow") -> None:
        row.mark_deleted()
        proxy = row.to_config()
        if proxy.id is not None:
            self.deleted_proxy_ids.append(proxy.id)
        self.proxy_rows.remove(row)
        self.proxy_rows_layout.removeWidget(row)
        row.deleteLater()
        self._renumber_proxy_rows()
        self._update_proxy_cleanup_buttons()

    def _clear_browser_rows(self) -> None:
        while self.browser_rows_layout.count():
            item = self.browser_rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.browser_rows.clear()

    def _clear_proxy_rows(self) -> None:
        while self.proxy_rows_layout.count():
            item = self.proxy_rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.proxy_rows.clear()
        self._update_proxy_cleanup_buttons()

    def _clear_fingerprint_rows(self) -> None:
        while self.fingerprint_rows_layout.count():
            item = self.fingerprint_rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.fingerprint_rows.clear()

    def _renumber_proxy_rows(self) -> None:
        for index, row in enumerate(self.proxy_rows, start=1):
            row.set_row_number(index)

    def _update_proxy_cleanup_buttons(self) -> None:
        if not hasattr(self, "delete_error_proxies_button"):
            return
        has_running_tests = any(row.is_test_running() for row in self.proxy_rows)
        self.delete_error_proxies_button.setEnabled(not has_running_tests)
        self.delete_slow_proxies_button.setEnabled(not has_running_tests)

    def _unique_browser_key(self, base_key: str) -> str:
        existing = {row.to_config().key for row in self.browser_rows}
        key = base_key
        index = 2
        while key in existing:
            key = f"{base_key}_{index}"
            index += 1
        return key

    def _unique_fingerprint_name(self, base_name: str) -> str:
        existing = {row.to_profile().name for row in self.fingerprint_rows}
        name = base_name
        index = 2
        while name in existing:
            name = f"{base_name} {index}"
            index += 1
        return name

    def _confirm_delete_if_needed(self, title: str, text: str) -> bool:
        if not self.confirm_before_delete_check.isChecked():
            return True
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setText(text)
        box.setIcon(QMessageBox.Icon.Question)
        yes_button = box.addButton(_("Yes"), QMessageBox.ButtonRole.YesRole)
        no_button = box.addButton(_("No"), QMessageBox.ButtonRole.NoRole)
        box.setDefaultButton(no_button)
        box.exec()
        return box.clickedButton() == yes_button
