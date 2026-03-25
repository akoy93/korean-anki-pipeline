from __future__ import annotations

import json
import shutil
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from korean_anki.push_service import PushServiceHandler, _new_vocab_job, _unique_new_vocab_output_path
from korean_anki.schema import (
    AnkiStatsSnapshot,
    NewVocabProposal,
    NewVocabProposalBatch,
    PushResult,
    ServiceStatus,
    StudyState,
)

from korean_anki.cards import generate_note
from support import make_batch, make_item


class PushServiceTests(unittest.TestCase):
    def _start_server(self) -> tuple[ThreadingHTTPServer, str, threading.Thread]:
        server = ThreadingHTTPServer(("127.0.0.1", 0), PushServiceHandler)
        host, port = server.server_address
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, f"http://{host}:{port}", thread

    def _stop_server(self, server: ThreadingHTTPServer, thread: threading.Thread) -> None:
        server.shutdown()
        thread.join()
        server.server_close()

    def _post_json(self, base_url: str, path: str, payload: dict[str, object]) -> dict[str, object]:
        request = urllib.request.Request(
            f"{base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))

    def _wait_for_job(self, base_url: str, job_id: str) -> dict[str, object]:
        for _ in range(20):
            with urllib.request.urlopen(f"{base_url}/api/jobs/{job_id}", timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if payload["status"] in {"succeeded", "failed"}:
                return payload
            time.sleep(0.05)
        raise AssertionError(f"Job did not finish: {job_id}")

    def test_health_endpoint_returns_ok(self) -> None:
        server, base_url, thread = self._start_server()
        self.addCleanup(self._stop_server, server, thread)

        with urllib.request.urlopen(f"{base_url}/api/health", timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))

        self.assertEqual(payload, {"ok": True})

    def test_status_endpoint_returns_service_state(self) -> None:
        server, base_url, thread = self._start_server()
        self.addCleanup(self._stop_server, server, thread)

        with patch(
            "korean_anki.push_service._service_status",
            return_value=ServiceStatus(
                backend_ok=True,
                anki_connect_ok=True,
                anki_connect_version=6,
                openai_configured=True,
            ),
        ):
            with urllib.request.urlopen(f"{base_url}/api/status", timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))

        self.assertEqual(
            payload,
            {
                "backend_ok": True,
                "anki_connect_ok": True,
                "anki_connect_version": 6,
                "openai_configured": True,
            },
        )

    def test_dashboard_endpoint_aggregates_batches_and_anki_counts(self) -> None:
        class FakeDashboardAnkiClient:
            def invoke(self, action: str, **params: object) -> object:
                if action == "version":
                    return 6
                if action == "findNotes":
                    return [1, 2]
                if action == "findCards":
                    query = params["query"]
                    if query == 'note:"Korean Lesson Item"':
                        return [10, 11, 12]
                    if query == 'deck:"Korean::Lessons::Numbers::Sino" note:"Korean Lesson Item"':
                        return [10, 11]
                    if query == 'deck:"Korean::New Vocab" note:"Korean Lesson Item"':
                        return [12]
                    return []
                if action == "deckNames":
                    return ["Default", "Korean::Lessons::Numbers::Sino", "Korean::New Vocab"]
                return None

        server, base_url, thread = self._start_server()
        self.addCleanup(self._stop_server, server, thread)

        with patch("korean_anki.push_service.AnkiConnectClient", return_value=FakeDashboardAnkiClient()):
            with urllib.request.urlopen(f"{base_url}/api/dashboard", timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))

        self.assertTrue(payload["status"]["anki_connect_ok"])
        self.assertGreaterEqual(payload["stats"]["local_batch_count"], 2)
        self.assertGreaterEqual(payload["stats"]["local_note_count"], 1)
        self.assertEqual(payload["stats"]["anki_note_count"], 2)
        self.assertEqual(payload["stats"]["anki_card_count"], 3)
        self.assertEqual(payload["stats"]["anki_deck_counts"]["Korean::Lessons::Numbers::Sino"], 2)
        self.assertTrue(any(batch["path"].endswith(".batch.json") for batch in payload["recent_batches"]))
        self.assertFalse(any(batch["path"].endswith(".synced.batch.json") for batch in payload["recent_batches"]))
        self.assertTrue(all("push_status" in batch for batch in payload["recent_batches"]))
        self.assertTrue(all("media_hydrated" in batch for batch in payload["recent_batches"]))
        self.assertTrue(any(context["path"].endswith("transcription.json") for context in payload["lesson_contexts"]))
        self.assertTrue(all("label" in context for context in payload["lesson_contexts"]))
        self.assertTrue(any(path.endswith(".batch.json") for path in payload["syncable_files"]))
        self.assertFalse(any(path.endswith(".lesson.json") for path in payload["syncable_files"]))
        self.assertFalse(any(path.endswith(".synced.batch.json") for path in payload["syncable_files"]))

    def test_dry_run_returns_push_plan(self) -> None:
        server, base_url, thread = self._start_server()
        self.addCleanup(self._stop_server, server, thread)

        batch = make_batch([generate_note(make_item())])
        plan = PushResult(
            deck_name="Korean::Lessons::Basics",
            approved_notes=1,
            approved_cards=3,
            dry_run=True,
            can_push=True,
        )

        with patch("korean_anki.push_service.plan_push", return_value=plan):
            request = urllib.request.Request(
                f"{base_url}/api/push",
                data=json.dumps({"batch": batch.model_dump(mode="json"), "dry_run": True}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))

        self.assertEqual(payload["deck_name"], "Korean::Lessons::Basics")
        self.assertTrue(payload["dry_run"])
        self.assertTrue(payload["can_push"])

    def test_real_push_writes_reviewed_batch_path(self) -> None:
        server, base_url, thread = self._start_server()
        self.addCleanup(self._stop_server, server, thread)

        batch = make_batch([generate_note(make_item())])
        result = PushResult(
            deck_name="Korean::Lessons::Basics",
            approved_notes=1,
            approved_cards=3,
            dry_run=False,
            can_push=True,
            notes_added=1,
            cards_created=3,
            pushed_note_ids=[789],
            sync_requested=True,
            sync_completed=True,
        )

        with patch("korean_anki.push_service.push_batch", return_value=result):
            request = urllib.request.Request(
                f"{base_url}/api/push",
                data=json.dumps({"batch": batch.model_dump(mode="json"), "dry_run": False}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))

        reviewed_batch_path = Path(payload["reviewed_batch_path"])
        self.assertTrue(reviewed_batch_path.exists())
        self.addCleanup(reviewed_batch_path.unlink, missing_ok=True)
        self.assertEqual(payload["notes_added"], 1)
        self.assertEqual(payload["pushed_note_ids"], [789])

    def test_real_push_overwrites_source_batch_path_when_provided(self) -> None:
        server, base_url, thread = self._start_server()
        self.addCleanup(self._stop_server, server, thread)

        batch = make_batch([generate_note(make_item(english="hello edited"))])
        result = PushResult(
            deck_name="Korean::Lessons::Basics",
            approved_notes=1,
            approved_cards=3,
            dry_run=False,
            can_push=True,
            notes_added=1,
            cards_created=3,
        )

        output_dir = Path(self._testMethodName)
        output_path = output_dir / "reviewed.batch.json"
        output_dir.mkdir(exist_ok=True)
        output_path.write_text("stale\n", encoding="utf-8")
        self.addCleanup(output_dir.rmdir)
        self.addCleanup(output_path.unlink, missing_ok=True)

        with patch("korean_anki.push_service.push_batch", return_value=result):
            request = urllib.request.Request(
                f"{base_url}/api/push",
                data=json.dumps(
                    {
                        "batch": batch.model_dump(mode="json"),
                        "dry_run": False,
                        "source_batch_path": str(output_path),
                    }
                ).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))

        self.assertEqual(payload["reviewed_batch_path"], str(output_path.resolve()))
        written = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual(written["notes"][0]["item"]["english"], "hello edited")

    def test_invalid_request_returns_400(self) -> None:
        server, base_url, thread = self._start_server()
        self.addCleanup(self._stop_server, server, thread)

        request = urllib.request.Request(
            f"{base_url}/api/push",
            data=b'{"dry_run": true}',
            headers={"Content-Type": "application/json"},
        )

        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(request, timeout=5)

        self.assertEqual(context.exception.code, 400)

    def test_new_vocab_job_endpoint_returns_async_job(self) -> None:
        server, base_url, thread = self._start_server()
        self.addCleanup(self._stop_server, server, thread)

        with patch("korean_anki.push_service._new_vocab_job", return_value=["data/generated/new-vocab.batch.json"]):
            payload = self._post_json(
                base_url,
                "/api/jobs/new-vocab",
                {"count": 20, "gap_ratio": 0.6, "lesson_context": None, "with_audio": True, "image_quality": "low"},
            )

        self.assertEqual(payload["kind"], "new-vocab")
        finished = self._wait_for_job(base_url, str(payload["id"]))
        self.assertEqual(finished["status"], "succeeded")
        self.assertEqual(finished["output_paths"], ["data/generated/new-vocab.batch.json"])

    def test_new_vocab_job_populates_pronunciations(self) -> None:
        project_root = Path(self._testMethodName)
        project_root.mkdir(exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(project_root, ignore_errors=True))

        proposal_batch = NewVocabProposalBatch(
            proposals=[
                NewVocabProposal(
                    candidate_id="candidate-1",
                    korean="물",
                    english="water",
                    topic_tag="food",
                    example_ko="물을 마셔요.",
                    example_en="I drink water.",
                    proposal_reason="Common A1 noun.",
                    image_prompt="A glass of water.",
                    adjacency_kind="coverage-gap",
                )
            ]
        )

        with (
            patch("korean_anki.push_service._project_root", return_value=project_root),
            patch("korean_anki.push_service._update_job"),
            patch(
                "korean_anki.push_service.build_study_state",
                return_value=StudyState(anki_stats=AnkiStatsSnapshot()),
            ),
            patch("korean_anki.new_vocab.propose_new_vocab", return_value=proposal_batch),
            patch("korean_anki.new_vocab.generate_pronunciations", return_value={"물": "mul"}) as mock_generate_pronunciations,
            patch("korean_anki.push_service.enrich_new_vocab_images", side_effect=lambda document, *_args, **_kwargs: document),
            patch("korean_anki.push_service.enrich_audio", side_effect=lambda document, *_args, **_kwargs: document),
        ):
            output_paths = _new_vocab_job(
                "job-1",
                json.dumps(
                    {
                        "count": 1,
                        "gap_ratio": 1.0,
                        "lesson_context": None,
                        "with_audio": False,
                        "image_quality": "low",
                    }
                ),
            )

        self.assertEqual(len(output_paths), 1)
        output_path = project_root / output_paths[0]
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["notes"][0]["item"]["pronunciation"], "mul")
        mock_generate_pronunciations.assert_called_once_with(["물"], model="gpt-5.4")

    def test_unique_new_vocab_output_path_does_not_overwrite_existing_files(self) -> None:
        output_dir = Path(self._testMethodName) / "data" / "generated"
        output_dir.mkdir(parents=True, exist_ok=True)
        first_path = _unique_new_vocab_output_path(Path(self._testMethodName))
        first_path.write_text("{}\n", encoding="utf-8")
        second_path = _unique_new_vocab_output_path(Path(self._testMethodName))

        self.assertNotEqual(first_path, second_path)
        self.assertEqual(first_path.parent, second_path.parent)

        self.addCleanup(lambda: shutil.rmtree(Path(self._testMethodName), ignore_errors=True))

    def test_sync_media_job_endpoint_returns_async_job(self) -> None:
        server, base_url, thread = self._start_server()
        self.addCleanup(self._stop_server, server, thread)

        with patch("korean_anki.push_service._sync_media_job", return_value=["data/generated/sample.synced.batch.json"]):
            payload = self._post_json(
                base_url,
                "/api/jobs/sync-media",
                {"input_path": "data/samples/numbers.batch.json", "sync_first": True},
            )

        self.assertEqual(payload["kind"], "sync-media")
        finished = self._wait_for_job(base_url, str(payload["id"]))
        self.assertEqual(finished["status"], "succeeded")
        self.assertEqual(finished["output_paths"], ["data/generated/sample.synced.batch.json"])

    def test_lesson_generate_job_endpoint_accepts_multipart_upload(self) -> None:
        server, base_url, thread = self._start_server()
        self.addCleanup(self._stop_server, server, thread)

        boundary = "----korean-anki-test"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="lesson_date"\r\n\r\n'
            "2026-03-24\r\n"
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="title"\r\n\r\n'
            "Numbers\r\n"
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="topic"\r\n\r\n'
            "Numbers\r\n"
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="source_summary"\r\n\r\n'
            "Slide\r\n"
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="images"; filename="lesson.png"\r\n'
            "Content-Type: image/png\r\n\r\n"
        ).encode("utf-8") + b"fake-image" + f"\r\n--{boundary}--\r\n".encode("utf-8")

        request = urllib.request.Request(
            f"{base_url}/api/jobs/lesson-generate",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )

        with patch(
            "korean_anki.push_service._lesson_generate_job",
            return_value=["lessons/2026-03-24-numbers/generated/section.batch.json"],
        ):
            with urllib.request.urlopen(request, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))

        self.assertEqual(payload["kind"], "lesson-generate")
        finished = self._wait_for_job(base_url, str(payload["id"]))
        self.assertEqual(finished["status"], "succeeded")
        self.assertEqual(
            finished["output_paths"],
            ["lessons/2026-03-24-numbers/generated/section.batch.json"],
        )


if __name__ == "__main__":
    unittest.main()
