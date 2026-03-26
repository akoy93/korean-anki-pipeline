from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from korean_anki.cards import generate_batch
from korean_anki.new_vocab import (
    LessonContext,
    build_new_vocab_document,
    build_new_vocab_document_from_state,
    choose_new_vocab_theme,
    new_vocab_batch_title,
    select_new_vocab_proposals,
    undercovered_topics,
)
from korean_anki.schema import NewVocabProposal, NewVocabProposalBatch, PriorNote, StudyState


def _proposal(
    index: int,
    *,
    korean: str,
    english: str,
    topic_tag: str,
    adjacency_kind: str,
) -> NewVocabProposal:
    return NewVocabProposal(
        candidate_id=f"cand-{index:03d}",
        korean=korean,
        english=english,
        topic_tag=topic_tag,
        example_ko=f"{korean} 있어요.",
        example_en=f"There is {english}.",
        proposal_reason=f"Useful beginner word for {topic_tag}.",
        image_prompt=f"Illustrate {english} in a friendly child-language-learning-book style with no text.",
        adjacency_kind=adjacency_kind,  # type: ignore[arg-type]
    )


class NewVocabTests(unittest.TestCase):
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

    def test_build_new_vocab_from_state_uses_theme_title_and_single_topic_prompt(self) -> None:
        state = StudyState()
        proposal_batch = NewVocabProposalBatch(
            proposals=[
                _proposal(
                    index,
                    korean=f"인사{index}",
                    english=f"greeting {index}",
                    topic_tag="greetings",
                    adjacency_kind="coverage-gap",
                )
                for index in range(1, 4)
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

        self.assertEqual(document.metadata.title, "Greetings Basics")
        self.assertEqual(document.metadata.topic, "New Vocab")
        propose.assert_called_once()
        self.assertEqual(propose.call_args.kwargs["batch_theme"], "Greetings Basics")
        self.assertEqual(propose.call_args.kwargs["target_gap_topics"], ["greetings"])


if __name__ == "__main__":
    unittest.main()
