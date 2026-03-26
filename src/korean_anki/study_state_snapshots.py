from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Callable

from .anki_client import AnkiConnectClient
from .anki_queries import existing_model_note_keys
from .anki_repository import AnkiRepository
from .batch_repository import BatchRepository
from .schema import StudyState
from .settings import DEFAULT_ANKI_URL


@lru_cache(maxsize=None)
def _cached_study_state_snapshot(
    project_root: str,
    anki_url: str,
    exclude_batch_path: str | None,
    project_version: int,
    anki_version: int,
    client_factory: Callable[..., object],
    note_keys_loader: Callable[..., set[str]],
) -> StudyState:
    del project_version, anki_version
    root = Path(project_root)
    batch_repository = BatchRepository(root)
    anki_repository = AnkiRepository(
        anki_url,
        client_factory=client_factory,
        note_keys_loader=note_keys_loader,
    )
    generated_notes = batch_repository.generated_history(
        exclude_batch_path=Path(exclude_batch_path) if exclude_batch_path is not None else None,
    )
    imported_notes, anki_stats = anki_repository.imported_history()
    return StudyState(
        generated_notes=generated_notes,
        imported_notes=imported_notes,
        anki_stats=anki_stats,
    )


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
    exclude_path = str(exclude_batch_path.resolve()) if exclude_batch_path is not None else None
    return _cached_study_state_snapshot(
        str(project_root.resolve()),
        anki_url,
        exclude_path,
        batch_repository.snapshot_version,
        anki_repository.snapshot_version,
        resolved_client_factory,
        resolved_note_keys_loader,
    ).model_copy(deep=True)
