from __future__ import annotations

import base64
import math
import re
import shutil
import subprocess
import tempfile
import wave
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Literal
from array import array

from openai import OpenAI

from .llm import plan_image_generation
from .schema import LessonDocument, LessonItem, MediaAsset

ImageQuality = Literal["auto", "low", "medium", "high"]

_SLUG_RE = re.compile(r"[^a-zA-Z0-9가-힣]+")
_IMAGE_NEVER_ITEM_TYPES = frozenset({"grammar", "number"})
_IMAGE_CANDIDATE_ITEM_TYPES = frozenset({"vocab", "phrase", "dialogue"})
_AUDIO_MAX_WORKERS = 8
_AUDIO_MAX_ATTEMPTS = 3
_AUDIO_MIN_PEAK = 10
_AUDIO_MIN_RMS = 5.0
_IMAGE_MAX_WORKERS = 4
_NEW_VOCAB_IMAGE_STYLE = (
    "Stylish, contemporary editorial illustration for an adult language learner in their 30s. "
    "Keep it warm, playful, and visually engaging without looking childish. "
    "Use clean composition, rich color, and a polished modern textbook feel. "
    "If the scene includes people, depict Korean people in a natural contemporary Korean setting. "
    "No text in the image."
)


def _slug(value: str) -> str:
    slug = _SLUG_RE.sub("-", value).strip("-").lower()
    return slug or "item"


def _parallel_update_items(
    items: Sequence[LessonItem],
    update_item: Callable[[LessonItem], LessonItem],
    *,
    max_workers: int,
) -> list[LessonItem]:
    if len(items) <= 1 or max_workers <= 1:
        return [update_item(item) for item in items]

    worker_count = min(max_workers, len(items))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        return list(executor.map(update_item, items))


def _decoded_audio_stats(audio_path: Path) -> tuple[float, float, int] | None:
    afconvert = shutil.which("afconvert")
    if afconvert is None:
        return None

    with tempfile.TemporaryDirectory() as temp_dir:
        wav_path = Path(temp_dir) / "audio.wav"
        result = subprocess.run(
            [
                afconvert,
                "-f",
                "WAVE",
                "-d",
                "LEI16@24000",
                str(audio_path),
                str(wav_path),
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode != 0 or not wav_path.exists():
            return None

        with wave.open(str(wav_path), "rb") as wav_file:
            frames = wav_file.readframes(wav_file.getnframes())
            samples = array("h")
            samples.frombytes(frames)
            if not samples:
                return (0.0, 0.0, 0)

            peak = max(abs(sample) for sample in samples)
            rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples))
            duration = wav_file.getnframes() / wav_file.getframerate()
            return (duration, rms, peak)


def _audio_asset_is_valid(audio_path: Path) -> bool:
    if not audio_path.exists() or audio_path.stat().st_size == 0:
        return False

    stats = _decoded_audio_stats(audio_path)
    if stats is None:
        return True

    _, rms, peak = stats
    return peak >= _AUDIO_MIN_PEAK and rms >= _AUDIO_MIN_RMS


def enrich_audio(
    document: LessonDocument,
    output_dir: Path,
    voice: str = "coral",
    max_workers: int = _AUDIO_MAX_WORKERS,
) -> LessonDocument:
    output_dir.mkdir(parents=True, exist_ok=True)

    def update_item(item: LessonItem) -> LessonItem:
        if item.audio is not None and _audio_asset_is_valid(Path(item.audio.path)):
            return item

        audio_path = Path(item.audio.path) if item.audio is not None else output_dir / f"{_slug(item.id)}.mp3"
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        client = OpenAI()
        for _ in range(_AUDIO_MAX_ATTEMPTS):
            speech = client.audio.speech.create(
                model="gpt-4o-mini-tts",
                voice=voice,
                input=item.korean,
                instructions="Speak naturally in Korean at a clear study pace.",
            )
            audio_path.write_bytes(speech.content)
            if _audio_asset_is_valid(audio_path):
                return item.model_copy(update={"audio": MediaAsset(path=str(audio_path))})

        raise RuntimeError(f"Audio generation produced invalid audio for item {item.id}")

    updated_items = _parallel_update_items(document.items, update_item, max_workers=max_workers)
    return document.model_copy(update={"items": updated_items})


def enrich_images(
    document: LessonDocument,
    output_dir: Path,
    decision_model: str = "gpt-5.4",
    image_quality: ImageQuality = "auto",
    max_workers: int = _IMAGE_MAX_WORKERS,
) -> LessonDocument:
    output_dir.mkdir(parents=True, exist_ok=True)
    image_decisions = plan_image_generation(document, model=decision_model)

    def update_item(item: LessonItem) -> LessonItem:
        if item.image is not None:
            return item
        if item.item_type in _IMAGE_NEVER_ITEM_TYPES:
            return item
        if item.item_type not in _IMAGE_CANDIDATE_ITEM_TYPES:
            raise RuntimeError(f"Unhandled item_type for image policy: {item.item_type}")
        if not image_decisions[item.id]:
            return item

        prompt = (
            f"Simple educational illustration for a Korean flashcard. "
            f"Concept: {item.english}. No text in the image. Clean, concrete, memorable."
        )
        client = OpenAI()
        result = client.images.generate(
            model="gpt-image-1.5",
            prompt=prompt,
            quality=image_quality,
            size="1024x1024",
        )
        b64_json = result.data[0].b64_json
        if b64_json is None:
            raise RuntimeError(f"Image generation returned no data for item {item.id}")

        image_path = output_dir / f"{_slug(item.id)}.png"
        image_path.write_bytes(base64.b64decode(b64_json))
        return item.model_copy(update={"image": MediaAsset(path=str(image_path), prompt=prompt)})

    updated_items = _parallel_update_items(document.items, update_item, max_workers=max_workers)
    return document.model_copy(update={"items": updated_items})


def enrich_new_vocab_images(
    document: LessonDocument,
    output_dir: Path,
    image_quality: ImageQuality = "low",
    max_workers: int = _IMAGE_MAX_WORKERS,
) -> LessonDocument:
    output_dir.mkdir(parents=True, exist_ok=True)

    def update_item(item: LessonItem) -> LessonItem:
        if item.image is not None:
            return item

        base_prompt = item.image_prompt or f"Concept: {item.english}."
        prompt = f"{base_prompt} {_NEW_VOCAB_IMAGE_STYLE}"
        client = OpenAI()
        result = client.images.generate(
            model="gpt-image-1.5",
            prompt=prompt,
            quality=image_quality,
            size="1024x1024",
        )
        b64_json = result.data[0].b64_json
        if b64_json is None:
            raise RuntimeError(f"Image generation returned no data for item {item.id}")

        image_path = output_dir / f"{_slug(item.id)}.png"
        image_path.write_bytes(base64.b64decode(b64_json))
        return item.model_copy(update={"image": MediaAsset(path=str(image_path), prompt=prompt)})

    updated_items = _parallel_update_items(document.items, update_item, max_workers=max_workers)
    return document.model_copy(update={"items": updated_items})
