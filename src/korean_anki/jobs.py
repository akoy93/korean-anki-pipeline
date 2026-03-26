from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from email.parser import BytesParser
from email.policy import default
from io import BytesIO
from pathlib import Path
import threading
import uuid

from . import application, path_policy
from .schema import JobResponse, NewVocabJobRequest, RawSourceAsset, SyncMediaJobRequest


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


_JOBS: dict[str, JobResponse] = {}
_JOBS_LOCK = threading.Lock()
_EXECUTOR = ThreadPoolExecutor(max_workers=2)


def job_snapshot(job_id: str) -> JobResponse:
    with _JOBS_LOCK:
        return _JOBS[job_id]


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
        kind=kind,
        status="queued",
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    with _JOBS_LOCK:
        _JOBS[job.id] = job
    return job


def _run_job(job_id: str, run: Callable[[str], list[str]]) -> None:
    update_job(job_id, status="running")
    try:
        output_paths = run(job_id)
        update_job(job_id, status="succeeded", output_paths=output_paths)
    except Exception as error:  # noqa: BLE001
        update_job(job_id, status="failed", error=str(error))


def submit_job(kind: str, run: Callable[[str], list[str]]) -> JobResponse:
    job = _create_job(kind)
    _EXECUTOR.submit(_run_job, job.id, run)
    return job


def parse_bool_field(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def field_value(form: MultipartForm, key: str) -> str | None:
    if key not in form:
        return None
    value = form.getvalue(key)
    if isinstance(value, str):
        return value
    return None


def save_upload(file_item: MultipartField, output_path: Path) -> None:
    if file_item.file is None:
        raise ValueError("Uploaded field is missing file content.")
    file_item.file.seek(0)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as handle:
        handle.write(file_item.file.read())


def lesson_generate_job(_job_id: str, form: MultipartForm) -> list[str]:
    lesson_date = field_value(form, "lesson_date")
    title = field_value(form, "title")
    topic = field_value(form, "topic")
    source_summary = field_value(form, "source_summary")
    if lesson_date is None or title is None or topic is None or source_summary is None:
        raise ValueError("lesson_date, title, topic, and source_summary are required.")

    project_root = path_policy.project_root()
    lesson_root = application.unique_lesson_root(project_root, lesson_date, topic)
    raw_source_dir = lesson_root / "raw-sources"
    raw_source_dir.mkdir(parents=True, exist_ok=True)

    raw_sources: list[RawSourceAsset] = []
    image_fields = form["images"] if "images" in form else []
    image_items = image_fields if isinstance(image_fields, list) else [image_fields]
    for index, image_item in enumerate(image_items, start=1):
        if not isinstance(image_item, MultipartField) or not image_item.filename:
            continue
        image_path = raw_source_dir / f"{index:02d}-{Path(image_item.filename).name}"
        save_upload(image_item, image_path)
        raw_sources.append(RawSourceAsset(kind="image", path=str(image_path), description="Lesson image"))

    notes_text = field_value(form, "notes_text")
    if notes_text is not None and notes_text.strip():
        notes_path = raw_source_dir / "notes.txt"
        notes_path.write_text(notes_text, encoding="utf-8")
        raw_sources.append(RawSourceAsset(kind="text", path=str(notes_path), description="User-provided raw notes"))

    if not raw_sources:
        raise ValueError("At least one image is required.")

    artifacts = application.generate_lesson_batches_from_sources(
        project_root=project_root,
        lesson_root=lesson_root,
        title=title,
        lesson_date=lesson_date,
        topic=topic,
        source_summary=source_summary,
        raw_sources=raw_sources,
        with_audio=parse_bool_field(field_value(form, "with_audio"), default=True),
    )
    return [str(path.relative_to(project_root)) for path in artifacts.batch_paths]


def new_vocab_job(job_id: str, raw_body: str) -> list[str]:
    request = NewVocabJobRequest.model_validate_json(raw_body)
    project_root = path_policy.project_root()
    output_path = application.unique_new_vocab_output_path(project_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lesson_id = output_path.name.removesuffix(".batch.json")
    progress_total = request.count * (5 if request.with_audio else 4)
    progress_current = 0

    def advance_progress(label: str, step: int = 1) -> None:
        nonlocal progress_current
        progress_current += step
        update_job(
            job_id,
            progress_current=progress_current,
            progress_total=progress_total,
            progress_label=label,
        )

    update_job(
        job_id,
        progress_current=0,
        progress_total=0,
        progress_label="Planning vocab candidates",
    )

    application.generate_new_vocab_batch(
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


def sync_media_job(_job_id: str, raw_body: str) -> list[str]:
    request = SyncMediaJobRequest.model_validate_json(raw_body)
    project_root = path_policy.project_root()
    result = application.sync_media_file(
        input_path=path_policy.resolve_project_path(request.input_path, project_root_path=project_root),
        output_path=path_policy.resolve_project_path(request.output_path, project_root_path=project_root)
        if request.output_path is not None
        else None,
        media_dir=project_root / request.media_dir,
        project_root=project_root,
        anki_url=request.anki_url,
        sync_first=request.sync_first,
    )
    return [str(result.output_path.relative_to(project_root))]
