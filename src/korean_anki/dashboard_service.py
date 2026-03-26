from __future__ import annotations

from pathlib import Path

from . import application, path_policy


def service_status(*, anki_url: str = "http://127.0.0.1:8765"):
    return application.build_service_status(anki_url=anki_url)


def dashboard_response(
    *,
    project_root_path: Path | None = None,
    anki_url: str = "http://127.0.0.1:8765",
):
    return application.build_dashboard_response(
        project_root=(project_root_path or path_policy.project_root()),
        anki_url=anki_url,
    )
