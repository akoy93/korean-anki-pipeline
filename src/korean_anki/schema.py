from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from .settings import (
    DEFAULT_ANKI_URL,
    DEFAULT_EXTRACTION_ITEM_TYPE,
    DEFAULT_LESSON_AUDIO,
    DEFAULT_LLM_MODEL,
    DEFAULT_MEDIA_DIR,
    DEFAULT_NEW_VOCAB_COUNT,
    DEFAULT_NEW_VOCAB_GAP_RATIO,
    DEFAULT_NEW_VOCAB_IMAGE_QUALITY,
    DEFAULT_NEW_VOCAB_TARGET_DECK,
    DEFAULT_NEW_VOCAB_WITH_AUDIO,
    DEFAULT_QA_MODEL,
    DEFAULT_SYNC_MEDIA_SYNC_FIRST,
)

SchemaVersion = Literal["1"]
ItemType = Literal["vocab", "phrase", "grammar", "dialogue", "number"]
CardKind = Literal[
    "recognition",
    "production",
    "listening",
    "number-context",
    "read-aloud",
    "chunked-reading",
    "decodable-passage",
]
StudyLane = Literal["lesson", "new-vocab", "reading-speed", "grammar", "listening"]
DuplicateStatus = Literal["new", "exact-duplicate", "near-duplicate"]
VocabAdjacencyKind = Literal["coverage-gap", "lesson-adjacent"]
RawSourceKind = Literal["image", "text"]
QaSeverity = Literal["error", "warning"]
JobStatus = Literal["queued", "running", "succeeded", "failed"]
JobKind = Literal["lesson-generate", "new-vocab", "sync-media"]
BatchPushStatus = Literal["not-pushed", "pushed"]


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


class DuplicateNote(StrictModel):
    item_id: str
    korean: str
    english: str
    existing_note_id: int


class PushRequest(StrictModel):
    batch: CardBatch
    dry_run: bool = True
    deck_name: str | None = None
    source_batch_path: str | None = None
    anki_url: str = DEFAULT_ANKI_URL
    sync: bool = True


class PushResult(StrictModel):
    deck_name: str
    approved_notes: int
    approved_cards: int
    duplicate_notes: list[DuplicateNote] = Field(default_factory=list)
    dry_run: bool
    can_push: bool
    notes_added: int = 0
    cards_created: int = 0
    pushed_note_ids: list[int] = Field(default_factory=list)
    sync_requested: bool = False
    sync_completed: bool = False
    reviewed_batch_path: str | None = None


class PreviewNoteRefreshRequest(StrictModel):
    note: GeneratedNote
    item: LessonItem


class DeleteBatchRequest(StrictModel):
    batch_path: str
    anki_url: str = DEFAULT_ANKI_URL


class DeleteBatchResult(StrictModel):
    deleted_paths: list[str] = Field(default_factory=list)
    deleted_media_paths: list[str] = Field(default_factory=list)


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


class ServiceStatus(StrictModel):
    backend_ok: bool = True
    anki_connect_ok: bool = False
    anki_connect_version: int | None = None
    openai_configured: bool = False


class DashboardBatch(StrictModel):
    canonical_batch_path: str
    preview_batch_path: str
    title: str
    topic: str
    lesson_date: date
    target_deck: str | None = None
    notes: int
    cards: int
    approved_notes: int
    approved_cards: int
    audio_notes: int
    image_notes: int
    exact_duplicates: int
    near_duplicates: int
    push_status: BatchPushStatus = "not-pushed"
    media_hydrated: bool = False
    synced_batch_path: str | None = None
    lanes: list[StudyLane] = Field(default_factory=list)


class DashboardLessonContext(StrictModel):
    path: str
    label: str


class DashboardStats(StrictModel):
    local_batch_count: int = 0
    local_note_count: int = 0
    local_card_count: int = 0
    pending_push_count: int = 0
    audio_note_count: int = 0
    image_note_count: int = 0
    lane_counts: dict[str, int] = Field(default_factory=dict)
    anki_note_count: int = 0
    anki_card_count: int = 0
    anki_deck_counts: dict[str, int] = Field(default_factory=dict)


class LessonGenerateDefaults(StrictModel):
    with_audio: bool = DEFAULT_LESSON_AUDIO


class NewVocabDefaults(StrictModel):
    count: int = DEFAULT_NEW_VOCAB_COUNT
    gap_ratio: float = DEFAULT_NEW_VOCAB_GAP_RATIO
    with_audio: bool = DEFAULT_NEW_VOCAB_WITH_AUDIO
    image_quality: Literal["auto", "low", "medium", "high"] = DEFAULT_NEW_VOCAB_IMAGE_QUALITY
    target_deck: str = DEFAULT_NEW_VOCAB_TARGET_DECK


class PreviewDefaults(StrictModel):
    lesson_generate: LessonGenerateDefaults = Field(default_factory=LessonGenerateDefaults)
    new_vocab: NewVocabDefaults = Field(default_factory=NewVocabDefaults)


class DashboardResponse(StrictModel):
    status: ServiceStatus
    stats: DashboardStats
    recent_batches: list[DashboardBatch] = Field(default_factory=list)
    lesson_contexts: list[DashboardLessonContext] = Field(default_factory=list)
    syncable_files: list[str] = Field(default_factory=list)
    defaults: PreviewDefaults = Field(default_factory=PreviewDefaults)


class BatchPreviewResponse(StrictModel):
    batch: CardBatch
    canonical_batch_path: str
    preview_batch_path: str
    synced_batch_path: str | None = None


class NewVocabJobRequest(StrictModel):
    count: int = DEFAULT_NEW_VOCAB_COUNT
    gap_ratio: float = DEFAULT_NEW_VOCAB_GAP_RATIO
    lesson_context: str | None = None
    with_audio: bool = DEFAULT_NEW_VOCAB_WITH_AUDIO
    image_quality: Literal["auto", "low", "medium", "high"] = DEFAULT_NEW_VOCAB_IMAGE_QUALITY
    target_deck: str = DEFAULT_NEW_VOCAB_TARGET_DECK
    anki_url: str = DEFAULT_ANKI_URL


class SyncMediaJobRequest(StrictModel):
    input_path: str
    output_path: str | None = None
    sync_first: bool = DEFAULT_SYNC_MEDIA_SYNC_FIRST
    media_dir: str = DEFAULT_MEDIA_DIR
    anki_url: str = DEFAULT_ANKI_URL


class JobResponse(StrictModel):
    id: str
    kind: JobKind
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    progress_current: int = 0
    progress_total: int = 0
    progress_label: str | None = None
    logs: list[str] = Field(default_factory=list)
    error: str | None = None
    output_paths: list[str] = Field(default_factory=list)
