from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from korean_anki.schema_codegen import build_preview_contract_schema, render_preview_contract_schema_json
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

    def test_preview_json_schema_contract_is_generated_from_backend_schema(self) -> None:
        generated_path = Path("preview/src/lib/schema.contract.json")
        self.assertEqual(
            generated_path.read_text(encoding="utf-8"),
            render_preview_contract_schema_json(),
        )

    def test_preview_contract_is_limited_to_frontend_transport_surface(self) -> None:
        contract = build_preview_contract_schema()
        definitions = contract["$defs"]

        for expected_name in {
            "BatchPushStatus",
            "CardBatch",
            "DashboardResponse",
            "GeneratedNote",
            "JobResponse",
            "LessonItem",
            "PushResult",
            "StudyLane",
        }:
            self.assertIn(expected_name, definitions)

        for unexpected_name in {
            "ExtractionRequest",
            "LessonDocument",
            "LessonTranscription",
            "NewVocabJobRequest",
            "NewVocabProposalBatch",
            "PushRequest",
            "QaReport",
            "SyncMediaJobRequest",
        }:
            self.assertNotIn(unexpected_name, definitions)

    def test_preview_typescript_schema_is_generated_from_contract(self) -> None:
        contract_path = Path("preview/src/lib/schema.contract.json").resolve()
        generated_path = Path("preview/src/lib/schema.ts").resolve()

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "schema.ts"
            subprocess.run(
                [
                    "node",
                    "scripts/generate-schema-types.mjs",
                    str(contract_path),
                    str(output_path),
                ],
                check=True,
                cwd=Path("preview").resolve(),
            )
            generated_from_contract = output_path.read_text(encoding="utf-8")

        self.assertEqual(
            generated_path.read_text(encoding="utf-8"),
            generated_from_contract,
        )


if __name__ == "__main__":
    unittest.main()
