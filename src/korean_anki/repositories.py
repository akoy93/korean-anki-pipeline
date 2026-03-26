from __future__ import annotations

from collections import Counter
from functools import lru_cache
import hashlib
from pathlib import Path
import tempfile
import threading
import time
from typing import Callable

from .anki import ANKI_MODEL_NAME, AnkiConnectClient
from .note_keys import normalize_text, prior_note_from_item
from .schema import AnkiStatsSnapshot, CardBatch, DashboardLessonContext, LessonTranscription, PriorNote


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
        if batch_path.name.endswith(".synced.batch.json"):
            return batch_path.with_name(f"{batch_path.name.removesuffix('.synced.batch.json')}.batch.json")
        return batch_path

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

    def lesson_contexts(self) -> list[DashboardLessonContext]:
        return LessonRepository(self.project_root).lesson_contexts()

    def syncable_files(self) -> list[str]:
        return list(_cached_syncable_files(str(self.project_root), self.snapshot_version))


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


class AnkiRepository:
    def __init__(
        self,
        anki_url: str,
        *,
        client_factory: Callable[..., object] = AnkiConnectClient,
        note_keys_loader: Callable[..., set[str]] | None = None,
    ) -> None:
        self.anki_url = anki_url
        self._client_factory = client_factory
        self._note_keys_loader = note_keys_loader

    @property
    def snapshot_version(self) -> int:
        return anki_snapshot_version(self.anki_url)

    def invalidate(self) -> None:
        invalidate_anki_snapshots(self.anki_url)

    def service_status(self) -> tuple[bool, int | None]:
        connected = False
        version: int | None = None
        try:
            result = self._client_factory(url=self.anki_url).invoke("version")
            if isinstance(result, int):
                connected = True
                version = result
        except Exception:  # noqa: BLE001
            connected = False
            version = None

        should_invalidate = False
        with _VERSION_LOCK:
            previous = _ANKI_AVAILABILITY.get(self.anki_url)
            current = (connected, version)
            if previous != current:
                _ANKI_AVAILABILITY[self.anki_url] = current
                should_invalidate = previous is not None
        if should_invalidate:
            invalidate_anki_snapshots(self.anki_url)
        return connected, version

    def dashboard_stats(self) -> tuple[int, int, dict[str, int]]:
        connected, _ = self.service_status()
        if not connected:
            return 0, 0, {}

        snapshot = _cached_anki_dashboard_stats(
            self.anki_url,
            self.snapshot_version,
            self._client_factory,
        )
        return snapshot

    def note_keys(self) -> set[str]:
        connected, _ = self.service_status()
        if not connected:
            return set()

        return set(
            _cached_anki_note_keys(
                self.anki_url,
                self.snapshot_version,
                self._note_keys_loader,
            )
        )

    def imported_history(self) -> tuple[list[PriorNote], AnkiStatsSnapshot]:
        connected, _ = self.service_status()
        if not connected:
            return [], AnkiStatsSnapshot()

        imported_notes, stats = _cached_imported_anki_history(
            self.anki_url,
            self.snapshot_version,
            self._client_factory,
        )
        return [note.model_copy(deep=True) for note in imported_notes], stats.model_copy(deep=True)


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


def _parse_item_type(tags: list[str]) -> str:
    for tag in tags:
        if tag.startswith("type:"):
            candidate = tag.removeprefix("type:")
            if candidate in {"vocab", "phrase", "grammar", "dialogue", "number"}:
                return candidate
    return "vocab"


def _parse_lane(tags: list[str]) -> str:
    for tag in tags:
        if tag.startswith("lane:"):
            candidate = tag.removeprefix("lane:")
            if candidate in {"lesson", "new-vocab", "reading-speed", "grammar", "listening"}:
                return candidate
    return "lesson"


def _parse_skill_tags(tags: list[str]) -> list[str]:
    return [tag.removeprefix("skill:") for tag in tags if tag.startswith("skill:")]


@lru_cache(maxsize=None)
def _cached_anki_note_keys(
    anki_url: str,
    version: int,
    note_keys_loader: Callable[..., set[str]] | None,
) -> tuple[str, ...]:
    del version
    if note_keys_loader is not None:
        return tuple(sorted(note_keys_loader(anki_url=anki_url)))

    imported_notes, _ = _cached_imported_anki_history(anki_url, anki_snapshot_version(anki_url), AnkiConnectClient)
    return tuple(sorted(note.note_key for note in imported_notes))


@lru_cache(maxsize=None)
def _cached_imported_anki_history(
    anki_url: str,
    version: int,
    client_factory: Callable[..., object],
) -> tuple[tuple[PriorNote, ...], AnkiStatsSnapshot]:
    del version
    client = client_factory(url=anki_url)
    note_ids = client.invoke("findNotes", query=f'note:"{ANKI_MODEL_NAME}"')
    if not isinstance(note_ids, list) or not note_ids:
        return tuple(), AnkiStatsSnapshot()

    notes_info = client.invoke("notesInfo", notes=note_ids)
    imported_notes: list[PriorNote] = []
    if isinstance(notes_info, list):
        for note_info in notes_info:
            if not isinstance(note_info, dict):
                continue
            fields = note_info.get("fields")
            tags = note_info.get("tags")
            note_id = note_info.get("noteId")
            if not isinstance(fields, dict) or not isinstance(tags, list) or not isinstance(note_id, int):
                continue
            korean_field = fields.get("Korean")
            english_field = fields.get("English")
            if not isinstance(korean_field, dict) or not isinstance(english_field, dict):
                continue
            korean = korean_field.get("value")
            english = english_field.get("value")
            if not isinstance(korean, str) or not isinstance(english, str):
                continue
            tag_strings = [tag for tag in tags if isinstance(tag, str)]
            imported_notes.append(
                PriorNote(
                    note_key=f"{_parse_item_type(tag_strings)}:{normalize_text(korean)}:{normalize_text(english)}",
                    korean=korean,
                    english=english,
                    item_type=_parse_item_type(tag_strings),  # type: ignore[arg-type]
                    lane=_parse_lane(tag_strings),  # type: ignore[arg-type]
                    skill_tags=_parse_skill_tags(tag_strings),
                    source="anki",
                    existing_note_id=note_id,
                )
            )

    card_ids = client.invoke("findCards", query=f'note:"{ANKI_MODEL_NAME}"')
    if not isinstance(card_ids, list) or not card_ids:
        return tuple(imported_notes), AnkiStatsSnapshot(note_count=len(imported_notes))

    cards_info = client.invoke("cardsInfo", cards=card_ids)
    template_counts: Counter[str] = Counter()
    tag_counts: Counter[str] = Counter()
    if isinstance(cards_info, list):
        for card_info in cards_info:
            if not isinstance(card_info, dict):
                continue
            template = card_info.get("template")
            tags = card_info.get("tags")
            if isinstance(template, str):
                template_counts[template] += 1
            if isinstance(tags, list):
                tag_counts.update(tag for tag in tags if isinstance(tag, str))

    return tuple(imported_notes), AnkiStatsSnapshot(
        note_count=len(imported_notes),
        card_count=len(card_ids),
        by_template=dict(template_counts),
        by_tag=dict(tag_counts),
    )


@lru_cache(maxsize=None)
def _cached_anki_dashboard_stats(
    anki_url: str,
    version: int,
    client_factory: Callable[..., object],
) -> tuple[int, int, dict[str, int]]:
    del version
    client = client_factory(url=anki_url)
    note_ids = client.invoke("findNotes", query=f'note:"{ANKI_MODEL_NAME}"')
    note_count = len(note_ids) if isinstance(note_ids, list) else 0

    card_ids = client.invoke("findCards", query=f'note:"{ANKI_MODEL_NAME}"')
    card_count = len(card_ids) if isinstance(card_ids, list) else 0

    deck_counts: dict[str, int] = {}
    deck_names = client.invoke("deckNames")
    if isinstance(deck_names, list):
        for deck_name in deck_names:
            if not isinstance(deck_name, str) or not deck_name.startswith("Korean::"):
                continue
            deck_cards = client.invoke("findCards", query=f'deck:"{deck_name}" note:"{ANKI_MODEL_NAME}"')
            if isinstance(deck_cards, list) and deck_cards:
                deck_counts[deck_name] = len(deck_cards)
    return note_count, card_count, deck_counts


_PROJECT_VERSIONS: dict[str, int] = {}
_ANKI_VERSIONS: dict[str, int] = {}
_ANKI_AVAILABILITY: dict[str, tuple[bool, int | None]] = {}
_VERSION_LOCK = threading.Lock()
_ANKI_SNAPSHOT_TTL_SECONDS = 15


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
