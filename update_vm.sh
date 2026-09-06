#!/usr/bin/env bash
# ==============================================================================
# Hermes Business Agent - 1-Click Production Update Script
# Pulls latest code, synchronizes dependencies, and restarts the gateway.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="${SCRIPT_DIR}/src"
HERMES_HOME="${HOME}/.hermes"

echo "======================================================================"
echo "HERMES BUSINESS AGENT - 1-CLICK PRODUCTION UPDATE"
echo "======================================================================"

cd "${SCRIPT_DIR}"

# 1. Pull latest code from GitHub
echo "[STEP 1/3] Pulling latest code from GitHub (git pull)..."
git pull
echo "[OK] Git pull complete."
echo ""

# 2. Synchronize Python virtual environment
echo "[STEP 2/3] Synchronizing Python dependencies (uv sync --frozen)..."
UV_BIN="$(command -v uv || echo "${HOME}/.local/bin/uv")"
cd "${SRC_DIR}"
"${UV_BIN}" sync --frozen
echo "[OK] Dependencies synchronized."
echo ""

# 3. Restart Gateway Daemon
echo "[STEP 3/3] Restarting Hermes Gateway service..."
if command -v systemctl >/dev/null 2>&1 && sudo systemctl is-active --quiet hermes-gateway 2>/dev/null; then
    sudo systemctl restart hermes-gateway
    echo "[OK] hermes-gateway service restarted via systemctl."
else
    hermes gateway restart 2>/dev/null || true
    echo "[OK] Gateway restarted via hermes CLI."
fi

sleep 2

echo ""
echo "======================================================================"
echo "GATEWAY STATUS"
echo "======================================================================"
hermes gateway status 2>/dev/null || true
echo ""
echo "[OK] Update complete."
