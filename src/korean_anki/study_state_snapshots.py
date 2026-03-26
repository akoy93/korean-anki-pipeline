from __future__ import annotations

from pathlib import Path
from typing import Callable

from .anki_client import AnkiConnectClient
from .anki_queries import existing_model_note_keys
from .anki_repository import AnkiRepository
from .batch_repository import BatchRepository
from .schema import StudyState
from .settings import DEFAULT_ANKI_URL


def study_state_snapshot(
    *,
    project_root: Path,
    anki_url: str = DEFAULT_ANKI_URL,
    exclude_batch_path: Path | None,
    client_factory: Callable[..., object] | None = None,
    note_keys_loader: Callable[..., set[str]] | None = None,
) -> StudyState:
    resolved_client_factory = client_factory or AnkiConnectClient
    resolved_note_keys_loader = note_keys_loader or existing_model_note_keys
    batch_repository = BatchRepository(project_root)
    anki_repository = AnkiRepository(
        anki_url,
        client_factory=resolved_client_factory,
        note_keys_loader=resolved_note_keys_loader,
    )
    anki_repository.service_status()
    generated_notes = batch_repository.generated_history(exclude_batch_path=exclude_batch_path)
    imported_notes, anki_stats = anki_repository.imported_history()
    return StudyState(
        generated_notes=generated_notes,
        imported_notes=imported_notes,
        anki_stats=anki_stats,
    )
