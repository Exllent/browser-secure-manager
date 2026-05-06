from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QWidget,
)

from app.app_service import AppService
from app.i18n import _
from models.proxy_config import ProxyConfig


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
        self.label_edit.setPlaceholderText(_("Title"))
        self.label_edit.setMinimumWidth(130)

        self.host_edit = QLineEdit(proxy.host)
        self.host_edit.setPlaceholderText(_("Host or IP"))
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
        self.username_edit.setPlaceholderText(_("Username"))
        self.username_edit.setMinimumWidth(100)

        self.password_edit = QLineEdit(proxy.password)
        self.password_edit.setPlaceholderText(_("Password"))
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setMinimumWidth(100)

        self.test_button = QPushButton(_("Test"))
        self.status_label = QLineEdit()
        self.status_label.setReadOnly(True)
        self.status_label.setFixedWidth(110)
        self._set_status(f"● {_('No test')}", "#777777")

        self.delete_button = QPushButton(_("Delete"))

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
        if not host:
            self._last_test_ok = False
            self._last_ping_ms = None
            self._set_status(f"● {_('No host')}", "#cc3333")
            return

        self._test_generation += 1
        generation = self._test_generation
        worker = ProxyTestWorker(generation, self.to_config(), self.app_service)
        worker.signals.finished.connect(self._handle_test_result)
        self._last_test_ok = None
        self._last_ping_ms = None
        self._test_running = True
        self._set_status(f"● {_('Testing')}...", "#777777")
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
            self._set_status(f"● {_('Error')}", "#cc3333")
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
        return (
            self._last_test_ok is True
            and self._last_ping_ms is not None
            and self._last_ping_ms > threshold_ms
        )

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
