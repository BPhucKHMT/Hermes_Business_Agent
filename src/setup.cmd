@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
if not "%~2"=="" goto usage
if not "%~1"=="" if /I not "%~1"=="--local" goto usage
set "PYTHONPATH="
set "PYTHONHOME="
set "VIRTUAL_ENV="
set "UV_PROJECT_ENVIRONMENT="
set "HERMES_TOOLS=%LOCALAPPDATA%\hermes"
if defined HERMES_HOME set "HERMES_TOOLS=%HERMES_HOME%"
set "PATH=%PATH%;%HERMES_TOOLS%;%HERMES_TOOLS%\bin;%HERMES_TOOLS%\node;%USERPROFILE%\.local\bin;%APPDATA%\npm"
for %%T in (uv node npm) do (
  where %%T >nul 2>&1
  if errorlevel 1 (
    echo ERROR: %%T is missing. Install official Hermes, reopen this window, then retry.
    exit /b 1
  )
)
if /I "%~1"=="--local" (
  where hermes >nul 2>&1
  if errorlevel 1 (
    echo ERROR: Hermes is missing. Install official Hermes before local setup.
    exit /b 1
  )
)
pushd "%SCRIPT_DIR%" || exit /b 1
uv sync --frozen || goto failed
uv run --frozen --no-sync python -m playwright install chromium || goto failed
uv run --frozen --no-sync crawl4ai-doctor || goto failed
uv tool install tavily-cli==0.1.6 || goto failed
call npm install -g agent-browser@0.35.1 || goto failed
call agent-browser install || goto failed
if /I "%~1"=="--local" (
  uv run --frozen --no-sync python setup_local.py --local || goto failed
)
echo Project setup finished. Channel credentials, Google consent and live verification are separate steps.
popd
exit /b 0
:failed
set "RESULT=%ERRORLEVEL%"
if "%RESULT%"=="0" set "RESULT=1"
echo ERROR: Setup stopped. Do not start the gateway until this step succeeds.
popd
exit /b %RESULT%
:usage
echo Usage: setup.cmd [--local]
exit /b 2
