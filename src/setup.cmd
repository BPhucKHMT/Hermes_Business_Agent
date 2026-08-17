@echo off
uv sync --frozen || exit /b 1
uv run python -m playwright install chromium || exit /b 1
uv run crawl4ai-doctor || exit /b 1
