from __future__ import annotations

import base64
from pathlib import Path
from typing import TypedDict

import requests

from .settings import DEFAULT_ANKI_URL, DEFAULT_LESSON_DECK

ANKI_MODEL_NAME = "Korean Lesson Item"
DEFAULT_DECK = DEFAULT_LESSON_DECK

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


class Template(TypedDict):
    Name: str
    Front: str
    Back: str


ANKI_TEMPLATES: list[Template] = [
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


class AnkiConnectClient:
    def __init__(self, url: str = DEFAULT_ANKI_URL) -> None:
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

    def retrieve_media_file(self, filename: str) -> bytes | None:
        result = self.invoke("retrieveMediaFile", filename=filename)
        if not isinstance(result, str) or result == "":
            return None
        return base64.b64decode(result)

    def sync(self) -> None:
        self.invoke("sync")
