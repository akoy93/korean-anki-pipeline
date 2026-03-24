from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from .anki import ANKI_MODEL_NAME, AnkiConnectClient
from .schema import (
    AnkiStatsSnapshot,
    CardBatch,
    ItemType,
    LessonItem,
    PriorNote,
    StudyLane,
    StudyState,
)

_SPACE_RE = re.compile(r"\s+")


def normalize_text(value: str) -> str:
    return _SPACE_RE.sub(" ", value.strip().casefold())


def note_key_for_item(item: LessonItem) -> str:
    return f"{item.item_type}:{normalize_text(item.korean)}:{normalize_text(item.english)}"


def _prior_note_from_item(item: LessonItem, source: str, existing_note_id: int | None = None) -> PriorNote:
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


def generated_history(project_root: Path, exclude_batch_path: Path | None = None) -> list[PriorNote]:
    prior_notes: list[PriorNote] = []
    resolved_exclude = exclude_batch_path.resolve() if exclude_batch_path is not None else None
    batch_paths = [
        *project_root.glob("lessons/**/generated/*.batch.json"),
        *project_root.glob("data/generated/*.batch.json"),
    ]
    for batch_path in sorted(batch_paths):
        if resolved_exclude is not None and batch_path.resolve() == resolved_exclude:
            continue
        try:
            batch = CardBatch.model_validate_json(batch_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue

        source = str(batch_path.relative_to(project_root))
        for note in batch.notes:
            prior_notes.append(_prior_note_from_item(note.item, source=source))

    return prior_notes


def _parse_item_type(tags: list[str]) -> ItemType:
    for tag in tags:
        if tag.startswith("type:"):
            candidate = tag.removeprefix("type:")
            if candidate in {"vocab", "phrase", "grammar", "dialogue", "number"}:
                return candidate  # type: ignore[return-value]
    return "vocab"


def _parse_lane(tags: list[str]) -> StudyLane:
    for tag in tags:
        if tag.startswith("lane:"):
            candidate = tag.removeprefix("lane:")
            if candidate in {"lesson", "new-vocab", "reading-speed", "grammar", "listening"}:
                return candidate  # type: ignore[return-value]
    return "lesson"


def _parse_skill_tags(tags: list[str]) -> list[str]:
    return [tag.removeprefix("skill:") for tag in tags if tag.startswith("skill:")]


def imported_anki_history(anki_url: str = "http://127.0.0.1:8765") -> tuple[list[PriorNote], AnkiStatsSnapshot]:
    client = AnkiConnectClient(url=anki_url)
    note_ids = client.invoke("findNotes", query=f'note:"{ANKI_MODEL_NAME}"')
    if not isinstance(note_ids, list) or not note_ids:
        return [], AnkiStatsSnapshot()

    notes_info = client.invoke("notesInfo", notes=note_ids)
    imported_notes: list[PriorNote] = []
    if isinstance(notes_info, list):
        for note_info in notes_info:
            if not isinstance(note_info, dict):
                continue
            fields = note_info.get("fields")
            tags = note_info.get("tags")
            note_id = note_info.get("noteId")
            if not isinstance(fields, dict) or not isinstance(tags, list) or not isinstance(note_id, int):
                continue
            korean_field = fields.get("Korean")
            english_field = fields.get("English")
            if not isinstance(korean_field, dict) or not isinstance(english_field, dict):
                continue
            korean = korean_field.get("value")
            english = english_field.get("value")
            if not isinstance(korean, str) or not isinstance(english, str):
                continue

            item_type = _parse_item_type([tag for tag in tags if isinstance(tag, str)])
            lane = _parse_lane([tag for tag in tags if isinstance(tag, str)])
            skill_tags = _parse_skill_tags([tag for tag in tags if isinstance(tag, str)])
            imported_notes.append(
                PriorNote(
                    note_key=f"{item_type}:{normalize_text(korean)}:{normalize_text(english)}",
                    korean=korean,
                    english=english,
                    item_type=item_type,
                    lane=lane,
                    skill_tags=skill_tags,
                    source="anki",
                    existing_note_id=note_id,
                )
            )

    card_ids = client.invoke("findCards", query=f'note:"{ANKI_MODEL_NAME}"')
    if not isinstance(card_ids, list) or not card_ids:
        return imported_notes, AnkiStatsSnapshot(note_count=len(imported_notes))

    cards_info = client.invoke("cardsInfo", cards=card_ids)
    template_counts: Counter[str] = Counter()
    tag_counts: Counter[str] = Counter()
    if isinstance(cards_info, list):
        for card_info in cards_info:
            if not isinstance(card_info, dict):
                continue
            template = card_info.get("template")
            tags = card_info.get("tags")
            if isinstance(template, str):
                template_counts[template] += 1
            if isinstance(tags, list):
                tag_counts.update(tag for tag in tags if isinstance(tag, str))

    return imported_notes, AnkiStatsSnapshot(
        note_count=len(imported_notes),
        card_count=len(card_ids),
        by_template=dict(template_counts),
        by_tag=dict(tag_counts),
    )


def build_study_state(
    project_root: Path,
    anki_url: str = "http://127.0.0.1:8765",
    exclude_batch_path: Path | None = None,
) -> StudyState:
    generated_notes = generated_history(project_root, exclude_batch_path=exclude_batch_path)
    try:
        imported_notes, anki_stats = imported_anki_history(anki_url=anki_url)
    except Exception:  # noqa: BLE001
        imported_notes = []
        anki_stats = AnkiStatsSnapshot()

    return StudyState(
        generated_notes=generated_notes,
        imported_notes=imported_notes,
        anki_stats=anki_stats,
    )
