from __future__ import annotations

import unittest
from datetime import date

from korean_anki.reading_speed import build_reading_speed_document, chunk_hangul, known_word_bank
from korean_anki.schema import PriorNote, StudyState


class ReadingSpeedTests(unittest.TestCase):
    def test_chunk_hangul_splits_syllables_and_preserves_spaces(self) -> None:
        self.assertEqual(chunk_hangul("안녕하세요 한국어"), "안·녕·하·세·요 한·국·어")

    def test_known_word_bank_dedupes_korean_and_skips_existing_reading_speed_notes(self) -> None:
        state = StudyState(
            generated_notes=[
                PriorNote(
                    note_key="vocab:감사합니다:thank you",
                    korean="감사합니다",
                    english="thank you",
                    item_type="vocab",
                    source="generated.batch.json",
                ),
                PriorNote(
                    note_key="vocab:안녕하세요:hello",
                    korean="안녕하세요",
                    english="hello",
                    item_type="vocab",
                    lane="reading-speed",
                    source="reading.batch.json",
                ),
            ],
            imported_notes=[
                PriorNote(
                    note_key="vocab:안녕하세요:hello",
                    korean="안녕하세요",
                    english="hello",
                    item_type="vocab",
                    source="anki",
                ),
                PriorNote(
                    note_key="vocab:안녕하세요:hello!",
                    korean="안녕하세요",
                    english="hello!",
                    item_type="vocab",
                    source="anki",
                ),
            ],
        )

        bank = known_word_bank(state)

        self.assertEqual([note.korean for note in bank], ["안녕하세요", "감사합니다"])

    def test_build_reading_speed_document_creates_read_aloud_chunked_and_passage_items(self) -> None:
        state = StudyState(
            imported_notes=[
                PriorNote(
                    note_key="vocab:안녕하세요:hello",
                    korean="안녕하세요",
                    english="hello",
                    item_type="vocab",
                    source="anki",
                ),
                PriorNote(
                    note_key="vocab:감사합니다:thank you",
                    korean="감사합니다",
                    english="thank you",
                    item_type="vocab",
                    source="anki",
                ),
            ]
        )

        document = build_reading_speed_document(
            state,
            lesson_id="reading-speed-2026-03-23",
            title="Reading Speed",
            lesson_date=date(2026, 3, 23),
            source_description="Known-word reading practice",
            max_read_aloud=2,
            max_chunked=1,
            passage_word_count=2,
        )

        self.assertEqual(document.metadata.target_deck, "Korean::Reading Speed")
        self.assertEqual(document.metadata.tags, ["reading-speed"])
        self.assertEqual(len(document.items), 3)
        self.assertTrue(all(item.lane == "reading-speed" for item in document.items))
        self.assertEqual(document.items[0].skill_tags, ["reading-speed", "read-aloud", "chunked"])
        self.assertEqual(document.items[1].skill_tags, ["reading-speed", "read-aloud"])
        self.assertEqual(document.items[2].skill_tags, ["reading-speed", "passage"])
        self.assertEqual(document.items[2].korean, "안녕하세요 감사합니다")


if __name__ == "__main__":
    unittest.main()
