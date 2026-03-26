from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .anki_media_sync import MediaSyncSummary, sync_batch_media, sync_lesson_media
from .lesson_io import read_lesson, write_json
from .path_policy import default_synced_output_path
from .schema import CardBatch
from .snapshot_cache import invalidate_project_snapshots
from .service_support import normalize_batch_media_paths


@dataclass(frozen=True)
class MediaSyncArtifacts:
    output_path: Path
    summary: MediaSyncSummary


def sync_media_file(
    *,
    input_path: Path,
    output_path: Path | None = None,
    media_dir: Path,
    project_root: Path,
    anki_url: str = "http://127.0.0.1:8765",
    sync_first: bool = False,
) -> MediaSyncArtifacts:
    resolved_output_path = output_path or default_synced_output_path(input_path)
    raw_text = input_path.read_text(encoding="utf-8")

    try:
        batch = CardBatch.model_validate_json(raw_text)
    except Exception:  # noqa: BLE001
        batch = None

    if batch is not None:
        synced_batch, summary = sync_batch_media(
            batch,
            media_dir=media_dir,
            anki_url=anki_url,
            sync_first=sync_first,
        )
        resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
        synced_batch = normalize_batch_media_paths(synced_batch, project_root)
        resolved_output_path.write_text(synced_batch.model_dump_json(indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    else:
        synced_document, summary = sync_lesson_media(
            read_lesson(input_path),
            media_dir=media_dir,
            anki_url=anki_url,
            sync_first=sync_first,
        )
        write_json(synced_document, resolved_output_path)

    invalidate_project_snapshots(project_root)
    return MediaSyncArtifacts(output_path=resolved_output_path, summary=summary)
