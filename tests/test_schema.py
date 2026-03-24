from __future__ import annotations

import unittest

from pydantic import ValidationError

from korean_anki.schema import LessonItem


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


if __name__ == "__main__":
    unittest.main()
