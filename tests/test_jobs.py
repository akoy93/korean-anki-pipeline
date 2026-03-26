from __future__ import annotations

import shutil
import unittest
from pathlib import Path

from korean_anki.job_store import JobStore


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


if __name__ == "__main__":
    unittest.main()
