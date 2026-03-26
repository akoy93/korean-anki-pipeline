from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from ..settings import (
    DEFAULT_ANKI_URL,
    DEFAULT_MEDIA_DIR,
    DEFAULT_NEW_VOCAB_COUNT,
    DEFAULT_NEW_VOCAB_GAP_RATIO,
    DEFAULT_NEW_VOCAB_IMAGE_QUALITY,
    DEFAULT_NEW_VOCAB_TARGET_DECK,
    DEFAULT_NEW_VOCAB_WITH_AUDIO,
    DEFAULT_SYNC_MEDIA_SYNC_FIRST,
)
from .common import StrictModel

JobStatus = Literal["queued", "running", "succeeded", "failed"]
JobKind = Literal["lesson-generate", "new-vocab", "sync-media"]


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


__all__ = [
    "JobKind",
    "JobResponse",
    "JobStatus",
    "NewVocabJobRequest",
    "SyncMediaJobRequest",
]
