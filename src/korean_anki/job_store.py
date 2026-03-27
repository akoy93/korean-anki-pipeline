from __future__ import annotations

from datetime import datetime
from pathlib import Path
import threading
import uuid

from .schema import JobKind, JobPhase, JobResponse

_ACTIVE_JOB_STATUSES = {"queued", "running"}
_INTERRUPTED_JOB_ERROR = "Job interrupted by backend restart."


class JobStore:
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._lock = threading.Lock()
        self._root.mkdir(parents=True, exist_ok=True)
        self.mark_interrupted_jobs_failed()

    @property
    def root(self) -> Path:
        return self._root

    def get(self, job_id: str) -> JobResponse:
        with self._lock:
            return self._read_job(job_id)

    def create(self, kind: JobKind) -> JobResponse:
        now = datetime.now()
        job = JobResponse(
            id=uuid.uuid4().hex,
            kind=kind,
            status="queued",
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._write_job(job)
        return job

    def update(
        self,
        job_id: str,
        *,
        status: str | None = None,
        log: str | None = None,
        error: str | None = None,
        output_paths: list[str] | None = None,
        progress_current: int | None = None,
        progress_total: int | None = None,
        progress_label: str | None = None,
        phases: list[JobPhase] | None = None,
    ) -> JobResponse:
        with self._lock:
            current = self._read_job(job_id)
            logs = [*current.logs]
            if log is not None:
                logs.append(log)
            next_job = current.model_copy(
                update={
                    "status": status or current.status,
                    "logs": logs,
                    "error": error if error is not None else current.error,
                    "output_paths": output_paths
                    if output_paths is not None
                    else current.output_paths,
                    "progress_current": progress_current
                    if progress_current is not None
                    else current.progress_current,
                    "progress_total": progress_total
                    if progress_total is not None
                    else current.progress_total,
                    "progress_label": progress_label
                    if progress_label is not None
                    else current.progress_label,
                    "phases": phases if phases is not None else current.phases,
                    "updated_at": datetime.now(),
                }
            )
            self._write_job(next_job)
        return next_job

    def mark_interrupted_jobs_failed(self) -> int:
        with self._lock:
            repaired = 0
            for path in sorted(self._root.glob("*.json")):
                job = JobResponse.model_validate_json(path.read_text(encoding="utf-8"))
                if job.status not in _ACTIVE_JOB_STATUSES:
                    continue
                repaired += 1
                self._write_job(
                    job.model_copy(
                        update={
                            "status": "failed",
                            "error": _INTERRUPTED_JOB_ERROR,
                            "updated_at": datetime.now(),
                        }
                    )
                )
            return repaired

    def _read_job(self, job_id: str) -> JobResponse:
        path = self._job_path(job_id)
        if not path.exists():
            raise KeyError(job_id)
        return JobResponse.model_validate_json(path.read_text(encoding="utf-8"))

    def _write_job(self, job: JobResponse) -> None:
        path = self._job_path(job.id)
        temp_path = path.with_suffix(f"{path.suffix}.tmp")
        temp_path.write_text(
            job.model_dump_json(indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temp_path.replace(path)

    def _job_path(self, job_id: str) -> Path:
        return self._root / f"{job_id}.json"
