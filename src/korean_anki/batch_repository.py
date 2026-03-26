from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from .note_keys import prior_note_from_item
from . import path_policy
from .schema import CardBatch, PriorNote


class BatchRepository:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()

    def batch_paths(self) -> list[Path]:
        return _sorted_batch_paths(self.project_root)

    def load_batch(self, batch_path: Path) -> CardBatch:
        resolved_path = batch_path.resolve()
        cached = _cached_batch(
            str(resolved_path),
            resolved_path.stat().st_mtime_ns,
        )
        return cached.model_copy(deep=True)

    def canonical_batch_path(self, batch_path: Path) -> Path:
        return path_policy.canonical_batch_path(batch_path)

    def synced_paths(self) -> dict[Path, Path]:
        return {
            self.canonical_batch_path(path): path
            for path in self.batch_paths()
            if path_policy.is_synced_batch_path(path)
        }

    def canonical_batch_paths(self) -> list[Path]:
        return [path for path in self.batch_paths() if not path_policy.is_synced_batch_path(path)]

    def generated_history(self, *, exclude_batch_path: Path | None = None) -> list[PriorNote]:
        exclude_resolved = exclude_batch_path.resolve() if exclude_batch_path is not None else None
        history: list[PriorNote] = []
        for batch_path in self.batch_paths():
            if exclude_resolved is not None and batch_path == exclude_resolved:
                continue
            try:
                batch = self.load_batch(batch_path)
            except Exception:  # noqa: BLE001
                continue
            source = str(batch_path.relative_to(self.project_root))
            for note in batch.notes:
                history.append(prior_note_from_item(note.item, source=source))
        return history

    def syncable_files(self) -> list[str]:
        return sorted(
            str(path.relative_to(self.project_root))
            for path in self.batch_paths()
            if not path_policy.is_synced_batch_path(path)
        )


def _sorted_batch_paths(project_root: Path) -> list[Path]:
    batch_paths = [
        *project_root.glob("lessons/**/generated/*.batch.json"),
        *project_root.glob("data/generated/*.batch.json"),
    ]
    return sorted(batch_paths, key=lambda path: path.stat().st_mtime, reverse=True)


@lru_cache(maxsize=None)
def _cached_batch(batch_path: str, mtime_ns: int) -> CardBatch:
    del mtime_ns
    return CardBatch.model_validate_json(Path(batch_path).read_text(encoding="utf-8"))
