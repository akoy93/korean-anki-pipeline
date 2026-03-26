from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from .anki_client import ANKI_MODEL_NAME, AnkiConnectClient
from .anki_note_codec import extract_audio_filename, extract_image_filename, note_key_for_fields, parse_item_type


class StoredNoteMedia(TypedDict):
    note_id: int
    audio_filename: str | None
    image_filename: str | None


def existing_model_notes(anki_url: str = "http://127.0.0.1:8765") -> dict[str, list[tuple[str, int]]]:
    client = AnkiConnectClient(url=anki_url)
    query = f'note:"{ANKI_MODEL_NAME}"'
    existing_note_ids = client.invoke("findNotes", query=query)
    if not isinstance(existing_note_ids, list) or not existing_note_ids:
        return {}

    notes_info = client.invoke("notesInfo", notes=existing_note_ids)
    if not isinstance(notes_info, list):
        return {}

    existing_by_korean: dict[str, list[tuple[str, int]]] = {}
    for note_info in notes_info:
        if not isinstance(note_info, dict):
            continue
        fields = note_info.get("fields")
        note_id = note_info.get("noteId")
        if not isinstance(fields, dict) or not isinstance(note_id, int):
            continue
        korean_field = fields.get("Korean")
        english_field = fields.get("English")
        if not isinstance(korean_field, dict) or not isinstance(english_field, dict):
            continue
        korean = korean_field.get("value")
        english = english_field.get("value")
        if not isinstance(korean, str) or not isinstance(english, str):
            continue
        existing_by_korean.setdefault(korean, []).append((english, note_id))

    return existing_by_korean


def existing_model_media_index(client: AnkiConnectClient) -> dict[str, StoredNoteMedia]:
    query = f'note:"{ANKI_MODEL_NAME}"'
    note_ids = client.invoke("findNotes", query=query)
    if not isinstance(note_ids, list) or not note_ids:
        return {}

    notes_info = client.invoke("notesInfo", notes=note_ids)
    if not isinstance(notes_info, list):
        return {}

    media_index: dict[str, StoredNoteMedia] = {}
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
        audio_field = fields.get("Audio")
        image_field = fields.get("Image")
        if not isinstance(korean_field, dict) or not isinstance(english_field, dict):
            continue

        korean = korean_field.get("value")
        english = english_field.get("value")
        if not isinstance(korean, str) or not isinstance(english, str):
            continue

        tag_values = [tag for tag in tags if isinstance(tag, str)]
        note_key = note_key_for_fields(parse_item_type(tag_values), korean, english)
        media_index[note_key] = {
            "note_id": note_id,
            "audio_filename": (
                extract_audio_filename(audio_field.get("value", "")) if isinstance(audio_field, dict) else None
            ),
            "image_filename": (
                extract_image_filename(image_field.get("value", "")) if isinstance(image_field, dict) else None
            ),
        }

    return media_index


def existing_model_note_keys(anki_url: str = "http://127.0.0.1:8765") -> set[str]:
    client = AnkiConnectClient(url=anki_url)
    return set(existing_model_media_index(client).keys())
