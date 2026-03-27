from __future__ import annotations

from datetime import date
from pathlib import Path

from .llm_service import generate_pronunciations, propose_new_vocab
from .note_keys import normalize_text
from .schema import (
    ExampleSentence,
    LessonDocument,
    LessonItem,
    LessonMetadata,
    NewVocabProposal,
    PriorNote,
    StudyState,
)
from .settings import (
    DEFAULT_LLM_MODEL,
    DEFAULT_NEW_VOCAB_COUNT,
    DEFAULT_NEW_VOCAB_GAP_RATIO,
    DEFAULT_NEW_VOCAB_TARGET_DECK,
    DEFAULT_NEW_VOCAB_TITLE,
    DEFAULT_NEW_VOCAB_TOPIC,
)
from .new_vocab_selection import (
    LessonContext,
    choose_new_vocab_theme,
    load_lesson_context,
    new_vocab_batch_title,
    prior_notes_for_vocab,
    select_new_vocab_proposals,
)


def _make_item(
    *,
    proposal: NewVocabProposal,
    lesson_id: str,
    index: int,
    lesson_context: LessonContext | None,
) -> LessonItem:
    context_label = lesson_context.topic if lesson_context is not None else proposal.topic_tag
    inclusion_notes = (
        f"Coverage gap: {proposal.topic_tag}"
        if proposal.adjacency_kind == "coverage-gap"
        else f"Lesson-adjacent: {context_label}/{proposal.topic_tag}"
    )
    return LessonItem(
        id=f"{lesson_id}-{index:03d}",
        lesson_id=lesson_id,
        item_type="vocab",
        korean=proposal.korean,
        english=proposal.english,
        pronunciation=None,
        examples=[ExampleSentence(korean=proposal.example_ko, english=proposal.example_en)],
        notes=f"{inclusion_notes}. {proposal.proposal_reason}".strip(),
        tags=["new-vocab", proposal.topic_tag, proposal.adjacency_kind],
        lane="new-vocab",
        skill_tags=[proposal.topic_tag],
        source_ref=(
            f"New vocab proposal • {proposal.adjacency_kind} • {proposal.topic_tag}"
            if lesson_context is None or proposal.adjacency_kind == "coverage-gap"
            else f"New vocab proposal • lesson-adjacent to {lesson_context.title} • {proposal.topic_tag}"
        ),
        image_prompt=proposal.image_prompt,
        audio=None,
        image=None,
    )


def build_new_vocab_document(
    proposals: list[NewVocabProposal],
    study_state: StudyState,
    *,
    lesson_id: str,
    title: str,
    lesson_date: date,
    count: int = DEFAULT_NEW_VOCAB_COUNT,
    gap_ratio: float = DEFAULT_NEW_VOCAB_GAP_RATIO,
    lesson_context: LessonContext | None = None,
    target_deck: str = DEFAULT_NEW_VOCAB_TARGET_DECK,
) -> LessonDocument:
    selected = select_new_vocab_proposals(
        proposals,
        study_state,
        count=count,
        gap_ratio=gap_ratio,
        lesson_context=lesson_context,
    )
    if not selected:
        raise ValueError("No new-vocab proposals survived local dedupe and selection.")

    items = [
        _make_item(
            proposal=proposal,
            lesson_id=lesson_id,
            index=index,
            lesson_context=lesson_context,
        )
        for index, (proposal, _near_duplicate) in enumerate(selected, start=1)
    ]

    metadata = LessonMetadata(
        lesson_id=lesson_id,
        title=title,
        topic=DEFAULT_NEW_VOCAB_TOPIC,
        lesson_date=lesson_date,
        source_description=(
            "Supplemental A1 vocab selected from coverage gaps"
            if lesson_context is None
            else f"Supplemental A1 vocab selected from coverage gaps and lesson-adjacent context: {lesson_context.summary}"
        ),
        target_deck=target_deck,
        tags=["new-vocab"],
    )
    return LessonDocument(metadata=metadata, items=items)


def build_new_vocab_document_from_state(
    state: StudyState,
    *,
    lesson_id: str,
    title: str,
    lesson_date: date,
    count: int,
    gap_ratio: float,
    lesson_context_path: Path | None,
    target_deck: str,
    model: str = DEFAULT_LLM_MODEL,
) -> LessonDocument:
    lesson_context = load_lesson_context(lesson_context_path) if lesson_context_path is not None else None
    theme_topic = choose_new_vocab_theme(state, lesson_context)
    prior_vocab = prior_notes_for_vocab(state)
    excluded_pairs = [
        f"{normalize_text(note.korean)} | {normalize_text(note.english)}"
        for note in prior_vocab
    ]
    proposal_batch = propose_new_vocab(
        model=model,
        candidate_count=max((count * 2) + 10, count + 15),
        batch_theme=new_vocab_batch_title(theme_topic),
        target_gap_topics=[theme_topic],
        lesson_context_summary=lesson_context.summary if lesson_context is not None else None,
        lesson_context_tags=lesson_context.tags if lesson_context is not None else [],
        excluded_pairs=excluded_pairs,
    )
    document = build_new_vocab_document(
        proposal_batch.proposals,
        state,
        lesson_id=lesson_id,
        title=new_vocab_batch_title(theme_topic) if title == DEFAULT_NEW_VOCAB_TITLE else title,
        lesson_date=lesson_date,
        count=count,
        gap_ratio=gap_ratio,
        lesson_context=lesson_context,
        target_deck=target_deck,
    )
    pronunciation_lookup = generate_pronunciations(
        [item.korean for item in document.items],
        model=model,
    )
    return document.model_copy(
        update={
            "items": [
                item.model_copy(update={"pronunciation": pronunciation_lookup.get(item.korean)})
                for item in document.items
            ]
        }
    )


def inclusion_reason_for_item(item: LessonItem) -> str:
    if "coverage-gap" in item.tags:
        return f"Coverage gap: {item.skill_tags[0]}" if item.skill_tags else "Coverage gap"
    if "lesson-adjacent" in item.tags:
        return f"Lesson-adjacent: {item.skill_tags[0]}" if item.skill_tags else "Lesson-adjacent"
    return "New card"
