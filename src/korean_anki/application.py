from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import json
import os
import re
from pathlib import Path
from typing import Callable

from .anki import (
    DEFAULT_DECK,
    AnkiConnectClient,
    MediaSyncSummary,
    existing_model_note_keys,
    plan_push,
    push_batch,
    sync_batch_media,
    sync_lesson_media,
)
from .cards import generate_batch
from .llm import generate_pronunciations, read_lesson, transcribe_sources, write_json
from .media import enrich_audio, enrich_images, enrich_new_vocab_images
from .new_vocab import build_new_vocab_document_from_state
from .reading_speed import build_reading_speed_document
from .repositories import AnkiRepository, BatchRepository, invalidate_anki_snapshots, invalidate_project_snapshots
from .schema import (
    CardBatch,
    DashboardResponse,
    DeleteBatchResult,
    GeneratedNote,
    LessonDocument,
    LessonTranscription,
    PushRequest,
    PushResult,
    RawSourceAsset,
    ServiceStatus,
    StudyState,
)
from .snapshots import batch_media_hydrated as snapshot_batch_media_hydrated
from .snapshots import batch_referenced_media_paths as snapshot_batch_referenced_media_paths
from .snapshots import dashboard_response_snapshot
from .stages import build_lesson_documents, qa_transcription, write_lesson_documents
from .study_state import build_study_state

_SLUG_RE = re.compile(r"[^a-zA-Z0-9가-힣]+")


@dataclass(frozen=True)
class BatchArtifacts:
    batch: CardBatch
    study_state: StudyState
    output_path: Path
    state_output_path: Path
    generation_plan_path: Path


@dataclass(frozen=True)
class LessonGenerationArtifacts:
    lesson_root: Path
    transcription_path: Path
    qa_report_path: Path
    lesson_paths: list[Path]
    batch_paths: list[Path]


@dataclass(frozen=True)
class MediaSyncArtifacts:
    output_path: Path
    summary: MediaSyncSummary


def _slugify(value: str) -> str:
    slug = _SLUG_RE.sub("-", value).strip("-").lower()
    return slug or "lesson"


def default_synced_output_path(input_path: Path) -> Path:
    name = input_path.name
    if name.endswith(".batch.json"):
        return input_path.with_name(f"{name.removesuffix('.batch.json')}.synced.batch.json")
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

    media_path = Path(path)
    if not media_path.is_absolute():
        return path

    try:
        return str(media_path.relative_to(project_root))
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
                else audio.model_copy(update={"path": project_relative_path(audio.path, project_root)}),
                "image": None
                if image is None
                else image.model_copy(update={"path": project_relative_path(image.path, project_root)}),
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


def build_service_status(*, anki_url: str = "http://127.0.0.1:8765") -> ServiceStatus:
    anki_repository = AnkiRepository(
        anki_url,
        client_factory=AnkiConnectClient,
        note_keys_loader=existing_model_note_keys,
    )
    anki_connect_ok, anki_connect_version = anki_repository.service_status()

    return ServiceStatus(
        backend_ok=True,
        anki_connect_ok=anki_connect_ok,
        anki_connect_version=anki_connect_version,
        openai_configured=bool(os.environ.get("OPENAI_API_KEY")),
    )


def build_lesson_documents_from_transcription(
    transcription: LessonTranscription,
    *,
    output_dir: Path,
    pronunciation_model: str = "gpt-5.4",
    skip_pronunciation_fill: bool = False,
) -> list[Path]:
    pronunciation_lookup: dict[str, str] = {}
    if not skip_pronunciation_fill:
        missing_pronunciations = [
            entry.korean
            for section in transcription.sections
            for entry in section.entries
            if entry.pronunciation is None
        ]
        pronunciation_lookup = generate_pronunciations(
            missing_pronunciations,
            model=pronunciation_model,
        )

    documents = build_lesson_documents(transcription, pronunciation_lookup=pronunciation_lookup)
    return write_lesson_documents(documents, output_dir)


def _generation_plan_payload(batch: CardBatch, *, include_image_prompt: bool = False) -> dict[str, object]:
    item_fields: set[str] = {"id", "korean", "english", "item_type", "lane", "skill_tags"}
    if include_image_prompt:
        item_fields.add("image_prompt")
    return {
        "lesson_id": batch.metadata.lesson_id,
        "notes": [
            note.model_dump(
                include={
                    "item": item_fields,
                    "note_key": True,
                    "lane": True,
                    "skill_tags": True,
                    "duplicate_status": True,
                    "duplicate_note_key": True,
                    "duplicate_note_id": True,
                    "duplicate_source": True,
                    "inclusion_reason": True,
                    "approved": True,
                }
            )
            for note in batch.notes
        ],
    }


def _write_batch_artifacts(
    *,
    batch: CardBatch,
    study_state: StudyState,
    output_path: Path,
    project_root: Path,
    include_image_prompt: bool = False,
    normalize_media_paths_for_output: bool = True,
) -> BatchArtifacts:
    batch_to_write = normalize_batch_media_paths(batch, project_root) if normalize_media_paths_for_output else batch
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(batch_to_write.model_dump_json(indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    state_output_path = project_root / "state" / "study-state.json"
    state_output_path.parent.mkdir(parents=True, exist_ok=True)
    state_output_path.write_text(study_state.model_dump_json(indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    generation_plan_path = output_path.with_suffix(".generation-plan.json")
    generation_plan_path.write_text(
        json.dumps(
            _generation_plan_payload(batch_to_write, include_image_prompt=include_image_prompt),
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    invalidate_project_snapshots(project_root)

    return BatchArtifacts(
        batch=batch_to_write,
        study_state=study_state,
        output_path=output_path,
        state_output_path=state_output_path,
        generation_plan_path=generation_plan_path,
    )


def generate_batch_from_document(
    document: LessonDocument,
    *,
    output_path: Path,
    project_root: Path,
    anki_url: str = "http://127.0.0.1:8765",
    include_image_prompt: bool = False,
    normalize_media_paths_for_output: bool = True,
    on_note_generated: Callable[[GeneratedNote], None] | None = None,
) -> BatchArtifacts:
    state = build_study_state(project_root, anki_url=anki_url, exclude_batch_path=output_path)
    batch = generate_batch(
        document,
        study_state=state,
        on_note_generated=on_note_generated,
    )
    return _write_batch_artifacts(
        batch=batch,
        study_state=state,
        output_path=output_path,
        project_root=project_root,
        include_image_prompt=include_image_prompt,
        normalize_media_paths_for_output=normalize_media_paths_for_output,
    )


def generate_batch_from_lesson_file(
    *,
    input_path: Path,
    output_path: Path,
    media_dir: Path,
    project_root: Path,
    anki_url: str = "http://127.0.0.1:8765",
    with_audio: bool = False,
    with_images: bool = False,
    image_quality: str = "auto",
) -> BatchArtifacts:
    document = read_lesson(input_path)
    if with_audio:
        document = enrich_audio(document, media_dir / "audio")
    if with_images:
        document = enrich_images(document, media_dir / "images", image_quality=image_quality)
    return generate_batch_from_document(
        document,
        output_path=output_path,
        project_root=project_root,
        anki_url=anki_url,
    )


def generate_reading_speed_batch(
    *,
    project_root: Path,
    output_path: Path,
    lesson_id: str,
    title: str,
    topic: str,
    lesson_date: date,
    source_description: str,
    target_deck: str,
    max_read_aloud: int,
    max_chunked: int,
    passage_word_count: int,
    media_dir: Path,
    anki_url: str = "http://127.0.0.1:8765",
    with_audio: bool = False,
) -> BatchArtifacts:
    state = build_study_state(project_root, anki_url=anki_url, exclude_batch_path=output_path)
    document = build_reading_speed_document(
        state,
        lesson_id=lesson_id,
        title=title,
        topic=topic,
        lesson_date=lesson_date,
        source_description=source_description,
        target_deck=target_deck,
        max_read_aloud=max_read_aloud,
        max_chunked=max_chunked,
        passage_word_count=passage_word_count,
    )
    if with_audio:
        document = enrich_audio(document, media_dir / "audio")

    batch = generate_batch(document, study_state=state)
    return _write_batch_artifacts(
        batch=batch,
        study_state=state,
        output_path=output_path,
        project_root=project_root,
    )


def generate_new_vocab_batch(
    *,
    project_root: Path,
    output_path: Path,
    lesson_id: str,
    title: str,
    lesson_date: date,
    count: int,
    gap_ratio: float,
    target_deck: str,
    lesson_context_path: Path | None,
    media_dir: Path,
    anki_url: str = "http://127.0.0.1:8765",
    with_audio: bool = False,
    image_quality: str = "low",
    model: str = "gpt-5.4",
    on_image_complete: Callable[[], None] | None = None,
    on_audio_complete: Callable[[], None] | None = None,
    on_note_generated: Callable[[GeneratedNote], None] | None = None,
) -> BatchArtifacts:
    state = build_study_state(project_root, anki_url=anki_url, exclude_batch_path=output_path)
    document = build_new_vocab_document_from_state(
        state,
        lesson_id=lesson_id,
        title=title,
        lesson_date=lesson_date,
        count=count,
        gap_ratio=gap_ratio,
        lesson_context_path=lesson_context_path,
        target_deck=target_deck,
        model=model,
    )
    document = enrich_new_vocab_images(
        document,
        media_dir / "images",
        image_quality=image_quality,
        on_item_complete=on_image_complete,
    )
    if with_audio:
        document = enrich_audio(
            document,
            media_dir / "audio",
            on_item_complete=on_audio_complete,
        )

    return generate_batch_from_document(
        document,
        output_path=output_path,
        project_root=project_root,
        anki_url=anki_url,
        include_image_prompt=True,
        on_note_generated=on_note_generated,
    )


def generate_lesson_batches_from_sources(
    *,
    project_root: Path,
    lesson_root: Path | None = None,
    lesson_date: str,
    title: str,
    topic: str,
    source_summary: str,
    raw_sources: list[RawSourceAsset],
    with_audio: bool = True,
    transcription_model: str = "gpt-5.4",
    pronunciation_model: str = "gpt-5.4",
    anki_url: str = "http://127.0.0.1:8765",
) -> LessonGenerationArtifacts:
    lesson_root = lesson_root or unique_lesson_root(project_root, lesson_date, topic)
    generated_dir = lesson_root / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)

    lesson_slug = lesson_root.name
    transcription = transcribe_sources(
        lesson_id=f"italki-{lesson_slug}",
        title=title,
        lesson_date=lesson_date,
        source_summary=source_summary,
        raw_sources=raw_sources,
        model=transcription_model,
    )
    transcription_path = lesson_root / "transcription.json"
    transcription_path.write_text(transcription.model_dump_json(indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    qa_report = qa_transcription(transcription)
    qa_report_path = lesson_root / "qa-report.json"
    qa_report_path.write_text(qa_report.model_dump_json(indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if not qa_report.passed:
        raise ValueError("Lesson QA failed.")

    lesson_paths = build_lesson_documents_from_transcription(
        transcription,
        output_dir=generated_dir,
        pronunciation_model=pronunciation_model,
    )
    batch_paths: list[Path] = []
    for lesson_path in lesson_paths:
        artifacts = generate_batch_from_lesson_file(
            input_path=lesson_path,
            output_path=lesson_path.with_suffix(".batch.json"),
            media_dir=project_root / "data/media",
            project_root=project_root,
            anki_url=anki_url,
            with_audio=with_audio,
        )
        batch_paths.append(artifacts.output_path)

    return LessonGenerationArtifacts(
        lesson_root=lesson_root,
        transcription_path=transcription_path,
        qa_report_path=qa_report_path,
        lesson_paths=lesson_paths,
        batch_paths=batch_paths,
    )


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


def resolve_push_deck_name(request: PushRequest) -> str:
    return request.deck_name or request.batch.metadata.target_deck or DEFAULT_DECK


def handle_push_request(
    request: PushRequest,
    *,
    project_root: Path | None = None,
    reviewed_batch_path: str | None = None,
) -> PushResult:
    deck_name = resolve_push_deck_name(request)
    if request.dry_run:
        return plan_push(
            request.batch,
            deck_name=deck_name,
            anki_url=request.anki_url,
        )

    if reviewed_batch_path is not None:
        reviewed_batch = request.batch
        if project_root is not None:
            reviewed_batch = normalize_batch_media_paths(reviewed_batch, project_root)
        Path(reviewed_batch_path).write_text(
            reviewed_batch.model_dump_json(indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    result = push_batch(
        request.batch,
        deck_name=deck_name,
        anki_url=request.anki_url,
        sync=request.sync,
    )
    invalidate_anki_snapshots(request.anki_url)
    if project_root is not None:
        invalidate_project_snapshots(project_root)
    if reviewed_batch_path is None:
        return result
    return PushResult.model_validate(result.model_dump() | {"reviewed_batch_path": reviewed_batch_path})


def batch_referenced_media_paths(batch: CardBatch, *, project_root: Path) -> set[Path]:
    return snapshot_batch_referenced_media_paths(batch, project_root=project_root)


def batch_media_hydrated(batch_path: Path, *, project_root: Path) -> bool:
    return snapshot_batch_media_hydrated(batch_path, project_root=project_root)


def batch_is_pushed(batch: CardBatch, *, anki_url: str) -> bool:
    anki_note_keys = AnkiRepository(
        anki_url,
        client_factory=AnkiConnectClient,
        note_keys_loader=existing_model_note_keys,
    ).note_keys()
    approved_notes = [note for note in batch.notes if note.approved]
    return len(approved_notes) > 0 and any(note.note_key in anki_note_keys for note in approved_notes)


def delete_batch(batch_path: Path, *, project_root: Path, anki_url: str = "http://127.0.0.1:8765") -> DeleteBatchResult:
    if not batch_path.name.endswith(".batch.json") or batch_path.name.endswith(".synced.batch.json"):
        raise ValueError("Batch path must be a canonical .batch.json file.")
    if not batch_path.exists():
        raise ValueError("Batch file not found.")

    batch = CardBatch.model_validate_json(batch_path.read_text(encoding="utf-8"))
    if batch_is_pushed(batch, anki_url=anki_url):
        raise ValueError("Cannot delete a batch that has already been pushed to Anki.")

    synced_batch_path = default_synced_output_path(batch_path)
    generation_plan_path = batch_path.with_suffix(".generation-plan.json")
    deleted_paths: list[str] = []
    for path in [batch_path, synced_batch_path, generation_plan_path]:
        if path.exists():
            path.unlink()
            deleted_paths.append(str(path.relative_to(project_root)))

    candidate_media_paths = batch_referenced_media_paths(batch, project_root=project_root)
    referenced_elsewhere: set[Path] = set()
    batch_repository = BatchRepository(project_root)
    for other_batch_path in batch_repository.batch_paths():
        if other_batch_path == batch_path or other_batch_path == synced_batch_path:
            continue
        try:
            other_batch = batch_repository.load_batch(other_batch_path)
        except Exception:  # noqa: BLE001
            continue
        referenced_elsewhere.update(batch_referenced_media_paths(other_batch, project_root=project_root))

    deleted_media_paths: list[str] = []
    for media_path in sorted(candidate_media_paths):
        if media_path in referenced_elsewhere or not media_path.exists() or not media_path.is_file():
            continue
        media_path.unlink()
        deleted_media_paths.append(str(media_path.relative_to(project_root)))

    invalidate_project_snapshots(project_root)
    return DeleteBatchResult(deleted_paths=deleted_paths, deleted_media_paths=deleted_media_paths)


def build_dashboard_response(
    *,
    project_root: Path,
    anki_url: str = "http://127.0.0.1:8765",
) -> DashboardResponse:
    return dashboard_response_snapshot(
        project_root=project_root,
        anki_url=anki_url,
        client_factory=AnkiConnectClient,
        note_keys_loader=existing_model_note_keys,
        openai_configured=bool(os.environ.get("OPENAI_API_KEY")),
    )
