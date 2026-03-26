from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .anki_client import AnkiConnectClient
from .anki_note_codec import note_key_for_fields
from .anki_queries import StoredNoteMedia, existing_model_media_index
from .cards import refresh_generated_note
from .schema import CardBatch, LessonDocument, LessonItem, MediaAsset


@dataclass(frozen=True)
class MediaSyncSummary:
    matched_notes: int = 0
    missing_notes: int = 0
    audio_downloaded: int = 0
    image_downloaded: int = 0


def _write_media_asset(
    client: AnkiConnectClient,
    filename: str | None,
    output_dir: Path,
    existing: MediaAsset | None,
) -> tuple[MediaAsset | None, bool]:
    if filename is None:
        return existing, False

    payload = client.retrieve_media_file(filename)
    if payload is None:
        return existing, False

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename
    output_path.write_bytes(payload)

    if existing is not None:
        return existing.model_copy(update={"path": str(output_path)}), True
    return MediaAsset(path=str(output_path)), True


def _sync_item_media(
    item: LessonItem,
    client: AnkiConnectClient,
    media_index: dict[str, StoredNoteMedia],
    media_dir: Path,
) -> tuple[LessonItem, bool, int, int]:
    note_key = note_key_for_fields(item.item_type, item.korean, item.english)
    stored = media_index.get(note_key)
    if stored is None:
        return item, False, 0, 0

    audio_asset, audio_downloaded = _write_media_asset(client, stored["audio_filename"], media_dir / "audio", item.audio)
    image_asset, image_downloaded = _write_media_asset(client, stored["image_filename"], media_dir / "images", item.image)

    return (
        item.model_copy(update={"audio": audio_asset, "image": image_asset}),
        True,
        1 if audio_downloaded else 0,
        1 if image_downloaded else 0,
    )


def sync_lesson_media(
    document: LessonDocument,
    *,
    media_dir: Path,
    anki_url: str = "http://127.0.0.1:8765",
    sync_first: bool = False,
) -> tuple[LessonDocument, MediaSyncSummary]:
    client = AnkiConnectClient(url=anki_url)
    if sync_first:
        client.sync()
    media_index = existing_model_media_index(client)

    matched_notes = 0
    missing_notes = 0
    audio_downloaded = 0
    image_downloaded = 0
    updated_items: list[LessonItem] = []
    for item in document.items:
        updated_item, matched, audio_count, image_count = _sync_item_media(item, client, media_index, media_dir)
        updated_items.append(updated_item)
        if matched:
            matched_notes += 1
        else:
            missing_notes += 1
        audio_downloaded += audio_count
        image_downloaded += image_count

    return (
        document.model_copy(update={"items": updated_items}),
        MediaSyncSummary(
            matched_notes=matched_notes,
            missing_notes=missing_notes,
            audio_downloaded=audio_downloaded,
            image_downloaded=image_downloaded,
        ),
    )


def sync_batch_media(
    batch: CardBatch,
    *,
    media_dir: Path,
    anki_url: str = "http://127.0.0.1:8765",
    sync_first: bool = False,
) -> tuple[CardBatch, MediaSyncSummary]:
    client = AnkiConnectClient(url=anki_url)
    if sync_first:
        client.sync()
    media_index = existing_model_media_index(client)

    matched_notes = 0
    missing_notes = 0
    audio_downloaded = 0
    image_downloaded = 0
    updated_notes = []
    for note in batch.notes:
        updated_item, matched, audio_count, image_count = _sync_item_media(note.item, client, media_index, media_dir)
        updated_notes.append(refresh_generated_note(note, updated_item))
        if matched:
            matched_notes += 1
        else:
            missing_notes += 1
        audio_downloaded += audio_count
        image_downloaded += image_count

    return (
        batch.model_copy(update={"notes": updated_notes}),
        MediaSyncSummary(
            matched_notes=matched_notes,
            missing_notes=missing_notes,
            audio_downloaded=audio_downloaded,
            image_downloaded=image_downloaded,
        ),
    )
