from __future__ import annotations

import cgi
import json
import os
import re
import tempfile
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Callable
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import cast
from urllib.parse import unquote, urlparse

from pydantic import ValidationError

from .anki import (
    ANKI_MODEL_NAME,
    AnkiConnectClient,
    existing_model_note_keys,
    plan_push,
    push_batch,
    sync_batch_media,
    sync_lesson_media,
)
from .cards import generate_batch
from .llm import generate_pronunciations, read_lesson, read_transcription, transcribe_sources, write_json
from .media import enrich_audio, enrich_new_vocab_images
from .new_vocab import build_new_vocab_document_from_state
from .schema import (
    CardBatch,
    DashboardBatch,
    DashboardLessonContext,
    DashboardResponse,
    DashboardStats,
    JobResponse,
    LessonTranscription,
    NewVocabJobRequest,
    PushRequest,
    PushResult,
    RawSourceAsset,
    ServiceStatus,
    SyncMediaJobRequest,
)
from .stages import build_lesson_documents, qa_transcription, write_lesson_documents
from .study_state import build_study_state

_SLUG_RE = re.compile(r"[^a-zA-Z0-9가-힣]+")
_JOBS: dict[str, JobResponse] = {}
_JOBS_LOCK = threading.Lock()
_EXECUTOR = ThreadPoolExecutor(max_workers=2)


def _slugify(value: str) -> str:
    slug = _SLUG_RE.sub("-", value).strip("-").lower()
    return slug or "lesson"


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
    name = input_path.name
    if name.endswith(".batch.json"):
        return input_path.with_name(f"{name.removesuffix('.batch.json')}.synced.batch.json")
    if name.endswith(".lesson.json"):
        return input_path.with_name(f"{name.removesuffix('.lesson.json')}.synced.lesson.json")
    return input_path.with_name(f"{name}.synced")


def _project_relative_path(path: str | None, project_root: Path) -> str | None:
    if path is None:
        return None

    media_path = Path(path)
    if not media_path.is_absolute():
        return path

    return str(media_path.relative_to(project_root))


def _normalize_batch_media_paths(batch: CardBatch, project_root: Path) -> CardBatch:
    notes = []
    for note in batch.notes:
        audio = note.item.audio
        image = note.item.image
        item = note.item.model_copy(
            update={
                "audio": None
                if audio is None
                else audio.model_copy(update={"path": _project_relative_path(audio.path, project_root)}),
                "image": None
                if image is None
                else image.model_copy(update={"path": _project_relative_path(image.path, project_root)}),
            }
        )
        cards = [
            card.model_copy(
                update={
                    "audio_path": _project_relative_path(card.audio_path, project_root),
                    "image_path": _project_relative_path(card.image_path, project_root),
                }
            )
            for card in note.cards
        ]
        notes.append(note.model_copy(update={"item": item, "cards": cards}))

    return batch.model_copy(update={"notes": notes})


def _unique_new_vocab_output_path(project_root: Path) -> Path:
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    output_path = project_root / "data/generated" / f"new-vocab-{timestamp}.batch.json"
    suffix = 2
    while output_path.exists():
        output_path = project_root / "data/generated" / f"new-vocab-{timestamp}-{suffix}.batch.json"
        suffix += 1
    return output_path


def _unique_lesson_root(project_root: Path, lesson_date: str, topic: str) -> Path:
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


def _service_status() -> ServiceStatus:
    anki_connect_ok = False
    anki_connect_version: int | None = None
    try:
      result = AnkiConnectClient().invoke("version")
      if isinstance(result, int):
          anki_connect_ok = True
          anki_connect_version = result
    except Exception:  # noqa: BLE001
      anki_connect_ok = False

    return ServiceStatus(
        backend_ok=True,
        anki_connect_ok=anki_connect_ok,
        anki_connect_version=anki_connect_version,
        openai_configured=bool(os.environ.get("OPENAI_API_KEY")),
    )


def _dashboard_batch(batch_path: Path) -> DashboardBatch | None:
    try:
        batch = CardBatch.model_validate_json(batch_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None

    approved_notes = [note for note in batch.notes if note.approved]
    approved_cards = [card for note in approved_notes for card in note.cards if card.approved]
    lanes = sorted({note.lane for note in batch.notes})

    return DashboardBatch(
        path=str(batch_path.relative_to(_project_root())),
        title=batch.metadata.title,
        topic=batch.metadata.topic,
        lesson_date=batch.metadata.lesson_date,
        target_deck=batch.metadata.target_deck,
        notes=len(batch.notes),
        cards=sum(len(note.cards) for note in batch.notes),
        approved_notes=len(approved_notes),
        approved_cards=len(approved_cards),
        audio_notes=sum(1 for note in batch.notes if note.item.audio is not None),
        image_notes=sum(1 for note in batch.notes if note.item.image is not None),
        exact_duplicates=sum(1 for note in batch.notes if note.duplicate_status == "exact-duplicate"),
        near_duplicates=sum(1 for note in batch.notes if note.duplicate_status == "near-duplicate"),
        lanes=cast(list, lanes),
    )


def _dashboard_lesson_context(transcription_path: Path) -> DashboardLessonContext | None:
    try:
        transcription = LessonTranscription.model_validate_json(transcription_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None

    return DashboardLessonContext(
        path=str(transcription_path.relative_to(_project_root())),
        label=f"{transcription.lesson_date.isoformat()} • {transcription.title} • {transcription.theme}",
    )


def _canonical_batch_path(batch_path: Path) -> Path:
    if batch_path.name.endswith(".synced.batch.json"):
        return batch_path.with_name(f"{batch_path.name.removesuffix('.synced.batch.json')}.batch.json")
    return batch_path


def _batch_media_hydrated(batch: DashboardBatch) -> bool:
    resolved_path = _resolve_project_path(batch.path)
    try:
        parsed_batch = CardBatch.model_validate_json(resolved_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return False

    return any(note.item.audio is not None or note.item.image is not None for note in parsed_batch.notes)


def _dashboard_response() -> DashboardResponse:
    project_root = _project_root()
    all_batch_paths = sorted(
        [
            *project_root.glob("lessons/**/generated/*.batch.json"),
            *project_root.glob("data/generated/*.batch.json"),
        ],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    synced_paths = {
        _canonical_batch_path(path): path
        for path in all_batch_paths
        if path.name.endswith(".synced.batch.json")
    }
    canonical_batch_paths = [path for path in all_batch_paths if not path.name.endswith(".synced.batch.json")]
    recent_batches = [batch for path in canonical_batch_paths if (batch := _dashboard_batch(path)) is not None]

    lane_counts: dict[str, int] = {}
    for batch in recent_batches:
        for lane in batch.lanes:
            lane_counts[lane] = lane_counts.get(lane, 0) + batch.notes

    anki_note_count = 0
    anki_card_count = 0
    anki_deck_counts: dict[str, int] = {}
    anki_note_keys: set[str] = set()
    try:
        client = AnkiConnectClient()
        note_ids = client.invoke("findNotes", query=f'note:"{ANKI_MODEL_NAME}"')
        if isinstance(note_ids, list):
            anki_note_count = len(note_ids)
        card_ids = client.invoke("findCards", query=f'note:"{ANKI_MODEL_NAME}"')
        if isinstance(card_ids, list):
            anki_card_count = len(card_ids)
        deck_names = client.invoke("deckNames")
        if isinstance(deck_names, list):
            for deck_name in deck_names:
                if not isinstance(deck_name, str) or not deck_name.startswith("Korean::"):
                    continue
                deck_cards = client.invoke("findCards", query=f'deck:"{deck_name}" note:"{ANKI_MODEL_NAME}"')
                if isinstance(deck_cards, list) and deck_cards:
                    anki_deck_counts[deck_name] = len(deck_cards)
        anki_note_keys = existing_model_note_keys()
    except Exception:  # noqa: BLE001
        anki_note_count = 0
        anki_card_count = 0
        anki_deck_counts = {}
        anki_note_keys = set()

    resolved_batches: list[DashboardBatch] = []
    for batch in recent_batches:
        canonical_path = _resolve_project_path(batch.path)
        synced_batch_path = synced_paths.get(canonical_path)
        push_status = "not-pushed"
        if batch.approved_notes > 0 and all(note.note_key in anki_note_keys for note in CardBatch.model_validate_json(canonical_path.read_text(encoding="utf-8")).notes if note.approved):
            push_status = "synced" if synced_batch_path is not None else "pushed"
        resolved_batches.append(
            batch.model_copy(
                update={
                    "push_status": push_status,
                    "media_hydrated": _batch_media_hydrated(batch),
                    "synced_batch_path": str(synced_batch_path.relative_to(project_root))
                    if synced_batch_path is not None
                    else None,
                }
            )
        )

    lesson_contexts = [
        context
        for path in sorted(project_root.glob("lessons/*/transcription.json"), reverse=True)
        if (context := _dashboard_lesson_context(path)) is not None
    ]
    syncable_files = sorted(
        str(path.relative_to(project_root))
        for path in [
            *project_root.glob("lessons/**/generated/*.batch.json"),
            *project_root.glob("data/generated/*.batch.json"),
        ]
        if not path.name.endswith(".synced.batch.json")
    )

    return DashboardResponse(
        status=_service_status(),
        stats=DashboardStats(
            local_batch_count=len(resolved_batches),
            local_note_count=sum(batch.notes for batch in resolved_batches),
            local_card_count=sum(batch.cards for batch in resolved_batches),
            pending_push_count=sum(
                1
                for batch in resolved_batches
                if batch.push_status == "not-pushed" and batch.approved_notes > 0 and batch.exact_duplicates == 0
            ),
            audio_note_count=sum(batch.audio_notes for batch in resolved_batches),
            image_note_count=sum(batch.image_notes for batch in resolved_batches),
            lane_counts=lane_counts,
            anki_note_count=anki_note_count,
            anki_card_count=anki_card_count,
            anki_deck_counts=anki_deck_counts,
        ),
        recent_batches=resolved_batches[:20],
        lesson_contexts=lesson_contexts,
        syncable_files=syncable_files,
    )


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


def _field_value(form: cgi.FieldStorage, key: str) -> str | None:
    if key not in form:
        return None
    value = form.getvalue(key)
    if isinstance(value, str):
        return value
    return None


def _save_upload(file_item: cgi.FieldStorage, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as handle:
        handle.write(file_item.file.read())


def _lesson_generate_job(_job_id: str, form: cgi.FieldStorage) -> list[str]:
    lesson_date = _field_value(form, "lesson_date")
    title = _field_value(form, "title")
    topic = _field_value(form, "topic")
    source_summary = _field_value(form, "source_summary")
    if lesson_date is None or title is None or topic is None or source_summary is None:
        raise ValueError("lesson_date, title, topic, and source_summary are required.")

    lesson_root = _unique_lesson_root(_project_root(), lesson_date, topic)
    lesson_slug = lesson_root.name
    raw_source_dir = lesson_root / "raw-sources"
    generated_dir = lesson_root / "generated"
    raw_source_dir.mkdir(parents=True, exist_ok=True)
    generated_dir.mkdir(parents=True, exist_ok=True)

    raw_sources: list[RawSourceAsset] = []
    image_fields = form["images"] if "images" in form else []
    image_items = image_fields if isinstance(image_fields, list) else [image_fields]
    for index, image_item in enumerate(image_items, start=1):
        if not isinstance(image_item, cgi.FieldStorage) or not image_item.filename:
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

    transcription = transcribe_sources(
        lesson_id=f"italki-{lesson_slug}",
        title=title,
        lesson_date=lesson_date,
        source_summary=source_summary,
        raw_sources=raw_sources,
    )
    transcription_path = lesson_root / "transcription.json"
    transcription_path.write_text(transcription.model_dump_json(indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    qa_report = qa_transcription(transcription)
    qa_path = lesson_root / "qa-report.json"
    qa_path.write_text(qa_report.model_dump_json(indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if not qa_report.passed:
        raise ValueError("Lesson QA failed.")

    missing_pronunciations = [
        entry.korean
        for section in transcription.sections
        for entry in section.entries
        if entry.pronunciation is None
    ]
    pronunciation_lookup = generate_pronunciations(missing_pronunciations)
    documents = build_lesson_documents(transcription, pronunciation_lookup=pronunciation_lookup)
    lesson_paths = write_lesson_documents(documents, generated_dir)

    with_audio = _parse_bool_field(_field_value(form, "with_audio"), default=True)
    output_paths: list[str] = []
    for lesson_path in lesson_paths:
        document = read_lesson(lesson_path)
        if with_audio:
            document = enrich_audio(document, _project_root() / "data/media/audio")
        batch_path = lesson_path.with_suffix(".batch.json")
        state = build_study_state(_project_root(), exclude_batch_path=batch_path)
        batch = generate_batch(document, study_state=state)
        batch_path.write_text(batch.model_dump_json(indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        output_paths.append(str(batch_path.relative_to(_project_root())))

    return output_paths


def _new_vocab_job(job_id: str, raw_body: str) -> list[str]:
    request = NewVocabJobRequest.model_validate_json(raw_body)
    project_root = _project_root()
    output_path = _unique_new_vocab_output_path(project_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lesson_id = output_path.name.removesuffix(".batch.json")
    progress_total = 0
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

    state = build_study_state(project_root, anki_url=request.anki_url, exclude_batch_path=output_path)
    document = build_new_vocab_document_from_state(
        state,
        lesson_id=lesson_id,
        title="New Vocab",
        lesson_date=date.today(),
        count=request.count,
        gap_ratio=request.gap_ratio,
        lesson_context_path=Path(request.lesson_context) if request.lesson_context is not None else None,
        target_deck=request.target_deck,
    )
    progress_total = len(document.items) * (5 if request.with_audio else 4)
    _update_job(
        job_id,
        progress_current=0,
        progress_total=progress_total,
        progress_label="Generating images",
    )
    document = enrich_new_vocab_images(
        document,
        project_root / "data/media/images",
        image_quality=request.image_quality,
        on_item_complete=lambda: advance_progress("Generating images"),
    )
    if request.with_audio:
        document = enrich_audio(
            document,
            project_root / "data/media/audio",
            on_item_complete=lambda: advance_progress("Generating audio"),
        )

    batch = generate_batch(
        document,
        study_state=state,
        on_note_generated=lambda note: advance_progress("Generating cards", step=len(note.cards)),
    )
    batch = _normalize_batch_media_paths(batch, project_root)
    output_path.write_text(batch.model_dump_json(indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return [str(output_path.relative_to(project_root))]


def _sync_media_job(_job_id: str, raw_body: str) -> list[str]:
    request = SyncMediaJobRequest.model_validate_json(raw_body)
    input_path = _resolve_project_path(request.input_path)
    output_path = (
        _resolve_project_path(request.output_path)
        if request.output_path is not None
        else _default_synced_output_path(input_path)
    )
    raw_text = input_path.read_text(encoding="utf-8")

    try:
        batch = CardBatch.model_validate_json(raw_text)
    except Exception:  # noqa: BLE001
        batch = None

    if batch is not None:
        synced_batch, _summary = sync_batch_media(
            batch,
            media_dir=_project_root() / request.media_dir,
            anki_url=request.anki_url,
            sync_first=request.sync_first,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        synced_batch = _normalize_batch_media_paths(synced_batch, _project_root())
        output_path.write_text(synced_batch.model_dump_json(indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    else:
        synced_document, _summary = sync_lesson_media(
            read_lesson(input_path),
            media_dir=_project_root() / request.media_dir,
            anki_url=request.anki_url,
            sync_first=request.sync_first,
        )
        write_json(synced_document, output_path)

    return [str(output_path.relative_to(_project_root()))]


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

    def _read_multipart(self) -> cgi.FieldStorage:
        return cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": self.headers.get("Content-Type", ""),
                "CONTENT_LENGTH": self.headers.get("Content-Length", "0"),
            },
            keep_blank_values=True,
        )

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

            if request.dry_run:
                result = plan_push(
                    request.batch,
                    deck_name=request.deck_name,
                    anki_url=request.anki_url,
                )
                self._send_json(200, cast(dict[str, object], result.model_dump()))
                return

            fd, reviewed_batch_path = _resolve_reviewed_batch_path(request.source_batch_path)
            reviewed_batch = _normalize_batch_media_paths(request.batch, _project_root())
            Path(reviewed_batch_path).write_text(
                reviewed_batch.model_dump_json(indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

            result = push_batch(
                request.batch,
                deck_name=request.deck_name,
                anki_url=request.anki_url,
                sync=request.sync,
            )
            result = PushResult.model_validate(result.model_dump() | {"reviewed_batch_path": reviewed_batch_path})
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
