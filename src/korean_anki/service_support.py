from __future__ import annotations

from datetime import datetime
import re
from pathlib import Path

from . import path_policy
from .schema import CardBatch

_SLUG_RE = re.compile(r"[^a-zA-Z0-9가-힣]+")


def _slugify(value: str) -> str:
    slug = _SLUG_RE.sub("-", value).strip("-").lower()
    return slug or "lesson"

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
def normalize_batch_media_paths(batch: CardBatch, project_root: Path) -> CardBatch:
    notes = []
    for note in batch.notes:
        audio = note.item.audio
        image = note.item.image
        item = note.item.model_copy(
            update={
                "audio": None
                if audio is None
                else audio.model_copy(
                    update={"path": path_policy.project_relative_path(audio.path, project_root)}
                ),
                "image": None
                if image is None
                else image.model_copy(
                    update={"path": path_policy.project_relative_path(image.path, project_root)}
                ),
            }
        )
        cards = [
            card.model_copy(
                update={
                    "audio_path": path_policy.project_relative_path(card.audio_path, project_root),
                    "image_path": path_policy.project_relative_path(card.image_path, project_root),
                }
            )
            for card in note.cards
        ]
        notes.append(note.model_copy(update={"item": item, "cards": cards}))

    return batch.model_copy(update={"notes": notes})
