from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from korean_anki.batch_repository import BatchRepository
from korean_anki.cards import generate_batch
from korean_anki.note_keys import normalize_text, note_key_for_item
from korean_anki.snapshots import study_state_snapshot

from support import make_document, make_item


class StudyStateTests(unittest.TestCase):
    def test_normalized_note_key_is_stable_across_case_and_spacing(self) -> None:
        item = make_item(korean=" 안녕 하세요 ", english=" Hello ")

        self.assertEqual(normalize_text("  Hello  World "), "hello world")
        self.assertEqual(note_key_for_item(item), "vocab:안녕 하세요:hello")

    def test_generated_history_scans_real_generated_batches_and_skips_samples(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)

            real_dir = project_root / "lessons" / "2026-03-23-test" / "generated"
            real_dir.mkdir(parents=True)
            sample_dir = project_root / "data" / "samples"
            sample_dir.mkdir(parents=True)

            real_batch = generate_batch(make_document([make_item(item_id="real-1", korean="일", english="one")]))
            sample_batch = generate_batch(make_document([make_item(item_id="sample-1", korean="이", english="two")]))

            (real_dir / "real.batch.json").write_text(real_batch.model_dump_json(), encoding="utf-8")
            (sample_dir / "sample.batch.json").write_text(sample_batch.model_dump_json(), encoding="utf-8")

            history = BatchRepository(project_root).generated_history()

        self.assertEqual([note.korean for note in history], ["일"])
        self.assertEqual(history[0].source, "lessons/2026-03-23-test/generated/real.batch.json")

    def test_build_study_state_refreshes_when_new_batch_is_written(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            generated_dir = project_root / "data" / "generated"
            generated_dir.mkdir(parents=True)

            first_batch = generate_batch(make_document([make_item(item_id="real-1", korean="일", english="one")]))
            second_batch = generate_batch(make_document([make_item(item_id="real-2", korean="이", english="two")]))

            (generated_dir / "first.batch.json").write_text(first_batch.model_dump_json(), encoding="utf-8")
            first_state = study_state_snapshot(project_root=project_root, exclude_batch_path=None)

            time.sleep(0.01)
            (generated_dir / "second.batch.json").write_text(second_batch.model_dump_json(), encoding="utf-8")
            second_state = study_state_snapshot(project_root=project_root, exclude_batch_path=None)

        self.assertEqual([note.korean for note in first_state.generated_notes], ["일"])
        self.assertEqual([note.korean for note in second_state.generated_notes], ["이", "일"])


if __name__ == "__main__":
    unittest.main()
