from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from korean_anki.job_handlers import new_vocab_job
from korean_anki.job_store import JobStore
from korean_anki.schema import JobPhase


class JobStoreTests(unittest.TestCase):
    def test_completed_job_persists_across_store_reopen(self) -> None:
        store_root = Path(self._testMethodName)
        self.addCleanup(lambda: shutil.rmtree(store_root, ignore_errors=True))

        first_store = JobStore(store_root)
        job = first_store.create("new-vocab")
        first_store.update(
            job.id,
            status="running",
            log="started",
            progress_current=4,
            progress_total=10,
            progress_label="Generating cards",
            phases=[
                JobPhase(key="study-state", label="Loading study state", status="succeeded"),
                JobPhase(key="cards", label="Building cards", status="running", current=4, total=10),
            ],
        )
        first_store.update(
            job.id,
            status="succeeded",
            output_paths=["data/generated/new-vocab.batch.json"],
        )

        reopened_store = JobStore(store_root)
        loaded_job = reopened_store.get(job.id)

        self.assertEqual(loaded_job.status, "succeeded")
        self.assertEqual(loaded_job.progress_current, 4)
        self.assertEqual(loaded_job.progress_total, 10)
        self.assertEqual(loaded_job.progress_label, "Generating cards")
        self.assertEqual(len(loaded_job.phases), 2)
        self.assertEqual(loaded_job.phases[1].key, "cards")
        self.assertEqual(loaded_job.phases[1].current, 4)
        self.assertEqual(
            loaded_job.output_paths,
            ["data/generated/new-vocab.batch.json"],
        )
        self.assertEqual(loaded_job.logs, ["started"])

    def test_incomplete_job_is_marked_failed_on_store_reopen(self) -> None:
        store_root = Path(self._testMethodName)
        self.addCleanup(lambda: shutil.rmtree(store_root, ignore_errors=True))

        first_store = JobStore(store_root)
        job = first_store.create("sync-media")
        first_store.update(
            job.id,
            status="running",
            progress_current=1,
            progress_total=2,
            progress_label="Downloading media",
        )

        reopened_store = JobStore(store_root)
        loaded_job = reopened_store.get(job.id)

        self.assertEqual(loaded_job.status, "failed")
        self.assertEqual(loaded_job.error, "Job interrupted by backend restart.")
        self.assertEqual(loaded_job.progress_current, 1)
        self.assertEqual(loaded_job.progress_total, 2)
        self.assertEqual(loaded_job.progress_label, "Downloading media")

    def test_new_vocab_job_reports_explicit_phase_progress(self) -> None:
        project_root = Path(self._testMethodName)
        project_root.mkdir(exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(project_root, ignore_errors=True))
        captured_updates: list[dict[str, object]] = []

        def fake_generate_new_vocab_batch(**kwargs):
            kwargs["on_study_state_loaded"]()
            kwargs["on_theme_selected"]("greetings")
            kwargs["on_proposals_generated"](25)
            kwargs["on_selection_complete"](3)
            kwargs["on_pronunciations_generated"](3)
            for _ in range(3):
                kwargs["on_image_complete"]()
            for _ in range(3):
                kwargs["on_audio_complete"]()
            for _ in range(3):
                kwargs["on_note_generated"](None)
            return object()

        with (
            patch("korean_anki.job_handlers.path_policy.project_root", return_value=project_root),
            patch(
                "korean_anki.job_handlers.unique_new_vocab_output_path",
                return_value=project_root / "data" / "generated" / "new-vocab-test.batch.json",
            ),
            patch(
                "korean_anki.job_handlers.generate_new_vocab_batch",
                side_effect=fake_generate_new_vocab_batch,
            ),
        ):
            output_paths = new_vocab_job(
                json.dumps(
                    {
                        "count": 3,
                        "gap_ratio": 1.0,
                        "lesson_context": None,
                        "with_audio": True,
                        "image_quality": "low",
                    }
                ),
                on_progress=lambda **progress: captured_updates.append(progress),
            )

        self.assertEqual(output_paths, ["data/generated/new-vocab-test.batch.json"])
        self.assertGreater(len(captured_updates), 0)
        phase_labels = [phase.label for phase in captured_updates[-1]["phases"]]
        self.assertEqual(
            phase_labels,
            [
                "Loading study state",
                "Choosing batch focus",
                "Generating vocab proposals",
                "Filtering and ranking proposals",
                "Generating pronunciations",
                "Generating images",
                "Generating audio",
                "Building cards",
            ],
        )
        final_phases = captured_updates[-1]["phases"]
        self.assertTrue(all(phase.status == "succeeded" for phase in final_phases))
        self.assertEqual(captured_updates[-1]["progress_label"], "Building cards")
        self.assertEqual(captured_updates[-1]["progress_current"], 3)
        self.assertEqual(captured_updates[-1]["progress_total"], 3)


if __name__ == "__main__":
    unittest.main()
