from __future__ import annotations

import json
import mimetypes
import os
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, cast
from urllib.parse import parse_qs, unquote, urlparse

from pydantic import ValidationError

from . import dashboard_service, jobs, path_policy
from .anki_client import AnkiConnectClient
from .anki_queries import existing_model_note_keys
from .anki_repository import AnkiRepository
from .batch_repository import BatchRepository
from .cards import refresh_preview_note
from .push_workflow_service import delete_batch, handle_push_request
from .schema import (
    BatchPreviewResponse,
    CardBatch,
    DeleteBatchRequest,
    PreviewNoteRefreshRequest,
    PushRequest,
)
from .snapshots import batch_media_hydrated, batch_push_status
from .settings import DEFAULT_ANKI_URL, DEFAULT_PREVIEW_HOST, DEFAULT_PREVIEW_PORT


class PushServiceHandler(BaseHTTPRequestHandler):
    server_version = "KoreanAnkiPushService/0.1"

    def _send_json(self, status_code: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self._send_bytes(status_code, body, content_type="application/json; charset=utf-8")

    def _send_bytes(self, status_code: int, body: bytes, *, content_type: str) -> None:
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
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
        if parsed.path.startswith("/media/"):
            self._handle_media_request(parsed.path)
            return
        if parsed.path == "/api/health":
            self._send_json(200, {"ok": True})
            return
        if parsed.path == "/api/status":
            self._send_json(200, cast(dict[str, object], dashboard_service.service_status().model_dump()))
            return
        if parsed.path == "/api/dashboard":
            self._send_json(200, cast(dict[str, object], dashboard_service.dashboard_response().model_dump()))
            return
        if parsed.path == "/api/batch":
            self._handle_batch_request(parsed.query)
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
        if parsed.path == "/api/open-anki":
            self._handle_open_anki()
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

            result = handle_push_request(
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
            result = delete_batch(
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

    def _handle_batch_request(self, raw_query: str) -> None:
        requested_path = parse_qs(raw_query).get("path", [None])[0]
        if requested_path is None or requested_path.strip() == "":
            self._send_json(400, {"error": "Missing path query parameter."})
            return
        if not requested_path.endswith(".batch.json"):
            self._send_json(400, {"error": "Only .batch.json files are supported."})
            return

        project_root = path_policy.project_root()
        try:
            resolved_path = path_policy.resolve_project_path(
                requested_path,
                project_root_path=project_root,
            )
        except ValueError as error:
            self._send_json(403 if "escapes" in str(error) else 400, {"error": str(error)})
            return

        try:
            batch_paths = path_policy.batch_path_identity(resolved_path)
        except FileNotFoundError:
            self._send_json(404, {"error": "Batch file not found."})
            return
        except ValueError as error:
            self._send_json(400, {"error": str(error)})
            return

        try:
            batch_repository = BatchRepository(project_root)
            batch = BatchPreviewResponse(
                batch=CardBatch.model_validate_json(
                    batch_paths.preview_path.read_text(encoding="utf-8")
                ),
                canonical_batch_path=str(batch_paths.canonical_path.relative_to(project_root)),
                preview_batch_path=str(batch_paths.preview_path.relative_to(project_root)),
                synced_batch_path=(
                    str(batch_paths.synced_path.relative_to(project_root))
                    if batch_paths.synced_path is not None
                    else None
                ),
                push_status=batch_push_status(
                    batch_repository.load_batch(batch_paths.canonical_path),
                    note_keys=AnkiRepository(
                        DEFAULT_ANKI_URL,
                        client_factory=AnkiConnectClient,
                        note_keys_loader=existing_model_note_keys,
                    ).note_keys(),
                ),
                media_hydrated=batch_media_hydrated(
                    batch_paths.preview_path,
                    project_root=project_root,
                    batch_repository=batch_repository,
                ),
            )
        except (OSError, ValidationError) as error:
            self._send_json(500, {"error": str(error)})
            return

        self._send_json(200, cast(dict[str, object], batch.model_dump(mode="json")))

    def _handle_media_request(self, request_path: str) -> None:
        relative_path = unquote(request_path.removeprefix("/media/"))
        if relative_path.strip() == "":
            self._send_json(404, {"error": "Not found"})
            return

        try:
            resolved_path = path_policy.resolve_media_path(
                relative_path,
                project_root_path=path_policy.project_root(),
            )
        except ValueError as error:
            self._send_json(403 if "escapes" in str(error) else 400, {"error": str(error)})
            return

        if not resolved_path.exists() or not resolved_path.is_file():
            self._send_json(404, {"error": "Media file not found."})
            return

        try:
            body = resolved_path.read_bytes()
        except OSError as error:
            self._send_json(500, {"error": str(error)})
            return

        content_type = mimetypes.guess_type(str(resolved_path))[0] or "application/octet-stream"
        self._send_bytes(200, body, content_type=content_type)

    def _handle_open_anki(self) -> None:
        try:
            subprocess.Popen(  # noqa: S603
                ["open", "-a", "Anki"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as error:
            self._send_json(500, {"error": str(error)})
            return

        self._send_json(200, {"ok": True})

    def log_message(self, format: str, *args: object) -> None:
        print(f"[push-service] {self.address_string()} - {format % args}")


def run_server(host: str = DEFAULT_PREVIEW_HOST, port: int = DEFAULT_PREVIEW_PORT) -> None:
    server = ThreadingHTTPServer((host, port), PushServiceHandler)
    print(f"Push service listening on http://{host}:{port}")
    print(
        "GET /media/*, GET /api/batch, POST /api/open-anki, POST /api/push, "
        "POST /api/jobs/*, GET /api/status, GET /api/dashboard, and GET /api/health"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Shutting down push service.")
    finally:
        server.server_close()
