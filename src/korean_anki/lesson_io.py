from __future__ import annotations

from pathlib import Path

from .schema import LessonDocument, LessonTranscription


def write_json(document: LessonDocument, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(document.model_dump_json(indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_lesson(path: Path) -> LessonDocument:
    return LessonDocument.model_validate_json(path.read_text(encoding="utf-8"))


def read_transcription(path: Path) -> LessonTranscription:
    return LessonTranscription.model_validate_json(path.read_text(encoding="utf-8"))
