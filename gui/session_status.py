from __future__ import annotations

from app.i18n import _


def _status_label(status: str) -> str:
    labels = {
        "idle": _("Idle"),
        "running": _("Running"),
        "stopped": _("Stopped"),
        "error": _("Error"),
    }
    return labels.get(status, status)
