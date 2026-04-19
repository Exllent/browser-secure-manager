from __future__ import annotations

import csv
from pathlib import Path
import re

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.app_service import AppService
from models.browser_config import BrowserConfig
from models.proxy_config import ProxyConfig


class AppSettingsDialog(QDialog):
    def __init__(self, app_service: AppService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Настройки программы")
        self.resize(980, 620)

        self.app_service = app_service
        self.browser_rows: list[BrowserConfigRow] = []
        self.proxy_rows: list[ProxyConfigRow] = []
        self.deleted_browser_ids: list[int] = []
        self.deleted_proxy_ids: list[int] = []
        self.thread_pool = QThreadPool.globalInstance()
        self.thread_pool.setMaxThreadCount(32)

        self.browsers_button = QPushButton("Браузеры")
        self.proxies_button = QPushButton("Прокси")
        nav_layout = QHBoxLayout()
        nav_layout.addWidget(self.browsers_button)
        nav_layout.addWidget(self.proxies_button)
        nav_layout.addStretch(1)

        self.stack = QStackedWidget()
        self.browser_page = self._build_browser_page()
        self.proxy_page = self._build_proxy_page()
        self.stack.addWidget(self.browser_page)
        self.stack.addWidget(self.proxy_page)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )

        layout = QVBoxLayout(self)
        layout.addLayout(nav_layout)
        layout.addWidget(self.stack, 1)
        layout.addWidget(buttons)

        self.browsers_button.clicked.connect(lambda: self.stack.setCurrentWidget(self.browser_page))
        self.proxies_button.clicked.connect(lambda: self.stack.setCurrentWidget(self.proxy_page))
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)

        self.load()

    def _build_browser_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        self.scan_browsers_button = QPushButton("Найти браузеры")
        self.add_browser_button = QPushButton("Добавить вручную")
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

        self.add_proxy_button = QPushButton("Добавить прокси")
        self.import_proxy_csv_button = QPushButton("Загрузить CSV")
        self.test_all_proxies_button = QPushButton("Тестировать все")
        self.select_all_proxies_button = QPushButton("Выбрать всё")
        self.clear_all_proxies_button = QPushButton("Снять всё")
        self.delete_error_proxies_button = QPushButton("Удалить с ошибками")
        self.delete_slow_proxies_button = QPushButton("Удалить ping > 500")
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

    def load(self) -> None:
        self._clear_browser_rows()
        self._clear_proxy_rows()
        for config in self.app_service.get_browser_configs():
            self._add_browser_row(config)
        for proxy in self.app_service.get_proxy_configs():
            self._add_proxy_row(proxy)

    def scan_browsers(self) -> None:
        discovered = self.app_service.discover_installed_browsers()
        if not discovered:
            QMessageBox.information(self, "Поиск браузеров", "Браузеры не найдены автоматически.")
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

        QMessageBox.information(self, "Поиск браузеров", f"Добавлено браузеров: {added}")

    def add_manual_browser(self) -> None:
        key = self._unique_browser_key("browser")
        self._add_browser_row(
            BrowserConfig(
                id=None,
                key=key,
                display_name="Новый браузер",
                browser_type="chromium",
                executable_path="",
                enabled=True,
            )
        )

    def add_proxy(self) -> None:
        self._add_proxy_row(
            ProxyConfig(
                id=None,
                label="Новый прокси",
                host="",
                port=8080,
                proxy_type="socks5",
                username="",
                password="",
                enabled=True,
            )
        )

    def import_proxy_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите CSV со списком прокси",
            "",
            "CSV files (*.csv);;All files (*)",
        )
        if not path:
            return

        try:
            proxies = parse_proxy_csv(Path(path))
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка импорта CSV", str(exc))
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

        QMessageBox.information(self, "Импорт CSV", f"Добавлено прокси: {added}. Тесты запущены.")

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
        self._delete_proxy_rows(rows)
        QMessageBox.information(self, "Прокси", f"Удалено прокси с ошибками: {len(rows)}")

    def delete_slow_proxies(self) -> None:
        rows = [row for row in self.proxy_rows if row.has_ping_greater_than(500)]
        self._delete_proxy_rows(rows)
        QMessageBox.information(self, "Прокси", f"Удалено прокси с ping > 500: {len(rows)}")

    def save(self) -> None:
        try:
            for config_id in self.deleted_browser_ids:
                self.app_service.delete_browser_config(config_id)
            for proxy_id in self.deleted_proxy_ids:
                self.app_service.delete_proxy_config(proxy_id)

            for row in self.browser_rows:
                config = row.to_config()
                if not config.display_name.strip():
                    raise ValueError("У каждого браузера должно быть название.")
                config.key = config.key.strip() or self.app_service.make_browser_key(config.display_name)
                self.app_service.save_browser_config(config)

            for row in self.proxy_rows:
                proxy = row.to_config()
                if not proxy.host.strip():
                    raise ValueError("У каждого прокси должен быть host или IP.")
                if proxy.port <= 0:
                    raise ValueError("У каждого прокси должен быть port.")
                self.app_service.save_proxy_config(proxy)
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка сохранения настроек", str(exc))
            return

        self.accept()

    def _add_browser_row(self, config: BrowserConfig) -> None:
        row = BrowserConfigRow(config)
        row.delete_requested.connect(lambda widget=row: self._delete_browser_row(widget))
        self.browser_rows.append(row)
        self.browser_rows_layout.addWidget(row)

    def _delete_browser_row(self, row: "BrowserConfigRow") -> None:
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
        row.mark_deleted()
        proxy = row.to_config()
        if proxy.id is not None:
            self.deleted_proxy_ids.append(proxy.id)
        self.proxy_rows.remove(row)
        self.proxy_rows_layout.removeWidget(row)
        row.deleteLater()
        self._renumber_proxy_rows()
        self._update_proxy_cleanup_buttons()

    def _delete_proxy_rows(self, rows: list["ProxyConfigRow"]) -> None:
        for row in list(rows):
            if row in self.proxy_rows:
                self._delete_proxy_row(row)

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


class BrowserConfigRow(QWidget):
    delete_requested = Signal()

    def __init__(self, config: BrowserConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config_id = config.id

        self.enabled_check = QCheckBox()
        self.enabled_check.setChecked(config.enabled)

        self.name_edit = QLineEdit(config.display_name)
        self.name_edit.setPlaceholderText("Название")
        self.name_edit.setMinimumWidth(140)

        self.key_edit = QLineEdit(config.key)
        self.key_edit.setPlaceholderText("key")
        self.key_edit.setMinimumWidth(110)

        self.type_combo = QComboBox()
        self.type_combo.addItem("Chromium-based", "chromium")
        self.type_combo.addItem("Firefox", "firefox")
        self.type_combo.addItem("Safari", "safari")
        index = self.type_combo.findData(config.normalized_type())
        self.type_combo.setCurrentIndex(max(index, 0))

        self.path_edit = QLineEdit(config.executable_path)
        self.path_edit.setPlaceholderText("Путь к исполняемому файлу")
        self.path_edit.setMinimumWidth(260)

        self.browse_button = QPushButton("Выбрать")
        self.delete_button = QPushButton("Удалить")

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
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите исполняемый файл браузера",
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


class ProxyTestSignals(QObject):
    finished = Signal(int, object)


class ProxyTestWorker(QRunnable):
    def __init__(self, generation: int, proxy: ProxyConfig, app_service: AppService) -> None:
        super().__init__()
        self.generation = generation
        self.proxy = proxy
        self.app_service = app_service
        self.signals = ProxyTestSignals()

    @Slot()
    def run(self) -> None:
        result = self.app_service.test_proxy(self.proxy)
        self.signals.finished.emit(self.generation, result)


class ProxyConfigRow(QWidget):
    delete_requested = Signal()
    test_state_changed = Signal()

    def __init__(
        self,
        proxy: ProxyConfig,
        app_service: AppService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.app_service = app_service
        self._proxy_id = proxy.id
        self._test_generation = 0
        self._deleted = False
        self._last_test_ok: bool | None = None
        self._last_ping_ms: int | None = None
        self._test_running = False

        self.number_label = QLineEdit()
        self.number_label.setReadOnly(True)
        self.number_label.setFixedWidth(42)
        self.number_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.enabled_check = QCheckBox()
        self.enabled_check.setChecked(proxy.enabled)

        self.label_edit = QLineEdit(proxy.label)
        self.label_edit.setPlaceholderText("Название")
        self.label_edit.setMinimumWidth(130)

        self.host_edit = QLineEdit(proxy.host)
        self.host_edit.setPlaceholderText("Host или IP")
        self.host_edit.setMinimumWidth(150)

        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(proxy.port)

        self.type_combo = QComboBox()
        self.type_combo.addItem("SOCKS5", "socks5")
        self.type_combo.addItem("SOCKS4", "socks4")
        self.type_combo.addItem("HTTP", "http")
        index = self.type_combo.findData(proxy.normalized_type())
        self.type_combo.setCurrentIndex(max(index, 0))

        self.username_edit = QLineEdit(proxy.username)
        self.username_edit.setPlaceholderText("Логин")
        self.username_edit.setMinimumWidth(100)

        self.password_edit = QLineEdit(proxy.password)
        self.password_edit.setPlaceholderText("Пароль")
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setMinimumWidth(100)

        self.test_button = QPushButton("Тест")
        self.status_label = QLineEdit()
        self.status_label.setReadOnly(True)
        self.status_label.setFixedWidth(110)
        self._set_status("● нет теста", "#777777")

        self.delete_button = QPushButton("Удалить")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(self.number_label)
        layout.addWidget(self.enabled_check)
        layout.addWidget(self.label_edit)
        layout.addWidget(self.host_edit)
        layout.addWidget(self.port_spin)
        layout.addWidget(self.type_combo)
        layout.addWidget(self.username_edit)
        layout.addWidget(self.password_edit)
        layout.addWidget(self.test_button)
        layout.addWidget(self.status_label)
        layout.addWidget(self.delete_button)

        self.test_button.clicked.connect(self.test_proxy)
        self.delete_button.clicked.connect(self.delete_requested.emit)
        self.delete_button.clicked.connect(self.mark_deleted)

    def test_proxy(self) -> None:
        host = self.host_edit.text().strip()
        port = self.port_spin.value()
        if not host:
            self._last_test_ok = False
            self._last_ping_ms = None
            self._set_status("● нет host", "#cc3333")
            return

        self._test_generation += 1
        generation = self._test_generation
        worker = ProxyTestWorker(generation, self.to_config(), self.app_service)
        worker.signals.finished.connect(self._handle_test_result)
        self._last_test_ok = None
        self._last_ping_ms = None
        self._test_running = True
        self._set_status("● тест...", "#777777")
        self.test_button.setEnabled(False)
        self.test_state_changed.emit()
        QThreadPool.globalInstance().start(worker)

    def mark_deleted(self) -> None:
        self._deleted = True

    def _handle_test_result(self, generation: int, result) -> None:
        if self._deleted or generation != self._test_generation:
            return

        self.test_button.setEnabled(True)
        self._test_running = False
        if not result.ok or result.elapsed_ms is None:
            self._last_test_ok = False
            self._last_ping_ms = None
            self._set_status("● ошибка", "#cc3333")
            self.status_label.setToolTip(result.message)
            self.test_state_changed.emit()
            return

        self._last_test_ok = True
        self._last_ping_ms = result.elapsed_ms
        if result.elapsed_ms < 200:
            color = "#1f9d55"
        elif result.elapsed_ms <= 500:
            color = "#d7a300"
        else:
            color = "#cc3333"
        self.status_label.setToolTip(result.message)
        self._set_status(f"● {result.elapsed_ms} ms", color)
        self.test_state_changed.emit()

    def _set_status(self, text: str, color: str) -> None:
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color}; font-weight: 600;")

    def set_row_number(self, number: int) -> None:
        self.number_label.setText(str(number))

    def set_checked(self, checked: bool) -> None:
        self.enabled_check.setChecked(checked)

    def has_test_error(self) -> bool:
        return self._last_test_ok is False

    def has_ping_greater_than(self, threshold_ms: int) -> bool:
        return self._last_test_ok is True and self._last_ping_ms is not None and self._last_ping_ms > threshold_ms

    def is_test_running(self) -> bool:
        return self._test_running

    def to_config(self) -> ProxyConfig:
        return ProxyConfig(
            id=self._proxy_id,
            label=self.label_edit.text().strip(),
            host=self.host_edit.text().strip(),
            port=self.port_spin.value(),
            proxy_type=str(self.type_combo.currentData() or "socks5"),
            username=self.username_edit.text().strip(),
            password=self.password_edit.text(),
            enabled=self.enabled_check.isChecked(),
        )


def parse_proxy_csv(path: Path) -> list[ProxyConfig]:
    proxies: list[ProxyConfig] = []
    with path.open("r", encoding="utf-8-sig", newline="", errors="replace") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None:
            raise ValueError("CSV должен содержать строку заголовков.")

        for index, row in enumerate(reader, start=2):
            host = _csv_value(row, "ip", "host", "address")
            port_text = _csv_value(row, "port")
            protocol = _csv_value(row, "protocols", "protocol", "type") or "socks5"

            if not host or not port_text:
                continue

            try:
                port = int(port_text)
            except ValueError:
                raise ValueError(f"Некорректный port в строке {index}: {port_text}") from None

            proxy_type = _normalize_csv_protocol(protocol)
            label = _csv_value(row, "country", "label", "name")
            username = _csv_value(row, "username", "user", "login")
            password = _csv_value(row, "password", "pass")

            proxies.append(
                ProxyConfig(
                    id=None,
                    label=label,
                    host=host,
                    port=port,
                    proxy_type=proxy_type,
                    username=username,
                    password=password,
                    enabled=True,
                )
            )

    return proxies


def _csv_value(row: dict[str, str], *names: str) -> str:
    lowered = {key.lower(): value for key, value in row.items() if key is not None}
    for name in names:
        value = lowered.get(name.lower())
        if value is not None:
            return value.strip()
    return ""


def _normalize_csv_protocol(value: str) -> str:
    protocol = value.strip().lower()
    if "," in protocol:
        protocol = protocol.split(",", 1)[0].strip()
    if protocol in {"socks4", "socks5", "http"}:
        return protocol
    if protocol == "https":
        return "http"
    return "socks5"


def _make_browser_key(display_name: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", display_name.strip().lower())
    return key.strip("_") or "browser"
