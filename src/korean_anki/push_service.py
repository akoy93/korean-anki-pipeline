from __future__ import annotations

import json
import os
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import cast
from urllib.parse import urlparse

from pydantic import ValidationError

from .anki import plan_push, push_batch
from .schema import PushRequest, PushResult


class PushServiceHandler(BaseHTTPRequestHandler):
    server_version = "KoreanAnkiPushService/0.1"

    def _send_json(self, status_code: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if urlparse(self.path).path == "/api/health":
            self._send_json(200, {"ok": True})
            return
        self._send_json(404, {"error": "Not found"})

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/api/push":
            self._send_json(404, {"error": "Not found"})
            return

        fd: int | None = None
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(length).decode("utf-8")
            request = PushRequest.model_validate_json(raw_body)

            if request.dry_run:
                result = plan_push(
                    request.batch,
                    deck_name=request.deck_name,
                    anki_url=request.anki_url,
                )
                self._send_json(200, cast(dict[str, object], result.model_dump()))
                return

            fd, temp_path = tempfile.mkstemp(prefix="korean-anki-reviewed-", suffix=".json")
            Path(temp_path).write_text(
                request.batch.model_dump_json(indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            Path(temp_path).chmod(0o600)

            result = push_batch(
                request.batch,
                deck_name=request.deck_name,
                anki_url=request.anki_url,
                sync=request.sync,
            )
            result = PushResult.model_validate(result.model_dump() | {"reviewed_batch_path": temp_path})
            self._send_json(200, cast(dict[str, object], result.model_dump()))
        except ValidationError as error:
            self._send_json(400, {"error": "Invalid push request.", "details": error.errors()})
        except Exception as error:  # noqa: BLE001
            self._send_json(409, {"error": str(error)})
        finally:
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass

    def log_message(self, format: str, *args: object) -> None:
        print(f"[push-service] {self.address_string()} - {format % args}")


def run_server(host: str = "127.0.0.1", port: int = 8767) -> None:
    server = ThreadingHTTPServer((host, port), PushServiceHandler)
    print(f"Push service listening on http://{host}:{port}")
    print(f"POST /api/push and GET /api/health")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Shutting down push service.")
    finally:
        server.server_close()
