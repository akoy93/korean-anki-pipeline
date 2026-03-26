from __future__ import annotations

import re

from .schema import LessonItem, PriorNote

_SPACE_RE = re.compile(r"\s+")


def normalize_text(value: str) -> str:
    return _SPACE_RE.sub(" ", value.strip().casefold())


def note_key_for_item(item: LessonItem) -> str:
    return f"{item.item_type}:{normalize_text(item.korean)}:{normalize_text(item.english)}"


def prior_note_from_item(
    item: LessonItem,
    *,
    source: str,
    existing_note_id: int | None = None,
) -> PriorNote:
    return PriorNote(
        note_key=note_key_for_item(item),
        korean=item.korean,
        english=item.english,
        item_type=item.item_type,
        lane=item.lane,
        skill_tags=item.skill_tags,
        source=source,
        existing_note_id=existing_note_id,
    )
