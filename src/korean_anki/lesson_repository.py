from __future__ import annotations

from pathlib import Path

from .schema import DashboardLessonContext, LessonTranscription


class LessonRepository:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()

    def lesson_contexts(self) -> list[DashboardLessonContext]:
        contexts: list[DashboardLessonContext] = []
        for transcription_path in sorted(self.project_root.glob("lessons/*/transcription.json"), reverse=True):
            try:
                transcription = LessonTranscription.model_validate_json(
                    transcription_path.read_text(encoding="utf-8")
                )
            except Exception:  # noqa: BLE001
                continue
            contexts.append(
                DashboardLessonContext(
                    path=str(transcription_path.relative_to(self.project_root)),
                    label=f"{transcription.lesson_date.isoformat()} • {transcription.title} • {transcription.theme}",
                )
            )
        return contexts
