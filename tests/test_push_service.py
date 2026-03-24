from __future__ import annotations

import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from korean_anki.push_service import PushServiceHandler
from korean_anki.schema import PushResult

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

    def test_health_endpoint_returns_ok(self) -> None:
        server, base_url, thread = self._start_server()
        self.addCleanup(self._stop_server, server, thread)

        with urllib.request.urlopen(f"{base_url}/api/health", timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))

        self.assertEqual(payload, {"ok": True})

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


if __name__ == "__main__":
    unittest.main()
