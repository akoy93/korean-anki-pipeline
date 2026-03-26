from __future__ import annotations

from pathlib import Path

from . import dashboard_service, jobs, path_policy
from .http_api import PushServiceHandler, run_server
from .push_workflow_service import (
    batch_is_pushed,
    batch_media_hydrated,
    batch_referenced_media_paths,
    delete_batch,
)
from .service_support import (
    normalize_batch_media_paths,
    unique_lesson_root,
    unique_new_vocab_output_path,
)

MultipartField = jobs.MultipartField
MultipartForm = jobs.MultipartForm


def _project_root() -> Path:
    return path_policy.project_root()


def _resolve_project_path(relative_path: str) -> Path:
    return path_policy.resolve_project_path(relative_path, project_root_path=_project_root())


def _resolve_media_reference_path(path: str) -> Path:
    return path_policy.resolve_media_reference_path(path, project_root_path=_project_root())


def _resolve_reviewed_batch_path(source_batch_path: str | None) -> tuple[int | None, str]:
    return path_policy.resolve_reviewed_batch_path(source_batch_path, project_root_path=_project_root())


def _default_synced_output_path(input_path: Path) -> Path:
    return path_policy.default_synced_output_path(input_path)


def _project_relative_path(path: str | None, project_root: Path) -> str | None:
    return path_policy.project_relative_path(path, project_root)


def _normalize_batch_media_paths(batch, project_root: Path):
    return normalize_batch_media_paths(batch, project_root)


def _unique_new_vocab_output_path(project_root: Path) -> Path:
    return unique_new_vocab_output_path(project_root)


def _unique_lesson_root(project_root: Path, lesson_date: str, topic: str) -> Path:
    return unique_lesson_root(project_root, lesson_date, topic)


def _service_status():
    return dashboard_service.service_status()


def _dashboard_response():
    return dashboard_service.dashboard_response(project_root_path=_project_root())


def _batch_media_hydrated(batch_path: Path) -> bool:
    return batch_media_hydrated(batch_path, project_root=_project_root())


def _batch_referenced_media_paths(batch) -> set[Path]:
    return batch_referenced_media_paths(batch, project_root=_project_root())


def _batch_is_pushed(batch, *, anki_url: str) -> bool:
    return batch_is_pushed(batch, anki_url=anki_url)


def _delete_batch(request):
    return delete_batch(
        _resolve_project_path(request.batch_path),
        project_root=_project_root(),
        anki_url=request.anki_url,
    )


def _job_snapshot(job_id: str):
    return jobs.job_snapshot(job_id)


def _update_job(
    job_id: str,
    *,
    status: str | None = None,
    log: str | None = None,
    error: str | None = None,
    output_paths: list[str] | None = None,
    progress_current: int | None = None,
    progress_total: int | None = None,
    progress_label: str | None = None,
) -> None:
    jobs.update_job(
        job_id,
        status=status,
        log=log,
        error=error,
        output_paths=output_paths,
        progress_current=progress_current,
        progress_total=progress_total,
        progress_label=progress_label,
    )


def _submit_job(kind: str, run):
    return jobs.submit_job(kind, run)


def _lesson_generate_job(job_id: str, form: MultipartForm) -> list[str]:
    return jobs.lesson_generate_job(job_id, form)


def _new_vocab_job(job_id: str, raw_body: str) -> list[str]:
    return jobs.new_vocab_job(job_id, raw_body)


def _sync_media_job(job_id: str, raw_body: str) -> list[str]:
    return jobs.sync_media_job(job_id, raw_body)


__all__ = [
    "MultipartField",
    "MultipartForm",
    "PushServiceHandler",
    "_batch_is_pushed",
    "_batch_media_hydrated",
    "_batch_referenced_media_paths",
    "_dashboard_response",
    "_default_synced_output_path",
    "_delete_batch",
    "_job_snapshot",
    "_lesson_generate_job",
    "_new_vocab_job",
    "_normalize_batch_media_paths",
    "_project_relative_path",
    "_project_root",
    "_resolve_media_reference_path",
    "_resolve_project_path",
    "_resolve_reviewed_batch_path",
    "_service_status",
    "_submit_job",
    "_sync_media_job",
    "_unique_lesson_root",
    "_unique_new_vocab_output_path",
    "_update_job",
    "run_server",
]
