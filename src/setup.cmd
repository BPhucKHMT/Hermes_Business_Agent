@echo off
set "SCRIPT_DIR=%~dp0"
where uv >nul 2>&1
if errorlevel 1 (
  echo ERROR: uv was not found on PATH. Install uv before running setup.
  exit /b 1
)
if /I "%~1"=="--local" (
  if not "%~2"=="" (
    echo ERROR: setup accepts only the optional --local flag.
    exit /b 2
  )
  where hermes >nul 2>&1
  if errorlevel 1 (
    echo ERROR: Hermes Agent was not found on PATH. Install native Hermes before --local setup.
    exit /b 1
  )
)
if not "%~1"=="" if /I not "%~1"=="--local" (
  echo ERROR: unknown setup option "%~1". Use --local for native CLI/Desktop Google mode.
  exit /b 2
)
uv sync --frozen || exit /b 1
uv run python -m playwright install chromium || exit /b 1
uv run crawl4ai-doctor || exit /b 1
uv tool install tavily-cli==0.1.6 || exit /b 1
call npm install -g agent-browser@0.35.1 || exit /b 1
call agent-browser install || exit /b 1
if /I "%~1"=="--local" (
  uv run --frozen python "%SCRIPT_DIR%setup_local.py" --local || exit /b 1
)
