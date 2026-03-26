from __future__ import annotations

import json
import subprocess
import shutil
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from korean_anki.http_api import PushServiceHandler
from korean_anki.jobs import new_vocab_job
from korean_anki.path_policy import unique_new_vocab_output_path
from korean_anki.schema import (
    AnkiStatsSnapshot,
    MediaAsset,
    NewVocabProposal,
    NewVocabProposalBatch,
    PushResult,
    ServiceStatus,
    StudyState,
)
from korean_anki.settings import (
    DEFAULT_LESSON_AUDIO,
    DEFAULT_NEW_VOCAB_COUNT,
    DEFAULT_NEW_VOCAB_GAP_RATIO,
    DEFAULT_NEW_VOCAB_IMAGE_QUALITY,
    DEFAULT_NEW_VOCAB_TARGET_DECK,
    DEFAULT_NEW_VOCAB_WITH_AUDIO,
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

    def test_batch_endpoint_returns_batch_json_from_project_root(self) -> None:
        project_root = Path(self._testMethodName)
        batch_path = project_root / "data/generated/sample.batch.json"
        batch_path.parent.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(project_root, ignore_errors=True))

        batch = make_batch([generate_note(make_item(korean="오늘", english="today"))])
        batch_path.write_text(batch.model_dump_json(indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        server, base_url, thread = self._start_server()
        self.addCleanup(self._stop_server, server, thread)

        with patch("korean_anki.path_policy.project_root", return_value=project_root.resolve()):
            with urllib.request.urlopen(
                f"{base_url}/api/batch?path=data/generated/sample.batch.json",
                timeout=5,
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))

        self.assertEqual(payload["canonical_batch_path"], "data/generated/sample.batch.json")
        self.assertEqual(payload["preview_batch_path"], "data/generated/sample.batch.json")
        self.assertIsNone(payload["synced_batch_path"])
        self.assertEqual(payload["batch"]["metadata"]["title"], batch.metadata.title)
        self.assertEqual(payload["batch"]["notes"][0]["item"]["korean"], "오늘")

    def test_batch_endpoint_falls_back_to_canonical_when_synced_path_is_missing(self) -> None:
        project_root = Path(self._testMethodName)
        canonical_path = project_root / "data/generated/sample.batch.json"
        canonical_path.parent.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(project_root, ignore_errors=True))

        batch = make_batch([generate_note(make_item(korean="오늘", english="today"))])
        canonical_path.write_text(
            batch.model_dump_json(indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        server, base_url, thread = self._start_server()
        self.addCleanup(self._stop_server, server, thread)

        with patch("korean_anki.path_policy.project_root", return_value=project_root.resolve()):
            with urllib.request.urlopen(
                f"{base_url}/api/batch?path=data/generated/sample.synced.batch.json",
                timeout=5,
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))

        self.assertEqual(payload["canonical_batch_path"], "data/generated/sample.batch.json")
        self.assertEqual(payload["preview_batch_path"], "data/generated/sample.batch.json")
        self.assertIsNone(payload["synced_batch_path"])
        self.assertEqual(payload["batch"]["notes"][0]["item"]["korean"], "오늘")

    def test_batch_endpoint_includes_push_and_hydration_status_for_non_recent_batch(self) -> None:
        project_root = Path(self._testMethodName)
        canonical_path = project_root / "data/generated/sample.batch.json"
        synced_path = project_root / "data/generated/sample.synced.batch.json"
        audio_path = project_root / "data/media/audio/sample.mp3"
        image_path = project_root / "data/media/images/sample.png"
        canonical_path.parent.mkdir(parents=True, exist_ok=True)
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.parent.mkdir(parents=True, exist_ok=True)
        audio_path.write_bytes(b"audio")
        image_path.write_bytes(b"image")
        self.addCleanup(lambda: shutil.rmtree(project_root, ignore_errors=True))

        canonical_batch = make_batch([generate_note(make_item(audio=None, image=None))])
        synced_batch = make_batch(
            [
                generate_note(
                    make_item(
                        audio=MediaAsset(path="data/media/audio/sample.mp3"),
                        image=MediaAsset(path="data/media/images/sample.png"),
                    )
                )
            ]
        )
        canonical_path.write_text(
            canonical_batch.model_dump_json(indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        synced_path.write_text(
            synced_batch.model_dump_json(indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        server, base_url, thread = self._start_server()
        self.addCleanup(self._stop_server, server, thread)

        with (
            patch("korean_anki.path_policy.project_root", return_value=project_root.resolve()),
            patch("korean_anki.http_api.AnkiRepository.note_keys", return_value={canonical_batch.notes[0].note_key}),
        ):
            with urllib.request.urlopen(
                f"{base_url}/api/batch?path=data/generated/sample.synced.batch.json",
                timeout=5,
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))

        self.assertEqual(payload["canonical_batch_path"], "data/generated/sample.batch.json")
        self.assertEqual(payload["preview_batch_path"], "data/generated/sample.synced.batch.json")
        self.assertEqual(payload["synced_batch_path"], "data/generated/sample.synced.batch.json")
        self.assertEqual(payload["push_status"], "pushed")
        self.assertTrue(payload["media_hydrated"])

    def test_media_endpoint_serves_files_from_data_media(self) -> None:
        project_root = Path(self._testMethodName)
        media_path = project_root / "data/media/audio/sample.mp3"
        media_path.parent.mkdir(parents=True, exist_ok=True)
        media_path.write_bytes(b"mp3-bytes")
        self.addCleanup(lambda: shutil.rmtree(project_root, ignore_errors=True))

        server, base_url, thread = self._start_server()
        self.addCleanup(self._stop_server, server, thread)

        with patch("korean_anki.path_policy.project_root", return_value=project_root.resolve()):
            with urllib.request.urlopen(f"{base_url}/media/audio/sample.mp3", timeout=5) as response:
                body = response.read()
                content_type = response.headers.get_content_type()

        self.assertEqual(body, b"mp3-bytes")
        self.assertEqual(content_type, "audio/mpeg")

    def test_open_anki_endpoint_launches_desktop_app(self) -> None:
        server, base_url, thread = self._start_server()
        self.addCleanup(self._stop_server, server, thread)

        request = urllib.request.Request(f"{base_url}/api/open-anki", method="POST")
        with patch("korean_anki.http_api.subprocess.Popen") as mock_popen:
            with urllib.request.urlopen(request, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))

        self.assertEqual(payload, {"ok": True})
        mock_popen.assert_called_once_with(
            ["open", "-a", "Anki"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

    def test_status_endpoint_returns_service_state(self) -> None:
        server, base_url, thread = self._start_server()
        self.addCleanup(self._stop_server, server, thread)

        with patch(
            "korean_anki.http_api.service_status_snapshot",
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

    def test_preview_note_endpoint_refreshes_cards_with_backend_logic(self) -> None:
        server, base_url, thread = self._start_server()
        self.addCleanup(self._stop_server, server, thread)

        item = make_item(item_id="preview-1", korean="오늘", english="today", audio=None, image=None)
        note = generate_note(item)

        payload = self._post_json(
            base_url,
            "/api/preview-note",
            {
                "note": note.model_dump(mode="json"),
                "item": item.model_copy(update={"english": "this day"}).model_dump(mode="json"),
            },
        )

        self.assertEqual(payload["item"]["english"], "this day")
        self.assertEqual(payload["duplicate_status"], "new")
        self.assertEqual(payload["inclusion_reason"], "Edited in preview")
        recognition = next(card for card in payload["cards"] if card["kind"] == "recognition")
        listening = next(card for card in payload["cards"] if card["kind"] == "listening")
        self.assertIn("this day", recognition["back_html"])
        self.assertFalse(listening["approved"])

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

        with (
            patch("korean_anki.snapshots.AnkiConnectClient", return_value=FakeDashboardAnkiClient()),
            patch("korean_anki.snapshots.existing_model_note_keys", return_value=set()),
        ):
            with urllib.request.urlopen(f"{base_url}/api/dashboard", timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))

        self.assertTrue(payload["status"]["anki_connect_ok"])
        self.assertGreaterEqual(payload["stats"]["local_batch_count"], 2)
        self.assertGreaterEqual(payload["stats"]["local_note_count"], 1)
        self.assertEqual(payload["stats"]["anki_note_count"], 2)
        self.assertEqual(payload["stats"]["anki_card_count"], 3)
        self.assertEqual(payload["stats"]["anki_deck_counts"]["Korean::Lessons::Numbers::Sino"], 2)
        self.assertTrue(
            any(
                batch["canonical_batch_path"].endswith(".batch.json")
                for batch in payload["recent_batches"]
            )
        )
        self.assertFalse(
            any(
                batch["canonical_batch_path"].endswith(".synced.batch.json")
                for batch in payload["recent_batches"]
            )
        )
        self.assertTrue(
            all("preview_batch_path" in batch for batch in payload["recent_batches"])
        )
        self.assertTrue(all("push_status" in batch for batch in payload["recent_batches"]))
        self.assertTrue(all("media_hydrated" in batch for batch in payload["recent_batches"]))
        self.assertTrue(any(context["path"].endswith("transcription.json") for context in payload["lesson_contexts"]))
        self.assertTrue(all("label" in context for context in payload["lesson_contexts"]))
        self.assertTrue(any(path.endswith(".batch.json") for path in payload["syncable_files"]))
        self.assertFalse(any(path.endswith(".lesson.json") for path in payload["syncable_files"]))
        self.assertFalse(any(path.endswith(".synced.batch.json") for path in payload["syncable_files"]))
        self.assertEqual(payload["defaults"]["lesson_generate"]["with_audio"], DEFAULT_LESSON_AUDIO)
        self.assertEqual(payload["defaults"]["new_vocab"]["count"], DEFAULT_NEW_VOCAB_COUNT)
        self.assertEqual(payload["defaults"]["new_vocab"]["gap_ratio"], DEFAULT_NEW_VOCAB_GAP_RATIO)
        self.assertEqual(payload["defaults"]["new_vocab"]["with_audio"], DEFAULT_NEW_VOCAB_WITH_AUDIO)
        self.assertEqual(payload["defaults"]["new_vocab"]["image_quality"], DEFAULT_NEW_VOCAB_IMAGE_QUALITY)
        self.assertEqual(payload["defaults"]["new_vocab"]["target_deck"], DEFAULT_NEW_VOCAB_TARGET_DECK)

    def test_dashboard_marks_missing_local_media_as_not_hydrated(self) -> None:
        class FakeDashboardAnkiClient:
            def invoke(self, action: str, **params: object) -> object:
                if action == "version":
                    return 6
                if action in {"findNotes", "findCards", "deckNames"}:
                    return []
                return None

        project_root = Path(self._testMethodName)
        (project_root / "data/generated").mkdir(parents=True, exist_ok=True)
        batch_path = project_root / "data/generated/sample.batch.json"
        batch = make_batch(
            [
                generate_note(
                    make_item(
                        audio=MediaAsset(path="data/media/audio/missing.mp3"),
                        image=MediaAsset(path="data/media/images/missing.png"),
                    )
                )
            ]
        )
        batch_path.write_text(batch.model_dump_json(indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self.addCleanup(lambda: shutil.rmtree(project_root, ignore_errors=True))

        server, base_url, thread = self._start_server()
        self.addCleanup(self._stop_server, server, thread)

        with (
            patch("korean_anki.path_policy.project_root", return_value=project_root.resolve()),
            patch("korean_anki.snapshots.AnkiConnectClient", return_value=FakeDashboardAnkiClient()),
            patch("korean_anki.snapshots.existing_model_note_keys", return_value=set()),
        ):
            with urllib.request.urlopen(f"{base_url}/api/dashboard", timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))

        dashboard_batch = next(
            batch
            for batch in payload["recent_batches"]
            if batch["canonical_batch_path"] == "data/generated/sample.batch.json"
        )
        self.assertFalse(dashboard_batch["media_hydrated"])
        self.assertEqual(
            dashboard_batch["preview_batch_path"],
            "data/generated/sample.batch.json",
        )
        self.assertIsNone(dashboard_batch["synced_batch_path"])

    def test_dashboard_uses_synced_batch_for_hydration_status(self) -> None:
        class FakeDashboardAnkiClient:
            def invoke(self, action: str, **params: object) -> object:
                if action == "version":
                    return 6
                if action in {"findNotes", "findCards", "deckNames"}:
                    return []
                return None

        project_root = Path(self._testMethodName)
        (project_root / "data/generated").mkdir(parents=True, exist_ok=True)
        (project_root / "data/media/audio").mkdir(parents=True, exist_ok=True)
        (project_root / "data/media/images").mkdir(parents=True, exist_ok=True)

        canonical_path = project_root / "data/generated/sample.batch.json"
        synced_path = project_root / "data/generated/sample.synced.batch.json"
        audio_path = project_root / "data/media/audio/sample.mp3"
        image_path = project_root / "data/media/images/sample.png"
        audio_path.write_bytes(b"audio")
        image_path.write_bytes(b"image")

        canonical_batch = make_batch([generate_note(make_item(audio=None, image=None))])
        synced_batch = make_batch(
            [
                generate_note(
                    make_item(
                        audio=MediaAsset(path="data/media/audio/sample.mp3"),
                        image=MediaAsset(path="data/media/images/sample.png"),
                    )
                )
            ]
        )
        canonical_path.write_text(
            canonical_batch.model_dump_json(indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        synced_path.write_text(
            synced_batch.model_dump_json(indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        self.addCleanup(lambda: shutil.rmtree(project_root, ignore_errors=True))

        server, base_url, thread = self._start_server()
        self.addCleanup(self._stop_server, server, thread)

        with (
            patch("korean_anki.path_policy.project_root", return_value=project_root.resolve()),
            patch("korean_anki.snapshots.AnkiConnectClient", return_value=FakeDashboardAnkiClient()),
            patch("korean_anki.snapshots.existing_model_note_keys", return_value=set()),
        ):
            with urllib.request.urlopen(f"{base_url}/api/dashboard", timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))

        dashboard_batch = next(
            batch
            for batch in payload["recent_batches"]
            if batch["canonical_batch_path"] == "data/generated/sample.batch.json"
        )
        self.assertTrue(dashboard_batch["media_hydrated"])
        self.assertEqual(
            dashboard_batch["preview_batch_path"],
            "data/generated/sample.synced.batch.json",
        )
        self.assertEqual(
            dashboard_batch["synced_batch_path"],
            "data/generated/sample.synced.batch.json",
        )
        self.assertEqual(dashboard_batch["push_status"], "not-pushed")

    def test_dashboard_keeps_push_status_separate_from_hydration(self) -> None:
        class FakeDashboardAnkiClient:
            def invoke(self, action: str, **params: object) -> object:
                if action == "version":
                    return 6
                if action in {"findNotes", "findCards", "deckNames"}:
                    return []
                return None

        project_root = Path(self._testMethodName)
        (project_root / "data/generated").mkdir(parents=True, exist_ok=True)

        canonical_path = project_root / "data/generated/sample.batch.json"
        synced_path = project_root / "data/generated/sample.synced.batch.json"
        batch = make_batch([generate_note(make_item())])
        canonical_path.write_text(
            batch.model_dump_json(indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        synced_path.write_text(
            batch.model_dump_json(indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        self.addCleanup(lambda: shutil.rmtree(project_root, ignore_errors=True))

        server, base_url, thread = self._start_server()
        self.addCleanup(self._stop_server, server, thread)

        with (
            patch("korean_anki.path_policy.project_root", return_value=project_root.resolve()),
            patch("korean_anki.snapshots.AnkiConnectClient", return_value=FakeDashboardAnkiClient()),
            patch("korean_anki.snapshots.existing_model_note_keys", return_value={batch.notes[0].note_key}),
        ):
            with urllib.request.urlopen(f"{base_url}/api/dashboard", timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))

        dashboard_batch = next(
            batch
            for batch in payload["recent_batches"]
            if batch["canonical_batch_path"] == "data/generated/sample.batch.json"
        )
        self.assertEqual(dashboard_batch["push_status"], "pushed")
        self.assertEqual(
            dashboard_batch["preview_batch_path"],
            "data/generated/sample.synced.batch.json",
        )
        self.assertEqual(
            dashboard_batch["synced_batch_path"],
            "data/generated/sample.synced.batch.json",
        )

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

        with patch("korean_anki.push_workflow_service.plan_push", return_value=plan):
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

        with patch("korean_anki.push_workflow_service.push_batch", return_value=result):
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

        with patch("korean_anki.push_workflow_service.push_batch", return_value=result):
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

        with patch("korean_anki.jobs.new_vocab_job", return_value=["data/generated/new-vocab.batch.json"]):
            payload = self._post_json(
                base_url,
                "/api/jobs/new-vocab",
                {"count": 20, "gap_ratio": 0.6, "lesson_context": None, "with_audio": True, "image_quality": "low"},
            )
            finished = self._wait_for_job(base_url, str(payload["id"]))

        self.assertEqual(payload["kind"], "new-vocab")
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
            patch("korean_anki.path_policy.project_root", return_value=project_root),
            patch("korean_anki.jobs.update_job"),
            patch("korean_anki.new_vocab_generation_service.study_state_snapshot", return_value=StudyState(anki_stats=AnkiStatsSnapshot())),
            patch("korean_anki.batch_generation_service.study_state_snapshot", return_value=StudyState(anki_stats=AnkiStatsSnapshot())),
            patch("korean_anki.new_vocab.propose_new_vocab", return_value=proposal_batch),
            patch("korean_anki.new_vocab.generate_pronunciations", return_value={"물": "mul"}) as mock_generate_pronunciations,
            patch("korean_anki.new_vocab_generation_service.enrich_new_vocab_images", side_effect=lambda document, *_args, **_kwargs: document),
            patch("korean_anki.new_vocab_generation_service.enrich_audio", side_effect=lambda document, *_args, **_kwargs: document),
        ):
            output_paths = new_vocab_job(
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
        first_path = unique_new_vocab_output_path(Path(self._testMethodName))
        first_path.write_text("{}\n", encoding="utf-8")
        second_path = unique_new_vocab_output_path(Path(self._testMethodName))

        self.assertNotEqual(first_path, second_path)
        self.assertEqual(first_path.parent, second_path.parent)

        self.addCleanup(lambda: shutil.rmtree(Path(self._testMethodName), ignore_errors=True))

    def test_sync_media_job_endpoint_returns_async_job(self) -> None:
        server, base_url, thread = self._start_server()
        self.addCleanup(self._stop_server, server, thread)

        with patch("korean_anki.jobs.sync_media_job", return_value=["data/generated/sample.synced.batch.json"]):
            payload = self._post_json(
                base_url,
                "/api/jobs/sync-media",
                {"input_path": "data/samples/numbers.batch.json", "sync_first": True},
            )
            finished = self._wait_for_job(base_url, str(payload["id"]))

        self.assertEqual(payload["kind"], "sync-media")
        self.assertEqual(finished["status"], "succeeded")
        self.assertEqual(finished["output_paths"], ["data/generated/sample.synced.batch.json"])

    def test_delete_batch_endpoint_deletes_unpushed_batch_and_orphaned_media(self) -> None:
        project_root = Path(self._testMethodName)
        batch_path = project_root / "data" / "generated" / "sample.batch.json"
        synced_path = project_root / "data" / "generated" / "sample.synced.batch.json"
        plan_path = project_root / "data" / "generated" / "sample.batch.generation-plan.json"
        other_synced_path = project_root / "lessons" / "sample" / "generated" / "other.synced.batch.json"
        audio_path = project_root / "data" / "media" / "audio" / "sample.mp3"
        other_audio_path = project_root / "data" / "media" / "audio" / "other.mp3"
        project_root.joinpath("data/generated").mkdir(parents=True, exist_ok=True)
        project_root.joinpath("data/media/audio").mkdir(parents=True, exist_ok=True)
        other_synced_path.parent.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(project_root, ignore_errors=True))

        batch = make_batch(
            [
                generate_note(
                    make_item(audio=MediaAsset(path=str(audio_path.relative_to(project_root))))
                )
            ]
        )
        other_batch = make_batch(
            [
                generate_note(
                    make_item(
                        item_id="item-2",
                        korean="감사합니다",
                        english="thank you",
                        audio=MediaAsset(path=str(other_audio_path.resolve())),
                    )
                )
            ]
        )
        batch_path.write_text(batch.model_dump_json(indent=2) + "\n", encoding="utf-8")
        synced_path.write_text(batch.model_dump_json(indent=2) + "\n", encoding="utf-8")
        plan_path.write_text("{}\n", encoding="utf-8")
        other_synced_path.write_text(other_batch.model_dump_json(indent=2) + "\n", encoding="utf-8")
        audio_path.write_bytes(b"audio")
        other_audio_path.write_bytes(b"other-audio")

        server, base_url, thread = self._start_server()
        self.addCleanup(self._stop_server, server, thread)

        with (
            patch("korean_anki.path_policy.project_root", return_value=project_root.resolve()),
            patch("korean_anki.push_workflow_service.AnkiConnectClient") as mock_client,
            patch("korean_anki.push_workflow_service.existing_model_note_keys", return_value=set()),
        ):
            mock_client.return_value.invoke.return_value = 6
            payload = self._post_json(
                base_url,
                "/api/delete-batch",
                {"batch_path": "data/generated/sample.batch.json"},
            )

        self.assertEqual(
            payload,
            {
                "deleted_paths": [
                    "data/generated/sample.batch.json",
                    "data/generated/sample.synced.batch.json",
                    "data/generated/sample.batch.generation-plan.json",
                ],
                "deleted_media_paths": ["data/media/audio/sample.mp3"],
            },
        )
        self.assertFalse(batch_path.exists())
        self.assertFalse(synced_path.exists())
        self.assertFalse(plan_path.exists())
        self.assertFalse(audio_path.exists())
        self.assertTrue(other_synced_path.exists())
        self.assertTrue(other_audio_path.exists())

    def test_delete_batch_endpoint_blocks_pushed_batch(self) -> None:
        project_root = Path(self._testMethodName)
        batch_path = project_root / "data" / "generated" / "sample.batch.json"
        batch_path.parent.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(project_root, ignore_errors=True))

        batch = make_batch([generate_note(make_item())])
        batch_path.write_text(batch.model_dump_json(indent=2) + "\n", encoding="utf-8")

        server, base_url, thread = self._start_server()
        self.addCleanup(self._stop_server, server, thread)

        with (
            patch("korean_anki.path_policy.project_root", return_value=project_root.resolve()),
            patch("korean_anki.push_workflow_service.AnkiConnectClient") as mock_client,
            patch("korean_anki.push_workflow_service.existing_model_note_keys", return_value={batch.notes[0].note_key}),
        ):
            mock_client.return_value.invoke.return_value = 6
            with self.assertRaises(urllib.error.HTTPError) as context:
                self._post_json(
                    base_url,
                    "/api/delete-batch",
                    {"batch_path": "data/generated/sample.batch.json"},
                )

        self.assertEqual(context.exception.code, 409)
        self.assertTrue(batch_path.exists())

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
            "korean_anki.jobs.lesson_generate_job",
            return_value=["lessons/2026-03-24-numbers/generated/section.batch.json"],
        ):
            with urllib.request.urlopen(request, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
            finished = self._wait_for_job(base_url, str(payload["id"]))

        self.assertEqual(payload["kind"], "lesson-generate")
        self.assertEqual(finished["status"], "succeeded")
        self.assertEqual(
            finished["output_paths"],
            ["lessons/2026-03-24-numbers/generated/section.batch.json"],
        )


if __name__ == "__main__":
    unittest.main()
