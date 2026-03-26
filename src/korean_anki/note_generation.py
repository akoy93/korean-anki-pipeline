from __future__ import annotations

from collections.abc import Callable

from .card_rendering import build_reading_speed_cards, build_standard_cards
from .new_vocab_documents import inclusion_reason_for_item
from .note_keys import normalize_text, note_key_for_item
from .schema import CardBatch, CardPreview, GeneratedNote, LessonDocument, LessonItem, PriorNote, StudyState


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
        cards = build_reading_speed_cards(item)
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

    cards = build_standard_cards(item)
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


def refresh_preview_note(note: GeneratedNote, item: LessonItem) -> GeneratedNote:
    if note.duplicate_status == "exact-duplicate":
        regenerated = generate_note(item)
        note_approved = True
    else:
        regenerated = refresh_generated_note(note, item)
        note_approved = note.approved

    cards = [
        card.model_copy(
            update={
                "approved": note_approved and (card.kind != "listening" or item.audio is not None),
            }
        )
        for card in regenerated.cards
    ]

    return regenerated.model_copy(
        update={
            "approved": note_approved,
            "cards": cards,
            "duplicate_status": "new",
            "duplicate_note_key": None,
            "duplicate_note_id": None,
            "duplicate_source": None,
            "inclusion_reason": "Edited in preview",
        }
    )


def generate_batch(
    document: LessonDocument,
    study_state: StudyState | None = None,
    on_note_generated: Callable[[GeneratedNote], None] | None = None,
) -> CardBatch:
    prior_notes = []
    if study_state is not None:
        prior_notes = [*study_state.generated_notes, *study_state.imported_notes]

    notes: list[GeneratedNote] = []
    for item in document.items:
        note = generate_note(item, prior_notes=prior_notes)
        notes.append(note)
        if on_note_generated is not None:
            on_note_generated(note)

    return CardBatch(
        metadata=document.metadata,
        notes=notes,
    )
