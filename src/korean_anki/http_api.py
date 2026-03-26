from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, cast
from urllib.parse import unquote, urlparse

from pydantic import ValidationError

from . import application, dashboard_service, jobs, path_policy
from .cards import refresh_preview_note
from .schema import DeleteBatchRequest, PreviewNoteRefreshRequest, PushRequest


class PushServiceHandler(BaseHTTPRequestHandler):
    server_version = "KoreanAnkiPushService/0.1"

    def _send_json(self, status_code: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> str:
        length = int(self.headers.get("Content-Length", "0"))
        return self.rfile.read(length).decode("utf-8")

    def _read_multipart(self) -> jobs.MultipartForm:
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length)
        return jobs.MultipartForm.parse(self.headers.get("Content-Type", ""), raw_body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self._send_json(200, {"ok": True})
            return
        if parsed.path == "/api/status":
            self._send_json(200, cast(dict[str, object], dashboard_service.service_status().model_dump()))
            return
        if parsed.path == "/api/dashboard":
            self._send_json(200, cast(dict[str, object], dashboard_service.dashboard_response().model_dump()))
            return
        if parsed.path.startswith("/api/jobs/"):
            job_id = unquote(parsed.path.removeprefix("/api/jobs/"))
            try:
                job = jobs.job_snapshot(job_id)
            except KeyError:
                self._send_json(404, {"error": "Job not found"})
                return
            self._send_json(200, cast(dict[str, object], job.model_dump()))
            return
        self._send_json(404, {"error": "Not found"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/push":
            self._handle_push()
            return
        if parsed.path == "/api/delete-batch":
            self._handle_delete_batch()
            return
        if parsed.path == "/api/preview-note":
            self._handle_preview_note_refresh()
            return
        if parsed.path == "/api/jobs/lesson-generate":
            self._handle_lesson_generate_job()
            return
        if parsed.path == "/api/jobs/new-vocab":
            self._handle_json_job("new-vocab", jobs.new_vocab_job)
            return
        if parsed.path == "/api/jobs/sync-media":
            self._handle_json_job("sync-media", jobs.sync_media_job)
            return
        self._send_json(404, {"error": "Not found"})

    def _handle_push(self) -> None:
        fd: int | None = None
        try:
            request = PushRequest.model_validate_json(self._read_body())
            reviewed_batch_path: str | None = None
            if not request.dry_run:
                fd, reviewed_batch_path = path_policy.resolve_reviewed_batch_path(
                    request.source_batch_path,
                    project_root_path=path_policy.project_root(),
                )

            result = application.handle_push_request(
                request,
                project_root=path_policy.project_root(),
                reviewed_batch_path=reviewed_batch_path,
            )
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

    def _handle_delete_batch(self) -> None:
        try:
            request = DeleteBatchRequest.model_validate_json(self._read_body())
            result = application.delete_batch(
                path_policy.resolve_project_path(request.batch_path, project_root_path=path_policy.project_root()),
                project_root=path_policy.project_root(),
                anki_url=request.anki_url,
            )
            self._send_json(200, cast(dict[str, object], result.model_dump()))
        except ValidationError as error:
            self._send_json(400, {"error": "Invalid delete request.", "details": error.errors()})
        except Exception as error:  # noqa: BLE001
            self._send_json(409, {"error": str(error)})

    def _handle_preview_note_refresh(self) -> None:
        try:
            request = PreviewNoteRefreshRequest.model_validate_json(self._read_body())
            refreshed_note = refresh_preview_note(request.note, request.item)
            self._send_json(200, cast(dict[str, object], refreshed_note.model_dump()))
        except ValidationError as error:
            self._send_json(400, {"error": "Invalid preview-note request.", "details": error.errors()})
        except Exception as error:  # noqa: BLE001
            self._send_json(400, {"error": str(error)})

    def _handle_lesson_generate_job(self) -> None:
        try:
            form = self._read_multipart()
            job = jobs.submit_job("lesson-generate", lambda job_id: jobs.lesson_generate_job(job_id, form))
            self._send_json(202, cast(dict[str, object], job.model_dump()))
        except Exception as error:  # noqa: BLE001
            self._send_json(400, {"error": str(error)})

    def _handle_json_job(self, kind: str, run_job: Callable[[str, str], list[str]]) -> None:
        try:
            raw_body = self._read_body()
            job = jobs.submit_job(kind, lambda job_id: run_job(job_id, raw_body))
            self._send_json(202, cast(dict[str, object], job.model_dump()))
        except ValidationError as error:
            self._send_json(400, {"error": "Invalid job request.", "details": error.errors()})
        except Exception as error:  # noqa: BLE001
            self._send_json(400, {"error": str(error)})

    def log_message(self, format: str, *args: object) -> None:
        print(f"[push-service] {self.address_string()} - {format % args}")


def run_server(host: str = "127.0.0.1", port: int = 8767) -> None:
    server = ThreadingHTTPServer((host, port), PushServiceHandler)
    print(f"Push service listening on http://{host}:{port}")
    print("POST /api/push, POST /api/jobs/*, GET /api/status, GET /api/dashboard, and GET /api/health")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Shutting down push service.")
    finally:
        server.server_close()
