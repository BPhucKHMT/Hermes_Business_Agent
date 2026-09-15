#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_MODE=0
if [[ "${1:-}" == "--local" ]]; then
  LOCAL_MODE=1
  if (($# > 1)); then
    echo "ERROR: setup accepts only the optional --local flag." >&2
    exit 2
  fi
elif (($# > 0)); then
  echo "ERROR: unknown setup option '$1'. Use --local for native CLI/Desktop Google mode." >&2
  exit 2
fi

unset PYTHONPATH PYTHONHOME VIRTUAL_ENV UV_PROJECT_ENVIRONMENT
export PATH="${PATH}:${HOME}/.local/bin"
for tool in node npm; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "ERROR: $tool is missing. Install Node.js before setup." >&2
    exit 1
  fi
done

if ! command -v uv >/dev/null 2>&1; then
  echo "ERROR: uv was not found on PATH. Install uv before running setup." >&2
  exit 1
fi
if ((LOCAL_MODE)) && ! command -v hermes >/dev/null 2>&1; then
  echo "ERROR: Hermes Agent was not found on PATH. Install native Hermes before --local setup." >&2
  exit 1
fi

cd -- "$SCRIPT_DIR"
uv sync --frozen
uv run --frozen --no-sync python -m playwright install --with-deps chromium
uv run --frozen --no-sync crawl4ai-doctor
uv tool install tavily-cli==0.1.6
npm install -g agent-browser@0.35.1
agent-browser install

if ((LOCAL_MODE)); then
  uv run --frozen --no-sync python "$SCRIPT_DIR/setup_local.py" --local
fi
