#!/usr/bin/env bash
set -euo pipefail
uv sync --frozen
uv run python -m playwright install --with-deps chromium
uv run crawl4ai-doctor
uv tool install tavily-cli==0.1.6
npm install -g agent-browser@0.35.1
agent-browser install
