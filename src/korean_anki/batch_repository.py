from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from .note_keys import prior_note_from_item
from .schema import CardBatch, PriorNote
from .snapshot_cache import invalidate_project_snapshots, project_snapshot_version


class BatchRepository:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()

    @property
    def snapshot_version(self) -> int:
        return project_snapshot_version(self.project_root)

    def invalidate(self) -> None:
        invalidate_project_snapshots(self.project_root)

    def batch_paths(self) -> list[Path]:
        return [Path(path) for path in _cached_batch_paths(str(self.project_root), self.snapshot_version)]

    def load_batch(self, batch_path: Path) -> CardBatch:
        resolved_path = batch_path.resolve()
        cached = _cached_batch(
            str(resolved_path),
            resolved_path.stat().st_mtime_ns,
        )
        return cached.model_copy(deep=True)

    def canonical_batch_path(self, batch_path: Path) -> Path:
        return canonical_batch_path(batch_path)

    def synced_paths(self) -> dict[Path, Path]:
        return {
            self.canonical_batch_path(path): path
            for path in self.batch_paths()
            if path.name.endswith(".synced.batch.json")
        }

    def canonical_batch_paths(self) -> list[Path]:
        return [path for path in self.batch_paths() if not path.name.endswith(".synced.batch.json")]

    def generated_history(self, *, exclude_batch_path: Path | None = None) -> list[PriorNote]:
        exclude_path = str(exclude_batch_path.resolve()) if exclude_batch_path is not None else None
        return [
            note.model_copy(deep=True)
            for note in _cached_generated_history(
                str(self.project_root),
                exclude_path,
                self.snapshot_version,
            )
        ]

    def syncable_files(self) -> list[str]:
        return list(_cached_syncable_files(str(self.project_root), self.snapshot_version))


def canonical_batch_path(batch_path: Path) -> Path:
    if batch_path.name.endswith(".synced.batch.json"):
        return batch_path.with_name(f"{batch_path.name.removesuffix('.synced.batch.json')}.batch.json")
    return batch_path


@lru_cache(maxsize=None)
def _cached_batch_paths(project_root: str, version: int) -> tuple[str, ...]:
    root = Path(project_root)
    batch_paths = [
        *root.glob("lessons/**/generated/*.batch.json"),
        *root.glob("data/generated/*.batch.json"),
    ]
    sorted_paths = sorted(batch_paths, key=lambda path: path.stat().st_mtime, reverse=True)
    return tuple(str(path.resolve()) for path in sorted_paths)


@lru_cache(maxsize=None)
def _cached_batch(batch_path: str, mtime_ns: int) -> CardBatch:
    del mtime_ns
    return CardBatch.model_validate_json(Path(batch_path).read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def _cached_generated_history(
    project_root: str,
    exclude_batch_path: str | None,
    version: int,
) -> tuple[PriorNote, ...]:
    root = Path(project_root)
    history: list[PriorNote] = []
    for batch_path_str in _cached_batch_paths(project_root, version):
        batch_path = Path(batch_path_str)
        if exclude_batch_path is not None and batch_path_str == exclude_batch_path:
            continue
        try:
            batch = _cached_batch(batch_path_str, batch_path.stat().st_mtime_ns)
        except Exception:  # noqa: BLE001
            continue

        source = str(batch_path.relative_to(root))
        for note in batch.notes:
            history.append(prior_note_from_item(note.item, source=source))
    return tuple(history)


@lru_cache(maxsize=None)
def _cached_syncable_files(project_root: str, version: int) -> tuple[str, ...]:
    root = Path(project_root)
    return tuple(
        sorted(
            str(path.relative_to(root))
            for path in [
                *root.glob("lessons/**/generated/*.batch.json"),
                *root.glob("data/generated/*.batch.json"),
            ]
            if not path.name.endswith(".synced.batch.json")
        )
    )
