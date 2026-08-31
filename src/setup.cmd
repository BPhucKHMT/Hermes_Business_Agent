@echo off
uv sync --frozen || exit /b 1
uv run python -m playwright install chromium || exit /b 1
uv run crawl4ai-doctor || exit /b 1
uv tool install tavily-cli==0.1.6 || exit /b 1
call npm install -g agent-browser@0.35.1 || exit /b 1
call agent-browser install || exit /b 1
