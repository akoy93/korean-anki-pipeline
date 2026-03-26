from __future__ import annotations

from pathlib import Path

from .anki_client import DEFAULT_DECK, AnkiConnectClient
from .anki_push_service import plan_push, push_batch
from .anki_queries import existing_model_note_keys
from .anki_repository import AnkiRepository
from .batch_repository import BatchRepository
from .path_policy import default_synced_output_path, normalize_batch_media_paths
from .schema import CardBatch, DeleteBatchResult, PushRequest, PushResult
from .snapshot_cache import invalidate_anki_snapshots, invalidate_project_snapshots
from .settings import DEFAULT_ANKI_URL
from .snapshots import batch_media_hydrated as snapshot_batch_media_hydrated
from .snapshots import batch_referenced_media_paths as snapshot_batch_referenced_media_paths


def resolve_push_deck_name(request: PushRequest) -> str:
    return request.deck_name or request.batch.metadata.target_deck or DEFAULT_DECK


def handle_push_request(
    request: PushRequest,
    *,
    project_root: Path | None = None,
    reviewed_batch_path: str | None = None,
) -> PushResult:
    deck_name = resolve_push_deck_name(request)
    if request.dry_run:
        return plan_push(
            request.batch,
            deck_name=deck_name,
            anki_url=request.anki_url,
        )

    if reviewed_batch_path is not None:
        reviewed_batch = request.batch
        if project_root is not None:
            reviewed_batch = normalize_batch_media_paths(reviewed_batch, project_root)
        Path(reviewed_batch_path).write_text(
            reviewed_batch.model_dump_json(indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    result = push_batch(
        request.batch,
        deck_name=deck_name,
        anki_url=request.anki_url,
        sync=request.sync,
    )
    invalidate_anki_snapshots(request.anki_url)
    if project_root is not None:
        invalidate_project_snapshots(project_root)
    if reviewed_batch_path is None:
        return result
    return PushResult.model_validate(result.model_dump() | {"reviewed_batch_path": reviewed_batch_path})


def batch_referenced_media_paths(batch: CardBatch, *, project_root: Path) -> set[Path]:
    return snapshot_batch_referenced_media_paths(batch, project_root=project_root)


def batch_media_hydrated(batch_path: Path, *, project_root: Path) -> bool:
    return snapshot_batch_media_hydrated(batch_path, project_root=project_root)


def batch_is_pushed(batch: CardBatch, *, anki_url: str) -> bool:
    anki_note_keys = AnkiRepository(
        anki_url,
        client_factory=AnkiConnectClient,
        note_keys_loader=existing_model_note_keys,
    ).note_keys()
    approved_notes = [note for note in batch.notes if note.approved]
    return len(approved_notes) > 0 and any(note.note_key in anki_note_keys for note in approved_notes)


def delete_batch(batch_path: Path, *, project_root: Path, anki_url: str = DEFAULT_ANKI_URL) -> DeleteBatchResult:
    if not batch_path.name.endswith(".batch.json") or batch_path.name.endswith(".synced.batch.json"):
        raise ValueError("Batch path must be a canonical .batch.json file.")
    if not batch_path.exists():
        raise ValueError("Batch file not found.")

    batch = CardBatch.model_validate_json(batch_path.read_text(encoding="utf-8"))
    if batch_is_pushed(batch, anki_url=anki_url):
        raise ValueError("Cannot delete a batch that has already been pushed to Anki.")

    synced_batch_path = default_synced_output_path(batch_path)
    generation_plan_path = batch_path.with_suffix(".generation-plan.json")
    deleted_paths: list[str] = []
    for path in [batch_path, synced_batch_path, generation_plan_path]:
        if path.exists():
            path.unlink()
            deleted_paths.append(str(path.relative_to(project_root)))

    candidate_media_paths = batch_referenced_media_paths(batch, project_root=project_root)
    referenced_elsewhere: set[Path] = set()
    batch_repository = BatchRepository(project_root)
    for other_batch_path in batch_repository.batch_paths():
        if other_batch_path == batch_path or other_batch_path == synced_batch_path:
            continue
        try:
            other_batch = batch_repository.load_batch(other_batch_path)
        except Exception:  # noqa: BLE001
            continue
        referenced_elsewhere.update(batch_referenced_media_paths(other_batch, project_root=project_root))

    deleted_media_paths: list[str] = []
    for media_path in sorted(candidate_media_paths):
        if media_path in referenced_elsewhere or not media_path.exists() or not media_path.is_file():
            continue
        media_path.unlink()
        deleted_media_paths.append(str(media_path.relative_to(project_root)))

    invalidate_project_snapshots(project_root)
    return DeleteBatchResult(deleted_paths=deleted_paths, deleted_media_paths=deleted_media_paths)
