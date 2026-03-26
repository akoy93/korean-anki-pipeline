from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
import re
import tempfile

from .schema import CardBatch
from .settings import DEFAULT_MEDIA_DIR


@dataclass(frozen=True)
class BatchPathIdentity:
    requested_path: Path
    canonical_path: Path
    preview_path: Path
    synced_path: Path | None


_SLUG_RE = re.compile(r"[^a-zA-Z0-9가-힣]+")


def project_root() -> Path:
    return Path.cwd().resolve()


def media_root(*, project_root_path: Path | None = None) -> Path:
    root = (project_root_path or project_root()).resolve()
    return (root / DEFAULT_MEDIA_DIR).resolve()


def job_state_root(*, project_root_path: Path | None = None) -> Path:
    root = (project_root_path or project_root()).resolve()
    return (root / "state" / "jobs").resolve()


def resolve_project_path(relative_path: str, *, project_root_path: Path | None = None) -> Path:
    if Path(relative_path).is_absolute():
        raise ValueError("Use a project-relative path.")

    root = (project_root_path or project_root()).resolve()
    resolved_path = (root / relative_path).resolve()
    normalized_root = f"{root}{os.sep}"
    if resolved_path != root and not str(resolved_path).startswith(normalized_root):
        raise ValueError("Path escapes project root.")
    return resolved_path


def resolve_media_path(relative_path: str, *, project_root_path: Path | None = None) -> Path:
    if Path(relative_path).is_absolute():
        raise ValueError("Use a media-root-relative path.")

    root = media_root(project_root_path=project_root_path)
    resolved_path = (root / relative_path).resolve()
    normalized_root = f"{root}{os.sep}"
    if resolved_path != root and not str(resolved_path).startswith(normalized_root):
        raise ValueError("Path escapes media root.")
    return resolved_path


def resolve_media_reference_path(path: str, *, project_root_path: Path | None = None) -> Path:
    media_path = Path(path)
    if not media_path.is_absolute():
        return resolve_project_path(path, project_root_path=project_root_path)

    root = (project_root_path or project_root()).resolve()
    resolved_path = media_path.resolve()
    normalized_root = f"{root}{os.sep}"
    if resolved_path != root and not str(resolved_path).startswith(normalized_root):
        raise ValueError("Path escapes project root.")
    return resolved_path


def is_synced_batch_path(batch_path: Path) -> bool:
    return batch_path.name.endswith(".synced.batch.json")


def canonical_batch_path(batch_path: Path) -> Path:
    if is_synced_batch_path(batch_path):
        return batch_path.with_name(
            f"{batch_path.name.removesuffix('.synced.batch.json')}.batch.json"
        )
    return batch_path


def default_synced_output_path(input_path: Path) -> Path:
    name = input_path.name
    if name.endswith(".synced.batch.json") or name.endswith(".synced.lesson.json"):
        return input_path
    if name.endswith(".batch.json"):
        canonical_path = canonical_batch_path(input_path)
        return canonical_path.with_name(
            f"{canonical_path.name.removesuffix('.batch.json')}.synced.batch.json"
        )
    if name.endswith(".lesson.json"):
        return input_path.with_name(f"{name.removesuffix('.lesson.json')}.synced.lesson.json")
    return input_path.with_name(f"{name}.synced")


def unique_new_vocab_output_path(project_root: Path) -> Path:
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    output_path = project_root / "data/generated" / f"new-vocab-{timestamp}.batch.json"
    suffix = 2
    while output_path.exists():
        output_path = project_root / "data/generated" / f"new-vocab-{timestamp}-{suffix}.batch.json"
        suffix += 1
    return output_path


def _slugify(value: str) -> str:
    slug = _SLUG_RE.sub("-", value).strip("-").lower()
    return slug or "lesson"


def unique_lesson_root(project_root: Path, lesson_date: str, topic: str) -> Path:
    base_slug = f"{lesson_date}-{_slugify(topic)}"
    lesson_root = project_root / "lessons" / base_slug
    if not lesson_root.exists():
        return lesson_root

    timestamp = datetime.now().strftime("%H%M%S")
    lesson_root = project_root / "lessons" / f"{base_slug}-{timestamp}"
    suffix = 2
    while lesson_root.exists():
        lesson_root = project_root / "lessons" / f"{base_slug}-{timestamp}-{suffix}"
        suffix += 1
    return lesson_root


def project_relative_path(path: str | None, project_root: Path) -> str | None:
    if path is None:
        return None

    maybe_absolute_path = Path(path)
    if not maybe_absolute_path.is_absolute():
        return path

    try:
        return str(maybe_absolute_path.relative_to(project_root))
    except ValueError:
        return path


def normalize_batch_media_paths(batch: CardBatch, project_root: Path) -> CardBatch:
    notes = []
    for note in batch.notes:
        audio = note.item.audio
        image = note.item.image
        item = note.item.model_copy(
            update={
                "audio": None
                if audio is None
                else audio.model_copy(
                    update={"path": project_relative_path(audio.path, project_root)}
                ),
                "image": None
                if image is None
                else image.model_copy(
                    update={"path": project_relative_path(image.path, project_root)}
                ),
            }
        )
        cards = [
            card.model_copy(
                update={
                    "audio_path": project_relative_path(card.audio_path, project_root),
                    "image_path": project_relative_path(card.image_path, project_root),
                }
            )
            for card in note.cards
        ]
        notes.append(note.model_copy(update={"item": item, "cards": cards}))

    return batch.model_copy(update={"notes": notes})


def batch_path_identity(batch_path: Path) -> BatchPathIdentity:
    requested_path = batch_path.resolve()
    canonical_path = canonical_batch_path(requested_path).resolve()
    synced_candidate = default_synced_output_path(canonical_path).resolve()

    synced_path = synced_candidate if synced_candidate.exists() and synced_candidate.is_file() else None
    if synced_path is not None:
        preview_path = synced_path
    elif canonical_path.exists() and canonical_path.is_file():
        preview_path = canonical_path
    elif requested_path.exists() and requested_path.is_file():
        preview_path = requested_path
    else:
        raise FileNotFoundError("Batch file not found.")

    return BatchPathIdentity(
        requested_path=requested_path,
        canonical_path=canonical_path,
        preview_path=preview_path,
        synced_path=synced_path,
    )


def resolve_reviewed_batch_path(
    source_batch_path: str | None,
    *,
    project_root_path: Path | None = None,
) -> tuple[int | None, str]:
    if source_batch_path is None:
        fd, temp_path = tempfile.mkstemp(prefix="korean-anki-reviewed-", suffix=".json")
        Path(temp_path).chmod(0o600)
        return fd, temp_path

    if not source_batch_path.endswith(".batch.json"):
        raise ValueError("Source batch path must be a .batch.json file.")

    resolved_path = resolve_project_path(source_batch_path, project_root_path=project_root_path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    return None, str(resolved_path)
