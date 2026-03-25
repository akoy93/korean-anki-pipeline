#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
log_dir="$repo_root/.logs"

is_port_open() {
  local port="$1"
  lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
}

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required." >&2
  exit 1
fi

if ! command -v pnpm >/dev/null 2>&1; then
  echo "pnpm is required. Install pnpm, then rerun this script." >&2
  exit 1
fi

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -e .

(
  cd preview
  pnpm install
)

if [ ! -f .env ] && [ -f .env.example ]; then
  cp .env.example .env
  echo "Created .env from .env.example. Set OPENAI_API_KEY before running model-backed commands."
fi

mkdir -p "$log_dir"

if ! is_port_open 8767; then
  nohup python -m korean_anki.cli serve >"$log_dir/push-service.log" 2>&1 &
  echo "Started push backend on http://127.0.0.1:8767"
else
  echo "Push backend already running on http://127.0.0.1:8767"
fi

if ! is_port_open 5173; then
  (
    cd preview
    nohup pnpm dev --host 127.0.0.1 >"$log_dir/preview.log" 2>&1 &
  )
  echo "Started preview app on http://127.0.0.1:5173"
else
  echo "Preview app already running on http://127.0.0.1:5173"
fi

if ! is_port_open 8765; then
  if [ "$(uname -s)" = "Darwin" ]; then
    open -ga Anki >/dev/null 2>&1 || true
    echo "Opened Anki Desktop. AnkiConnect should become available on http://127.0.0.1:8765 once Anki finishes starting."
  else
    echo "AnkiConnect is not available on http://127.0.0.1:8765. Start Anki Desktop manually."
  fi
else
  echo "AnkiConnect already running on http://127.0.0.1:8765"
fi

echo "Bootstrap complete."
