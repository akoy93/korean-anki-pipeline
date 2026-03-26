from __future__ import annotations

import os
from pathlib import Path
import tempfile


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
