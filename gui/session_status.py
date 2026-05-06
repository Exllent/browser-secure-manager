from __future__ import annotations

from app.i18n import _
from app_config import APP_CONFIG


def _status_label(status: str) -> str:
    labels = {
        APP_CONFIG.storage.default_status: _("Idle"),
        APP_CONFIG.session_process.starting_state: _("Starting"),
        APP_CONFIG.session_process.running_state: _("Running"),
        APP_CONFIG.session_process.stopped_state: _("Stopped"),
        APP_CONFIG.session_process.error_state: _("Error"),
    }
    return labels.get(status, status)
