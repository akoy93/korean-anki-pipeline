from __future__ import annotations

from dataclasses import dataclass
from email.parser import BytesParser
from email.policy import default
from io import BytesIO
import json
import os
import tempfile
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Callable
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import cast
from urllib.parse import unquote, urlparse

from pydantic import ValidationError

from .application import (
    batch_is_pushed as batch_is_pushed_service,
    batch_media_hydrated as batch_media_hydrated_service,
    batch_referenced_media_paths as batch_referenced_media_paths_service,
    build_dashboard_response as build_dashboard_response_service,
    build_service_status as build_service_status_service,
    default_synced_output_path as default_synced_output_path_service,
    delete_batch as delete_batch_service,
    generate_lesson_batches_from_sources,
    generate_new_vocab_batch,
    handle_push_request,
    normalize_batch_media_paths as normalize_batch_media_paths_service,
    project_relative_path as project_relative_path_service,
    sync_media_file,
    unique_lesson_root as unique_lesson_root_service,
    unique_new_vocab_output_path as unique_new_vocab_output_path_service,
)
from .cards import refresh_preview_note
from .schema import (
    DeleteBatchRequest,
    JobResponse,
    NewVocabJobRequest,
    PreviewNoteRefreshRequest,
    PushRequest,
    RawSourceAsset,
    SyncMediaJobRequest,
)

_JOBS: dict[str, JobResponse] = {}
_JOBS_LOCK = threading.Lock()
_EXECUTOR = ThreadPoolExecutor(max_workers=2)


@dataclass
class MultipartField:
    name: str
    value: str | None = None
    filename: str | None = None
    file: BytesIO | None = None


class MultipartForm:
    def __init__(self, fields: dict[str, list[MultipartField]]) -> None:
        self._fields = fields

    def __contains__(self, key: str) -> bool:
        return key in self._fields

    def __getitem__(self, key: str) -> MultipartField | list[MultipartField]:
        values = self._fields[key]
        if len(values) == 1:
            return values[0]
        return values

    def getvalue(self, key: str) -> str | list[str] | None:
        values = self._fields.get(key)
        if not values:
            return None
        text_values = [value.value for value in values if value.value is not None]
        if not text_values:
            return None
        if len(text_values) == 1:
            return text_values[0]
        return text_values

    @classmethod
    def parse(cls, content_type: str, raw_body: bytes) -> MultipartForm:
        parser = BytesParser(policy=default)
        message = parser.parsebytes(
            (
                f"Content-Type: {content_type}\r\n"
                "MIME-Version: 1.0\r\n"
                "\r\n"
            ).encode("utf-8")
            + raw_body
        )
        if not message.is_multipart():
            raise ValueError("Expected multipart form-data request.")

        fields: dict[str, list[MultipartField]] = {}
        for part in message.iter_parts():
            if part.get_content_disposition() != "form-data":
                continue

            name = part.get_param("name", header="content-disposition")
            if not isinstance(name, str) or not name:
                continue

            payload = part.get_payload(decode=True) or b""
            filename = part.get_filename()
            value = None
            file = None
            if filename is None:
                charset = part.get_content_charset() or "utf-8"
                value = payload.decode(charset)
            else:
                file = BytesIO(payload)

            fields.setdefault(name, []).append(
                MultipartField(name=name, value=value, filename=filename, file=file)
            )

        return cls(fields)

def _project_root() -> Path:
    return Path.cwd().resolve()


def _resolve_project_path(relative_path: str) -> Path:
    if Path(relative_path).is_absolute():
        raise ValueError("Use a project-relative path.")

    project_root = _project_root()
    resolved_path = (project_root / relative_path).resolve()
    normalized_root = f"{project_root}{os.sep}"
    if resolved_path != project_root and not str(resolved_path).startswith(normalized_root):
        raise ValueError("Path escapes project root.")
    return resolved_path


def _resolve_media_reference_path(path: str) -> Path:
    media_path = Path(path)
    if not media_path.is_absolute():
        return _resolve_project_path(path)

    project_root = _project_root()
    resolved_path = media_path.resolve()
    normalized_root = f"{project_root}{os.sep}"
    if resolved_path != project_root and not str(resolved_path).startswith(normalized_root):
        raise ValueError("Path escapes project root.")
    return resolved_path


def _resolve_reviewed_batch_path(source_batch_path: str | None) -> tuple[int | None, str]:
    if source_batch_path is None:
        fd, temp_path = tempfile.mkstemp(prefix="korean-anki-reviewed-", suffix=".json")
        Path(temp_path).chmod(0o600)
        return fd, temp_path

    if not source_batch_path.endswith(".batch.json"):
        raise ValueError("Source batch path must be a .batch.json file.")

    resolved_path = _resolve_project_path(source_batch_path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    return None, str(resolved_path)


def _default_synced_output_path(input_path: Path) -> Path:
    return default_synced_output_path_service(input_path)


def _project_relative_path(path: str | None, project_root: Path) -> str | None:
    return project_relative_path_service(path, project_root)


def _normalize_batch_media_paths(batch, project_root: Path):
    return normalize_batch_media_paths_service(batch, project_root)


def _unique_new_vocab_output_path(project_root: Path) -> Path:
    return unique_new_vocab_output_path_service(project_root)


def _unique_lesson_root(project_root: Path, lesson_date: str, topic: str) -> Path:
    return unique_lesson_root_service(project_root, lesson_date, topic)


def _service_status():
    return build_service_status_service()


def _batch_media_hydrated(batch_path: Path) -> bool:
    return batch_media_hydrated_service(batch_path, project_root=_project_root())


def _batch_referenced_media_paths(batch) -> set[Path]:
    return batch_referenced_media_paths_service(batch, project_root=_project_root())


def _batch_is_pushed(batch, *, anki_url: str) -> bool:
    return batch_is_pushed_service(batch, anki_url=anki_url)


def _delete_batch(request: DeleteBatchRequest):
    return delete_batch_service(
        _resolve_project_path(request.batch_path),
        project_root=_project_root(),
        anki_url=request.anki_url,
    )


def _dashboard_response():
    return build_dashboard_response_service(project_root=_project_root())


def _job_snapshot(job_id: str) -> JobResponse:
    with _JOBS_LOCK:
        return _JOBS[job_id]


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
    with _JOBS_LOCK:
        current = _JOBS[job_id]
        logs = [*current.logs]
        if log is not None:
            logs.append(log)
        _JOBS[job_id] = current.model_copy(
            update={
                "status": status or current.status,
                "logs": logs,
                "error": error if error is not None else current.error,
                "output_paths": output_paths if output_paths is not None else current.output_paths,
                "progress_current": progress_current if progress_current is not None else current.progress_current,
                "progress_total": progress_total if progress_total is not None else current.progress_total,
                "progress_label": progress_label if progress_label is not None else current.progress_label,
                "updated_at": datetime.now(),
            }
        )


def _create_job(kind: str) -> JobResponse:
    job = JobResponse(
        id=uuid.uuid4().hex,
        kind=cast(object, kind),
        status="queued",
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    with _JOBS_LOCK:
        _JOBS[job.id] = job
    return job


def _run_job(job_id: str, run: Callable[[str], list[str]]) -> None:
    _update_job(job_id, status="running")
    try:
        output_paths = run(job_id)
        _update_job(job_id, status="succeeded", output_paths=output_paths)
    except Exception as error:  # noqa: BLE001
        _update_job(job_id, status="failed", error=str(error))


def _submit_job(kind: str, run: Callable[[str], list[str]]) -> JobResponse:
    job = _create_job(kind)
    _EXECUTOR.submit(_run_job, job.id, run)
    return job


def _parse_bool_field(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _field_value(form: MultipartForm, key: str) -> str | None:
    if key not in form:
        return None
    value = form.getvalue(key)
    if isinstance(value, str):
        return value
    return None


def _save_upload(file_item: MultipartField, output_path: Path) -> None:
    if file_item.file is None:
        raise ValueError("Uploaded field is missing file content.")
    file_item.file.seek(0)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as handle:
        handle.write(file_item.file.read())


def _lesson_generate_job(_job_id: str, form: MultipartForm) -> list[str]:
    lesson_date = _field_value(form, "lesson_date")
    title = _field_value(form, "title")
    topic = _field_value(form, "topic")
    source_summary = _field_value(form, "source_summary")
    if lesson_date is None or title is None or topic is None or source_summary is None:
        raise ValueError("lesson_date, title, topic, and source_summary are required.")

    lesson_root = _unique_lesson_root(_project_root(), lesson_date, topic)
    raw_source_dir = lesson_root / "raw-sources"
    raw_source_dir.mkdir(parents=True, exist_ok=True)

    raw_sources: list[RawSourceAsset] = []
    image_fields = form["images"] if "images" in form else []
    image_items = image_fields if isinstance(image_fields, list) else [image_fields]
    for index, image_item in enumerate(image_items, start=1):
        if not isinstance(image_item, MultipartField) or not image_item.filename:
            continue
        image_path = raw_source_dir / f"{index:02d}-{Path(image_item.filename).name}"
        _save_upload(image_item, image_path)
        raw_sources.append(RawSourceAsset(kind="image", path=str(image_path), description="Lesson image"))

    notes_text = _field_value(form, "notes_text")
    if notes_text is not None and notes_text.strip():
        notes_path = raw_source_dir / "notes.txt"
        notes_path.write_text(notes_text, encoding="utf-8")
        raw_sources.append(RawSourceAsset(kind="text", path=str(notes_path), description="User-provided raw notes"))

    if not raw_sources:
        raise ValueError("At least one image is required.")

    artifacts = generate_lesson_batches_from_sources(
        project_root=_project_root(),
        lesson_root=lesson_root,
        title=title,
        lesson_date=lesson_date,
        topic=topic,
        source_summary=source_summary,
        raw_sources=raw_sources,
        with_audio=_parse_bool_field(_field_value(form, "with_audio"), default=True),
    )
    return [str(path.relative_to(_project_root())) for path in artifacts.batch_paths]


def _new_vocab_job(job_id: str, raw_body: str) -> list[str]:
    request = NewVocabJobRequest.model_validate_json(raw_body)
    project_root = _project_root()
    output_path = _unique_new_vocab_output_path(project_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lesson_id = output_path.name.removesuffix(".batch.json")
    progress_total = request.count * (5 if request.with_audio else 4)
    progress_current = 0

    def advance_progress(label: str, step: int = 1) -> None:
        nonlocal progress_current
        progress_current += step
        _update_job(
            job_id,
            progress_current=progress_current,
            progress_total=progress_total,
            progress_label=label,
        )

    _update_job(
        job_id,
        progress_current=0,
        progress_total=0,
        progress_label="Planning vocab candidates",
    )

    generate_new_vocab_batch(
        project_root=project_root,
        output_path=output_path,
        lesson_id=lesson_id,
        title="New Vocab",
        lesson_date=datetime.now().date(),
        count=request.count,
        gap_ratio=request.gap_ratio,
        target_deck=request.target_deck,
        lesson_context_path=Path(request.lesson_context) if request.lesson_context is not None else None,
        media_dir=project_root / "data/media",
        anki_url=request.anki_url,
        with_audio=request.with_audio,
        image_quality=request.image_quality,
        on_image_complete=lambda: advance_progress("Generating images"),
        on_audio_complete=lambda: advance_progress("Generating audio"),
        on_note_generated=lambda note: advance_progress("Generating cards", step=len(note.cards)),
    )
    return [str(output_path.relative_to(project_root))]


def _sync_media_job(_job_id: str, raw_body: str) -> list[str]:
    request = SyncMediaJobRequest.model_validate_json(raw_body)
    result = sync_media_file(
        input_path=_resolve_project_path(request.input_path),
        output_path=_resolve_project_path(request.output_path)
        if request.output_path is not None
        else None,
        media_dir=_project_root() / request.media_dir,
        project_root=_project_root(),
        anki_url=request.anki_url,
        sync_first=request.sync_first,
    )
    return [str(result.output_path.relative_to(_project_root()))]


class PushServiceHandler(BaseHTTPRequestHandler):
    server_version = "KoreanAnkiPushService/0.1"

    def _send_json(self, status_code: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> str:
        length = int(self.headers.get("Content-Length", "0"))
        return self.rfile.read(length).decode("utf-8")

    def _read_multipart(self) -> MultipartForm:
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length)
        return MultipartForm.parse(self.headers.get("Content-Type", ""), raw_body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self._send_json(200, {"ok": True})
            return
        if parsed.path == "/api/status":
            self._send_json(200, cast(dict[str, object], _service_status().model_dump()))
            return
        if parsed.path == "/api/dashboard":
            self._send_json(200, cast(dict[str, object], _dashboard_response().model_dump()))
            return
        if parsed.path.startswith("/api/jobs/"):
            job_id = unquote(parsed.path.removeprefix("/api/jobs/"))
            with _JOBS_LOCK:
                job = _JOBS.get(job_id)
            if job is None:
                self._send_json(404, {"error": "Job not found"})
                return
            self._send_json(200, cast(dict[str, object], job.model_dump()))
            return
        self._send_json(404, {"error": "Not found"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/push":
            self._handle_push()
            return
        if parsed.path == "/api/delete-batch":
            self._handle_delete_batch()
            return
        if parsed.path == "/api/preview-note":
            self._handle_preview_note_refresh()
            return
        if parsed.path == "/api/jobs/lesson-generate":
            self._handle_lesson_generate_job()
            return
        if parsed.path == "/api/jobs/new-vocab":
            self._handle_json_job("new-vocab", _new_vocab_job)
            return
        if parsed.path == "/api/jobs/sync-media":
            self._handle_json_job("sync-media", _sync_media_job)
            return
        self._send_json(404, {"error": "Not found"})

    def _handle_push(self) -> None:
        fd: int | None = None
        try:
            request = PushRequest.model_validate_json(self._read_body())
            reviewed_batch_path: str | None = None
            if not request.dry_run:
                fd, reviewed_batch_path = _resolve_reviewed_batch_path(request.source_batch_path)

            result = handle_push_request(
                request,
                project_root=_project_root(),
                reviewed_batch_path=reviewed_batch_path,
            )
            self._send_json(200, cast(dict[str, object], result.model_dump()))
        except ValidationError as error:
            self._send_json(400, {"error": "Invalid push request.", "details": error.errors()})
        except Exception as error:  # noqa: BLE001
            self._send_json(409, {"error": str(error)})
        finally:
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass

    def _handle_delete_batch(self) -> None:
        try:
            request = DeleteBatchRequest.model_validate_json(self._read_body())
            result = _delete_batch(request)
            self._send_json(200, cast(dict[str, object], result.model_dump()))
        except ValidationError as error:
            self._send_json(400, {"error": "Invalid delete request.", "details": error.errors()})
        except Exception as error:  # noqa: BLE001
            self._send_json(409, {"error": str(error)})

    def _handle_preview_note_refresh(self) -> None:
        try:
            request = PreviewNoteRefreshRequest.model_validate_json(self._read_body())
            refreshed_note = refresh_preview_note(request.note, request.item)
            self._send_json(200, cast(dict[str, object], refreshed_note.model_dump()))
        except ValidationError as error:
            self._send_json(400, {"error": "Invalid preview-note request.", "details": error.errors()})
        except Exception as error:  # noqa: BLE001
            self._send_json(400, {"error": str(error)})

    def _handle_lesson_generate_job(self) -> None:
        try:
            form = self._read_multipart()
            job = _submit_job("lesson-generate", lambda job_id: _lesson_generate_job(job_id, form))
            self._send_json(202, cast(dict[str, object], job.model_dump()))
        except Exception as error:  # noqa: BLE001
            self._send_json(400, {"error": str(error)})

    def _handle_json_job(self, kind: str, run_job: object) -> None:
        try:
            raw_body = self._read_body()
            job = _submit_job(kind, lambda job_id: cast("list[str]", run_job(job_id, raw_body)))
            self._send_json(202, cast(dict[str, object], job.model_dump()))
        except ValidationError as error:
            self._send_json(400, {"error": "Invalid job request.", "details": error.errors()})
        except Exception as error:  # noqa: BLE001
            self._send_json(400, {"error": str(error)})

    def log_message(self, format: str, *args: object) -> None:
        print(f"[push-service] {self.address_string()} - {format % args}")


def run_server(host: str = "127.0.0.1", port: int = 8767) -> None:
    server = ThreadingHTTPServer((host, port), PushServiceHandler)
    print(f"Push service listening on http://{host}:{port}")
    print("POST /api/push, POST /api/jobs/*, GET /api/status, GET /api/dashboard, and GET /api/health")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Shutting down push service.")
    finally:
        server.server_close()
