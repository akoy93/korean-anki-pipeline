from __future__ import annotations

import re
from pathlib import Path
from typing import Literal, TypedDict

from .anki_client import ANKI_MODEL_NAME, DEFAULT_DECK
from .schema import CardBatch, GeneratedNote

_SPACE_RE = re.compile(r"\s+")
_SOUND_RE = re.compile(r"\[sound:([^\]]+)\]")
_IMAGE_RE = re.compile(r"""<img\s+[^>]*src=['"]([^'"]+)['"]""")


class AnkiNote(TypedDict):
    deckName: str
    modelName: str
    fields: dict[str, str]
    tags: list[str]
    options: dict[str, bool]


def normalize_text(value: str) -> str:
    return _SPACE_RE.sub(" ", value.strip().casefold())


def note_key_for_fields(item_type: str, korean: str, english: str) -> str:
    return f"{item_type}:{normalize_text(korean)}:{normalize_text(english)}"


def parse_item_type(tags: list[str]) -> str:
    for tag in tags:
        if tag.startswith("type:"):
            candidate = tag.removeprefix("type:")
            if candidate in {"vocab", "phrase", "grammar", "dialogue", "number"}:
                return candidate
    return "vocab"


def extract_audio_filename(value: str) -> str | None:
    match = _SOUND_RE.search(value)
    return match.group(1) if match is not None else None


def extract_image_filename(value: str) -> str | None:
    match = _IMAGE_RE.search(value)
    return Path(match.group(1)).name if match is not None else None


def chunk_hangul(text: str) -> str:
    return " ".join("·".join(segment) for segment in text.split())


def approved_notes(batch: CardBatch) -> list[GeneratedNote]:
    return [note for note in batch.notes if note.approved and any(card.approved for card in note.cards)]


def approved_card_count(note: GeneratedNote) -> int:
    return sum(
        1
        for card in note.cards
        if card.approved and (card.kind != "listening" or note.item.audio is not None)
    )


def join_examples(note: GeneratedNote, field: Literal["korean", "english"]) -> str:
    if field == "korean":
        return "\n".join(example.korean for example in note.item.examples)
    return "\n".join(example.english for example in note.item.examples)


def build_note_payload(
    note: GeneratedNote,
    deck_name: str,
    media_names: dict[str, str],
    *,
    allow_duplicate: bool = False,
) -> AnkiNote:
    approved_kinds = {card.kind for card in note.cards if card.approved}
    audio = ""
    if note.item.audio is not None:
        audio_name = media_names[note.item.audio.path]
        audio = f"[sound:{audio_name}]"
    image = ""
    if note.item.image is not None:
        image_name = media_names[note.item.image.path]
        image = f"<img src='{image_name}'>"

    tags = sorted(
        {
            "korean",
            f"lesson:{note.item.lesson_id}",
            f"lane:{note.lane}",
            f"type:{note.item.item_type}",
            *note.item.tags,
            *(f"skill:{skill_tag}" for skill_tag in note.skill_tags),
        }
    )

    return {
        "deckName": deck_name,
        "modelName": ANKI_MODEL_NAME,
        "fields": {
            "Korean": note.item.korean,
            "English": note.item.english,
            "Pronunciation": note.item.pronunciation or "",
            "ExampleKo": join_examples(note, "korean"),
            "ExampleEn": join_examples(note, "english"),
            "Notes": note.item.notes or "",
            "Audio": audio,
            "Image": image,
            "SourceRef": note.item.source_ref or "",
            "ChunkedKorean": chunk_hangul(note.item.korean),
            "EnableRecognition": "1" if "recognition" in approved_kinds else "",
            "EnableProduction": "1" if "production" in approved_kinds else "",
            "EnableListening": "1" if "listening" in approved_kinds and note.item.audio is not None else "",
            "EnableNumberContext": "1" if "number-context" in approved_kinds else "",
            "EnableReadAloud": "1" if "read-aloud" in approved_kinds else "",
            "EnableChunkedReading": "1" if "chunked-reading" in approved_kinds else "",
            "EnableDecodablePassage": "1" if "decodable-passage" in approved_kinds else "",
        },
        "tags": tags,
        "options": {"allowDuplicate": allow_duplicate},
    }


def target_deck(batch: CardBatch, deck_name: str | None) -> str:
    return deck_name or batch.metadata.target_deck or DEFAULT_DECK
