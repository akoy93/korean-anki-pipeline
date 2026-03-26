from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .llm_service import generate_pronunciations, propose_new_vocab
from .schema import (
    ExampleSentence,
    LessonDocument,
    LessonItem,
    LessonMetadata,
    LessonTranscription,
    NewVocabProposal,
    PriorNote,
    StudyState,
    VocabAdjacencyKind,
)
from .settings import (
    DEFAULT_LLM_MODEL,
    DEFAULT_NEW_VOCAB_COUNT,
    DEFAULT_NEW_VOCAB_GAP_RATIO,
    DEFAULT_NEW_VOCAB_TARGET_DECK,
    DEFAULT_NEW_VOCAB_TITLE,
    DEFAULT_NEW_VOCAB_TOPIC,
)
from .study_state import normalize_text

A1_TOPIC_INVENTORY = [
    "greetings",
    "family",
    "food",
    "numbers",
    "time",
    "places",
    "daily-routines",
    "weather",
]

A1_TOPIC_TITLES = {
    "greetings": "Greetings",
    "family": "Family",
    "food": "Food",
    "numbers": "Numbers",
    "time": "Time",
    "places": "Places",
    "daily-routines": "Daily Routines",
    "weather": "Weather",
}


@dataclass(frozen=True)
class LessonContext:
    title: str
    topic: str
    summary: str
    tags: list[str]


def load_lesson_context(path: Path) -> LessonContext:
    raw_text = path.read_text(encoding="utf-8")

    try:
        transcription = LessonTranscription.model_validate_json(raw_text)
        return LessonContext(
            title=transcription.title,
            topic=transcription.theme,
            summary=" ".join(
                [
                    transcription.source_summary,
                    f"Goals: {'; '.join(transcription.goals)}" if transcription.goals else "",
                ]
            ).strip(),
            tags=sorted(
                {
                    tag
                    for section in transcription.sections
                    for tag in section.tags
                    if tag in A1_TOPIC_INVENTORY
                }
            ),
        )
    except Exception:  # noqa: BLE001
        data = json.loads(raw_text)

    metadata = data["metadata"]
    if not isinstance(metadata, dict):
        raise ValueError(f"Unsupported lesson context file: {path}")

    tags_value = metadata["tags"]
    if not isinstance(tags_value, list):
        raise ValueError(f"Unsupported lesson context tags in: {path}")
    tags = [tag for tag in tags_value if isinstance(tag, str) and tag in A1_TOPIC_INVENTORY]

    title = metadata["title"]
    topic = metadata["topic"]
    source_description = metadata["source_description"]
    if not isinstance(title, str) or not isinstance(topic, str) or not isinstance(source_description, str):
        raise ValueError(f"Unsupported lesson context metadata in: {path}")

    return LessonContext(
        title=title,
        topic=topic,
        summary=source_description,
        tags=sorted(set(tags)),
    )


def undercovered_topics(study_state: StudyState, limit: int = 4) -> list[str]:
    topic_counts = Counter(
        tag.removeprefix("skill:")
        for tag, count in study_state.anki_stats.by_tag.items()
        if tag.startswith("skill:")
        for _ in range(count)
    )
    topic_counts.update(
        skill_tag
        for note in [*study_state.generated_notes, *study_state.imported_notes]
        for skill_tag in note.skill_tags
    )

    return sorted(
        A1_TOPIC_INVENTORY,
        key=lambda topic: (topic_counts[topic], A1_TOPIC_INVENTORY.index(topic)),
    )[:limit]


def choose_new_vocab_theme(study_state: StudyState, lesson_context: LessonContext | None = None) -> str:
    undercovered = undercovered_topics(study_state, limit=len(A1_TOPIC_INVENTORY))
    if lesson_context is not None:
        for topic in undercovered:
            if topic in lesson_context.tags:
                return topic
    return undercovered[0]


def new_vocab_batch_title(topic_tag: str) -> str:
    return f"{A1_TOPIC_TITLES[topic_tag]} Basics"


def prior_notes_for_vocab(study_state: StudyState) -> list[PriorNote]:
    return [note for note in [*study_state.generated_notes, *study_state.imported_notes] if note.item_type == "vocab"]


def proposal_note_key(proposal: NewVocabProposal) -> str:
    return f"vocab:{normalize_text(proposal.korean)}:{normalize_text(proposal.english)}"


def find_exact_duplicate(proposal: NewVocabProposal, prior_notes: list[PriorNote]) -> PriorNote | None:
    note_key = proposal_note_key(proposal)
    for prior_note in prior_notes:
        if prior_note.note_key == note_key:
            return prior_note
    return None


def find_near_duplicate(proposal: NewVocabProposal, prior_notes: list[PriorNote]) -> PriorNote | None:
    korean = normalize_text(proposal.korean)
    english = normalize_text(proposal.english)
    for prior_note in prior_notes:
        if prior_note.note_key == proposal_note_key(proposal):
            continue
        if normalize_text(prior_note.korean) == korean or normalize_text(prior_note.english) == english:
            return prior_note
    return None


def _score_proposal(
    proposal: NewVocabProposal,
    *,
    target_topics: list[str],
    near_duplicate: bool,
) -> tuple[int, int, int, str]:
    topic_rank = target_topics.index(proposal.topic_tag) if proposal.topic_tag in target_topics else len(target_topics)
    adjacency_rank = 0 if proposal.adjacency_kind == "coverage-gap" else 1
    near_penalty = 1 if near_duplicate else 0
    return (near_penalty, adjacency_rank, topic_rank, normalize_text(proposal.korean))


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


def _set_inclusion_reason(item: LessonItem, proposal: NewVocabProposal, lesson_context: LessonContext | None) -> str:
    if proposal.adjacency_kind == "coverage-gap":
        return f"Coverage gap: {proposal.topic_tag}"
    context_label = lesson_context.topic if lesson_context is not None else proposal.topic_tag
    return f"Lesson-adjacent: {context_label}/{proposal.topic_tag}"


def select_new_vocab_proposals(
    proposals: list[NewVocabProposal],
    study_state: StudyState,
    *,
    count: int = 20,
    gap_ratio: float = 0.6,
    lesson_context: LessonContext | None = None,
) -> list[tuple[NewVocabProposal, PriorNote | None]]:
    prior_notes = prior_notes_for_vocab(study_state)
    target_gap_count = round(count * gap_ratio)
    target_adjacent_count = count - target_gap_count
    if lesson_context is None:
        target_gap_count = count
        target_adjacent_count = 0

    target_topics = undercovered_topics(study_state, limit=len(A1_TOPIC_INVENTORY))

    clean_by_kind: dict[VocabAdjacencyKind, list[tuple[NewVocabProposal, PriorNote | None]]] = {
        "coverage-gap": [],
        "lesson-adjacent": [],
    }
    near_by_kind: dict[VocabAdjacencyKind, list[tuple[NewVocabProposal, PriorNote | None]]] = {
        "coverage-gap": [],
        "lesson-adjacent": [],
    }
    seen_keys: set[str] = set()

    for proposal in proposals:
        note_key = proposal_note_key(proposal)
        if note_key in seen_keys:
            continue
        seen_keys.add(note_key)

        if find_exact_duplicate(proposal, prior_notes) is not None:
            continue

        near_duplicate = find_near_duplicate(proposal, prior_notes)
        entry = (proposal, near_duplicate)
        if near_duplicate is None:
            clean_by_kind[proposal.adjacency_kind].append(entry)
        else:
            near_by_kind[proposal.adjacency_kind].append(entry)

    for bucket in [clean_by_kind, near_by_kind]:
        for adjacency_kind, entries in bucket.items():
            entries.sort(
                key=lambda entry: _score_proposal(
                    entry[0],
                    target_topics=target_topics,
                    near_duplicate=entry[1] is not None,
                )
            )

    selected: list[tuple[NewVocabProposal, PriorNote | None]] = []
    selected_keys: set[str] = set()

    def take_from(
        entries: list[tuple[NewVocabProposal, PriorNote | None]],
        needed: int,
    ) -> None:
        for proposal, near_duplicate in entries:
            if len(selected) >= count or needed <= 0:
                return
            note_key = proposal_note_key(proposal)
            if note_key in selected_keys:
                continue
            selected.append((proposal, near_duplicate))
            selected_keys.add(note_key)
            needed -= 1

    if lesson_context is None:
        take_from(clean_by_kind["coverage-gap"], target_gap_count)
        take_from(near_by_kind["coverage-gap"], target_gap_count - len(selected))
    else:
        initial_selected = len(selected)
        take_from(clean_by_kind["coverage-gap"], target_gap_count)
        clean_gap_taken = len(selected) - initial_selected

        before_adjacent = len(selected)
        take_from(clean_by_kind["lesson-adjacent"], target_adjacent_count)
        clean_adjacent_taken = len(selected) - before_adjacent

        remaining_gap = target_gap_count - clean_gap_taken
        remaining_adjacent = target_adjacent_count - clean_adjacent_taken
        if remaining_gap > 0:
            take_from(near_by_kind["coverage-gap"], remaining_gap)
        if remaining_adjacent > 0:
            take_from(near_by_kind["lesson-adjacent"], remaining_adjacent)

    if len(selected) < count:
        fallback_pool = [
            *clean_by_kind["coverage-gap"],
            *clean_by_kind["lesson-adjacent"],
            *near_by_kind["coverage-gap"],
            *near_by_kind["lesson-adjacent"],
        ]
        take_from(fallback_pool, count - len(selected))

    return selected


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
        candidate_count=max(count * 2, count + 10),
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
