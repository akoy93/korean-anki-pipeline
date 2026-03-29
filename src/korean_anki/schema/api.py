from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import Field

from ..settings import (
    DEFAULT_ANKI_URL,
    DEFAULT_LESSON_AUDIO,
    DEFAULT_NEW_VOCAB_COUNT,
    DEFAULT_NEW_VOCAB_GAP_RATIO,
    DEFAULT_NEW_VOCAB_IMAGE_QUALITY,
    DEFAULT_NEW_VOCAB_TARGET_DECK,
    DEFAULT_NEW_VOCAB_WITH_AUDIO,
)
from .common import BatchPushStatus, StrictModel, StudyLane
from .domain import CardBatch, GeneratedNote, LessonItem


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


class ServiceStatus(StrictModel):
    backend_ok: bool = True
    anki_connect_ok: bool = False
    anki_connect_version: int | None = None
    openai_configured: bool = False
    preview_ok: bool = False
    preview_detail: str | None = None
    tailscale_ok: bool = False
    tailscale_detail: str | None = None
    tailscale_dns_name: str | None = None
    tailscale_key_expiry_at: datetime | None = None
    remote_url: str | None = None


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


class VocabularyModelPoint(StrictModel):
    date: date
    estimated_size: float = 0
    retained_units: int = 0
    at_risk_units: int = 0
    review_count: int = 0
    is_forecast: bool = False


class VocabularyModelSummary(StrictModel):
    current_estimated_size: float = 0
    change_7d: float = 0
    projected_30d_size: float = 0
    peak_estimated_size: float = 0
    total_observed_units: int = 0
    at_risk_units: int = 0
    current_streak_days: int = 0


class VocabularyModelResponse(StrictModel):
    available: bool = False
    reason: str | None = None
    scope_label: str = "Words + phrases"
    forecast_days: int = 30
    points: list[VocabularyModelPoint] = Field(default_factory=list)
    summary: VocabularyModelSummary | None = None


class BatchPreviewResponse(StrictModel):
    batch: CardBatch
    canonical_batch_path: str
    preview_batch_path: str
    synced_batch_path: str | None = None
    push_status: BatchPushStatus | None = None
    media_hydrated: bool | None = None


__all__ = [
    "BatchPreviewResponse",
    "DashboardBatch",
    "DashboardLessonContext",
    "DashboardResponse",
    "DashboardStats",
    "DeleteBatchRequest",
    "DeleteBatchResult",
    "DuplicateNote",
    "LessonGenerateDefaults",
    "NewVocabDefaults",
    "PreviewDefaults",
    "PreviewNoteRefreshRequest",
    "PushRequest",
    "PushResult",
    "ServiceStatus",
    "VocabularyModelPoint",
    "VocabularyModelResponse",
    "VocabularyModelSummary",
]
