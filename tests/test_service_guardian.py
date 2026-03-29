from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from korean_anki.schema import ServiceStatus
from korean_anki.service_guardian import (
    TailscaleServiceStatus,
    WatchdogState,
    collect_preview_status,
    collect_service_status,
    collect_tailscale_status,
    run_watchdog_once,
)


class ServiceGuardianTests(unittest.TestCase):
    def _service_status(
        self,
        *,
        backend_ok: bool = True,
        anki_connect_ok: bool = True,
        openai_configured: bool = True,
        preview_ok: bool = True,
        tailscale_ok: bool = True,
    ) -> ServiceStatus:
        return ServiceStatus(
            backend_ok=backend_ok,
            anki_connect_ok=anki_connect_ok,
            anki_connect_version=6 if anki_connect_ok else None,
            openai_configured=openai_configured,
            preview_ok=preview_ok,
            preview_detail="Built preview bundle available at preview/dist." if preview_ok else "Preview build is missing.",
            tailscale_ok=tailscale_ok,
            tailscale_detail="https://alberts-mac-mini.tailnet.test/" if tailscale_ok else "Tailscale is not online.",
            tailscale_dns_name="alberts-mac-mini.tailnet.test" if tailscale_ok else None,
            remote_url="https://alberts-mac-mini.tailnet.test/" if tailscale_ok else None,
        )

    def _tailscale_status(
        self,
        *,
        ok: bool = True,
        daemon_ok: bool = True,
        serve_ok: bool = True,
        key_ttl_ok: bool = True,
    ) -> TailscaleServiceStatus:
        return TailscaleServiceStatus(
            ok=ok,
            detail="https://alberts-mac-mini.tailnet.test/" if ok else "Tailscale is not online.",
            dns_name="alberts-mac-mini.tailnet.test",
            key_expiry_at=None,
            remote_url="https://alberts-mac-mini.tailnet.test/",
            cli_path="/Applications/Tailscale.app/Contents/MacOS/tailscale",
            daemon_ok=daemon_ok,
            serve_ok=serve_ok,
            key_ttl_ok=key_ttl_ok,
        )

    def test_collect_preview_status_requires_built_index(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            status = collect_preview_status(project_root=project_root)

        self.assertFalse(status.ok)
        self.assertIn("preview/dist", status.detail or "")

    def test_collect_tailscale_status_flags_expiring_key(self) -> None:
        with (
            patch("korean_anki.service_guardian.resolve_tailscale_cli", return_value="/fake/tailscale"),
            patch(
                "korean_anki.service_guardian._run_command",
                side_effect=[
                    subprocess.CompletedProcess(
                        args=["tailscale", "status", "--json"],
                        returncode=0,
                        stdout=(
                            '{"BackendState":"Running","Self":{"Online":true,'
                            '"DNSName":"mini.tailnet.test.","KeyExpiry":"2026-03-29T04:32:19Z"}}'
                        ),
                        stderr="",
                    ),
                    subprocess.CompletedProcess(
                        args=["tailscale", "serve", "status", "--json"],
                        returncode=0,
                        stdout='{"handlers":["http://127.0.0.1:8767"]}',
                        stderr="",
                    ),
                ],
            ),
        ):
            status = collect_tailscale_status()

        self.assertFalse(status.ok)
        self.assertFalse(status.key_ttl_ok)
        self.assertIn("remaining key lifetime", status.detail or "")

    def test_collect_service_status_marks_missing_openai_key(self) -> None:
        with (
            patch.dict(os.environ, {}, clear=True),
            patch(
                "korean_anki.service_guardian.collect_preview_status",
                return_value=collect_preview_status(project_root=Path(".")),
            ),
            patch(
                "korean_anki.service_guardian.collect_tailscale_status",
                return_value=self._tailscale_status(),
            ),
            patch("korean_anki.service_guardian.AnkiRepository.service_status", return_value=(True, 6)),
        ):
            status = collect_service_status(project_root=Path("."))

        self.assertFalse(status.openai_configured)

    def test_run_watchdog_restarts_backend_when_health_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            with (
                patch("korean_anki.service_guardian.load_watchdog_state", return_value=WatchdogState()),
                patch("korean_anki.service_guardian.save_watchdog_state"),
                patch("korean_anki.service_guardian.append_watchdog_log"),
                patch("korean_anki.service_guardian.check_backend_health", return_value=False),
                patch(
                    "korean_anki.service_guardian.collect_tailscale_status",
                    return_value=self._tailscale_status(),
                ),
                patch(
                    "korean_anki.service_guardian.collect_service_status",
                    return_value=self._service_status(backend_ok=False),
                ),
                patch(
                    "korean_anki.service_guardian._run_launchctl_kickstart",
                    return_value=subprocess.CompletedProcess(
                        args=["launchctl"],
                        returncode=0,
                        stdout="",
                        stderr="",
                    ),
                ) as mock_kickstart,
            ):
                result = run_watchdog_once(project_root=project_root)

        self.assertIn("restart-backend", result.actions)
        mock_kickstart.assert_called_once()

    def test_run_watchdog_opens_anki_before_relaunch_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            with (
                patch("korean_anki.service_guardian.load_watchdog_state", return_value=WatchdogState()),
                patch("korean_anki.service_guardian.save_watchdog_state"),
                patch("korean_anki.service_guardian.append_watchdog_log"),
                patch("korean_anki.service_guardian.check_backend_health", return_value=True),
                patch(
                    "korean_anki.service_guardian.collect_tailscale_status",
                    return_value=self._tailscale_status(),
                ),
                patch(
                    "korean_anki.service_guardian.collect_service_status",
                    return_value=self._service_status(anki_connect_ok=False),
                ),
                patch("korean_anki.service_guardian._open_app") as mock_open_app,
                patch("korean_anki.service_guardian._quit_anki_gracefully") as mock_quit,
            ):
                result = run_watchdog_once(project_root=project_root)

        self.assertIn("open-anki", result.actions)
        mock_open_app.assert_called_once_with("Anki")
        mock_quit.assert_not_called()

    def test_run_watchdog_relaunches_anki_after_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            with (
                patch(
                    "korean_anki.service_guardian.load_watchdog_state",
                    return_value=WatchdogState(anki_failures=2),
                ),
                patch("korean_anki.service_guardian.save_watchdog_state"),
                patch("korean_anki.service_guardian.append_watchdog_log"),
                patch("korean_anki.service_guardian.check_backend_health", return_value=True),
                patch(
                    "korean_anki.service_guardian.collect_tailscale_status",
                    return_value=self._tailscale_status(),
                ),
                patch(
                    "korean_anki.service_guardian.collect_service_status",
                    return_value=self._service_status(anki_connect_ok=False),
                ),
                patch("korean_anki.service_guardian._quit_anki_gracefully") as mock_quit,
                patch("korean_anki.service_guardian._wait_for_anki_port_to_close", return_value=True),
                patch("korean_anki.service_guardian._kill_anki_process") as mock_kill,
                patch("korean_anki.service_guardian._open_app") as mock_open_app,
            ):
                result = run_watchdog_once(project_root=project_root)

        self.assertIn("relaunch-anki", result.actions)
        mock_quit.assert_called_once()
        mock_kill.assert_not_called()
        mock_open_app.assert_called_once_with("Anki")

    def test_run_watchdog_configures_tailscale_serve_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            with (
                patch("korean_anki.service_guardian.load_watchdog_state", return_value=WatchdogState()),
                patch("korean_anki.service_guardian.save_watchdog_state"),
                patch("korean_anki.service_guardian.append_watchdog_log"),
                patch("korean_anki.service_guardian.check_backend_health", return_value=True),
                patch(
                    "korean_anki.service_guardian.collect_tailscale_status",
                    return_value=self._tailscale_status(ok=False, serve_ok=False),
                ),
                patch(
                    "korean_anki.service_guardian.collect_service_status",
                    return_value=self._service_status(tailscale_ok=False),
                ),
                patch(
                    "korean_anki.service_guardian._run_command",
                    return_value=subprocess.CompletedProcess(
                        args=["tailscale"],
                        returncode=0,
                        stdout="",
                        stderr="",
                    ),
                ) as mock_run_command,
            ):
                result = run_watchdog_once(project_root=project_root)

        self.assertIn("configure-tailscale-serve", result.actions)
        mock_run_command.assert_called_with(
            [
                "/Applications/Tailscale.app/Contents/MacOS/tailscale",
                "serve",
                "--bg",
                "--yes",
                "8767",
            ],
            timeout=15,
        )


if __name__ == "__main__":
    unittest.main()
