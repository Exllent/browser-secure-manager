from __future__ import annotations

from dataclasses import dataclass

from browser_backends.base import BrowserBackend
from db import storage
from app.session_process import SessionProcessEvent, SessionProcessManager
from models.browser_config import BrowserConfig
from models.fingerprint_profile import FingerprintProfile
from models.proxy_config import ProxyConfig
from models.session_entry import SessionEntry
from services.proxy_tester import ProxyTestResult, test_proxy


@dataclass(slots=True)
class OpenSessionResult:
    session: SessionEntry
    error_title: str | None = None
    error_message: str | None = None

    @property
    def ok(self) -> bool:
        return self.error_title is None


class AppService:
    def __init__(self, browser_backend: BrowserBackend) -> None:
        self.browser_backend = browser_backend
        self.session_processes = SessionProcessManager()

    def init_storage(self) -> None:
        storage.init_db()

    def get_sessions(self) -> list[SessionEntry]:
        return storage.get_all_sessions()

    def create_session(self, session: SessionEntry) -> SessionEntry:
        return storage.create_session(session)

    def save_session(self, session: SessionEntry) -> SessionEntry:
        return storage.update_session(session)

    def delete_session(self, session_id: int) -> None:
        self.close_session(session_id)
        storage.delete_session(session_id)

    def open_session(self, session: SessionEntry) -> OpenSessionResult:
        saved = storage.update_session(session)

        browser_config = storage.get_browser_config(saved.browser)
        if browser_config is None or not browser_config.enabled:
            return OpenSessionResult(
                session=saved,
                error_title="Browser not found",
                error_message=f"Browser '{saved.browser}' was not found in application settings.",
            )

        proxy_config = storage.get_proxy_config(saved.proxy_id)
        if saved.proxy_id is not None and (proxy_config is None or not proxy_config.enabled):
            return OpenSessionResult(
                session=saved,
                error_title="Proxy not found",
                error_message="The selected proxy was not found or is disabled in application settings.",
            )

        fingerprint_profile = storage.get_fingerprint_profile(saved.fingerprint_id)
        if saved.fingerprint_id is not None and (
            fingerprint_profile is None or not fingerprint_profile.enabled
        ):
            return OpenSessionResult(
                session=saved,
                error_title="Fingerprint not found",
                error_message="The selected fingerprint was not found or is disabled in application settings.",
            )

        try:
            self.session_processes.start_session(
                saved,
                browser_config,
                proxy_config,
                fingerprint_profile.config if fingerprint_profile is not None else None,
            )
        except Exception as exc:
            saved.status = "error"
            storage.update_session(saved)
            return OpenSessionResult(
                session=saved,
                error_title="Browser launch error",
                error_message=str(exc),
            )

        saved.status = "starting"
        saved = storage.update_session(saved)
        return OpenSessionResult(session=saved)

    def close_session(self, session_id: int) -> None:
        self.session_processes.kill_session(session_id)
        session = self._get_session(session_id)
        if session is not None:
            session.status = "stopped"
            storage.update_session(session)

    def close_all_sessions(self) -> None:
        self.session_processes.kill_all()
        self.browser_backend.close_all()
        for session in storage.get_all_sessions():
            session.status = "stopped"
            storage.update_session(session)

    def poll_session_process_events(self) -> list[SessionProcessEvent]:
        events = self.session_processes.poll_events()
        for event in events:
            if event.session_id < 0:
                continue
            session = self._get_session(event.session_id)
            if session is None:
                continue
            if event.type == "started":
                session.status = "running"
                storage.update_session(session)
            elif event.type == "failed":
                session.status = "error"
                storage.update_session(session)
            elif event.type == "stopped":
                session.status = "stopped"
                storage.update_session(session)
        return events

    def refresh_session_statuses(self) -> list[SessionProcessEvent]:
        events = self.poll_session_process_events()
        active_ids = self.session_processes.active_session_ids()
        for session in storage.get_all_sessions():
            if session.status in {"starting", "running"} and session.id not in active_ids:
                session.status = "stopped"
                storage.update_session(session)
        return events

    def _get_session(self, session_id: int) -> SessionEntry | None:
        for session in storage.get_all_sessions():
            if session.id == session_id:
                return session
        return None

    def get_browser_configs(self, *, enabled_only: bool = False) -> list[BrowserConfig]:
        return storage.get_browser_configs(enabled_only=enabled_only)

    def get_browser_config(self, key: str) -> BrowserConfig | None:
        return storage.get_browser_config(key)

    def save_browser_config(self, config: BrowserConfig) -> BrowserConfig:
        return storage.upsert_browser_config(config)

    def delete_browser_config(self, config_id: int) -> None:
        storage.delete_browser_config(config_id)

    def make_browser_key(self, display_name: str) -> str:
        return storage.make_browser_key(display_name)

    def discover_installed_browsers(self) -> list[BrowserConfig]:
        return self.browser_backend.discover_installed_browsers()

    def get_proxy_configs(self, *, enabled_only: bool = False) -> list[ProxyConfig]:
        return storage.get_proxy_configs(enabled_only=enabled_only)

    def get_proxy_config(self, proxy_id: int | None) -> ProxyConfig | None:
        return storage.get_proxy_config(proxy_id)

    def save_proxy_config(self, proxy: ProxyConfig) -> ProxyConfig:
        return storage.upsert_proxy_config(proxy)

    def delete_proxy_config(self, proxy_id: int) -> None:
        storage.delete_proxy_config(proxy_id)

    def test_proxy(self, proxy: ProxyConfig) -> ProxyTestResult:
        return test_proxy(proxy)

    def get_fingerprint_profiles(self, *, enabled_only: bool = False) -> list[FingerprintProfile]:
        return storage.get_fingerprint_profiles(enabled_only=enabled_only)

    def get_fingerprint_profile(self, fingerprint_id: int | None) -> FingerprintProfile | None:
        return storage.get_fingerprint_profile(fingerprint_id)

    def save_fingerprint_profile(self, profile: FingerprintProfile) -> FingerprintProfile:
        return storage.upsert_fingerprint_profile(profile)

    def delete_fingerprint_profile(self, fingerprint_id: int) -> None:
        storage.delete_fingerprint_profile(fingerprint_id)

    def get_setting(self, key: str, default: str = "") -> str:
        return storage.get_setting(key, default)

    def set_setting(self, key: str, value: str) -> None:
        storage.set_setting(key, value)

    def confirm_before_delete(self) -> bool:
        return self.get_setting("confirm_before_delete", "1") != "0"
