from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import threading
import time

_PROJECT_VERSIONS: dict[str, int] = {}
_ANKI_VERSIONS: dict[str, int] = {}
_ANKI_AVAILABILITY: dict[str, tuple[bool, int | None]] = {}
_VERSION_LOCK = threading.Lock()
_ANKI_SNAPSHOT_TTL_SECONDS = 15


def project_snapshot_version(project_root: Path) -> int:
    resolved_root = project_root.resolve()
    root_key = str(resolved_root)
    return max(
        _PROJECT_VERSIONS.get(root_key, 0),
        _marker_version(_project_snapshot_marker(resolved_root)),
        _project_filesystem_version(resolved_root),
    )


def anki_snapshot_version(anki_url: str) -> int:
    return max(
        _ANKI_VERSIONS.get(anki_url, 0),
        _marker_version(_anki_snapshot_marker(anki_url)),
        _anki_time_bucket(),
    )


def invalidate_project_snapshots(project_root: Path) -> None:
    resolved_root = project_root.resolve()
    root_key = str(resolved_root)
    with _VERSION_LOCK:
        _PROJECT_VERSIONS[root_key] = _PROJECT_VERSIONS.get(root_key, 0) + 1
    _touch_marker(_project_snapshot_marker(resolved_root))


def invalidate_anki_snapshots(anki_url: str) -> None:
    with _VERSION_LOCK:
        _ANKI_VERSIONS[anki_url] = _ANKI_VERSIONS.get(anki_url, 0) + 1
    _touch_marker(_anki_snapshot_marker(anki_url))


def record_anki_availability(anki_url: str, *, connected: bool, version: int | None) -> bool:
    current = (connected, version)
    with _VERSION_LOCK:
        previous = _ANKI_AVAILABILITY.get(anki_url)
        if previous == current:
            return False
        _ANKI_AVAILABILITY[anki_url] = current
        return previous is not None


def _project_snapshot_marker(project_root: Path) -> Path:
    return project_root / "state" / ".snapshot-stamps" / "project.stamp"


def _anki_snapshot_marker(anki_url: str) -> Path:
    digest = hashlib.sha1(anki_url.encode("utf-8")).hexdigest()[:16]
    return Path(tempfile.gettempdir()) / "korean-anki-pipeline" / f"anki-{digest}.stamp"


def _touch_marker(marker_path: Path) -> None:
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.touch()


def _marker_version(marker_path: Path) -> int:
    try:
        return marker_path.stat().st_mtime_ns
    except FileNotFoundError:
        return 0


def _project_filesystem_version(project_root: Path) -> int:
    max_mtime = 0
    for path in (
        *project_root.glob("data/generated/*.batch.json"),
        *project_root.glob("lessons/**/generated/*.batch.json"),
        *project_root.glob("lessons/*/transcription.json"),
    ):
        try:
            max_mtime = max(max_mtime, path.stat().st_mtime_ns)
        except FileNotFoundError:
            continue
    return max_mtime


def _anki_time_bucket() -> int:
    return int(time.time() // _ANKI_SNAPSHOT_TTL_SECONDS)
