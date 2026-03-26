from __future__ import annotations

import hashlib
from pathlib import Path
import threading
import time

_ANKI_VERSIONS: dict[str, int] = {}
_ANKI_AVAILABILITY: dict[str, tuple[bool, int | None]] = {}
_VERSION_LOCK = threading.Lock()
_ANKI_SNAPSHOT_TTL_SECONDS = 15


def project_snapshot_version(project_root: Path) -> int:
    return _project_filesystem_version(project_root.resolve())


def anki_snapshot_version(anki_url: str) -> int:
    return max(
        _ANKI_VERSIONS.get(anki_url, 0),
        _anki_time_bucket(),
    )


def invalidate_anki_snapshots(anki_url: str) -> None:
    with _VERSION_LOCK:
        _ANKI_VERSIONS[anki_url] = _ANKI_VERSIONS.get(anki_url, 0) + 1


def record_anki_availability(anki_url: str, *, connected: bool, version: int | None) -> bool:
    current = (connected, version)
    with _VERSION_LOCK:
        previous = _ANKI_AVAILABILITY.get(anki_url)
        if previous == current:
            return False
        _ANKI_AVAILABILITY[anki_url] = current
        return previous is not None


def _project_filesystem_version(project_root: Path) -> int:
    signatures: list[str] = []
    for path in sorted(
        (
            *project_root.glob("data/generated/*.batch.json"),
            *project_root.glob("lessons/**/generated/*.batch.json"),
            *project_root.glob("lessons/*/transcription.json"),
        ),
        key=lambda item: str(item),
    ):
        try:
            stat = path.stat()
        except FileNotFoundError:
            continue
        signatures.append(
            f"{path.relative_to(project_root)}:{stat.st_mtime_ns}:{stat.st_size}"
        )
    if not signatures:
        return 0
    digest = hashlib.sha1("\n".join(signatures).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _anki_time_bucket() -> int:
    return int(time.time() // _ANKI_SNAPSHOT_TTL_SECONDS)
