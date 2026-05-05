from __future__ import annotations

import logging
import multiprocessing
import queue
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from browser_backends.selenium_backend import SeleniumBrowserBackend
from models.browser_config import BrowserConfig
from models.fingerprint_config import FingerprintConfig
from models.proxy_config import ProxyConfig
from models.session_entry import SessionEntry
from services.proxy_tester import test_proxy

logger = logging.getLogger(__name__)

LOG_DIR = Path(__file__).resolve().parents[1] / "logs" / "sessions"


@dataclass(slots=True)
class SessionProcessEvent:
    session_id: int
    type: str
    message: str = ""
    level: str = "INFO"
    log_path: str = ""
    traceback: str = ""
    exitcode: int | None = None


@dataclass(slots=True)
class _SessionProcessRecord:
    process: multiprocessing.Process
    command_queue: Any
    state: str = "starting"
    log_path: str = ""


class SessionProcessManager:
    def __init__(self) -> None:
        self._context = multiprocessing.get_context("spawn")
        self._event_queue = self._context.Queue()
        self._records: dict[int, _SessionProcessRecord] = {}

    def start_session(
        self,
        session: SessionEntry,
        browser_config: BrowserConfig,
        proxy_config: ProxyConfig | None,
        fingerprint_config: FingerprintConfig | None,
    ) -> str:
        if session.id is None:
            raise ValueError("Session must be saved before opening a browser")

        self.kill_session(session.id)
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_path = str(LOG_DIR / f"session_{session.id}.log")
        command_queue = self._context.Queue()
        process = self._context.Process(
            target=_run_browser_session_process,
            args=(
                session,
                browser_config,
                proxy_config,
                fingerprint_config,
                command_queue,
                self._event_queue,
                log_path,
            ),
            name=f"secure-browser-session-{session.id}",
        )
        process.daemon = False
        process.start()
        self._records[session.id] = _SessionProcessRecord(
            process=process,
            command_queue=command_queue,
            log_path=log_path,
        )
        return log_path

    def kill_session(self, session_id: int, *, timeout: float = 2.0) -> bool:
        record = self._records.pop(session_id, None)
        if record is None:
            return False

        if record.process.is_alive():
            try:
                record.command_queue.put_nowait({"type": "stop"})
            except Exception:
                logger.exception("Failed to send stop command to session process %s", session_id)

            record.process.join(timeout)
            if record.process.is_alive():
                record.process.terminate()
                record.process.join(timeout)
            if record.process.is_alive():
                record.process.kill()
                record.process.join(timeout)

        record.process.close()
        return True

    def kill_all(self) -> None:
        for session_id in list(self._records):
            self.kill_session(session_id)

    def is_session_active(self, session_id: int) -> bool:
        record = self._records.get(session_id)
        return bool(record and record.process.is_alive())

    def active_session_ids(self) -> set[int]:
        return {
            session_id
            for session_id, record in self._records.items()
            if record.process.is_alive()
        }

    def poll_events(self) -> list[SessionProcessEvent]:
        events: list[SessionProcessEvent] = []
        while True:
            try:
                raw_event = self._event_queue.get_nowait()
            except queue.Empty:
                break

            event = _event_from_payload(raw_event)
            self._update_record_from_event(event)
            events.append(event)

        events.extend(self._collect_exited_process_events())
        return events

    def _update_record_from_event(self, event: SessionProcessEvent) -> None:
        record = self._records.get(event.session_id)
        if record is None:
            return

        if event.type == "started":
            record.state = "running"
        elif event.type in {"failed", "stopped"}:
            record.state = event.type
            record.process.join(0.1)
            if not record.process.is_alive():
                self._records.pop(event.session_id, None)
                record.process.close()

    def _collect_exited_process_events(self) -> list[SessionProcessEvent]:
        events: list[SessionProcessEvent] = []
        for session_id, record in list(self._records.items()):
            if record.process.is_alive():
                continue

            exitcode = record.process.exitcode
            self._records.pop(session_id, None)
            record.process.close()
            if record.state in {"failed", "stopped"}:
                continue
            if record.state == "running" or exitcode == 0:
                events.append(
                    SessionProcessEvent(
                        session_id=session_id,
                        type="stopped",
                        message="Session process exited.",
                        log_path=record.log_path,
                        exitcode=exitcode,
                    )
                )
            else:
                events.append(
                    SessionProcessEvent(
                        session_id=session_id,
                        type="failed",
                        message=f"Session process exited before startup. Exit code: {exitcode}",
                        level="ERROR",
                        log_path=record.log_path,
                        exitcode=exitcode,
                    )
                )

        return events


class _QueueLogHandler(logging.Handler):
    def __init__(self, session_id: int, event_queue: Any, log_path: str) -> None:
        super().__init__()
        self.session_id = session_id
        self.event_queue = event_queue
        self.log_path = log_path

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.event_queue.put(
                {
                    "session_id": self.session_id,
                    "type": "log",
                    "level": record.levelname,
                    "message": self.format(record),
                    "log_path": self.log_path,
                }
            )
        except Exception:
            pass


def _run_browser_session_process(
    session: SessionEntry,
    browser_config: BrowserConfig,
    proxy_config: ProxyConfig | None,
    fingerprint_config: FingerprintConfig | None,
    command_queue: Any,
    event_queue: Any,
    log_path: str,
) -> None:
    assert session.id is not None
    _configure_child_logging(session.id, event_queue, log_path)
    backend = SeleniumBrowserBackend()
    child_logger = logging.getLogger(__name__)

    try:
        child_logger.info("Session process started")
        if proxy_config is not None:
            child_logger.info("Testing proxy %s", proxy_config.display_name())
            proxy_result = test_proxy(proxy_config)
            if not proxy_result.ok:
                raise RuntimeError(
                    f"Proxy {proxy_config.display_name()} did not pass validation. "
                    f"Error: {proxy_result.message}"
                )

        backend.open_session(session, browser_config, proxy_config, fingerprint_config)
        event_queue.put(
            {
                "session_id": session.id,
                "type": "started",
                "message": "Browser session started.",
                "log_path": log_path,
            }
        )
        child_logger.info("Browser session started")
        _process_session_loop(session.id, backend, command_queue, child_logger)
        event_queue.put(
            {
                "session_id": session.id,
                "type": "stopped",
                "message": "Browser session stopped.",
                "log_path": log_path,
            }
        )
    except Exception as exc:
        error_traceback = traceback.format_exc()
        child_logger.exception("Browser session failed")
        event_queue.put(
            {
                "session_id": session.id,
                "type": "failed",
                "level": "ERROR",
                "message": str(exc),
                "traceback": error_traceback,
                "log_path": log_path,
            }
        )
    finally:
        backend.close_all()
        child_logger.info("Session process exiting")


def _process_session_loop(
    session_id: int,
    backend: SeleniumBrowserBackend,
    command_queue: Any,
    child_logger: logging.Logger,
) -> None:
    while True:
        try:
            command = command_queue.get(timeout=1.0)
        except queue.Empty:
            command = None

        if isinstance(command, dict) and command.get("type") == "stop":
            child_logger.info("Stop command received")
            backend.close_session(session_id)
            return

        if not backend.is_session_running(session_id):
            child_logger.info("Browser session is no longer running")
            return

        time.sleep(0.2)


def _configure_child_logging(session_id: int, event_queue: Any, log_path: str) -> None:
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(logging.INFO)

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    queue_handler = _QueueLogHandler(session_id, event_queue, log_path)
    queue_handler.setFormatter(formatter)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(queue_handler)


def _event_from_payload(payload: object) -> SessionProcessEvent:
    if not isinstance(payload, dict):
        return SessionProcessEvent(session_id=-1, type="log", message=str(payload))

    return SessionProcessEvent(
        session_id=int(payload.get("session_id", -1)),
        type=str(payload.get("type", "log")),
        message=str(payload.get("message", "")),
        level=str(payload.get("level", "INFO")),
        log_path=str(payload.get("log_path", "")),
        traceback=str(payload.get("traceback", "")),
        exitcode=payload.get("exitcode"),
    )
