from __future__ import annotations

import base64
import re
from pathlib import Path

from openai import OpenAI

from .schema import LessonDocument, MediaAsset


_SLUG_RE = re.compile(r"[^a-zA-Z0-9가-힣]+")


def _slug(value: str) -> str:
    slug = _SLUG_RE.sub("-", value).strip("-").lower()
    return slug or "item"


def enrich_audio(document: LessonDocument, output_dir: Path, voice: str = "coral") -> LessonDocument:
    client = OpenAI()
    output_dir.mkdir(parents=True, exist_ok=True)
    updated_items = []

    for item in document.items:
        if item.audio is not None:
            updated_items.append(item)
            continue

        audio_path = output_dir / f"{_slug(item.id)}.mp3"
        speech = client.audio.speech.create(
            model="gpt-4o-mini-tts",
            voice=voice,
            input=item.korean,
            instructions="Speak naturally in Korean at a clear study pace.",
        )
        audio_path.write_bytes(speech.content)
        updated_items.append(item.model_copy(update={"audio": MediaAsset(path=str(audio_path))}))

    return document.model_copy(update={"items": updated_items})


def enrich_images(document: LessonDocument, output_dir: Path) -> LessonDocument:
    client = OpenAI()
    output_dir.mkdir(parents=True, exist_ok=True)
    updated_items = []

    for item in document.items:
        if item.image is not None:
            updated_items.append(item)
            continue

        prompt = (
            f"Simple educational illustration for a Korean flashcard. "
            f"Concept: {item.english}. No text in the image. Clean, concrete, memorable."
        )
        result = client.images.generate(
            model="gpt-image-1.5",
            prompt=prompt,
            size="1024x1024",
        )
        b64_json = result.data[0].b64_json
        if b64_json is None:
            raise RuntimeError(f"Image generation returned no data for item {item.id}")

        image_path = output_dir / f"{_slug(item.id)}.png"
        image_path.write_bytes(base64.b64decode(b64_json))
        updated_items.append(
            item.model_copy(update={"image": MediaAsset(path=str(image_path), prompt=prompt)})
        )

    return document.model_copy(update={"items": updated_items})
