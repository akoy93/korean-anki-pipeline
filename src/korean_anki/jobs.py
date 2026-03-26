from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading

from .job_store import JobStore
from . import path_policy
from .job_handlers import lesson_generate_job, new_vocab_job, sync_media_job
from .multipart_form import MultipartForm
from .schema import JobResponse

_JOB_STORES: dict[Path, JobStore] = {}
_JOB_STORES_LOCK = threading.Lock()
_EXECUTOR = ThreadPoolExecutor(max_workers=2)


def _job_store() -> JobStore:
    project_root = path_policy.project_root().resolve()
    with _JOB_STORES_LOCK:
        store = _JOB_STORES.get(project_root)
        if store is None:
            store = JobStore(path_policy.job_state_root(project_root_path=project_root))
            _JOB_STORES[project_root] = store
        return store


def job_snapshot(job_id: str) -> JobResponse:
    return _job_store().get(job_id)


def update_job(
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
    _job_store().update(
        job_id,
        status=status,
        log=log,
        error=error,
        output_paths=output_paths,
        progress_current=progress_current,
        progress_total=progress_total,
        progress_label=progress_label,
    )


def _create_job(kind: str) -> JobResponse:
    return _job_store().create(kind)


def _run_job(job_id: str, run: Callable[[str], list[str]]) -> None:
    update_job(job_id, status="running")
    try:
        output_paths = run(job_id)
        update_job(job_id, status="succeeded", output_paths=output_paths)
    except Exception as error:  # noqa: BLE001
        update_job(job_id, status="failed", error=str(error))


def _submit_job(kind: str, run: Callable[[str], list[str]]) -> JobResponse:
    job = _create_job(kind)
    _EXECUTOR.submit(_run_job, job.id, run)
    return job


def submit_lesson_generate_job(form: MultipartForm) -> JobResponse:
    return _submit_job("lesson-generate", lambda _job_id: lesson_generate_job(form))


def submit_new_vocab_job(raw_body: str) -> JobResponse:
    return _submit_job(
        "new-vocab",
        lambda job_id: new_vocab_job(
            raw_body,
            on_progress=lambda **progress: update_job(job_id, **progress),
        ),
    )


def submit_sync_media_job(raw_body: str) -> JobResponse:
    return _submit_job("sync-media", lambda _job_id: sync_media_job(raw_body))
