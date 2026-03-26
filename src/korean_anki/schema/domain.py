from __future__ import annotations

from datetime import date
from typing import Annotated

from pydantic import Field, HttpUrl

from .common import (
    CardKind,
    DuplicateStatus,
    ItemType,
    SchemaVersion,
    StrictModel,
    StudyLane,
    VocabAdjacencyKind,
)


class ExampleSentence(StrictModel):
    korean: str
    english: str


class MediaAsset(StrictModel):
    path: str
    prompt: str | None = None
    source_url: HttpUrl | None = None


class LessonMetadata(StrictModel):
    lesson_id: str
    title: str
    topic: str
    lesson_date: date
    source_description: str
    target_deck: str | None = None
    tags: list[str] = Field(default_factory=list)


class LessonItem(StrictModel):
    id: str
    lesson_id: str
    item_type: ItemType
    korean: str
    english: str
    pronunciation: str | None = None
    examples: list[ExampleSentence] = Field(default_factory=list)
    notes: str | None = None
    tags: list[str] = Field(default_factory=list)
    lane: StudyLane = "lesson"
    skill_tags: list[str] = Field(default_factory=list)
    source_ref: str | None = None
    image_prompt: str | None = None
    audio: MediaAsset | None = None
    image: MediaAsset | None = None


class LessonDocument(StrictModel):
    schema_version: SchemaVersion = "1"
    metadata: LessonMetadata
    items: Annotated[list[LessonItem], Field(min_length=1)]


class CardPreview(StrictModel):
    id: str
    item_id: str
    kind: CardKind
    front_html: str
    back_html: str
    audio_path: str | None = None
    image_path: str | None = None
    approved: bool = True


class GeneratedNote(StrictModel):
    item: LessonItem
    cards: Annotated[list[CardPreview], Field(min_length=1)]
    approved: bool = True
    note_key: str = ""
    lane: StudyLane = "lesson"
    skill_tags: list[str] = Field(default_factory=list)
    duplicate_status: DuplicateStatus = "new"
    duplicate_note_key: str | None = None
    duplicate_note_id: int | None = None
    duplicate_source: str | None = None
    inclusion_reason: str = "New card"


class CardBatch(StrictModel):
    schema_version: SchemaVersion = "1"
    metadata: LessonMetadata
    notes: Annotated[list[GeneratedNote], Field(min_length=1)]


class PronunciationSuggestion(StrictModel):
    korean: str
    pronunciation: str


class PronunciationBatch(StrictModel):
    items: Annotated[list[PronunciationSuggestion], Field(min_length=1)]


class ImageGenerationDecision(StrictModel):
    item_id: str
    generate_image: bool
    reason: str


class ImageGenerationPlan(StrictModel):
    decisions: Annotated[list[ImageGenerationDecision], Field(min_length=1)]


class NewVocabProposal(StrictModel):
    candidate_id: str
    korean: str
    english: str
    topic_tag: str
    example_ko: str
    example_en: str
    proposal_reason: str
    image_prompt: str
    adjacency_kind: VocabAdjacencyKind


class NewVocabProposalBatch(StrictModel):
    proposals: Annotated[list[NewVocabProposal], Field(min_length=1)]


class PriorNote(StrictModel):
    note_key: str
    korean: str
    english: str
    item_type: ItemType
    lane: StudyLane = "lesson"
    skill_tags: list[str] = Field(default_factory=list)
    source: str
    existing_note_id: int | None = None


class AnkiStatsSnapshot(StrictModel):
    note_count: int = 0
    card_count: int = 0
    by_template: dict[str, int] = Field(default_factory=dict)
    by_tag: dict[str, int] = Field(default_factory=dict)


class StudyState(StrictModel):
    generated_notes: list[PriorNote] = Field(default_factory=list)
    imported_notes: list[PriorNote] = Field(default_factory=list)
    anki_stats: AnkiStatsSnapshot = Field(default_factory=AnkiStatsSnapshot)


__all__ = [
    "AnkiStatsSnapshot",
    "CardBatch",
    "CardPreview",
    "ExampleSentence",
    "GeneratedNote",
    "ImageGenerationDecision",
    "ImageGenerationPlan",
    "LessonDocument",
    "LessonItem",
    "LessonMetadata",
    "MediaAsset",
    "NewVocabProposal",
    "NewVocabProposalBatch",
    "PriorNote",
    "PronunciationBatch",
    "PronunciationSuggestion",
    "StudyState",
]
