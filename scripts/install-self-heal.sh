#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

backend_label="com.albertkoy.korean-anki.backend"
watchdog_label="com.albertkoy.korean-anki.watchdog"
launch_agents_dir="$HOME/Library/LaunchAgents"
backend_plist="$launch_agents_dir/${backend_label}.plist"
watchdog_plist="$launch_agents_dir/${watchdog_label}.plist"
python_bin="$repo_root/.venv/bin/python"
log_dir="$repo_root/.logs"
uid="$(id -u)"

fail() {
  echo "$1" >&2
  exit 1
}

if [ "$(uname -s)" != "Darwin" ]; then
  fail "install-self-heal.sh only supports macOS launchd."
fi

if [ ! -x "$python_bin" ]; then
  fail "Missing $python_bin. Create the virtualenv first."
fi

if ! command -v pnpm >/dev/null 2>&1; then
  fail "pnpm is required to build the unattended preview bundle."
fi

if [ ! -f "$repo_root/.env" ]; then
  fail "Missing $repo_root/.env. Copy .env.example and set OPENAI_API_KEY first."
fi

if ! grep -Eq '^OPENAI_API_KEY=.+$' "$repo_root/.env"; then
  fail "OPENAI_API_KEY is missing or empty in $repo_root/.env."
fi

tailscale_bin="$(command -v tailscale || true)"
if [ -z "$tailscale_bin" ] && [ -x /Applications/Tailscale.app/Contents/MacOS/tailscale ]; then
  tailscale_bin=/Applications/Tailscale.app/Contents/MacOS/tailscale
fi
if [ -z "$tailscale_bin" ]; then
  fail "Tailscale CLI was not found. Install the macOS app first."
fi

status_json="$("$tailscale_bin" status --json)"
remote_url="$(
  STATUS_JSON="$status_json" python3 - <<'PY'
import json
import os
import sys
from datetime import datetime, timedelta, timezone

payload = json.loads(os.environ["STATUS_JSON"])
self_info = payload.get("Self") or {}
key_expiry_raw = self_info.get("KeyExpiry")
dns_name = (self_info.get("DNSName") or "").rstrip(".")

key_expiry = None
if key_expiry_raw and key_expiry_raw != "0001-01-01T00:00:00Z":
    key_expiry = datetime.fromisoformat(key_expiry_raw.replace("Z", "+00:00"))

if key_expiry is not None and key_expiry - datetime.now(timezone.utc) < timedelta(days=7):
    local_expiry = key_expiry.astimezone().strftime("%B %d, %Y %I:%M:%S %p %Z")
    sys.stderr.write(
        "Tailscale node key expires too soon for unattended mode: "
        f"{local_expiry}. Disable key expiry or reauthenticate before installing.\n"
    )
    sys.exit(1)

print(f"https://{dns_name}/" if dns_name else "")
PY
)" || fail "Tailscale preflight failed. See the error above."

mkdir -p "$log_dir" "$launch_agents_dir"

echo "Building unattended preview bundle..."
(
  cd "$repo_root/preview"
  pnpm build
)

cat >"$backend_plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>$backend_label</string>
    <key>ProgramArguments</key>
    <array>
      <string>$python_bin</string>
      <string>-m</string>
      <string>korean_anki.cli</string>
      <string>serve</string>
      <string>--host</string>
      <string>127.0.0.1</string>
      <string>--port</string>
      <string>8767</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
      <key>PYTHONPATH</key>
      <string>$repo_root/src</string>
    </dict>
    <key>WorkingDirectory</key>
    <string>$repo_root</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$log_dir/backend.launchd.out.log</string>
    <key>StandardErrorPath</key>
    <string>$log_dir/backend.launchd.err.log</string>
  </dict>
</plist>
EOF

cat >"$watchdog_plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>$watchdog_label</string>
    <key>ProgramArguments</key>
    <array>
      <string>$python_bin</string>
      <string>-m</string>
      <string>korean_anki.cli</string>
      <string>watchdog</string>
      <string>--backend-label</string>
      <string>$backend_label</string>
      <string>--tailscale-bin</string>
      <string>$tailscale_bin</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
      <key>PYTHONPATH</key>
      <string>$repo_root/src</string>
    </dict>
    <key>WorkingDirectory</key>
    <string>$repo_root</string>
    <key>RunAtLoad</key>
    <true/>
    <key>StartInterval</key>
    <integer>60</integer>
    <key>StandardOutPath</key>
    <string>$log_dir/watchdog.launchd.out.log</string>
    <key>StandardErrorPath</key>
    <string>$log_dir/watchdog.launchd.err.log</string>
  </dict>
</plist>
EOF

launchctl bootout "gui/$uid" "$backend_plist" >/dev/null 2>&1 || true
launchctl bootout "gui/$uid" "$watchdog_plist" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$uid" "$backend_plist"
launchctl bootstrap "gui/$uid" "$watchdog_plist"
launchctl kickstart -k "gui/$uid/$backend_label"

serve_output="$(
  TAILSCALE_BIN="$tailscale_bin" "$python_bin" - <<'PY'
import os
import subprocess
import sys

tailscale_bin = os.environ["TAILSCALE_BIN"]
try:
    result = subprocess.run(
        [tailscale_bin, "serve", "--bg", "--yes", "8767"],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
except subprocess.TimeoutExpired as error:
    stderr = error.stderr if isinstance(error.stderr, str) else ""
    stdout = error.stdout if isinstance(error.stdout, str) else ""
    sys.stderr.write((stderr or stdout or "Timed out configuring Tailscale Serve.") + "\n")
    sys.exit(1)

if result.returncode != 0:
    sys.stderr.write(result.stderr or result.stdout or f"Tailscale Serve failed with exit code {result.returncode}.\n")
    sys.exit(result.returncode)
PY
)" || {
  [ -n "$serve_output" ] && echo "$serve_output" >&2
  fail "Failed to configure Tailscale Serve. Enable Serve for this tailnet in the Tailscale admin console, then rerun the installer."
}

pmset_output="$(pmset -g)"
if printf '%s\n' "$pmset_output" | grep -Eq '^[[:space:]]*autorestart[[:space:]]+0$'; then
  echo "Warning: current power settings show autorestart 0. Enable restart-after-power-failure separately for true unattended recovery." >&2
fi

echo "Installed launch agents:"
echo "  $backend_plist"
echo "  $watchdog_plist"
echo "Remote preview URL: ${remote_url:-"(Tailscale DNS unavailable)"}"
echo "Unattended mode is installed. Keep a logged-in macOS user session available so Anki can relaunch after reboot."
