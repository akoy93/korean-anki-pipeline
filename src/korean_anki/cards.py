from __future__ import annotations

from html import escape
from pathlib import Path

from .new_vocab import inclusion_reason_for_item
from .reading_speed import chunk_hangul
from .schema import CardBatch, CardPreview, GeneratedNote, LessonDocument, LessonItem, PriorNote, StudyState
from .study_state import normalize_text, note_key_for_item


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


def _read_aloud_card(item: LessonItem) -> CardPreview:
    audio_html = ""
    if item.audio is not None:
        audio_name = escape(Path(item.audio.path).name)
        audio_html = f"<div class='reading-audio'><audio controls src='/media/audio/{audio_name}'></audio></div>"

    return CardPreview(
        id=f"{item.id}-read-aloud",
        item_id=item.id,
        kind="read-aloud",
        front_html=(
            "<div class='prompt prompt-context'>Read aloud before revealing anything else.</div>"
            f"<div class='prompt prompt-ko'>{escape(item.korean)}</div>"
        ),
        back_html=(
            f"<div class='answer answer-ko'>{escape(item.korean)}</div>"
            f"<div class='answer answer-en'>{escape(item.english)}</div>"
            f"{_render_back_common(item)}"
            f"{audio_html}"
        ),
        audio_path=item.audio.path if item.audio is not None else None,
        image_path=None,
    )


def _chunked_reading_card(item: LessonItem) -> CardPreview:
    chunked = chunk_hangul(item.korean)
    return CardPreview(
        id=f"{item.id}-chunked-reading",
        item_id=item.id,
        kind="chunked-reading",
        front_html=(
            "<div class='prompt prompt-context'>Sound out the chunks, then blend the full word.</div>"
            f"<div class='prompt prompt-ko'>{escape(chunked)}</div>"
        ),
        back_html=(
            f"<div class='answer answer-ko'>{escape(item.korean)}</div>"
            f"<div class='answer answer-en'>{escape(item.english)}</div>"
            f"{_render_back_common(item)}"
        ),
        audio_path=item.audio.path if item.audio is not None else None,
        image_path=None,
    )


def _decodable_passage_card(item: LessonItem) -> CardPreview:
    audio_html = ""
    if item.audio is not None:
        audio_name = escape(Path(item.audio.path).name)
        audio_html = f"<div class='reading-audio'><audio controls src='/media/audio/{audio_name}'></audio></div>"

    return CardPreview(
        id=f"{item.id}-decodable-passage",
        item_id=item.id,
        kind="decodable-passage",
        front_html=(
            "<div class='prompt prompt-context'>Read this tiny passage smoothly.</div>"
            f"<div class='prompt prompt-ko'>{escape(item.korean)}</div>"
        ),
        back_html=(
            f"<div class='answer answer-en'>{escape(item.english)}</div>"
            f"{_render_back_common(item)}"
            f"{audio_html}"
        ),
        audio_path=item.audio.path if item.audio is not None else None,
        image_path=None,
    )


def _reading_speed_cards(item: LessonItem) -> list[CardPreview]:
    if "passage" in item.skill_tags:
        return [_decodable_passage_card(item)]

    cards = [_read_aloud_card(item)]
    if "chunked" in item.skill_tags:
        cards.append(_chunked_reading_card(item))
    return cards


def _find_exact_duplicate(item: LessonItem, prior_notes: list[PriorNote]) -> PriorNote | None:
    note_key = note_key_for_item(item)
    for prior_note in prior_notes:
        if prior_note.lane == "reading-speed":
            continue
        if prior_note.note_key == note_key:
            return prior_note
    return None


def _find_near_duplicate(item: LessonItem, prior_notes: list[PriorNote]) -> PriorNote | None:
    korean = normalize_text(item.korean)
    english = normalize_text(item.english)
    for prior_note in prior_notes:
        if prior_note.lane == "reading-speed":
            continue
        if prior_note.item_type != item.item_type:
            continue
        if prior_note.note_key == note_key_for_item(item):
            continue
        if normalize_text(prior_note.korean) == korean or normalize_text(prior_note.english) == english:
            return prior_note
    return None


def generate_note(item: LessonItem, prior_notes: list[PriorNote] | None = None) -> GeneratedNote:
    resolved_prior_notes = prior_notes or []
    if item.lane == "reading-speed":
        cards = _reading_speed_cards(item)
        return GeneratedNote(
            item=item,
            cards=cards,
            note_key=note_key_for_item(item),
            lane=item.lane,
            skill_tags=item.skill_tags,
            inclusion_reason=(
                "Weekly decodable passage from known-word bank"
                if "passage" in item.skill_tags
                else "Reading-speed drill from known-word bank"
            ),
        )

    cards = [_recognition_card(item), _production_card(item), _listening_card(item)]

    number_context = _number_context_card(item)
    if number_context is not None:
        cards.append(number_context)

    note_key = note_key_for_item(item)
    exact_duplicate = _find_exact_duplicate(item, resolved_prior_notes)
    if exact_duplicate is not None:
        cards = [card.model_copy(update={"approved": False}) for card in cards]
        return GeneratedNote(
            item=item,
            cards=cards,
            approved=False,
            note_key=note_key,
            lane=item.lane,
            skill_tags=item.skill_tags,
            duplicate_status="exact-duplicate",
            duplicate_note_key=exact_duplicate.note_key,
            duplicate_note_id=exact_duplicate.existing_note_id,
            duplicate_source=exact_duplicate.source,
            inclusion_reason=f"Exact duplicate of prior card from {exact_duplicate.source}",
        )

    near_duplicate = _find_near_duplicate(item, resolved_prior_notes)
    if near_duplicate is not None:
        return GeneratedNote(
            item=item,
            cards=cards,
            note_key=note_key,
            lane=item.lane,
            skill_tags=item.skill_tags,
            duplicate_status="near-duplicate",
            duplicate_note_key=near_duplicate.note_key,
            duplicate_note_id=near_duplicate.existing_note_id,
            duplicate_source=near_duplicate.source,
            inclusion_reason=f"Near-duplicate of prior card from {near_duplicate.source}",
        )

    return GeneratedNote(
        item=item,
        cards=cards,
        note_key=note_key,
        lane=item.lane,
        skill_tags=item.skill_tags,
        inclusion_reason=inclusion_reason_for_item(item) if item.lane == "new-vocab" else "New card",
    )


def refresh_generated_note(note: GeneratedNote, item: LessonItem) -> GeneratedNote:
    regenerated = generate_note(item)
    previous_cards_by_kind = {card.kind: card for card in note.cards}
    updated_cards: list[CardPreview] = []

    for card in regenerated.cards:
        previous_card = previous_cards_by_kind.get(card.kind)
        if previous_card is None:
            updated_cards.append(card)
            continue

        approved = previous_card.approved
        if (
            card.kind == "listening"
            and not previous_card.approved
            and note.item.audio is None
            and "Audio not generated yet." in previous_card.front_html
            and card.audio_path is not None
        ):
            approved = card.approved

        updated_cards.append(card.model_copy(update={"approved": approved}))

    return note.model_copy(update={"item": item, "cards": updated_cards})


def generate_batch(document: LessonDocument, study_state: StudyState | None = None) -> CardBatch:
    prior_notes = []
    if study_state is not None:
        prior_notes = [*study_state.generated_notes, *study_state.imported_notes]

    return CardBatch(
        metadata=document.metadata,
        notes=[generate_note(item, prior_notes=prior_notes) for item in document.items],
    )
