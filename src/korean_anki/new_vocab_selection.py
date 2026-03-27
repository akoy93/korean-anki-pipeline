from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .note_keys import normalize_text
from .schema import (
    LessonTranscription,
    NewVocabProposal,
    PriorNote,
    StudyState,
    VocabAdjacencyKind,
)

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

A1_CURRICULUM_ORDER = [
    "greetings",
    "numbers",
    "time",
    "places",
    "food",
    "daily-routines",
    "family",
    "weather",
]

A1_TOPIC_TARGET_COUNTS = {
    "greetings": 8,
    "numbers": 12,
    "time": 10,
    "places": 10,
    "food": 10,
    "daily-routines": 10,
    "family": 8,
    "weather": 6,
}

CURRICULUM_FOCUS_WINDOW = 3
UTILITY_FIRST_VOCAB_THRESHOLD = 200
THEMED_VOCAB_THRESHOLD = 350
UTILITY_FOCUS_TOPIC_LIMIT = 4
HYBRID_FOCUS_TOPIC_LIMIT = 4

_SURFACE_FORM_SUFFIXES = (
    "했습니다",
    "합니다",
    "였어요",
    "했어요",
    "았어요",
    "었어요",
    "이에요",
    "예요",
    "에요",
    "해요",
    "아요",
    "어요",
    "여요",
    "네요",
    "군요",
    "나요",
    "세요",
    "니다",
    "했다",
    "했어",
    "았다",
    "었다",
    "요",
)

_UTILITY_RANK = {
    "core": 0,
    "supporting": 1,
    "expansion": 2,
}

_FREQUENCY_RANK = {
    "high": 0,
    "medium": 1,
    "low": 2,
}

_REGISTER_RANK = {
    "polite-formula": 0,
    "everyday-spoken": 1,
    "formal-written": 2,
    "literary": 3,
    "niche": 4,
}

_PART_OF_SPEECH_RANK = {
    "noun": 0,
    "verb": 1,
    "fixed-expression": 2,
    "adjective": 3,
}

NewVocabSelectionStrategy = Literal["utility", "hybrid", "themed"]

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
    topic_counts = topic_coverage_counts(study_state)

    return sorted(
        A1_TOPIC_INVENTORY,
        key=lambda topic: (topic_counts[topic], A1_TOPIC_INVENTORY.index(topic)),
    )[:limit]


def known_vocab_count(study_state: StudyState) -> int:
    return len({note.note_key for note in prior_notes_for_vocab(study_state)})


def choose_new_vocab_strategy(study_state: StudyState) -> NewVocabSelectionStrategy:
    current_count = known_vocab_count(study_state)
    if current_count < UTILITY_FIRST_VOCAB_THRESHOLD:
        return "utility"
    if current_count < THEMED_VOCAB_THRESHOLD:
        return "hybrid"
    return "themed"


def choose_new_vocab_theme(study_state: StudyState, lesson_context: LessonContext | None = None) -> str:
    focus_topics = curriculum_focus_topics(
        study_state,
        limit=CURRICULUM_FOCUS_WINDOW,
    )
    if not focus_topics:
        focus_topics = undercovered_topics(study_state, limit=len(A1_TOPIC_INVENTORY))
    topic_counts = topic_coverage_counts(study_state)
    if lesson_context is not None:
        matching_focus_topics = [topic for topic in focus_topics if topic in lesson_context.tags]
        if matching_focus_topics:
            return min(
                matching_focus_topics,
                key=lambda topic: (topic_counts[topic], A1_CURRICULUM_ORDER.index(topic)),
            )
    return min(
        focus_topics,
        key=lambda topic: (topic_counts[topic], A1_CURRICULUM_ORDER.index(topic)),
    )


def new_vocab_batch_title(topic_tag: str) -> str:
    return f"{A1_TOPIC_TITLES[topic_tag]} Basics"


def auto_new_vocab_batch_title(
    proposals: list[NewVocabProposal],
    *,
    selection_strategy: NewVocabSelectionStrategy,
) -> str:
    if not proposals:
        return "New Vocab"

    topic_counts = Counter(
        proposal.topic_tag for proposal in proposals if proposal.topic_tag in A1_TOPIC_TITLES
    )
    if not topic_counts:
        return "Core Korean" if selection_strategy != "themed" else "New Vocab"

    ordered_topics = sorted(
        topic_counts,
        key=lambda topic: (-topic_counts[topic], A1_CURRICULUM_ORDER.index(topic)),
    )
    if selection_strategy == "themed":
        return new_vocab_batch_title(ordered_topics[0])
    if len(ordered_topics) == 1:
        return f"Core Korean: {A1_TOPIC_TITLES[ordered_topics[0]]}"
    return (
        f"Core Korean: {A1_TOPIC_TITLES[ordered_topics[0]]} "
        f"and {A1_TOPIC_TITLES[ordered_topics[1]]}"
    )


def prior_notes_for_vocab(study_state: StudyState) -> list[PriorNote]:
    return [note for note in [*study_state.generated_notes, *study_state.imported_notes] if note.item_type == "vocab"]


def topic_coverage_counts(study_state: StudyState) -> Counter[str]:
    topic_counts: Counter[str] = Counter()
    seen_note_keys_by_topic: dict[str, set[str]] = {topic: set() for topic in A1_TOPIC_INVENTORY}

    for note in [*study_state.generated_notes, *study_state.imported_notes]:
        for topic in {skill_tag for skill_tag in note.skill_tags if skill_tag in seen_note_keys_by_topic}:
            if note.note_key in seen_note_keys_by_topic[topic]:
                continue
            seen_note_keys_by_topic[topic].add(note.note_key)
            topic_counts[topic] += 1

    for topic in A1_TOPIC_INVENTORY:
        topic_counts[topic] = max(
            topic_counts[topic],
            study_state.anki_stats.by_tag.get(f"skill:{topic}", 0),
        )

    return topic_counts


def curriculum_focus_topics(study_state: StudyState, limit: int = len(A1_TOPIC_INVENTORY)) -> list[str]:
    topic_counts = topic_coverage_counts(study_state)
    unmet_topics = [
        topic
        for topic in A1_CURRICULUM_ORDER
        if topic_counts[topic] < A1_TOPIC_TARGET_COUNTS[topic]
    ]
    focus_topics = unmet_topics[:CURRICULUM_FOCUS_WINDOW]
    ordered_topics = [
        *sorted(
            focus_topics,
            key=lambda topic: (topic_counts[topic], A1_CURRICULUM_ORDER.index(topic)),
        ),
        *[topic for topic in unmet_topics if topic not in focus_topics],
        *[
            topic
            for topic in A1_CURRICULUM_ORDER
            if topic not in focus_topics and topic not in unmet_topics
        ],
    ]
    return ordered_topics[:limit]


def prompt_focus_topics(
    study_state: StudyState,
    *,
    selection_strategy: NewVocabSelectionStrategy,
    lesson_context: LessonContext | None = None,
) -> list[str]:
    focus_limit = (
        UTILITY_FOCUS_TOPIC_LIMIT
        if selection_strategy == "utility"
        else HYBRID_FOCUS_TOPIC_LIMIT
    )
    if selection_strategy == "themed":
        return [choose_new_vocab_theme(study_state, lesson_context)]

    ordered_topics = curriculum_focus_topics(study_state, limit=focus_limit)
    if lesson_context is None:
        return ordered_topics

    lesson_topics = [topic for topic in ordered_topics if topic in lesson_context.tags]
    if not lesson_topics:
        return ordered_topics
    return [*lesson_topics, *[topic for topic in ordered_topics if topic not in lesson_topics]]


def proposal_note_key(proposal: NewVocabProposal) -> str:
    return f"vocab:{normalize_text(proposal.korean)}:{normalize_text(proposal.english)}"


def _collapsed_korean(value: str) -> str:
    return normalize_text(value).replace(" ", "").rstrip(".?!")


def _is_fixed_expression_target(proposal: NewVocabProposal) -> bool:
    return (
        proposal.part_of_speech == "fixed-expression"
        and proposal.target_form == "fixed-expression"
    )


def _looks_like_conjugated_surface_form(korean: str) -> bool:
    collapsed = _collapsed_korean(korean)
    if not collapsed or collapsed.endswith("다"):
        return False
    return any(collapsed.endswith(suffix) for suffix in _SURFACE_FORM_SUFFIXES)


def _is_beginner_headword_target(proposal: NewVocabProposal) -> bool:
    collapsed = _collapsed_korean(proposal.korean)
    if not collapsed:
        return False
    if _is_fixed_expression_target(proposal):
        return True
    if proposal.target_form != "headword":
        return False
    if proposal.part_of_speech in {"verb", "adjective"}:
        return collapsed.endswith("다")
    if proposal.part_of_speech != "noun":
        return False
    if " " in normalize_text(proposal.korean):
        return False
    if _looks_like_conjugated_surface_form(proposal.korean):
        return False
    return True


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
) -> tuple[int, int, int, int, int, int, str]:
    topic_rank = target_topics.index(proposal.topic_tag) if proposal.topic_tag in target_topics else len(target_topics)
    adjacency_rank = 0 if proposal.adjacency_kind == "coverage-gap" else 1
    near_penalty = 1 if near_duplicate else 0
    utility_rank = _UTILITY_RANK[proposal.utility_band]
    frequency_rank = _FREQUENCY_RANK[proposal.frequency_band]
    register_rank = _REGISTER_RANK[proposal.usage_register]
    part_of_speech_rank = _PART_OF_SPEECH_RANK[proposal.part_of_speech]
    return (
        near_penalty,
        utility_rank,
        frequency_rank,
        register_rank,
        part_of_speech_rank,
        adjacency_rank,
        topic_rank,
        normalize_text(proposal.korean),
    )


def _is_strategy_appropriate(
    proposal: NewVocabProposal,
    *,
    selection_strategy: NewVocabSelectionStrategy,
) -> bool:
    if selection_strategy == "utility":
        return (
            proposal.frequency_band == "high"
            and proposal.usage_register in {"everyday-spoken", "polite-formula"}
        )
    if selection_strategy == "hybrid":
        return (
            proposal.frequency_band != "low"
            and proposal.usage_register not in {"formal-written", "literary", "niche"}
        )
    return True


def select_new_vocab_proposals(
    proposals: list[NewVocabProposal],
    study_state: StudyState,
    *,
    count: int = 20,
    gap_ratio: float = 0.6,
    lesson_context: LessonContext | None = None,
    selection_strategy: NewVocabSelectionStrategy | None = None,
) -> list[tuple[NewVocabProposal, PriorNote | None]]:
    resolved_strategy = selection_strategy or choose_new_vocab_strategy(study_state)
    prior_notes = prior_notes_for_vocab(study_state)
    target_gap_count = round(count * gap_ratio)
    target_adjacent_count = count - target_gap_count
    if lesson_context is None:
        target_gap_count = count
        target_adjacent_count = 0
    elif resolved_strategy == "utility":
        target_gap_count = count
        target_adjacent_count = 0

    target_topics = curriculum_focus_topics(study_state, limit=len(A1_TOPIC_INVENTORY))

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
        if not _is_beginner_headword_target(proposal):
            continue
        if not _is_strategy_appropriate(proposal, selection_strategy=resolved_strategy):
            continue

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
