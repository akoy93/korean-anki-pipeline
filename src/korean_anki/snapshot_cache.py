from __future__ import annotations

import threading
import time

_ANKI_VERSIONS: dict[str, int] = {}
_ANKI_AVAILABILITY: dict[str, tuple[bool, int | None]] = {}
_VERSION_LOCK = threading.Lock()
_ANKI_SNAPSHOT_TTL_SECONDS = 15


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


def _anki_time_bucket() -> int:
    return int(time.time() // _ANKI_SNAPSHOT_TTL_SECONDS)
