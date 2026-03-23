from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

SchemaVersion = Literal["1"]
ItemType = Literal["vocab", "phrase", "grammar", "dialogue", "number"]
CardKind = Literal["recognition", "production", "listening", "number-context"]
RawSourceKind = Literal["image", "text"]
QaSeverity = Literal["error", "warning"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


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
    source_ref: str | None = None
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


class CardBatch(StrictModel):
    schema_version: SchemaVersion = "1"
    metadata: LessonMetadata
    notes: Annotated[list[GeneratedNote], Field(min_length=1)]


class ExtractionRequest(StrictModel):
    lesson_id: str
    title: str
    topic: str
    lesson_date: date
    source_description: str
    item_type_default: ItemType = "vocab"
    text: str | None = None
    image_path: str | None = None
    model: str = "gpt-5.4"
    qa_model: str = "gpt-5.4-pro"
    run_qa: bool = False


class RawSourceAsset(StrictModel):
    kind: RawSourceKind
    path: str
    description: str


class TranscriptionEntry(StrictModel):
    label: str
    korean: str
    english: str
    pronunciation: str | None = None
    notes: str | None = None


class TranscriptionSection(StrictModel):
    id: str
    title: str
    item_type: ItemType = "vocab"
    side: str | None = None
    number_system: str | None = None
    usage_notes: list[str] = Field(default_factory=list)
    expected_entry_count: int | None = None
    target_deck: str | None = None
    tags: list[str] = Field(default_factory=list)
    entries: Annotated[list[TranscriptionEntry], Field(min_length=1)]


class LessonTranscription(StrictModel):
    schema_version: SchemaVersion = "1"
    lesson_id: str
    title: str
    lesson_date: date
    source_summary: str
    theme: str
    goals: list[str] = Field(default_factory=list)
    raw_sources: Annotated[list[RawSourceAsset], Field(min_length=1)]
    expected_section_count: int | None = None
    sections: Annotated[list[TranscriptionSection], Field(min_length=1)]
    notes: list[str] = Field(default_factory=list)


class QaIssue(StrictModel):
    severity: QaSeverity
    code: str
    message: str
    section_id: str | None = None


class QaReport(StrictModel):
    schema_version: SchemaVersion = "1"
    lesson_id: str
    passed: bool
    issues: list[QaIssue] = Field(default_factory=list)
