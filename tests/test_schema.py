from __future__ import annotations

import unittest

from pydantic import ValidationError

from korean_anki.schema import CardPreview, GeneratedNote, LessonItem


class SchemaTests(unittest.TestCase):
    def test_strict_models_reject_unknown_fields(self) -> None:
        with self.assertRaises(ValidationError):
            LessonItem.model_validate(
                {
                    "id": "item-1",
                    "lesson_id": "lesson-1",
                    "item_type": "vocab",
                    "korean": "안녕하세요",
                    "english": "hello",
                    "examples": [],
                    "tags": [],
                    "unexpected": True,
                }
            )

    def test_generated_note_remains_backward_compatible_with_existing_batches(self) -> None:
        note = GeneratedNote.model_validate(
            {
                "item": {
                    "id": "item-1",
                    "lesson_id": "lesson-1",
                    "item_type": "vocab",
                    "korean": "안녕하세요",
                    "english": "hello",
                    "examples": [],
                    "tags": [],
                },
                "cards": [
                    {
                        "id": "item-1-recognition",
                        "item_id": "item-1",
                        "kind": "recognition",
                        "front_html": "front",
                        "back_html": "back",
                    }
                ],
                "approved": True,
            }
        )

        self.assertEqual(note.note_key, "")
        self.assertEqual(note.lane, "lesson")
        self.assertEqual(note.duplicate_status, "new")


if __name__ == "__main__":
    unittest.main()
