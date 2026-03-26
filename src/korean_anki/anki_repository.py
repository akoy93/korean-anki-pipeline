from __future__ import annotations

from collections import Counter
from functools import lru_cache
from typing import Callable

from .anki_client import ANKI_MODEL_NAME, AnkiConnectClient
from .note_keys import normalize_text
from .schema import AnkiStatsSnapshot, PriorNote
from .snapshot_cache import (
    anki_snapshot_version,
    invalidate_anki_snapshots,
    record_anki_availability,
)


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

        if record_anki_availability(self.anki_url, connected=connected, version=version):
            invalidate_anki_snapshots(self.anki_url)
        return connected, version

    def dashboard_stats(self) -> tuple[int, int, dict[str, int]]:
        connected, _ = self.service_status()
        if not connected:
            return 0, 0, {}

        return _cached_anki_dashboard_stats(
            self.anki_url,
            self.snapshot_version,
            self._client_factory,
        )

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
    if note_keys_loader is not None:
        return tuple(sorted(note_keys_loader(anki_url=anki_url)))

    imported_notes, _ = _cached_imported_anki_history(anki_url, version, AnkiConnectClient)
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
