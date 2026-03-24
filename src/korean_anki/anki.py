from __future__ import annotations

import base64
from pathlib import Path
from typing import Literal, TypedDict

import requests

from .schema import CardBatch, DuplicateNote, GeneratedNote, PushResult

ANKI_MODEL_NAME = "Korean Lesson Item"
DEFAULT_DECK = "Korean::Lessons"

ANKI_FIELDS = [
    "Korean",
    "English",
    "Pronunciation",
    "ExampleKo",
    "ExampleEn",
    "Notes",
    "Audio",
    "Image",
    "SourceRef",
    "ChunkedKorean",
    "EnableRecognition",
    "EnableProduction",
    "EnableListening",
    "EnableNumberContext",
    "EnableReadAloud",
    "EnableChunkedReading",
    "EnableDecodablePassage",
]

ANKI_TEMPLATES: list[_Template] = [
    {
        "Name": "Recognition",
        "Front": "{{#EnableRecognition}}<div class='card-ko'>{{Korean}}</div>{{/EnableRecognition}}",
        "Back": (
            "{{FrontSide}}<hr id='answer'>"
            "<div class='card-en'>{{English}}</div>"
            "<div class='pronunciation'>{{Pronunciation}}</div>"
            "<div class='example-ko'>{{ExampleKo}}</div>"
            "<div class='example-en'>{{ExampleEn}}</div>"
            "<div class='notes'>{{Notes}}</div>"
            "<div class='media'>{{Audio}}{{Image}}</div>"
            "<div class='source'>{{SourceRef}}</div>"
        ),
    },
    {
        "Name": "Production",
        "Front": "{{#EnableProduction}}<div class='card-en'>{{English}}</div>{{/EnableProduction}}",
        "Back": (
            "{{FrontSide}}<hr id='answer'>"
            "<div class='card-ko'>{{Korean}}</div>"
            "<div class='pronunciation'>{{Pronunciation}}</div>"
            "<div class='example-ko'>{{ExampleKo}}</div>"
            "<div class='example-en'>{{ExampleEn}}</div>"
            "<div class='notes'>{{Notes}}</div>"
            "<div class='media'>{{Audio}}{{Image}}</div>"
            "<div class='source'>{{SourceRef}}</div>"
        ),
    },
    {
        "Name": "Listening",
        "Front": "{{#EnableListening}}<div class='listening'>{{Audio}}</div>{{/EnableListening}}",
        "Back": (
            "{{FrontSide}}<hr id='answer'>"
            "<div class='card-ko'>{{Korean}}</div>"
            "<div class='card-en'>{{English}}</div>"
            "<div class='pronunciation'>{{Pronunciation}}</div>"
            "<div class='example-ko'>{{ExampleKo}}</div>"
            "<div class='example-en'>{{ExampleEn}}</div>"
            "<div class='notes'>{{Notes}}</div>"
            "<div class='media'>{{Image}}</div>"
            "<div class='source'>{{SourceRef}}</div>"
        ),
    },
    {
        "Name": "Number Context",
        "Front": (
            "{{#EnableNumberContext}}"
            "<div class='prompt-context'>In what context is this number form used?</div>"
            "<div class='card-ko'>{{Korean}}</div>"
            "{{/EnableNumberContext}}"
        ),
        "Back": (
            "{{FrontSide}}<hr id='answer'>"
            "<div class='card-en'>{{English}}</div>"
            "<div class='notes'>{{Notes}}</div>"
            "<div class='example-ko'>{{ExampleKo}}</div>"
            "<div class='example-en'>{{ExampleEn}}</div>"
        ),
    },
    {
        "Name": "Read Aloud",
        "Front": (
            "{{#EnableReadAloud}}"
            "<div class='prompt-context'>Read aloud before revealing anything else.</div>"
            "<div class='card-ko'>{{Korean}}</div>"
            "{{/EnableReadAloud}}"
        ),
        "Back": (
            "{{FrontSide}}<hr id='answer'>"
            "<div class='card-ko'>{{Korean}}</div>"
            "<div class='card-en'>{{English}}</div>"
            "<div class='pronunciation'>{{Pronunciation}}</div>"
            "<div class='notes'>{{Notes}}</div>"
            "<div class='media'>{{Audio}}</div>"
            "<div class='source'>{{SourceRef}}</div>"
        ),
    },
    {
        "Name": "Chunked Reading",
        "Front": (
            "{{#EnableChunkedReading}}"
            "<div class='prompt-context'>Sound out the chunks, then blend the full word.</div>"
            "<div class='card-ko'>{{ChunkedKorean}}</div>"
            "{{/EnableChunkedReading}}"
        ),
        "Back": (
            "{{FrontSide}}<hr id='answer'>"
            "<div class='card-ko'>{{Korean}}</div>"
            "<div class='card-en'>{{English}}</div>"
            "<div class='pronunciation'>{{Pronunciation}}</div>"
            "<div class='notes'>{{Notes}}</div>"
            "<div class='source'>{{SourceRef}}</div>"
        ),
    },
    {
        "Name": "Decodable Passage",
        "Front": (
            "{{#EnableDecodablePassage}}"
            "<div class='prompt-context'>Read this tiny passage smoothly.</div>"
            "<div class='card-ko'>{{Korean}}</div>"
            "{{/EnableDecodablePassage}}"
        ),
        "Back": (
            "{{FrontSide}}<hr id='answer'>"
            "<div class='card-en'>{{English}}</div>"
            "<div class='notes'>{{Notes}}</div>"
            "<div class='media'>{{Audio}}</div>"
            "<div class='source'>{{SourceRef}}</div>"
        ),
    },
]

ANKI_CSS = """
.card {
  font-family: -apple-system, BlinkMacSystemFont, sans-serif;
  font-size: 22px;
  text-align: center;
  color: #111;
  background: #fff;
}
.card-ko { font-size: 40px; font-weight: 700; margin-bottom: 12px; }
.card-en { font-size: 24px; margin-bottom: 8px; }
.prompt-context { color: #555; font-size: 18px; margin-bottom: 12px; }
.pronunciation { color: #555; margin-bottom: 12px; }
.example-ko { margin-top: 12px; font-size: 22px; }
.example-en, .notes, .source { color: #666; font-size: 18px; margin-top: 6px; }
img { max-width: 280px; max-height: 280px; margin-top: 12px; }
"""


class _Template(TypedDict):
    Name: str
    Front: str
    Back: str


class _AnkiNote(TypedDict):
    deckName: str
    modelName: str
    fields: dict[str, str]
    tags: list[str]
    options: dict[str, bool]


class AnkiConnectClient:
    def __init__(self, url: str = "http://127.0.0.1:8765") -> None:
        self.url = url

    def invoke(self, action: str, **params: object) -> object:
        payload = {"action": action, "version": 6, "params": params}
        response = requests.post(self.url, json=payload, timeout=30)
        response.raise_for_status()
        body = response.json()
        if body["error"] is not None:
            raise RuntimeError(f"AnkiConnect error for {action}: {body['error']}")
        return body["result"]

    def ensure_deck(self, deck_name: str) -> None:
        self.invoke("createDeck", deck=deck_name)

    def ensure_model(self) -> None:
        model_names = self.invoke("modelNames")
        if ANKI_MODEL_NAME in model_names:
            existing_fields = self.invoke("modelFieldNames", modelName=ANKI_MODEL_NAME)
            if isinstance(existing_fields, list):
                for field_name in ANKI_FIELDS:
                    if field_name not in existing_fields:
                        self.invoke("modelFieldAdd", modelName=ANKI_MODEL_NAME, fieldName=field_name)

            existing_templates = self.invoke("modelTemplates", modelName=ANKI_MODEL_NAME)
            if isinstance(existing_templates, dict):
                for template in ANKI_TEMPLATES:
                    if template["Name"] not in existing_templates:
                        self.invoke(
                            "modelTemplateAdd",
                            modelName=ANKI_MODEL_NAME,
                            template=template,
                        )
            return

        self.invoke(
            "createModel",
            modelName=ANKI_MODEL_NAME,
            inOrderFields=ANKI_FIELDS,
            cardTemplates=ANKI_TEMPLATES,
            css=ANKI_CSS,
        )

    def store_media_file(self, path: str) -> str:
        media_path = Path(path)
        data = base64.b64encode(media_path.read_bytes()).decode("ascii")
        self.invoke("storeMediaFile", filename=media_path.name, data=data)
        return media_path.name

    def sync(self) -> None:
        self.invoke("sync")


def _chunk_hangul(text: str) -> str:
    return " ".join("·".join(segment) for segment in text.split())


def _approved_notes(batch: CardBatch) -> list[GeneratedNote]:
    return [note for note in batch.notes if note.approved and any(card.approved for card in note.cards)]


def _approved_card_count(note: GeneratedNote) -> int:
    return sum(
        1
        for card in note.cards
        if card.approved and (card.kind != "listening" or note.item.audio is not None)
    )


def _join_examples(note: GeneratedNote, field: Literal["korean", "english"]) -> str:
    if field == "korean":
        return "\n".join(example.korean for example in note.item.examples)
    return "\n".join(example.english for example in note.item.examples)


def _note_payload(
    note: GeneratedNote,
    deck_name: str,
    media_names: dict[str, str],
    *,
    allow_duplicate: bool = False,
) -> _AnkiNote:
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
            "ExampleKo": _join_examples(note, "korean"),
            "ExampleEn": _join_examples(note, "english"),
            "Notes": note.item.notes or "",
            "Audio": audio,
            "Image": image,
            "SourceRef": note.item.source_ref or "",
            "ChunkedKorean": _chunk_hangul(note.item.korean),
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


def _target_deck(batch: CardBatch, deck_name: str | None) -> str:
    return deck_name or batch.metadata.target_deck or DEFAULT_DECK


def _existing_model_notes(anki_url: str = "http://127.0.0.1:8765") -> dict[str, list[tuple[str, int]]]:
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


def find_duplicate_notes(
    batch: CardBatch,
    deck_name: str | None = None,
    anki_url: str = "http://127.0.0.1:8765",
) -> list[DuplicateNote]:
    existing_by_korean = _existing_model_notes(anki_url=anki_url)
    duplicates: list[DuplicateNote] = []
    for note in _approved_notes(batch):
        existing_matches = existing_by_korean.get(note.item.korean, [])
        existing_note_id = next(
            (note_id for existing_english, note_id in existing_matches if existing_english == note.item.english),
            None,
        )
        if existing_note_id is not None:
            duplicates.append(
                DuplicateNote(
                    item_id=note.item.id,
                    korean=note.item.korean,
                    english=note.item.english,
                    existing_note_id=existing_note_id,
                )
            )

    return duplicates


def _homograph_item_ids(batch: CardBatch, anki_url: str = "http://127.0.0.1:8765") -> set[str]:
    existing_by_korean = _existing_model_notes(anki_url=anki_url)
    homograph_ids: set[str] = set()
    for note in _approved_notes(batch):
        existing_matches = existing_by_korean.get(note.item.korean, [])
        if not existing_matches:
            continue
        if any(existing_english == note.item.english for existing_english, _note_id in existing_matches):
            continue
        homograph_ids.add(note.item.id)
    return homograph_ids


def plan_push(
    batch: CardBatch,
    deck_name: str | None = None,
    anki_url: str = "http://127.0.0.1:8765",
) -> PushResult:
    resolved_deck = _target_deck(batch, deck_name)
    approved_notes = _approved_notes(batch)
    duplicate_notes = find_duplicate_notes(batch, deck_name=resolved_deck, anki_url=anki_url)
    approved_cards = sum(_approved_card_count(note) for note in approved_notes)

    return PushResult(
        deck_name=resolved_deck,
        approved_notes=len(approved_notes),
        approved_cards=approved_cards,
        duplicate_notes=duplicate_notes,
        dry_run=True,
        can_push=len(approved_notes) > 0 and len(duplicate_notes) == 0,
    )


def push_batch(
    batch: CardBatch,
    deck_name: str | None = None,
    anki_url: str = "http://127.0.0.1:8765",
    sync: bool = True,
) -> PushResult:
    client = AnkiConnectClient(url=anki_url)
    resolved_deck = _target_deck(batch, deck_name)
    plan = plan_push(batch, deck_name=resolved_deck, anki_url=anki_url)
    if plan.duplicate_notes:
        raise RuntimeError(
            "Duplicate notes already exist for this Anki note type: "
            + ", ".join(f"{duplicate.korean} / {duplicate.english}" for duplicate in plan.duplicate_notes)
        )

    client.ensure_deck(resolved_deck)
    client.ensure_model()

    media_names: dict[str, str] = {}
    approved_notes = _approved_notes(batch)
    for note in approved_notes:
        if note.item.audio is not None and note.item.audio.path not in media_names:
            media_names[note.item.audio.path] = client.store_media_file(note.item.audio.path)
        if note.item.image is not None and note.item.image.path not in media_names:
            media_names[note.item.image.path] = client.store_media_file(note.item.image.path)

    homograph_ids = _homograph_item_ids(batch, anki_url=anki_url)
    payloads = [
        _note_payload(
            note,
            resolved_deck,
            media_names,
            allow_duplicate=note.item.id in homograph_ids,
        )
        for note in approved_notes
    ]
    if not payloads:
        return PushResult(
            deck_name=resolved_deck,
            approved_notes=0,
            approved_cards=0,
            dry_run=False,
            can_push=False,
            sync_requested=sync,
            sync_completed=False,
        )

    result = client.invoke("addNotes", notes=payloads)
    if not isinstance(result, list):
        raise RuntimeError("Unexpected AnkiConnect addNotes response.")

    pushed_note_ids = [int(note_id) for note_id in result if isinstance(note_id, int)]
    if sync:
        client.sync()

    notes_added = len(pushed_note_ids)
    cards_created = sum(
        _approved_card_count(note)
        for note, note_id in zip(approved_notes, result, strict=False)
        if isinstance(note_id, int)
    )

    return PushResult(
        deck_name=resolved_deck,
        approved_notes=plan.approved_notes,
        approved_cards=plan.approved_cards,
        duplicate_notes=[],
        dry_run=False,
        can_push=True,
        notes_added=notes_added,
        cards_created=cards_created,
        pushed_note_ids=pushed_note_ids,
        sync_requested=sync,
        sync_completed=sync,
    )
