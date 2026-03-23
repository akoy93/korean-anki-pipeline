from __future__ import annotations

import base64
from pathlib import Path
from typing import Literal, TypedDict

import requests

from .schema import CardBatch, GeneratedNote

ANKI_MODEL_NAME = "Korean Lesson Item"
DEFAULT_DECK = "Korean::Lessons"


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
            return

        fields = [
            "Korean",
            "English",
            "Pronunciation",
            "ExampleKo",
            "ExampleEn",
            "Notes",
            "Audio",
            "Image",
            "SourceRef",
            "EnableRecognition",
            "EnableProduction",
            "EnableListening",
            "EnableNumberContext",
        ]
        templates: list[_Template] = [
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
        ]
        css = """
.card {
  font-family: -apple-system, BlinkMacSystemFont, sans-serif;
  font-size: 22px;
  text-align: center;
  color: #111;
  background: #fff;
}
.card-ko { font-size: 40px; font-weight: 700; margin-bottom: 12px; }
.card-en { font-size: 24px; margin-bottom: 8px; }
.pronunciation { color: #555; margin-bottom: 12px; }
.example-ko { margin-top: 12px; font-size: 22px; }
.example-en, .notes, .source { color: #666; font-size: 18px; margin-top: 6px; }
img { max-width: 280px; max-height: 280px; margin-top: 12px; }
"""
        self.invoke(
            "createModel",
            modelName=ANKI_MODEL_NAME,
            inOrderFields=fields,
            cardTemplates=templates,
            css=css,
        )

    def store_media_file(self, path: str) -> str:
        media_path = Path(path)
        data = base64.b64encode(media_path.read_bytes()).decode("ascii")
        self.invoke("storeMediaFile", filename=media_path.name, data=data)
        return media_path.name

    def sync(self) -> None:
        self.invoke("sync")


def _join_examples(note: GeneratedNote, field: Literal["korean", "english"]) -> str:
    if field == "korean":
        return "\n".join(example.korean for example in note.item.examples)
    return "\n".join(example.english for example in note.item.examples)


def _note_payload(note: GeneratedNote, deck_name: str, media_names: dict[str, str]) -> _AnkiNote:
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
            f"type:{note.item.item_type}",
            *note.item.tags,
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
            "EnableRecognition": "1" if "recognition" in approved_kinds else "",
            "EnableProduction": "1" if "production" in approved_kinds else "",
            "EnableListening": "1" if "listening" in approved_kinds and note.item.audio is not None else "",
            "EnableNumberContext": "1" if "number-context" in approved_kinds else "",
        },
        "tags": tags,
        "options": {"allowDuplicate": False},
    }


def push_batch(
    batch: CardBatch,
    deck_name: str = DEFAULT_DECK,
    anki_url: str = "http://127.0.0.1:8765",
    sync: bool = True,
) -> list[int | None]:
    client = AnkiConnectClient(url=anki_url)
    client.ensure_deck(deck_name)
    client.ensure_model()

    media_names: dict[str, str] = {}
    approved_notes = [note for note in batch.notes if note.approved and any(card.approved for card in note.cards)]
    for note in approved_notes:
        if note.item.audio is not None and note.item.audio.path not in media_names:
            media_names[note.item.audio.path] = client.store_media_file(note.item.audio.path)
        if note.item.image is not None and note.item.image.path not in media_names:
            media_names[note.item.image.path] = client.store_media_file(note.item.image.path)

    payloads = [_note_payload(note, deck_name, media_names) for note in approved_notes]
    if not payloads:
        return []

    result = client.invoke("addNotes", notes=payloads)
    if sync:
        client.sync()
    return [int(note_id) if note_id is not None else None for note_id in result]
