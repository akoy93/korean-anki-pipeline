from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import tempfile


@dataclass(frozen=True)
class BatchPathIdentity:
    requested_path: Path
    canonical_path: Path
    preview_path: Path
    synced_path: Path | None


def project_root() -> Path:
    return Path.cwd().resolve()


def media_root(*, project_root_path: Path | None = None) -> Path:
    root = (project_root_path or project_root()).resolve()
    return (root / "data" / "media").resolve()


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
