from __future__ import annotations

import unittest
from pathlib import Path

from pydantic import ValidationError

from korean_anki.schema_codegen import render_preview_schema_ts
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

    def test_preview_typescript_schema_is_generated_from_backend_schema(self) -> None:
        generated_path = Path("preview/src/lib/schema.ts")
        self.assertEqual(
            generated_path.read_text(encoding="utf-8"),
            render_preview_schema_ts(),
        )


if __name__ == "__main__":
    unittest.main()
