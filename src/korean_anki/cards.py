from __future__ import annotations

from html import escape
from pathlib import Path

from .schema import CardBatch, CardPreview, GeneratedNote, LessonDocument, LessonItem


def _render_examples(item: LessonItem) -> str:
    if not item.examples:
        return ""

    rows = "".join(
        f"<li><div class='example-ko'>{escape(example.korean)}</div>"
        f"<div class='example-en'>{escape(example.english)}</div></li>"
        for example in item.examples
    )
    return f"<section class='examples'><h4>Examples</h4><ul>{rows}</ul></section>"


def _render_back_common(item: LessonItem) -> str:
    pronunciation = (
        f"<div class='pronunciation'>{escape(item.pronunciation)}</div>"
        if item.pronunciation is not None
        else ""
    )
    notes = f"<div class='notes'>{escape(item.notes)}</div>" if item.notes is not None else ""
    source_ref = (
        f"<div class='source-ref'>Source: {escape(item.source_ref)}</div>"
        if item.source_ref is not None
        else ""
    )
    image = ""
    if item.image is not None:
        image_name = escape(Path(item.image.path).name)
        image = f"<div class='image-wrap'><img src='/media/images/{image_name}' alt='{escape(item.english)}' /></div>"

    return "".join([pronunciation, _render_examples(item), notes, source_ref, image])


def _recognition_card(item: LessonItem) -> CardPreview:
    return CardPreview(
        id=f"{item.id}-recognition",
        item_id=item.id,
        kind="recognition",
        front_html=f"<div class='prompt prompt-ko'>{escape(item.korean)}</div>",
        back_html=(
            f"<div class='answer answer-en'>{escape(item.english)}</div>"
            f"<div class='answer answer-ko'>{escape(item.korean)}</div>"
            f"{_render_back_common(item)}"
        ),
        audio_path=item.audio.path if item.audio is not None else None,
        image_path=item.image.path if item.image is not None else None,
    )


def _production_card(item: LessonItem) -> CardPreview:
    return CardPreview(
        id=f"{item.id}-production",
        item_id=item.id,
        kind="production",
        front_html=f"<div class='prompt prompt-en'>{escape(item.english)}</div>",
        back_html=(
            f"<div class='answer answer-ko'>{escape(item.korean)}</div>"
            f"<div class='answer answer-en'>{escape(item.english)}</div>"
            f"{_render_back_common(item)}"
        ),
        audio_path=item.audio.path if item.audio is not None else None,
        image_path=item.image.path if item.image is not None else None,
    )


def _listening_card(item: LessonItem) -> CardPreview:
    if item.audio is None:
        return CardPreview(
            id=f"{item.id}-listening",
            item_id=item.id,
            kind="listening",
            front_html=(
                "<div class='prompt prompt-listening'>Audio not generated yet.</div>"
                "<div class='prompt prompt-hint'>Run generate with --with-audio to enable this card.</div>"
            ),
            back_html=(
                f"<div class='answer answer-ko'>{escape(item.korean)}</div>"
                f"<div class='answer answer-en'>{escape(item.english)}</div>"
                f"{_render_back_common(item)}"
            ),
            audio_path=None,
            image_path=item.image.path if item.image is not None else None,
            approved=False,
        )

    audio_name = escape(Path(item.audio.path).name)
    return CardPreview(
        id=f"{item.id}-listening",
        item_id=item.id,
        kind="listening",
        front_html=(
            "<div class='prompt prompt-listening'>Listen and recall the meaning.</div>"
            f"<audio controls src='/media/audio/{audio_name}'></audio>"
        ),
        back_html=(
            f"<div class='answer answer-ko'>{escape(item.korean)}</div>"
            f"<div class='answer answer-en'>{escape(item.english)}</div>"
            f"{_render_back_common(item)}"
        ),
        audio_path=item.audio.path,
        image_path=item.image.path if item.image is not None else None,
    )


def _number_context_card(item: LessonItem) -> CardPreview | None:
    if item.item_type != "number":
        return None
    if item.notes is None:
        return None

    return CardPreview(
        id=f"{item.id}-number-context",
        item_id=item.id,
        kind="number-context",
        front_html=(
            "<div class='prompt prompt-context'>In what context is this number form used?</div>"
            f"<div class='prompt prompt-ko'>{escape(item.korean)}</div>"
        ),
        back_html=(
            f"<div class='answer answer-en'>{escape(item.english)}</div>"
            f"<div class='notes'>{escape(item.notes)}</div>"
            f"{_render_examples(item)}"
        ),
        audio_path=item.audio.path if item.audio is not None else None,
        image_path=item.image.path if item.image is not None else None,
    )


def generate_note(item: LessonItem) -> GeneratedNote:
    cards = [_recognition_card(item), _production_card(item), _listening_card(item)]

    number_context = _number_context_card(item)
    if number_context is not None:
        cards.append(number_context)

    return GeneratedNote(item=item, cards=cards)


def generate_batch(document: LessonDocument) -> CardBatch:
    return CardBatch(
        metadata=document.metadata,
        notes=[generate_note(item) for item in document.items],
    )
