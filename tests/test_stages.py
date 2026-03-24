from __future__ import annotations

import unittest

from korean_anki.schema import LessonTranscription, TranscriptionEntry, TranscriptionSection
from korean_anki.stages import build_lesson_documents, qa_transcription

from support import make_transcription


class StageTests(unittest.TestCase):
    def test_build_lesson_documents_fills_pronunciation_filters_positional_tags_and_sets_source_ref(self) -> None:
        transcription = make_transcription()

        documents = build_lesson_documents(transcription, pronunciation_lookup={"일": "il"})

        self.assertEqual(len(documents), 1)
        document = documents[0]
        self.assertEqual(document.metadata.target_deck, "Korean::Lessons::italki-2026-03-23-test::Left-Side")
        self.assertEqual(document.metadata.tags, ["numbers", "sino-korean"])

        item = document.items[0]
        self.assertEqual(item.pronunciation, "il")
        self.assertEqual(item.tags, ["numbers", "sino-korean"])
        self.assertEqual(item.lane, "lesson")
        self.assertEqual(item.skill_tags, ["numbers", "sino-korean"])
        self.assertEqual(item.notes, "Used for sequence and prices.")
        self.assertEqual(
            item.source_ref,
            "2026-03-23 Numbers lesson • 2026-03-21_1.png • Left Side • 1",
        )

    def test_qa_transcription_reports_structure_errors_and_warnings(self) -> None:
        base = make_transcription()
        bad_section = TranscriptionSection(
            id="section-left-sino",
            title="Duplicate Section",
            item_type="number",
            side="right",
            number_system="sino-korean",
            usage_notes=[],
            expected_entry_count=2,
            target_deck=None,
            tags=[],
            entries=[
                TranscriptionEntry(label="1", korean="이", english="two", pronunciation=None, notes=None),
                TranscriptionEntry(label="1", korean="삼", english="three", pronunciation=None, notes=None),
            ],
        )
        transcription = LessonTranscription(
            lesson_id=base.lesson_id,
            title=base.title,
            lesson_date=base.lesson_date,
            source_summary=base.source_summary,
            theme="",
            goals=[],
            raw_sources=base.raw_sources,
            expected_section_count=1,
            sections=[base.sections[0], bad_section],
            notes=[],
        )

        report = qa_transcription(transcription)

        self.assertFalse(report.passed)
        codes = {issue.code for issue in report.issues}
        self.assertTrue(
            {
                "section_count_mismatch",
                "duplicate_section_id",
                "missing_usage_notes",
                "duplicate_entry_label",
                "missing_theme",
                "missing_goals",
            }.issubset(codes)
        )


if __name__ == "__main__":
    unittest.main()
