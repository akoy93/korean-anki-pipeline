from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

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
BatchPushStatus = Literal["not-pushed", "pushed"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


__all__ = [
    "BatchPushStatus",
    "CardKind",
    "DuplicateStatus",
    "ItemType",
    "QaSeverity",
    "RawSourceKind",
    "SchemaVersion",
    "StrictModel",
    "StudyLane",
    "VocabAdjacencyKind",
]
