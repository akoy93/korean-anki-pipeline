from __future__ import annotations

from pathlib import Path

from .anki import AnkiConnectClient, existing_model_note_keys
from .note_keys import normalize_text, note_key_for_item
from .repositories import AnkiRepository, BatchRepository
from .schema import PriorNote, StudyState
from .snapshots import study_state_snapshot


def generated_history(project_root: Path, exclude_batch_path: Path | None = None) -> list[PriorNote]:
    return BatchRepository(project_root).generated_history(exclude_batch_path=exclude_batch_path)


def imported_anki_history(anki_url: str = "http://127.0.0.1:8765") -> tuple[list[PriorNote], AnkiStatsSnapshot]:
    return AnkiRepository(
        anki_url,
        client_factory=AnkiConnectClient,
        note_keys_loader=existing_model_note_keys,
    ).imported_history()


def build_study_state(
    project_root: Path,
    anki_url: str = "http://127.0.0.1:8765",
    exclude_batch_path: Path | None = None,
) -> StudyState:
    return study_state_snapshot(
        project_root=project_root,
        anki_url=anki_url,
        exclude_batch_path=exclude_batch_path,
        client_factory=AnkiConnectClient,
        note_keys_loader=existing_model_note_keys,
    )
