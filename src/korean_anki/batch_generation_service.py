from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
from pathlib import Path
from typing import Callable

from .cards import generate_batch
from .lesson_io import read_lesson
from .media import enrich_audio, enrich_images
from .path_policy import normalize_batch_media_paths
from .reading_speed import build_reading_speed_document
from .schema import CardBatch, GeneratedNote, LessonDocument, StudyState
from .snapshot_cache import invalidate_project_snapshots
from .snapshots import study_state_snapshot
from .settings import DEFAULT_ANKI_URL, DEFAULT_GENERATE_IMAGE_QUALITY


@dataclass(frozen=True)
class BatchArtifacts:
    batch: CardBatch
    study_state: StudyState
    output_path: Path
    state_output_path: Path
    generation_plan_path: Path


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
    anki_url: str = DEFAULT_ANKI_URL,
    include_image_prompt: bool = False,
    normalize_media_paths_for_output: bool = True,
    on_note_generated: Callable[[GeneratedNote], None] | None = None,
) -> BatchArtifacts:
    state = study_state_snapshot(
        project_root=project_root,
        anki_url=anki_url,
        exclude_batch_path=output_path,
    )
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
    anki_url: str = DEFAULT_ANKI_URL,
    with_audio: bool = False,
    with_images: bool = False,
    image_quality: str = DEFAULT_GENERATE_IMAGE_QUALITY,
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
    anki_url: str = DEFAULT_ANKI_URL,
    with_audio: bool = False,
) -> BatchArtifacts:
    state = study_state_snapshot(
        project_root=project_root,
        anki_url=anki_url,
        exclude_batch_path=output_path,
    )
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
