from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
from typing import Any, Callable

import requests

from . import path_policy
from .anki_client import AnkiConnectClient
from .anki_repository import AnkiRepository
from .schema import ServiceStatus
from .settings import (
    DEFAULT_ANKI_URL,
    DEFAULT_PREVIEW_DIST_DIR,
    DEFAULT_PREVIEW_PORT,
    DEFAULT_SELF_HEAL_ANKI_FAILURE_THRESHOLD,
    DEFAULT_SELF_HEAL_ANKI_RELAUNCH_COOLDOWN_MINUTES,
    DEFAULT_SELF_HEAL_BACKEND_LABEL,
    DEFAULT_TAILSCALE_MIN_KEY_TTL_DAYS,
)

TAILSCALE_APP_BINARY = "/Applications/Tailscale.app/Contents/MacOS/tailscale"
TAILSCALE_COMMON_BINARIES = (
    "/usr/local/bin/tailscale",
    "/opt/homebrew/bin/tailscale",
)
ANKI_APP_NAME = "Anki"
TAILSCALE_APP_NAME = "Tailscale"
SELF_HEAL_STATE_PATH = Path("state/self-heal.json")
SELF_HEAL_LOG_PATH = Path(".logs/self-heal.log")
BACKEND_REPAIR_COOLDOWN = timedelta(minutes=2)
TAILSCALE_REPAIR_COOLDOWN = timedelta(minutes=5)
ANKI_PORT_CLOSE_TIMEOUT_SECONDS = 20.0


@dataclass(frozen=True)
class PreviewServiceStatus:
    ok: bool
    detail: str | None
    dist_root: Path


@dataclass(frozen=True)
class TailscaleServiceStatus:
    ok: bool
    detail: str | None
    dns_name: str | None
    key_expiry_at: datetime | None
    remote_url: str | None
    cli_path: str | None
    daemon_ok: bool
    serve_ok: bool
    key_ttl_ok: bool


@dataclass
class WatchdogState:
    anki_failures: int = 0
    last_anki_relaunch_at: str | None = None
    last_backend_repair_at: str | None = None
    last_tailscale_open_at: str | None = None
    last_tailscale_serve_at: str | None = None
    last_status_signature: str | None = None


@dataclass(frozen=True)
class WatchdogRunResult:
    status: ServiceStatus
    actions: tuple[str, ...]


def preview_dist_root(*, project_root: Path | None = None) -> Path:
    root = (project_root or path_policy.project_root()).resolve()
    return (root / DEFAULT_PREVIEW_DIST_DIR).resolve()


def collect_preview_status(*, project_root: Path | None = None) -> PreviewServiceStatus:
    dist_root = preview_dist_root(project_root=project_root)
    index_path = dist_root / "index.html"
    if not dist_root.exists():
        return PreviewServiceStatus(
            ok=False,
            detail=f"Preview build is missing at {DEFAULT_PREVIEW_DIST_DIR}.",
            dist_root=dist_root,
        )
    if not index_path.is_file():
        return PreviewServiceStatus(
            ok=False,
            detail="Preview build is incomplete: preview/dist/index.html is missing.",
            dist_root=dist_root,
        )
    return PreviewServiceStatus(
        ok=True,
        detail=f"Built preview bundle available at {DEFAULT_PREVIEW_DIST_DIR}.",
        dist_root=dist_root,
    )


def resolve_tailscale_cli(explicit_path: str | None = None) -> str | None:
    if explicit_path is not None:
        resolved = Path(explicit_path).expanduser()
        return str(resolved) if resolved.is_file() else None

    system_path = shutil.which("tailscale")
    if system_path is not None:
        return system_path

    for candidate in TAILSCALE_COMMON_BINARIES:
        candidate_path = Path(candidate)
        if candidate_path.is_file():
            return str(candidate_path)

    bundled_path = Path(TAILSCALE_APP_BINARY)
    if bundled_path.is_file():
        return str(bundled_path)
    return None


def _run_command(args: list[str], *, timeout: float = 5.0) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout if isinstance(error.stdout, str) else ""
        stderr = error.stderr if isinstance(error.stderr, str) else ""
        timeout_message = f"Command timed out after {timeout:.1f}s: {' '.join(args)}"
        return subprocess.CompletedProcess(
            args=args,
            returncode=124,
            stdout=stdout,
            stderr=f"{stderr}\n{timeout_message}".strip(),
        )


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None or value in {"", "0001-01-01T00:00:00Z"}:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _format_local_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def _json_mentions_port(payload: Any, port: int) -> bool:
    if isinstance(payload, dict):
        return any(_json_mentions_port(value, port) for value in payload.values())
    if isinstance(payload, list):
        return any(_json_mentions_port(value, port) for value in payload)
    if isinstance(payload, int):
        return payload == port
    if isinstance(payload, str):
        return payload == str(port) or f":{port}" in payload
    return False


def collect_tailscale_status(
    *,
    tailscale_bin: str | None = None,
    expected_port: int = DEFAULT_PREVIEW_PORT,
    min_key_ttl_days: int = DEFAULT_TAILSCALE_MIN_KEY_TTL_DAYS,
    now: datetime | None = None,
) -> TailscaleServiceStatus:
    cli_path = resolve_tailscale_cli(tailscale_bin)
    if cli_path is None:
        return TailscaleServiceStatus(
            ok=False,
            detail="Tailscale CLI was not found.",
            dns_name=None,
            key_expiry_at=None,
            remote_url=None,
            cli_path=None,
            daemon_ok=False,
            serve_ok=False,
            key_ttl_ok=False,
        )

    status_process = _run_command([cli_path, "status", "--json"])
    if status_process.returncode != 0:
        detail = status_process.stderr.strip() or status_process.stdout.strip() or "Tailscale status failed."
        return TailscaleServiceStatus(
            ok=False,
            detail=detail,
            dns_name=None,
            key_expiry_at=None,
            remote_url=None,
            cli_path=cli_path,
            daemon_ok=False,
            serve_ok=False,
            key_ttl_ok=False,
        )

    try:
        payload = json.loads(status_process.stdout or "{}")
    except json.JSONDecodeError:
        return TailscaleServiceStatus(
            ok=False,
            detail="Tailscale status returned invalid JSON.",
            dns_name=None,
            key_expiry_at=None,
            remote_url=None,
            cli_path=cli_path,
            daemon_ok=False,
            serve_ok=False,
            key_ttl_ok=False,
        )

    self_info = payload.get("Self", {}) if isinstance(payload, dict) else {}
    backend_state = payload.get("BackendState") if isinstance(payload, dict) else None
    daemon_ok = backend_state == "Running" and bool(isinstance(self_info, dict) and self_info.get("Online"))
    dns_name = self_info.get("DNSName") if isinstance(self_info, dict) and isinstance(self_info.get("DNSName"), str) else None
    key_expiry_at = _parse_datetime(self_info.get("KeyExpiry") if isinstance(self_info, dict) else None)
    remote_url = f"https://{dns_name.removesuffix('.')}/" if dns_name else None

    serve_ok = False
    if daemon_ok:
        serve_process = _run_command([cli_path, "serve", "status", "--json"])
        if serve_process.returncode == 0:
            try:
                serve_payload = json.loads(serve_process.stdout or "{}")
            except json.JSONDecodeError:
                serve_payload = {}
            serve_ok = _json_mentions_port(serve_payload, expected_port)

    now_utc = now or datetime.now(timezone.utc)
    min_key_ttl = timedelta(days=min_key_ttl_days)
    key_ttl_ok = key_expiry_at is None or (key_expiry_at - now_utc) >= min_key_ttl

    if not daemon_ok:
        detail = "Tailscale is not online."
    elif not key_ttl_ok:
        detail = (
            f"Tailscale node key expires at {_format_local_datetime(key_expiry_at)}; "
            f"unattended mode requires at least {min_key_ttl_days} days of remaining key lifetime."
        )
    elif not serve_ok:
        detail = f"Tailscale Serve is not proxying local port {expected_port}."
    else:
        detail = remote_url or "Tailscale is online."

    return TailscaleServiceStatus(
        ok=daemon_ok and serve_ok and key_ttl_ok,
        detail=detail,
        dns_name=dns_name.removesuffix(".") if dns_name else None,
        key_expiry_at=key_expiry_at,
        remote_url=remote_url,
        cli_path=cli_path,
        daemon_ok=daemon_ok,
        serve_ok=serve_ok,
        key_ttl_ok=key_ttl_ok,
    )


def collect_service_status(
    *,
    project_root: Path | None = None,
    anki_url: str = DEFAULT_ANKI_URL,
    client_factory: Callable[..., object] | None = None,
    note_keys_loader: Callable[..., set[str]] | None = None,
    openai_configured: bool | None = None,
    tailscale_bin: str | None = None,
    backend_ok: bool = True,
) -> ServiceStatus:
    root = (project_root or path_policy.project_root()).resolve()
    preview = collect_preview_status(project_root=root)
    tailscale = collect_tailscale_status(tailscale_bin=tailscale_bin)
    anki_repository = AnkiRepository(
        anki_url,
        client_factory=client_factory or AnkiConnectClient,
        note_keys_loader=note_keys_loader,
    )
    anki_connect_ok, anki_connect_version = anki_repository.service_status()
    configured = bool(os.environ.get("OPENAI_API_KEY")) if openai_configured is None else openai_configured
    return ServiceStatus(
        backend_ok=backend_ok,
        anki_connect_ok=anki_connect_ok,
        anki_connect_version=anki_connect_version,
        openai_configured=configured,
        preview_ok=preview.ok,
        preview_detail=preview.detail,
        tailscale_ok=tailscale.ok,
        tailscale_detail=tailscale.detail,
        tailscale_dns_name=tailscale.dns_name,
        tailscale_key_expiry_at=tailscale.key_expiry_at,
        remote_url=tailscale.remote_url,
    )


def _state_path(project_root: Path) -> Path:
    return (project_root / SELF_HEAL_STATE_PATH).resolve()


def _log_path(project_root: Path) -> Path:
    return (project_root / SELF_HEAL_LOG_PATH).resolve()


def load_watchdog_state(project_root: Path) -> WatchdogState:
    state_path = _state_path(project_root)
    if not state_path.exists():
        return WatchdogState()
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return WatchdogState()
    if not isinstance(payload, dict):
        return WatchdogState()
    return WatchdogState(
        anki_failures=int(payload.get("anki_failures", 0)),
        last_anki_relaunch_at=payload.get("last_anki_relaunch_at"),
        last_backend_repair_at=payload.get("last_backend_repair_at"),
        last_tailscale_open_at=payload.get("last_tailscale_open_at"),
        last_tailscale_serve_at=payload.get("last_tailscale_serve_at"),
        last_status_signature=payload.get("last_status_signature"),
    )


def save_watchdog_state(project_root: Path, state: WatchdogState) -> None:
    state_path = _state_path(project_root)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(asdict(state), indent=2) + "\n", encoding="utf-8")


def append_watchdog_log(project_root: Path, message: str) -> None:
    log_path = _log_path(project_root)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] {message}\n")


def _parse_state_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _should_run_action(last_run_at: str | None, *, now: datetime, cooldown: timedelta) -> bool:
    parsed = _parse_state_datetime(last_run_at)
    if parsed is None:
        return True
    return (now - parsed) >= cooldown


def _port_is_open(host: str, port: int, *, timeout: float = 1.0) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        connection.settimeout(timeout)
        return connection.connect_ex((host, port)) == 0


def check_backend_health(*, port: int = DEFAULT_PREVIEW_PORT) -> bool:
    try:
        response = requests.get(f"http://127.0.0.1:{port}/api/health", timeout=3)
    except requests.RequestException:
        return False
    if not response.ok:
        return False
    try:
        payload = response.json()
    except ValueError:
        return False
    return isinstance(payload, dict) and payload.get("ok") is True


def _run_launchctl_kickstart(label: str) -> subprocess.CompletedProcess[str]:
    return _run_command(
        ["launchctl", "kickstart", "-k", f"gui/{os.getuid()}/{label}"],
        timeout=15,
    )


def _open_app(app_name: str) -> None:
    _run_command(["open", "-ga", app_name])


def _quit_anki_gracefully() -> None:
    _run_command(
        [
            "osascript",
            "-e",
            f'tell application "{ANKI_APP_NAME}" to quit',
        ],
        timeout=10,
    )


def _kill_anki_process() -> None:
    _run_command(["pkill", "-f", "aqt.run"], timeout=10)


def _wait_for_anki_port_to_close(timeout_seconds: float) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if not _port_is_open("127.0.0.1", 8765):
            return True
        time.sleep(0.5)
    return not _port_is_open("127.0.0.1", 8765)


def run_watchdog_once(
    *,
    project_root: Path | None = None,
    anki_url: str = DEFAULT_ANKI_URL,
    backend_label: str = DEFAULT_SELF_HEAL_BACKEND_LABEL,
    tailscale_bin: str | None = None,
    repair: bool = True,
) -> WatchdogRunResult:
    root = (project_root or path_policy.project_root()).resolve()
    state = load_watchdog_state(root)
    now = datetime.now().astimezone()
    actions: list[str] = []
    backend_ok = check_backend_health()
    tailscale = collect_tailscale_status(tailscale_bin=tailscale_bin)
    status = collect_service_status(
        project_root=root,
        anki_url=anki_url,
        openai_configured=None,
        tailscale_bin=tailscale.cli_path,
        backend_ok=backend_ok,
    )

    signature = json.dumps(
        {
            "backend_ok": status.backend_ok,
            "anki_connect_ok": status.anki_connect_ok,
            "anki_connect_version": status.anki_connect_version,
            "openai_configured": status.openai_configured,
            "preview_ok": status.preview_ok,
            "preview_detail": status.preview_detail,
            "tailscale_ok": status.tailscale_ok,
            "tailscale_detail": status.tailscale_detail,
            "tailscale_dns_name": status.tailscale_dns_name,
            "remote_url": status.remote_url,
        },
        sort_keys=True,
    )
    if signature != state.last_status_signature:
        append_watchdog_log(root, f"Service status changed: {signature}")
        state.last_status_signature = signature

    if status.anki_connect_ok:
        state.anki_failures = 0
    else:
        state.anki_failures += 1

    if repair and not backend_ok and _should_run_action(
        state.last_backend_repair_at,
        now=now,
        cooldown=BACKEND_REPAIR_COOLDOWN,
    ):
        backend_repair = _run_launchctl_kickstart(backend_label)
        state.last_backend_repair_at = now.isoformat()
        if backend_repair.returncode == 0:
            actions.append("restart-backend")
            append_watchdog_log(root, f"Restarted backend launch agent {backend_label}.")
        else:
            append_watchdog_log(
                root,
                "Backend restart attempt failed: "
                f"{backend_repair.stderr.strip() or backend_repair.stdout.strip() or backend_repair.returncode}",
            )

    if repair and not status.anki_connect_ok:
        if state.anki_failures < DEFAULT_SELF_HEAL_ANKI_FAILURE_THRESHOLD:
            _open_app(ANKI_APP_NAME)
            actions.append("open-anki")
            append_watchdog_log(root, f"Opened {ANKI_APP_NAME} after AnkiConnect failure {state.anki_failures}.")
        elif _should_run_action(
            state.last_anki_relaunch_at,
            now=now,
            cooldown=timedelta(minutes=DEFAULT_SELF_HEAL_ANKI_RELAUNCH_COOLDOWN_MINUTES),
        ):
            _quit_anki_gracefully()
            if not _wait_for_anki_port_to_close(ANKI_PORT_CLOSE_TIMEOUT_SECONDS):
                _kill_anki_process()
                _wait_for_anki_port_to_close(5.0)
            _open_app(ANKI_APP_NAME)
            state.last_anki_relaunch_at = now.isoformat()
            actions.append("relaunch-anki")
            append_watchdog_log(root, "Relaunched Anki after repeated AnkiConnect failures.")

    if repair and tailscale.cli_path is not None and not tailscale.serve_ok and _should_run_action(
        state.last_tailscale_serve_at,
        now=now,
        cooldown=TAILSCALE_REPAIR_COOLDOWN,
    ):
        tailscale_serve = _run_command(
            [tailscale.cli_path, "serve", "--bg", "--yes", str(DEFAULT_PREVIEW_PORT)],
            timeout=15,
        )
        state.last_tailscale_serve_at = now.isoformat()
        if tailscale_serve.returncode == 0:
            actions.append("configure-tailscale-serve")
            append_watchdog_log(root, f"Configured Tailscale Serve for local port {DEFAULT_PREVIEW_PORT}.")
        else:
            append_watchdog_log(
                root,
                "Tailscale Serve configuration failed: "
                f"{tailscale_serve.stderr.strip() or tailscale_serve.stdout.strip() or tailscale_serve.returncode}",
            )

    if repair and tailscale.cli_path is not None and not tailscale.daemon_ok and _should_run_action(
        state.last_tailscale_open_at,
        now=now,
        cooldown=TAILSCALE_REPAIR_COOLDOWN,
    ):
        _open_app(TAILSCALE_APP_NAME)
        state.last_tailscale_open_at = now.isoformat()
        actions.append("open-tailscale")
        append_watchdog_log(root, f"Opened {TAILSCALE_APP_NAME} because Tailscale was offline.")

    save_watchdog_state(root, state)
    return WatchdogRunResult(status=status, actions=tuple(actions))
