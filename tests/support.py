from __future__ import annotations

from datetime import date

from korean_anki.schema import (
    CardBatch,
    ExampleSentence,
    GeneratedNote,
    LessonDocument,
    LessonItem,
    LessonMetadata,
    LessonTranscription,
    MediaAsset,
    RawSourceAsset,
    TranscriptionEntry,
    TranscriptionSection,
)


def make_metadata(
    *,
    lesson_id: str = "lesson-1",
    title: str = "Lesson 1",
    topic: str = "Basics",
    target_deck: str | None = "Korean::Lessons::Basics",
    tags: list[str] | None = None,
) -> LessonMetadata:
    return LessonMetadata(
        lesson_id=lesson_id,
        title=title,
        topic=topic,
        lesson_date=date(2026, 3, 23),
        source_description="Test source",
        target_deck=target_deck,
        tags=tags or [],
    )


def make_item(
    *,
    item_id: str = "item-1",
    lesson_id: str = "lesson-1",
    item_type: str = "vocab",
    korean: str = "안녕하세요",
    english: str = "hello",
    pronunciation: str | None = "annyeonghaseyo",
    examples: list[ExampleSentence] | None = None,
    notes: str | None = "Greeting",
    tags: list[str] | None = None,
    source_ref: str | None = "2026-03-23 Lesson 1 lesson • source.png • section • 1",
    image_prompt: str | None = None,
    audio: MediaAsset | None = None,
    image: MediaAsset | None = None,
) -> LessonItem:
    return LessonItem(
        id=item_id,
        lesson_id=lesson_id,
        item_type=item_type,  # type: ignore[arg-type]
        korean=korean,
        english=english,
        pronunciation=pronunciation,
        examples=examples or [],
        notes=notes,
        tags=tags or [],
        source_ref=source_ref,
        image_prompt=image_prompt,
        audio=audio,
        image=image,
    )


def make_document(
    items: list[LessonItem],
    *,
    metadata: LessonMetadata | None = None,
) -> LessonDocument:
    return LessonDocument(metadata=metadata or make_metadata(), items=items)


def make_batch(
    notes: list[GeneratedNote],
    *,
    metadata: LessonMetadata | None = None,
) -> CardBatch:
    return CardBatch(metadata=metadata or make_metadata(), notes=notes)


def make_transcription() -> LessonTranscription:
    return LessonTranscription(
        lesson_id="italki-2026-03-23-test",
        title="Numbers",
        lesson_date=date(2026, 3, 23),
        source_summary="Test slide",
        theme="Number systems",
        goals=["Learn one number system"],
        raw_sources=[
            RawSourceAsset(
                kind="image",
                path="lessons/2026-03-23-numbers/raw-sources/2026-03-21_1.png",
                description="Slide",
            )
        ],
        expected_section_count=1,
        sections=[
            TranscriptionSection(
                id="section-left-sino",
                title="Left Side",
                item_type="number",
                side="left",
                number_system="sino-korean",
                usage_notes=["Used for sequence and prices."],
                expected_entry_count=1,
                target_deck=None,
                tags=["numbers", "sino-korean", "left-column"],
                entries=[
                    TranscriptionEntry(
                        label="1",
                        korean="일",
                        english="one",
                        pronunciation=None,
                        notes=None,
                    )
                ],
            )
        ],
        notes=[],
    )
