from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Callable, cast

from . import path_policy
from .anki_repository import AnkiRepository
from .batch_repository import BatchRepository
from .lesson_repository import LessonRepository
from .schema import (
    CardBatch,
    DashboardBatch,
    DashboardResponse,
    DashboardStats,
    ServiceStatus,
    StudyState,
)


def _dashboard_batch(
    batch_path: Path,
    *,
    project_root: Path,
    batch_repository: BatchRepository,
) -> DashboardBatch | None:
    try:
        batch = batch_repository.load_batch(batch_path)
    except Exception:  # noqa: BLE001
        return None

    approved_notes = [note for note in batch.notes if note.approved]
    approved_cards = [card for note in approved_notes for card in note.cards if card.approved]
    lanes = sorted({note.lane for note in batch.notes})

    return DashboardBatch(
        canonical_batch_path=str(batch_path.relative_to(project_root)),
        preview_batch_path=str(batch_path.relative_to(project_root)),
        title=batch.metadata.title,
        topic=batch.metadata.topic,
        lesson_date=batch.metadata.lesson_date,
        target_deck=batch.metadata.target_deck,
        notes=len(batch.notes),
        cards=sum(len(note.cards) for note in batch.notes),
        approved_notes=len(approved_notes),
        approved_cards=len(approved_cards),
        audio_notes=sum(1 for note in batch.notes if note.item.audio is not None),
        image_notes=sum(1 for note in batch.notes if note.item.image is not None),
        exact_duplicates=sum(1 for note in batch.notes if note.duplicate_status == "exact-duplicate"),
        near_duplicates=sum(1 for note in batch.notes if note.duplicate_status == "near-duplicate"),
        synced_batch_path=None,
        lanes=cast(list, lanes),
    )


def batch_referenced_media_paths(batch: CardBatch, *, project_root: Path) -> set[Path]:
    media_paths: set[Path] = set()
    for note in batch.notes:
        if note.item.audio is not None:
            media_paths.add(
                path_policy.resolve_media_reference_path(
                    note.item.audio.path,
                    project_root_path=project_root,
                )
            )
        if note.item.image is not None:
            media_paths.add(
                path_policy.resolve_media_reference_path(
                    note.item.image.path,
                    project_root_path=project_root,
                )
            )
        for card in note.cards:
            if card.audio_path is not None:
                media_paths.add(
                    path_policy.resolve_media_reference_path(
                        card.audio_path,
                        project_root_path=project_root,
                    )
                )
            if card.image_path is not None:
                media_paths.add(
                    path_policy.resolve_media_reference_path(
                        card.image_path,
                        project_root_path=project_root,
                    )
                )
    return media_paths


def batch_media_hydrated(
    batch_path: Path,
    *,
    project_root: Path,
    batch_repository: BatchRepository | None = None,
) -> bool:
    repository = batch_repository or BatchRepository(project_root)
    try:
        parsed_batch = repository.load_batch(batch_path)
    except Exception:  # noqa: BLE001
        return False

    referenced_media = batch_referenced_media_paths(parsed_batch, project_root=project_root)
    return all(path.exists() and path.is_file() for path in referenced_media)


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
    anki_url: str,
    exclude_batch_path: Path | None,
    client_factory: Callable[..., object],
    note_keys_loader: Callable[..., set[str]],
) -> StudyState:
    batch_repository = BatchRepository(project_root)
    anki_repository = AnkiRepository(
        anki_url,
        client_factory=client_factory,
        note_keys_loader=note_keys_loader,
    )
    anki_repository.service_status()
    exclude_path = str(exclude_batch_path.resolve()) if exclude_batch_path is not None else None
    return _cached_study_state_snapshot(
        str(project_root.resolve()),
        anki_url,
        exclude_path,
        batch_repository.snapshot_version,
        anki_repository.snapshot_version,
        client_factory,
        note_keys_loader,
    ).model_copy(deep=True)


@lru_cache(maxsize=None)
def _cached_dashboard_response(
    project_root: str,
    anki_url: str,
    project_version: int,
    anki_version: int,
    client_factory: Callable[..., object],
    note_keys_loader: Callable[..., set[str]],
) -> DashboardResponse:
    del project_version, anki_version
    root = Path(project_root)
    batch_repository = BatchRepository(root)
    lesson_repository = LessonRepository(root)
    anki_repository = AnkiRepository(
        anki_url,
        client_factory=client_factory,
        note_keys_loader=note_keys_loader,
    )

    recent_batches = [
        batch
        for path in batch_repository.canonical_batch_paths()
        if (batch := _dashboard_batch(path, project_root=root, batch_repository=batch_repository)) is not None
    ]

    lane_counts: dict[str, int] = {}
    for batch in recent_batches:
        for lane in batch.lanes:
            lane_counts[lane] = lane_counts.get(lane, 0) + batch.notes

    note_count, card_count, deck_counts = anki_repository.dashboard_stats()
    note_keys = anki_repository.note_keys()

    resolved_batches: list[DashboardBatch] = []
    for batch in recent_batches:
        canonical_path = root / batch.canonical_batch_path
        batch_paths = path_policy.batch_path_identity(canonical_path)
        synced_batch_path = batch_paths.synced_path
        preview_batch_path = batch_paths.preview_path
        push_status = "not-pushed"
        canonical_batch = batch_repository.load_batch(canonical_path)
        approved_notes = [note for note in canonical_batch.notes if note.approved]
        if approved_notes and all(note.note_key in note_keys for note in approved_notes):
            push_status = "pushed"
        resolved_batches.append(
            batch.model_copy(
                update={
                    "push_status": push_status,
                    "media_hydrated": batch_media_hydrated(
                        preview_batch_path,
                        project_root=root,
                        batch_repository=batch_repository,
                    ),
                    "preview_batch_path": str(preview_batch_path.relative_to(root)),
                    "synced_batch_path": str(synced_batch_path.relative_to(root))
                    if synced_batch_path is not None
                    else None,
                }
            )
        )

    connected, version = anki_repository.service_status()
    return DashboardResponse(
        status=ServiceStatus(
            backend_ok=True,
            anki_connect_ok=connected,
            anki_connect_version=version,
        ),
        stats=DashboardStats(
            local_batch_count=len(resolved_batches),
            local_note_count=sum(batch.notes for batch in resolved_batches),
            local_card_count=sum(batch.cards for batch in resolved_batches),
            pending_push_count=sum(
                1
                for batch in resolved_batches
                if batch.push_status == "not-pushed" and batch.approved_notes > 0 and batch.exact_duplicates == 0
            ),
            audio_note_count=sum(batch.audio_notes for batch in resolved_batches),
            image_note_count=sum(batch.image_notes for batch in resolved_batches),
            lane_counts=lane_counts,
            anki_note_count=note_count,
            anki_card_count=card_count,
            anki_deck_counts=deck_counts,
        ),
        recent_batches=resolved_batches[:20],
        lesson_contexts=lesson_repository.lesson_contexts(),
        syncable_files=batch_repository.syncable_files(),
    )


def dashboard_response_snapshot(
    *,
    project_root: Path,
    anki_url: str,
    client_factory: Callable[..., object],
    note_keys_loader: Callable[..., set[str]],
    openai_configured: bool,
) -> DashboardResponse:
    batch_repository = BatchRepository(project_root)
    anki_repository = AnkiRepository(
        anki_url,
        client_factory=client_factory,
        note_keys_loader=note_keys_loader,
    )
    connected, version = anki_repository.service_status()
    response = _cached_dashboard_response(
        str(project_root.resolve()),
        anki_url,
        batch_repository.snapshot_version,
        anki_repository.snapshot_version,
        client_factory,
        note_keys_loader,
    ).model_copy(deep=True)
    return response.model_copy(
        update={
            "status": response.status.model_copy(
                update={
                    "anki_connect_ok": connected,
                    "anki_connect_version": version,
                    "openai_configured": openai_configured,
                }
            )
        }
    )
