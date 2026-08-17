#!/usr/bin/env bash
set -euo pipefail
uv sync --frozen
uv run python -m playwright install --with-deps chromium
uv run crawl4ai-doctor
