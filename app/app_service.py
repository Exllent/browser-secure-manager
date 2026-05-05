from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from app.logging_config import export_log_file
from browser_backends.base import BrowserBackend
from db import storage
from app.session_process import SessionProcessEvent, SessionProcessManager
from models.browser_config import BrowserConfig
from models.fingerprint_profile import FingerprintProfile
from models.proxy_config import ProxyConfig
from models.session_entry import SessionEntry
from services.proxy_tester import ProxyTestResult, test_proxy

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class OpenSessionResult:
    session: SessionEntry
    error_title: str | None = None
    error_message: str | None = None

    @property
    def ok(self) -> bool:
        return self.error_title is None


@dataclass(slots=True)
class BackupImportResult:
    scope: str
    sessions: int = 0
    browser_configs: int = 0
    proxy_configs: int = 0
    fingerprint_profiles: int = 0
    app_settings: int = 0


class AppService:
    def __init__(self, browser_backend: BrowserBackend) -> None:
        self.browser_backend = browser_backend
        self.session_processes = SessionProcessManager()

    def init_storage(self) -> None:
        logger.info("Initializing application storage")
        storage.init_db()
        deleted_profiles = storage.cleanup_expired_profile_cache()
        if deleted_profiles:
            logger.info("Profile cache cleanup removed %s profile(s)", deleted_profiles)

    def get_sessions(self) -> list[SessionEntry]:
        return storage.get_all_sessions()

    def create_session(self, session: SessionEntry) -> SessionEntry:
        created = storage.create_session(session)
        logger.info("Session %s created", created.id)
        return created

    def save_session(self, session: SessionEntry) -> SessionEntry:
        saved = storage.update_session(session)
        logger.info("Session %s saved", saved.id)
        return saved

    def delete_session(self, session_id: int) -> None:
        logger.info("Deleting session %s", session_id)
        session = self._get_session(session_id)
        self.close_session(session_id)
        if session is not None and not storage.is_profile_cache_enabled():
            storage.delete_profile_directory(session.profile_path)
        storage.delete_session(session_id)

    def open_session(self, session: SessionEntry) -> OpenSessionResult:
        logger.info("Opening session %s", session.id)
        saved = storage.update_session(session)

        browser_config = storage.get_browser_config(saved.browser)
        if browser_config is None or not browser_config.enabled:
            logger.warning(
                "Session %s cannot start: browser '%s' is missing or disabled",
                saved.id,
                saved.browser,
            )
            return OpenSessionResult(
                session=saved,
                error_title="Browser not found",
                error_message=f"Browser '{saved.browser}' was not found in application settings.",
            )

        proxy_config = storage.get_proxy_config(saved.proxy_id)
        if saved.proxy_id is not None and (proxy_config is None or not proxy_config.enabled):
            logger.warning(
                "Session %s cannot start: proxy %s is missing or disabled",
                saved.id,
                saved.proxy_id,
            )
            return OpenSessionResult(
                session=saved,
                error_title="Proxy not found",
                error_message="The selected proxy was not found or is disabled in application settings.",
            )

        fingerprint_profile = storage.get_fingerprint_profile(saved.fingerprint_id)
        if saved.fingerprint_id is not None and (
            fingerprint_profile is None or not fingerprint_profile.enabled
        ):
            logger.warning(
                "Session %s cannot start: fingerprint %s is missing or disabled",
                saved.id,
                saved.fingerprint_id,
            )
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
            logger.exception("Failed to start session process for session %s", saved.id)
            saved.status = "error"
            storage.update_session(saved)
            return OpenSessionResult(
                session=saved,
                error_title="Browser launch error",
                error_message=str(exc),
            )

        saved.status = "starting"
        saved = storage.update_session(saved)
        logger.info("Session %s moved to starting state", saved.id)
        return OpenSessionResult(session=saved)

    def close_session(self, session_id: int) -> None:
        logger.info("Closing session %s", session_id)
        self.session_processes.kill_session(session_id)
        session = self._get_session(session_id)
        if session is not None:
            session.status = "stopped"
            storage.update_session(session)

    def close_all_sessions(self) -> None:
        logger.info("Closing all sessions")
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
                logger.info("Session %s reported running", event.session_id)
                session.status = "running"
                storage.update_session(session)
            elif event.type == "failed":
                logger.error("Session %s reported failure: %s", event.session_id, event.message)
                session.status = "error"
                storage.update_session(session)
            elif event.type == "stopped":
                logger.info("Session %s reported stopped", event.session_id)
                session.status = "stopped"
                storage.update_session(session)
        return events

    def refresh_session_statuses(self) -> list[SessionProcessEvent]:
        events = self.poll_session_process_events()
        active_ids = self.session_processes.active_session_ids()
        for session in storage.get_all_sessions():
            if session.status in {"starting", "running"} and session.id not in active_ids:
                logger.warning(
                    "Session %s was marked %s but has no active process; marking stopped",
                    session.id,
                    session.status,
                )
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
        saved = storage.upsert_browser_config(config)
        logger.info("Browser config '%s' saved", saved.key)
        return saved

    def delete_browser_config(self, config_id: int) -> None:
        logger.info("Deleting browser config %s", config_id)
        storage.delete_browser_config(config_id)

    def make_browser_key(self, display_name: str) -> str:
        return storage.make_browser_key(display_name)

    def discover_installed_browsers(self) -> list[BrowserConfig]:
        browsers = self.browser_backend.discover_installed_browsers()
        logger.info("Browser discovery found %s browser(s)", len(browsers))
        return browsers

    def get_proxy_configs(self, *, enabled_only: bool = False) -> list[ProxyConfig]:
        return storage.get_proxy_configs(enabled_only=enabled_only)

    def get_proxy_config(self, proxy_id: int | None) -> ProxyConfig | None:
        return storage.get_proxy_config(proxy_id)

    def save_proxy_config(self, proxy: ProxyConfig) -> ProxyConfig:
        saved = storage.upsert_proxy_config(proxy)
        logger.info("Proxy config %s saved", saved.id)
        return saved

    def delete_proxy_config(self, proxy_id: int) -> None:
        logger.info("Deleting proxy config %s", proxy_id)
        storage.delete_proxy_config(proxy_id)

    def test_proxy(self, proxy: ProxyConfig) -> ProxyTestResult:
        result = test_proxy(proxy)
        if result.ok:
            logger.info("Proxy test passed for %s in %s ms", proxy.display_name(), result.elapsed_ms)
        else:
            logger.warning("Proxy test failed for %s: %s", proxy.display_name(), result.message)
        return result

    def get_fingerprint_profiles(self, *, enabled_only: bool = False) -> list[FingerprintProfile]:
        return storage.get_fingerprint_profiles(enabled_only=enabled_only)

    def get_fingerprint_profile(self, fingerprint_id: int | None) -> FingerprintProfile | None:
        return storage.get_fingerprint_profile(fingerprint_id)

    def save_fingerprint_profile(self, profile: FingerprintProfile) -> FingerprintProfile:
        saved = storage.upsert_fingerprint_profile(profile)
        logger.info("Fingerprint profile %s saved", saved.id)
        return saved

    def delete_fingerprint_profile(self, fingerprint_id: int) -> None:
        logger.info("Deleting fingerprint profile %s", fingerprint_id)
        storage.delete_fingerprint_profile(fingerprint_id)

    def get_setting(self, key: str, default: str = "") -> str:
        return storage.get_setting(key, default)

    def set_setting(self, key: str, value: str) -> None:
        storage.set_setting(key, value)

    def confirm_before_delete(self) -> bool:
        return self.get_setting("confirm_before_delete", "1") != "0"

    def profile_cache_enabled(self) -> bool:
        return storage.is_profile_cache_enabled()

    def profile_cache_days(self) -> str:
        return storage.get_profile_cache_days()

    def export_log_file(self, kind: str, destination: str | Path) -> Path:
        exported_path = export_log_file(kind, destination)
        logger.info("Exported %s log file to %s", kind, exported_path)
        return exported_path

    def export_full_backup(self, destination: str | Path) -> Path:
        logger.info("Exporting full backup to %s", destination)
        return storage.export_full_backup(destination)

    def export_session_backup(self, session: SessionEntry, destination: str | Path) -> Path:
        saved = storage.update_session(session)
        if saved.id is None:
            raise ValueError("Session must be saved before backup export")
        logger.info("Exporting session %s backup to %s", saved.id, destination)
        return storage.export_session_backup(saved.id, destination)

    def import_backup(self, source: str | Path) -> BackupImportResult:
        logger.warning("Importing backup from %s; active sessions will be stopped", source)
        self.close_all_sessions()
        raw_result = storage.import_backup(source)
        return BackupImportResult(
            scope=str(raw_result.get("scope", "")),
            sessions=int(raw_result.get("sessions", 0)),
            browser_configs=int(raw_result.get("browser_configs", 0)),
            proxy_configs=int(raw_result.get("proxy_configs", 0)),
            fingerprint_profiles=int(raw_result.get("fingerprint_profiles", 0)),
            app_settings=int(raw_result.get("app_settings", 0)),
        )
