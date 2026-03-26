from __future__ import annotations

import os
from pathlib import Path

from .anki import AnkiConnectClient, existing_model_note_keys
from . import path_policy
from .repositories import AnkiRepository
from .schema import DashboardResponse, ServiceStatus
from .snapshots import dashboard_response_snapshot


def service_status(*, anki_url: str = "http://127.0.0.1:8765") -> ServiceStatus:
    anki_repository = AnkiRepository(
        anki_url,
        client_factory=AnkiConnectClient,
        note_keys_loader=existing_model_note_keys,
    )
    anki_connect_ok, anki_connect_version = anki_repository.service_status()

    return ServiceStatus(
        backend_ok=True,
        anki_connect_ok=anki_connect_ok,
        anki_connect_version=anki_connect_version,
        openai_configured=bool(os.environ.get("OPENAI_API_KEY")),
    )


def dashboard_response(
    *,
    project_root_path: Path | None = None,
    anki_url: str = "http://127.0.0.1:8765",
) -> DashboardResponse:
    return dashboard_response_snapshot(
        project_root=(project_root_path or path_policy.project_root()),
        anki_url=anki_url,
        client_factory=AnkiConnectClient,
        note_keys_loader=existing_model_note_keys,
        openai_configured=bool(os.environ.get("OPENAI_API_KEY")),
    )
