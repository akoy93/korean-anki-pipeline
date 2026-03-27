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
from .schema import JobPhase, NewVocabJobRequest, RawSourceAsset, SyncMediaJobRequest
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
    phases = [
        JobPhase(key="study-state", label="Loading study state"),
        JobPhase(key="topic", label="Choosing batch focus"),
        JobPhase(key="proposals", label="Generating vocab proposals"),
        JobPhase(key="filtering", label="Filtering and ranking proposals"),
        JobPhase(key="pronunciations", label="Generating pronunciations"),
        JobPhase(key="images", label="Generating images"),
        *([JobPhase(key="audio", label="Generating audio")] if request.with_audio else []),
        JobPhase(key="cards", label="Building cards"),
    ]
    selected_count = 0

    def emit_progress() -> None:
        if on_progress is None:
            return
        active_phase = next((phase for phase in phases if phase.status == "running"), None)
        summary_phase = active_phase
        if summary_phase is None:
            summary_phase = next(
                (phase for phase in reversed(phases) if phase.status in {"succeeded", "failed"}),
                None,
            )
        on_progress(
            progress_current=summary_phase.current if summary_phase is not None else 0,
            progress_total=summary_phase.total if summary_phase is not None else 0,
            progress_label=summary_phase.label if summary_phase is not None else None,
            phases=[phase.model_copy(deep=True) for phase in phases],
        )

    def phase(key: str) -> JobPhase:
        for current_phase in phases:
            if current_phase.key == key:
                return current_phase
        raise KeyError(key)

    def start_phase(key: str, *, total: int = 0) -> None:
        current_phase = phase(key)
        current_phase.status = "running"
        current_phase.current = 0
        current_phase.total = total
        emit_progress()

    def complete_phase(key: str, *, current: int | None = None, total: int | None = None) -> None:
        current_phase = phase(key)
        if current is not None:
            current_phase.current = current
        if total is not None:
            current_phase.total = total
        if current_phase.total > 0 and current_phase.current == 0:
            current_phase.current = current_phase.total
        current_phase.status = "succeeded"
        emit_progress()

    def advance_phase(key: str, *, step: int = 1) -> None:
        current_phase = phase(key)
        if current_phase.status != "running":
            current_phase.status = "running"
        current_phase.current += step
        if current_phase.total > 0:
            current_phase.current = min(current_phase.current, current_phase.total)
        emit_progress()

    def fail_running_phase() -> None:
        current_phase = next((entry for entry in phases if entry.status == "running"), None)
        if current_phase is None:
            return
        current_phase.status = "failed"
        emit_progress()

    def handle_selection_complete(item_count: int) -> None:
        nonlocal selected_count
        selected_count = item_count
        complete_phase("filtering", current=item_count, total=request.count)
        start_phase("pronunciations", total=item_count)

    def handle_pronunciations_generated(item_count: int) -> None:
        complete_phase("pronunciations", current=item_count, total=item_count)
        start_phase("images", total=item_count)

    def handle_image_complete() -> None:
        advance_phase("images")
        current_phase = phase("images")
        if current_phase.total > 0 and current_phase.current >= current_phase.total:
            complete_phase("images")
            if request.with_audio:
                start_phase("audio", total=selected_count)
            else:
                start_phase("cards", total=selected_count)

    def handle_audio_complete() -> None:
        advance_phase("audio")
        current_phase = phase("audio")
        if current_phase.total > 0 and current_phase.current >= current_phase.total:
            complete_phase("audio")
            start_phase("cards", total=selected_count)

    def handle_note_generated() -> None:
        advance_phase("cards")
        current_phase = phase("cards")
        if current_phase.total > 0 and current_phase.current >= current_phase.total:
            complete_phase("cards")

    start_phase("study-state")

    try:
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
            on_study_state_loaded=lambda: (
                complete_phase("study-state"),
                start_phase("topic"),
            ),
            on_theme_selected=lambda _theme: (
                complete_phase("topic"),
                start_phase("proposals"),
            ),
            on_proposals_generated=lambda proposal_count: (
                complete_phase("proposals", current=proposal_count, total=proposal_count),
                start_phase("filtering"),
            ),
            on_selection_complete=handle_selection_complete,
            on_pronunciations_generated=handle_pronunciations_generated,
            on_image_complete=handle_image_complete,
            on_audio_complete=handle_audio_complete,
            on_note_generated=lambda _note: handle_note_generated(),
        )
    except Exception:
        fail_running_phase()
        raise
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
