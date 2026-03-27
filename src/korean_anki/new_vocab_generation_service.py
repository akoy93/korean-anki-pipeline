from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Callable

from .batch_generation_service import BatchArtifacts, generate_batch_from_document
from .media import enrich_audio, enrich_new_vocab_images
from .new_vocab_documents import build_new_vocab_document_from_state
from .schema import GeneratedNote
from .settings import DEFAULT_ANKI_URL, DEFAULT_LLM_MODEL, DEFAULT_NEW_VOCAB_IMAGE_QUALITY
from .study_state_snapshots import study_state_snapshot


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
    anki_url: str = DEFAULT_ANKI_URL,
    with_audio: bool = False,
    image_quality: str = DEFAULT_NEW_VOCAB_IMAGE_QUALITY,
    model: str = DEFAULT_LLM_MODEL,
    on_study_state_loaded: Callable[[], None] | None = None,
    on_theme_selected: Callable[[str], None] | None = None,
    on_proposals_generated: Callable[[int], None] | None = None,
    on_selection_complete: Callable[[int], None] | None = None,
    on_pronunciations_generated: Callable[[int], None] | None = None,
    on_image_complete: Callable[[], None] | None = None,
    on_audio_complete: Callable[[], None] | None = None,
    on_note_generated: Callable[[GeneratedNote], None] | None = None,
) -> BatchArtifacts:
    state = study_state_snapshot(
        project_root=project_root,
        anki_url=anki_url,
        exclude_batch_path=output_path,
    )
    if on_study_state_loaded is not None:
        on_study_state_loaded()
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
        on_theme_selected=on_theme_selected,
        on_proposals_generated=on_proposals_generated,
        on_selection_complete=on_selection_complete,
        on_pronunciations_generated=on_pronunciations_generated,
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
