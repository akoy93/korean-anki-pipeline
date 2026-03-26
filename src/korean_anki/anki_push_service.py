from __future__ import annotations

from .anki_client import AnkiConnectClient
from .anki_note_codec import approved_card_count, approved_notes, build_note_payload, target_deck
from .anki_queries import existing_model_notes
from .schema import CardBatch, DuplicateNote, PushResult
from .settings import DEFAULT_ANKI_URL


def find_duplicate_notes(
    batch: CardBatch,
    deck_name: str | None = None,
    anki_url: str = DEFAULT_ANKI_URL,
) -> list[DuplicateNote]:
    del deck_name
    existing_by_korean = existing_model_notes(anki_url=anki_url)
    duplicates: list[DuplicateNote] = []
    for note in approved_notes(batch):
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


def _homograph_item_ids(batch: CardBatch, anki_url: str = DEFAULT_ANKI_URL) -> set[str]:
    existing_by_korean = existing_model_notes(anki_url=anki_url)
    homograph_ids: set[str] = set()
    for note in approved_notes(batch):
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
    anki_url: str = DEFAULT_ANKI_URL,
) -> PushResult:
    resolved_deck = target_deck(batch, deck_name)
    approved = approved_notes(batch)
    duplicate_notes = find_duplicate_notes(batch, deck_name=resolved_deck, anki_url=anki_url)
    approved_cards = sum(approved_card_count(note) for note in approved)

    return PushResult(
        deck_name=resolved_deck,
        approved_notes=len(approved),
        approved_cards=approved_cards,
        duplicate_notes=duplicate_notes,
        dry_run=True,
        can_push=len(approved) > 0 and len(duplicate_notes) == 0,
    )


def push_batch(
    batch: CardBatch,
    deck_name: str | None = None,
    anki_url: str = DEFAULT_ANKI_URL,
    sync: bool = True,
) -> PushResult:
    client = AnkiConnectClient(url=anki_url)
    resolved_deck = target_deck(batch, deck_name)
    plan = plan_push(batch, deck_name=resolved_deck, anki_url=anki_url)
    if plan.duplicate_notes:
        raise RuntimeError(
            "Duplicate notes already exist for this Anki note type: "
            + ", ".join(f"{duplicate.korean} / {duplicate.english}" for duplicate in plan.duplicate_notes)
        )

    client.ensure_deck(resolved_deck)
    client.ensure_model()

    media_names: dict[str, str] = {}
    approved = approved_notes(batch)
    for note in approved:
        if note.item.audio is not None and note.item.audio.path not in media_names:
            media_names[note.item.audio.path] = client.store_media_file(note.item.audio.path)
        if note.item.image is not None and note.item.image.path not in media_names:
            media_names[note.item.image.path] = client.store_media_file(note.item.image.path)

    homograph_ids = _homograph_item_ids(batch, anki_url=anki_url)
    payloads = [
        build_note_payload(
            note,
            resolved_deck,
            media_names,
            allow_duplicate=note.item.id in homograph_ids,
        )
        for note in approved
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

    cards_created = sum(
        approved_card_count(note)
        for note, note_id in zip(approved, result, strict=False)
        if isinstance(note_id, int)
    )

    return PushResult(
        deck_name=resolved_deck,
        approved_notes=plan.approved_notes,
        approved_cards=plan.approved_cards,
        duplicate_notes=[],
        dry_run=False,
        can_push=True,
        notes_added=len(pushed_note_ids),
        cards_created=cards_created,
        pushed_note_ids=pushed_note_ids,
        sync_requested=sync,
        sync_completed=sync,
    )
