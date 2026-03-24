from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from .schema import LessonDocument, LessonItem, LessonMetadata, PriorNote, StudyState
from .study_state import normalize_text


def chunk_hangul(text: str) -> str:
    return " ".join("·".join(segment) for segment in text.split())


def known_word_bank(study_state: StudyState) -> list[PriorNote]:
    seen: set[str] = set()
    bank: list[PriorNote] = []
    for prior_note in [*study_state.imported_notes, *study_state.generated_notes]:
        if prior_note.lane == "reading-speed":
            continue
        normalized_korean = normalize_text(prior_note.korean)
        if normalized_korean in seen:
            continue
        seen.add(normalized_korean)
        bank.append(prior_note)

    return bank


def _make_reading_item(
    *,
    lesson_id: str,
    index: int,
    prior_note: PriorNote,
    add_chunked_card: bool,
) -> LessonItem:
    skill_tags = ["reading-speed", "read-aloud"]
    if add_chunked_card:
        skill_tags.append("chunked")

    return LessonItem(
        id=f"{lesson_id}-read-{index:03d}",
        lesson_id=lesson_id,
        item_type=prior_note.item_type,
        korean=prior_note.korean,
        english=prior_note.english,
        pronunciation=None,
        examples=[],
        notes="Read aloud before revealing meaning. Focus on fast Hangul decoding, not learning a new word.",
        tags=["reading-speed", "read-aloud"],
        lane="reading-speed",
        skill_tags=skill_tags,
        source_ref=f"Known-word bank from {prior_note.source}",
        audio=None,
        image=None,
    )


def _make_passage_item(
    *,
    lesson_id: str,
    passage_notes: Iterable[PriorNote],
) -> LessonItem:
    selected = list(passage_notes)
    passage_korean = " ".join(note.korean for note in selected)
    passage_english = " / ".join(note.english for note in selected)

    return LessonItem(
        id=f"{lesson_id}-passage-001",
        lesson_id=lesson_id,
        item_type="phrase",
        korean=passage_korean,
        english=f"Decodable passage: {passage_english}",
        pronunciation=None,
        examples=[],
        notes="Tiny decodable passage built mostly from known words. Read it smoothly before checking meaning.",
        tags=["reading-speed", "passage"],
        lane="reading-speed",
        skill_tags=["reading-speed", "passage"],
        source_ref="Generated from known-word bank for weekly reading fluency practice",
        audio=None,
        image=None,
    )


def build_reading_speed_document(
    study_state: StudyState,
    *,
    lesson_id: str,
    title: str,
    topic: str = "Reading Speed",
    lesson_date: date,
    source_description: str,
    target_deck: str | None = "Korean::Reading Speed",
    max_read_aloud: int = 20,
    max_chunked: int = 10,
    passage_word_count: int = 5,
) -> LessonDocument:
    bank = known_word_bank(study_state)
    if not bank:
        raise ValueError("No known words available in study state for a reading-speed batch.")

    read_aloud_notes = bank[: min(max_read_aloud, len(bank))]
    chunkable_note_keys = [
        note.note_key
        for note in read_aloud_notes
        if len(note.korean.replace(" ", "")) >= 2
    ]
    chunked_note_keys = set(chunkable_note_keys[: min(max_chunked, len(chunkable_note_keys))])

    items = [
        _make_reading_item(
            lesson_id=lesson_id,
            index=index,
            prior_note=prior_note,
            add_chunked_card=prior_note.note_key in chunked_note_keys,
        )
        for index, prior_note in enumerate(read_aloud_notes, start=1)
    ]

    if len(bank) >= 2:
        items.append(_make_passage_item(lesson_id=lesson_id, passage_notes=bank[: min(passage_word_count, len(bank))]))

    metadata = LessonMetadata(
        lesson_id=lesson_id,
        title=title,
        topic=topic,
        lesson_date=lesson_date,
        source_description=source_description,
        target_deck=target_deck,
        tags=["reading-speed"],
    )
    return LessonDocument(metadata=metadata, items=items)
