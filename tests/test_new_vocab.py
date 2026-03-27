from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from korean_anki.new_vocab_documents import (
    build_new_vocab_document,
    build_new_vocab_document_from_state,
)
from korean_anki.new_vocab_selection import (
    LessonContext,
    auto_new_vocab_batch_title,
    choose_new_vocab_strategy,
    choose_new_vocab_theme,
    curriculum_focus_topics,
    known_vocab_count,
    new_vocab_batch_title,
    select_new_vocab_proposals,
    topic_coverage_counts,
    undercovered_topics,
)
from korean_anki.note_generation import generate_batch
from korean_anki.schema import NewVocabProposal, NewVocabProposalBatch, PriorNote, StudyState


def _proposal(
    index: int,
    *,
    korean: str,
    english: str,
    topic_tag: str,
    adjacency_kind: str,
    part_of_speech: str | None = None,
    target_form: str | None = None,
    utility_band: str = "core",
    frequency_band: str = "high",
    usage_register: str | None = None,
) -> NewVocabProposal:
    resolved_part_of_speech = (
        part_of_speech
        if part_of_speech is not None
        else ("verb" if korean.endswith("다") else "noun")
    )
    resolved_target_form = (
        target_form
        if target_form is not None
        else ("fixed-expression" if resolved_part_of_speech == "fixed-expression" else "headword")
    )
    resolved_register = usage_register
    if resolved_register is None:
        resolved_register = "polite-formula" if resolved_part_of_speech == "fixed-expression" else "everyday-spoken"
    return NewVocabProposal(
        candidate_id=f"cand-{index:03d}",
        korean=korean,
        english=english,
        part_of_speech=resolved_part_of_speech,  # type: ignore[arg-type]
        target_form=resolved_target_form,  # type: ignore[arg-type]
        utility_band=utility_band,  # type: ignore[arg-type]
        frequency_band=frequency_band,  # type: ignore[arg-type]
        usage_register=resolved_register,  # type: ignore[arg-type]
        topic_tag=topic_tag,
        example_ko=f"{korean} 있어요.",
        example_en=f"There is {english}.",
        proposal_reason=f"Useful beginner word for {topic_tag}.",
        image_prompt=f"Illustrate {english} in a friendly child-language-learning-book style with no text.",
        adjacency_kind=adjacency_kind,  # type: ignore[arg-type]
    )


class NewVocabTests(unittest.TestCase):
    def _state_with_vocab_count(self, count: int) -> StudyState:
        return StudyState(
            generated_notes=[
                PriorNote(
                    note_key=f"vocab:단어{index}:word{index}",
                    korean=f"단어{index}",
                    english=f"word {index}",
                    item_type="vocab",
                    source="prior.batch.json",
                    skill_tags=["greetings"],
                )
                for index in range(count)
            ]
        )

    def test_undercovered_topics_prefers_low_count_skill_tags(self) -> None:
        state = StudyState()
        state.anki_stats.by_tag = {
            "skill:greetings": 10,
            "skill:family": 2,
            "skill:food": 0,
        }

        topics = undercovered_topics(state, limit=3)

        self.assertEqual(topics, ["food", "numbers", "time"])

    def test_choose_new_vocab_theme_prefers_undercovered_lesson_tag(self) -> None:
        state = StudyState()
        state.anki_stats.by_tag = {
            "skill:greetings": 10,
            "skill:family": 2,
            "skill:food": 0,
            "skill:numbers": 1,
        }
        lesson_context = LessonContext(
            title="Numbers",
            topic="numbers used for prices, time, counting, age",
            summary="Numbers used for prices, time, counting, age",
            tags=["numbers", "time"],
        )

        self.assertEqual(choose_new_vocab_theme(state, lesson_context), "time")
        self.assertEqual(new_vocab_batch_title("time"), "Time Basics")

    def test_choose_new_vocab_strategy_uses_vocab_count_thresholds(self) -> None:
        utility_state = self._state_with_vocab_count(20)
        hybrid_state = self._state_with_vocab_count(220)
        themed_state = self._state_with_vocab_count(400)

        self.assertEqual(known_vocab_count(utility_state), 20)
        self.assertEqual(choose_new_vocab_strategy(utility_state), "utility")
        self.assertEqual(choose_new_vocab_strategy(hybrid_state), "hybrid")
        self.assertEqual(choose_new_vocab_strategy(themed_state), "themed")

    def test_curriculum_focus_topics_hold_back_later_expansion_topics(self) -> None:
        state = StudyState()
        state.anki_stats.by_tag = {
            "skill:greetings": 8,
            "skill:numbers": 12,
            "skill:time": 3,
            "skill:places": 0,
            "skill:food": 0,
            "skill:daily-routines": 0,
            "skill:family": 0,
            "skill:weather": 0,
        }

        self.assertEqual(
            curriculum_focus_topics(state, limit=4),
            ["places", "food", "time", "daily-routines"],
        )
        self.assertEqual(choose_new_vocab_theme(state), "places")

    def test_select_new_vocab_respects_split_excludes_exact_and_uses_near_only_to_fill(self) -> None:
        state = StudyState(
            generated_notes=[
                PriorNote(
                    note_key="vocab:사과:apple",
                    korean="사과",
                    english="apple",
                    item_type="vocab",
                    source="prior.batch.json",
                ),
                PriorNote(
                    note_key="vocab:바나나:banana",
                    korean="바나나",
                    english="banana",
                    item_type="vocab",
                    source="prior.batch.json",
                ),
            ]
        )
        lesson_context = LessonContext(
            title="Numbers",
            topic="numbers used for prices, time, counting, age",
            summary="Numbers used for prices, time, counting, age",
            tags=["numbers", "time"],
        )
        proposals = [
            _proposal(1, korean="사과", english="apple", topic_tag="food", adjacency_kind="coverage-gap"),
            _proposal(2, korean="바나나", english="yellow fruit", topic_tag="food", adjacency_kind="coverage-gap"),
            *[
                _proposal(
                    index,
                    korean=f"음식{index}",
                    english=f"food word {index}",
                    topic_tag="food",
                    adjacency_kind="coverage-gap",
                )
                for index in range(3, 14)
            ],
            *[
                _proposal(
                    index,
                    korean=f"시간{index}",
                    english=f"time word {index}",
                    topic_tag="time",
                    adjacency_kind="lesson-adjacent",
                )
                for index in range(14, 22)
            ],
        ]

        selected = select_new_vocab_proposals(proposals, state, count=20, gap_ratio=0.6, lesson_context=lesson_context)
        selected_proposals = [proposal for proposal, _near_duplicate in selected]
        document = build_new_vocab_document(
            proposals,
            state,
            lesson_id="new-vocab-2026-03-24",
            title="New Vocab",
            lesson_date=date(2026, 3, 24),
            count=20,
            gap_ratio=0.6,
            lesson_context=lesson_context,
        )
        batch = generate_batch(document, study_state=state)

        self.assertEqual(len(selected), 20)
        self.assertNotIn("사과", [proposal.korean for proposal in selected_proposals])
        self.assertEqual(
            sum(1 for proposal in selected_proposals if proposal.adjacency_kind == "coverage-gap"),
            12,
        )
        self.assertEqual(
            sum(1 for proposal in selected_proposals if proposal.adjacency_kind == "lesson-adjacent"),
            8,
        )

        near_notes = [note for note in batch.notes if note.duplicate_status == "near-duplicate"]
        self.assertEqual(len(near_notes), 1)
        self.assertEqual(near_notes[0].item.korean, "바나나")
        self.assertEqual(batch.notes[0].lane, "new-vocab")
        self.assertEqual(batch.notes[0].skill_tags, ["food"])
        self.assertTrue(batch.notes[0].inclusion_reason.startswith("Coverage gap:"))
        self.assertEqual(document.metadata.target_deck, "Korean::New Vocab")

    def test_build_new_vocab_without_lesson_context_uses_coverage_gap_only(self) -> None:
        state = StudyState()
        proposals = [
            _proposal(index, korean=f"단어{index}", english=f"word {index}", topic_tag="food", adjacency_kind="coverage-gap")
            for index in range(1, 4)
        ] + [
            _proposal(index, korean=f"수업{index}", english=f"class {index}", topic_tag="time", adjacency_kind="lesson-adjacent")
            for index in range(4, 8)
        ]

        document = build_new_vocab_document(
            proposals,
            state,
            lesson_id="new-vocab-2026-03-24",
            title="New Vocab",
            lesson_date=date(2026, 3, 24),
            count=3,
            gap_ratio=0.6,
            lesson_context=None,
        )

        self.assertEqual(len(document.items), 3)
        self.assertTrue(all("coverage-gap" in item.tags for item in document.items))
        self.assertTrue(all(item.lane == "new-vocab" for item in document.items))
        self.assertTrue(all(item.image_prompt is not None for item in document.items))

    def test_select_new_vocab_filters_surface_forms_but_keeps_fixed_expressions(self) -> None:
        state = StudyState()
        proposals = [
            _proposal(
                1,
                korean="먹어요",
                english="eat",
                topic_tag="food",
                adjacency_kind="coverage-gap",
                part_of_speech="verb",
                target_form="headword",
            ),
            _proposal(
                2,
                korean="바빠요",
                english="busy",
                topic_tag="daily-routines",
                adjacency_kind="coverage-gap",
                part_of_speech="adjective",
                target_form="headword",
            ),
            _proposal(
                3,
                korean="먹다",
                english="eat",
                topic_tag="food",
                adjacency_kind="coverage-gap",
                part_of_speech="verb",
                target_form="headword",
            ),
            _proposal(4, korean="버스", english="bus", topic_tag="places", adjacency_kind="coverage-gap"),
            _proposal(5, korean="학교", english="school", topic_tag="places", adjacency_kind="coverage-gap"),
            _proposal(
                6,
                korean="안녕하세요",
                english="hello",
                topic_tag="greetings",
                adjacency_kind="coverage-gap",
                part_of_speech="fixed-expression",
                target_form="fixed-expression",
            ),
            _proposal(
                7,
                korean="안녕히 가세요",
                english="goodbye",
                topic_tag="greetings",
                adjacency_kind="coverage-gap",
                part_of_speech="fixed-expression",
                target_form="fixed-expression",
            ),
        ]

        selected = select_new_vocab_proposals(proposals, state, count=5, gap_ratio=1.0, lesson_context=None)
        selected_korean = [proposal.korean for proposal, _near_duplicate in selected]

        self.assertNotIn("먹어요", selected_korean)
        self.assertNotIn("바빠요", selected_korean)
        self.assertIn("먹다", selected_korean)
        self.assertIn("버스", selected_korean)
        self.assertIn("안녕하세요", selected_korean)
        self.assertIn("안녕히 가세요", selected_korean)

    def test_select_new_vocab_prefers_core_utility_before_expansion(self) -> None:
        state = StudyState()
        proposals = [
            _proposal(1, korean="물", english="water", topic_tag="food", adjacency_kind="coverage-gap", utility_band="core"),
            _proposal(2, korean="밥", english="rice", topic_tag="food", adjacency_kind="coverage-gap", utility_band="core"),
            _proposal(
                3,
                korean="먹다",
                english="eat",
                topic_tag="food",
                adjacency_kind="coverage-gap",
                part_of_speech="verb",
                target_form="headword",
                utility_band="core",
            ),
            _proposal(4, korean="후식", english="dessert", topic_tag="food", adjacency_kind="coverage-gap", utility_band="supporting"),
            _proposal(5, korean="식초", english="vinegar", topic_tag="food", adjacency_kind="coverage-gap", utility_band="expansion"),
        ]

        selected = select_new_vocab_proposals(proposals, state, count=3, gap_ratio=1.0, lesson_context=None)
        selected_korean = [proposal.korean for proposal, _near_duplicate in selected]

        self.assertEqual(selected_korean, ["물", "밥", "먹다"])

    def test_utility_stage_filters_low_frequency_and_formal_words(self) -> None:
        state = StudyState()
        proposals = [
            _proposal(
                1,
                korean="소강하다",
                english="subside temporarily",
                topic_tag="weather",
                adjacency_kind="coverage-gap",
                part_of_speech="verb",
                target_form="headword",
                utility_band="core",
                frequency_band="low",
                usage_register="formal-written",
            ),
            _proposal(
                2,
                korean="안녕하세요",
                english="hello",
                topic_tag="greetings",
                adjacency_kind="coverage-gap",
                part_of_speech="fixed-expression",
                target_form="fixed-expression",
                utility_band="core",
                frequency_band="high",
                usage_register="polite-formula",
            ),
            _proposal(
                3,
                korean="감사합니다",
                english="thank you",
                topic_tag="greetings",
                adjacency_kind="coverage-gap",
                part_of_speech="fixed-expression",
                target_form="fixed-expression",
                utility_band="core",
                frequency_band="high",
                usage_register="polite-formula",
            ),
        ]

        selected = select_new_vocab_proposals(proposals, state, count=2, gap_ratio=1.0, lesson_context=None)

        self.assertEqual(
            [proposal.korean for proposal, _near_duplicate in selected],
            ["감사합니다", "안녕하세요"],
        )

    def test_auto_new_vocab_batch_title_uses_selected_topics_for_utility_mode(self) -> None:
        title = auto_new_vocab_batch_title(
            [
                _proposal(1, korean="안녕하세요", english="hello", topic_tag="greetings", adjacency_kind="coverage-gap", part_of_speech="fixed-expression", target_form="fixed-expression"),
                _proposal(2, korean="감사합니다", english="thank you", topic_tag="greetings", adjacency_kind="coverage-gap", part_of_speech="fixed-expression", target_form="fixed-expression"),
                _proposal(3, korean="하나", english="one", topic_tag="numbers", adjacency_kind="coverage-gap"),
            ],
            selection_strategy="utility",
        )

        self.assertEqual(title, "Core Korean: Greetings and Numbers")

    def test_build_new_vocab_from_state_uses_utility_prompt_and_auto_title_early(self) -> None:
        state = StudyState()
        proposal_batch = NewVocabProposalBatch(
            proposals=[
                _proposal(
                    1,
                    korean="안녕하세요",
                    english="hello",
                    topic_tag="greetings",
                    adjacency_kind="coverage-gap",
                    part_of_speech="fixed-expression",
                    target_form="fixed-expression",
                    usage_register="polite-formula",
                ),
                _proposal(
                    2,
                    korean="감사합니다",
                    english="thank you",
                    topic_tag="greetings",
                    adjacency_kind="coverage-gap",
                    part_of_speech="fixed-expression",
                    target_form="fixed-expression",
                    usage_register="polite-formula",
                ),
                _proposal(
                    3,
                    korean="하나",
                    english="one",
                    topic_tag="numbers",
                    adjacency_kind="coverage-gap",
                ),
            ]
        )

        with (
            patch("korean_anki.new_vocab_documents.propose_new_vocab", return_value=proposal_batch) as propose,
            patch("korean_anki.new_vocab_documents.generate_pronunciations", return_value={}),
        ):
            document = build_new_vocab_document_from_state(
                state,
                lesson_id="new-vocab-2026-03-25",
                title="New Vocab",
                lesson_date=date(2026, 3, 25),
                count=3,
                gap_ratio=0.6,
                lesson_context_path=None,
                target_deck="Korean::New Vocab",
            )

        self.assertEqual(document.metadata.title, "Core Korean: Greetings and Numbers")
        self.assertEqual(document.metadata.topic, "New Vocab")
        propose.assert_called_once()
        self.assertIsNone(propose.call_args.kwargs["batch_theme"])
        self.assertEqual(propose.call_args.kwargs["selection_strategy"], "utility")
        self.assertEqual(propose.call_args.kwargs["target_gap_topics"], ["greetings", "numbers", "time", "places"])
        self.assertEqual(
            propose.call_args.kwargs["curriculum_focus_topics"],
            ["greetings", "numbers", "time", "places"],
        )
        self.assertEqual(
            propose.call_args.kwargs["topic_coverage_counts"],
            dict(topic_coverage_counts(state)),
        )


if __name__ == "__main__":
    unittest.main()
