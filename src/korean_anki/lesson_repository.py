from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from .schema import DashboardLessonContext, LessonTranscription
from .snapshot_cache import invalidate_project_snapshots, project_snapshot_version


class LessonRepository:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()

    @property
    def snapshot_version(self) -> int:
        return project_snapshot_version(self.project_root)

    def invalidate(self) -> None:
        invalidate_project_snapshots(self.project_root)

    def lesson_contexts(self) -> list[DashboardLessonContext]:
        return [
            context.model_copy(deep=True)
            for context in _cached_lesson_contexts(str(self.project_root), self.snapshot_version)
        ]


@lru_cache(maxsize=None)
def _cached_lesson_contexts(project_root: str, version: int) -> tuple[DashboardLessonContext, ...]:
    root = Path(project_root)
    contexts: list[DashboardLessonContext] = []
    for transcription_path in sorted(root.glob("lessons/*/transcription.json"), reverse=True):
        try:
            transcription = LessonTranscription.model_validate_json(transcription_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        contexts.append(
            DashboardLessonContext(
                path=str(transcription_path.relative_to(root)),
                label=f"{transcription.lesson_date.isoformat()} • {transcription.title} • {transcription.theme}",
            )
        )
    return tuple(contexts)
