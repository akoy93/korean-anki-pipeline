from __future__ import annotations

from datetime import date
from typing import Annotated

from pydantic import Field

from ..settings import DEFAULT_EXTRACTION_ITEM_TYPE, DEFAULT_LLM_MODEL, DEFAULT_QA_MODEL
from .common import ItemType, QaSeverity, RawSourceKind, SchemaVersion, StrictModel
from .domain import ExampleSentence


class LessonExtractionMetadata(StrictModel):
    lesson_id: str
    title: str
    topic: str
    lesson_date: date
    source_description: str
    target_deck: str | None
    tags: list[str]


class LessonExtractionItem(StrictModel):
    id: str
    lesson_id: str
    item_type: ItemType
    korean: str
    english: str
    pronunciation: str | None
    examples: list[ExampleSentence]
    notes: str | None
    tags: list[str]
    source_ref: str | None
    audio: None
    image: None


class LessonExtractionDocument(StrictModel):
    schema_version: SchemaVersion
    metadata: LessonExtractionMetadata
    items: Annotated[list[LessonExtractionItem], Field(min_length=1)]


class ExtractionRequest(StrictModel):
    lesson_id: str
    title: str
    topic: str
    lesson_date: date
    source_description: str
    item_type_default: ItemType = DEFAULT_EXTRACTION_ITEM_TYPE
    text: str | None = None
    image_path: str | None = None
    model: str = DEFAULT_LLM_MODEL
    qa_model: str = DEFAULT_QA_MODEL
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


class TranscriptionOutputEntry(StrictModel):
    label: str
    korean: str
    english: str
    pronunciation: str | None
    notes: str | None


class TranscriptionOutputSection(StrictModel):
    id: str
    title: str
    item_type: ItemType
    side: str | None
    number_system: str | None
    usage_notes: list[str]
    expected_entry_count: int | None
    target_deck: str | None
    tags: list[str]
    entries: Annotated[list[TranscriptionOutputEntry], Field(min_length=1)]


class LessonTranscriptionOutput(StrictModel):
    schema_version: SchemaVersion
    lesson_id: str
    title: str
    lesson_date: date
    source_summary: str
    theme: str
    goals: list[str]
    raw_sources: Annotated[list[RawSourceAsset], Field(min_length=1)]
    expected_section_count: int | None
    sections: Annotated[list[TranscriptionOutputSection], Field(min_length=1)]
    notes: list[str]


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


__all__ = [
    "ExtractionRequest",
    "LessonExtractionDocument",
    "LessonExtractionItem",
    "LessonExtractionMetadata",
    "LessonTranscription",
    "LessonTranscriptionOutput",
    "QaIssue",
    "QaReport",
    "RawSourceAsset",
    "TranscriptionEntry",
    "TranscriptionOutputEntry",
    "TranscriptionOutputSection",
    "TranscriptionSection",
]
