from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from . import path_policy
from .multipart_form import (
    MultipartField,
    MultipartForm,
    field_value,
    parse_bool_field,
    save_upload,
)
from .lesson_generation_service import generate_lesson_batches_from_sources
from .new_vocab_generation_service import generate_new_vocab_batch
from .path_policy import unique_lesson_root, unique_new_vocab_output_path
from .schema import NewVocabJobRequest, RawSourceAsset, SyncMediaJobRequest
from .settings import DEFAULT_LESSON_AUDIO, DEFAULT_MEDIA_DIR, DEFAULT_NEW_VOCAB_TITLE
from .sync_media_service import sync_media_file


def lesson_generate_job(form: MultipartForm) -> list[str]:
    lesson_date = field_value(form, "lesson_date")
    title = field_value(form, "title")
    topic = field_value(form, "topic")
    source_summary = field_value(form, "source_summary")
    if lesson_date is None or title is None or topic is None or source_summary is None:
        raise ValueError("lesson_date, title, topic, and source_summary are required.")

    project_root = path_policy.project_root()
    lesson_root = unique_lesson_root(project_root, lesson_date, topic)
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

    artifacts = generate_lesson_batches_from_sources(
        project_root=project_root,
        lesson_root=lesson_root,
        title=title,
        lesson_date=lesson_date,
        topic=topic,
        source_summary=source_summary,
        raw_sources=raw_sources,
        with_audio=parse_bool_field(field_value(form, "with_audio"), default=DEFAULT_LESSON_AUDIO),
    )
    return [str(path.relative_to(project_root)) for path in artifacts.batch_paths]


def new_vocab_job(
    raw_body: str,
    *,
    on_progress: Callable[..., None] | None = None,
) -> list[str]:
    request = NewVocabJobRequest.model_validate_json(raw_body)
    project_root = path_policy.project_root()
    output_path = unique_new_vocab_output_path(project_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lesson_id = output_path.name.removesuffix(".batch.json")
    progress_total = request.count * (5 if request.with_audio else 4)
    progress_current = 0

    def advance_progress(label: str, step: int = 1) -> None:
        nonlocal progress_current
        progress_current += step
        if on_progress is not None:
            on_progress(
                progress_current=progress_current,
                progress_total=progress_total,
                progress_label=label,
            )

    if on_progress is not None:
        on_progress(
            progress_current=0,
            progress_total=0,
            progress_label="Planning vocab candidates",
        )

    generate_new_vocab_batch(
        project_root=project_root,
        output_path=output_path,
        lesson_id=lesson_id,
        title=DEFAULT_NEW_VOCAB_TITLE,
        lesson_date=datetime.now().date(),
        count=request.count,
        gap_ratio=request.gap_ratio,
        target_deck=request.target_deck,
        lesson_context_path=Path(request.lesson_context) if request.lesson_context is not None else None,
        media_dir=project_root / DEFAULT_MEDIA_DIR,
        anki_url=request.anki_url,
        with_audio=request.with_audio,
        image_quality=request.image_quality,
        on_image_complete=lambda: advance_progress("Generating images"),
        on_audio_complete=lambda: advance_progress("Generating audio"),
        on_note_generated=lambda note: advance_progress("Generating cards", step=len(note.cards)),
    )
    return [str(output_path.relative_to(project_root))]


def sync_media_job(raw_body: str) -> list[str]:
    request = SyncMediaJobRequest.model_validate_json(raw_body)
    project_root = path_policy.project_root()
    result = sync_media_file(
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
