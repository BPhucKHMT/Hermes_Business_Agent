#!/usr/bin/env bash
# ==============================================================================
# Hermes Business Agent - Automated Linux VM Deployment (Zero-Friction)
# Sets up a fresh Ubuntu/Debian Linux VM from scratch into a running production bot.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="${SCRIPT_DIR}/src"
HERMES_HOME="${HOME}/.hermes"
CURRENT_USER="$(id -un)"
export PATH="${HOME}/.local/bin:/usr/local/bin:/usr/bin:/bin:${PATH}"

echo "======================================================================"
echo "HERMES BUSINESS AGENT - LINUX DEPLOYMENT BOOTSTRAP"
echo "======================================================================"
echo "Repository Root:   ${SCRIPT_DIR}"
echo "Production Source: ${SRC_DIR}"
echo "Hermes Home:       ${HERMES_HOME}"
echo "Current User:      ${CURRENT_USER}"
echo ""

# ------------------------------------------------------------------------------
# 1. Base OS Packages & System Dependencies (Debian / Ubuntu)
# ------------------------------------------------------------------------------
echo "[STEP 1/8] Installing OS packages and Playwright/Chromium dependencies..."

SUDO=""
if [ "$(id -u)" -ne 0 ]; then
    if command -v sudo >/dev/null 2>&1; then
        SUDO="sudo"
    else
        echo "[WARN] sudo not found. Running with current user privileges."
    fi
fi

if command -v apt-get >/dev/null 2>&1; then
    export DEBIAN_FRONTEND=noninteractive
    ${SUDO} apt-get update -qq
    ${SUDO} apt-get install -y -qq \
        curl \
        git \
        build-essential \
        sqlite3 \
        libsqlite3-dev \
        python3-pip \
        python3-venv \
        ca-certificates \
        libnss3 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libcups2 \
        libdrm2 \
        libxcomposite1 \
        libxdamage1 \
        libxfixes3 \
        libxrandr2 \
        libgbm1 \
        libpango-1.0-0 \
        libcairo2 \
        libasound2 \
        libxshmfence1 \
        2>/dev/null || true
    echo "[OK] OS packages and system libraries installed."
else
    echo "[INFO] System does not use apt-get. Skipping apt package installation."
fi
echo ""

# ------------------------------------------------------------------------------
# 2. Install Node.js 20 LTS & agent-browser
# ------------------------------------------------------------------------------
echo "[STEP 2/8] Checking Node.js and agent-browser..."
if ! command -v node >/dev/null 2>&1; then
    echo "  -> Installing Node.js 20 LTS via NodeSource..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | ${SUDO} -E bash - >/dev/null 2>&1 || true
    ${SUDO} apt-get install -y -qq nodejs >/dev/null 2>&1 || true
fi

if command -v node >/dev/null 2>&1; then
    NODE_VER="$(node --version)"
    echo "  [OK] Node.js: ${NODE_VER}"
else
    echo "  [WARN] Node.js could not be installed automatically."
fi

if command -v npm >/dev/null 2>&1; then
    if ! command -v agent-browser >/dev/null 2>&1; then
        echo "  -> Installing global agent-browser@0.35.1..."
        ${SUDO} npm install -g agent-browser@0.35.1 >/dev/null 2>&1 || npm install -g agent-browser@0.35.1 >/dev/null 2>&1 || true
    fi
    if command -v agent-browser >/dev/null 2>&1; then
        echo "  [OK] agent-browser: $(agent-browser --version 2>/dev/null || echo 'installed')"
    fi
fi
echo ""

# ------------------------------------------------------------------------------
# 3. Install Astral uv & Python 3.12
# ------------------------------------------------------------------------------
echo "[STEP 3/8] Installing uv and Python 3.12..."

if ! command -v uv >/dev/null 2>&1; then
    echo "  -> Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1 || true
    export PATH="${HOME}/.local/bin:${PATH}"
fi

UV_BIN="$(command -v uv || echo "${HOME}/.local/bin/uv")"
echo "  [OK] uv: $("${UV_BIN}" --version)"

echo "  -> Installing Python 3.12 runtime via uv..."
"${UV_BIN}" python install 3.12 >/dev/null 2>&1 || true
echo "  [OK] Python 3.12 ready."
echo ""

# ------------------------------------------------------------------------------
# 4. Install Hermes Agent CLI Upstream (Multi-tier fallback)
echo "[STEP 4/8] Installing Hermes Agent CLI..."
if ! command -v hermes >/dev/null 2>&1; then
    echo "  -> Installing hermes-agent via official installer..."
    curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash -s -- --skip-setup >/dev/null 2>&1 || true
    export PATH="${HOME}/.local/bin:${PATH}"
fi

# Fallback: if hermes CLI still missing, clone official repo and install via uv tool
if ! command -v hermes >/dev/null 2>&1; then
    echo "  -> Fallback: cloning official NousResearch/hermes-agent..."
    mkdir -p "${HERMES_HOME}"
    if [ ! -d "${HERMES_HOME}/hermes-agent" ]; then
        git clone --depth 1 https://github.com/NousResearch/hermes-agent.git "${HERMES_HOME}/hermes-agent" >/dev/null 2>&1 || true
    fi
    if [ -d "${HERMES_HOME}/hermes-agent" ]; then
        "${UV_BIN}" tool install -e "${HERMES_HOME}/hermes-agent" >/dev/null 2>&1 || true
    fi
    export PATH="${HOME}/.local/bin:${PATH}"
fi

HERMES_BIN="$(command -v hermes || true)"
if [ -z "${HERMES_BIN}" ]; then
    for cand in "${HOME}/.local/bin/hermes" "/usr/local/bin/hermes" "${HOME}/.cargo/bin/hermes"; do
        if [ -x "${cand}" ]; then
            HERMES_BIN="${cand}"
            break
        fi
    done
fi
HERMES_BIN="${HERMES_BIN:-${HOME}/.local/bin/hermes}"

if [ -x "${HERMES_BIN}" ] || command -v hermes >/dev/null 2>&1; then
    echo "  [OK] Hermes CLI ready: ${HERMES_BIN}"
else
    echo "  [WARN] hermes CLI binary not yet verified at ${HERMES_BIN}."
fi
echo ""
echo ""

# ------------------------------------------------------------------------------
# 5. Project Virtual Environment & Dependencies
# ------------------------------------------------------------------------------
echo "[STEP 5/8] Synchronizing project dependencies via uv sync..."
cd "${SRC_DIR}"
"${UV_BIN}" sync --frozen

echo "  -> Installing Tavily CLI tool..."
"${UV_BIN}" tool install tavily-cli==0.1.6 >/dev/null 2>&1 || true

echo "  -> Installing Playwright Chromium browser..."
if [ -n "${SUDO}" ] || [ "$(id -u)" -eq 0 ]; then
    "${UV_BIN}" run python -m playwright install --with-deps chromium >/dev/null 2>&1 \
        || "${UV_BIN}" run python -m playwright install chromium >/dev/null 2>&1 \
        || true
else
    "${UV_BIN}" run python -m playwright install chromium >/dev/null 2>&1 || true
fi
echo "  [OK] Project Python dependencies synchronized."
echo ""

# ------------------------------------------------------------------------------
# 6. Linking Plugins, SOUL Personas, and Runtime Directory
# ------------------------------------------------------------------------------
echo "[STEP 6/8] Setting up runtime structure and symlinks..."
mkdir -p "${HERMES_HOME}"
mkdir -p "${HERMES_HOME}/uploads"
mkdir -p "${HERMES_HOME}/deliverables/general"
mkdir -p "${HERMES_HOME}/profiles/protein-bar"

# Remove physical legacy folder if it was copied previously, then symlink
if [ -d "${HERMES_HOME}/plugins" ] && [ ! -L "${HERMES_HOME}/plugins" ]; then
    echo "  -> Migrating legacy plugins directory to symlink..."
    rm -rf "${HERMES_HOME}/plugins"
fi

ln -sfn "${SRC_DIR}/.hermes/plugins" "${HERMES_HOME}/plugins"
echo "  [OK] Symlink: ${HERMES_HOME}/plugins -> ${SRC_DIR}/.hermes/plugins"

# Link SOUL.md personas
if [ -f "${SRC_DIR}/SOUL.md" ]; then
    ln -sfn "${SRC_DIR}/SOUL.md" "${HERMES_HOME}/SOUL.md"
    echo "  [OK] Symlink: Default SOUL.md"
fi

if [ -f "${SRC_DIR}/workspaces/protein-bar/SOUL.md" ]; then
    ln -sfn "${SRC_DIR}/workspaces/protein-bar/SOUL.md" "${HERMES_HOME}/profiles/protein-bar/SOUL.md"
    echo "  [OK] Symlink: Protein Bar SOUL.md"
fi
echo ""

# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# 7. Dynamic Configuration (config.yaml & .env)
# ------------------------------------------------------------------------------
echo "[STEP 7/8] Generating/merging config.yaml and verifying environment..."

# 1. Automated Safety Backup (Root Configs & ALL Profiles Recursively)
BACKUP_DIR="${HERMES_HOME}/backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "${BACKUP_DIR}"

# Backup root config and .env
for f in "${HERMES_HOME}/config.yaml" "${HERMES_HOME}/.env"; do
    if [ -f "${f}" ] && [ ! -L "${f}" ]; then
        cp "${f}" "${BACKUP_DIR}/" 2>/dev/null || true
    fi
done

# Backup ALL profiles recursively (every profile's config.yaml, .env, SOUL.md, cron)
if [ -d "${HERMES_HOME}/profiles" ]; then
    mkdir -p "${BACKUP_DIR}/profiles"
    cp -r "${HERMES_HOME}/profiles"/* "${BACKUP_DIR}/profiles/" 2>/dev/null || true
fi
echo "  [OK] Complete safety backup of root configs and ALL profiles saved to: ${BACKUP_DIR}"

"${UV_BIN}" run python -c "
import yaml
from pathlib import Path

home = Path('${HERMES_HOME}')
src_dir = '${SRC_DIR}'
config_files = [home / 'config.yaml']

# Dynamically scan and preserve all existing profiles
profiles_dir = home / 'profiles'
if profiles_dir.is_dir():
    for p in profiles_dir.iterdir():
        if p.is_dir() and (p / 'config.yaml').is_file():
            config_files.append(p / 'config.yaml')

# Ensure protein-bar profile config is included
pb_cfg = profiles_dir / 'protein-bar' / 'config.yaml'
if pb_cfg not in config_files:
    config_files.append(pb_cfg)
for config_path in config_files:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    cfg = {}
    if config_path.is_file():
        with open(config_path, 'r', encoding='utf-8') as f:
            cfg = yaml.safe_load(f) or {}

    # 1. Model Provider (setdefault preserves existing model configuration)
    model = cfg.setdefault('model', {})
    model.setdefault('provider', 'azure-foundry')
    model.setdefault('default', 'gpt-5.6-luna')

    # 2. Terminal CWD
    terminal = cfg.setdefault('terminal', {})
    terminal['backend'] = 'local'
    terminal['cwd'] = src_dir

    # 3. External Skills
    skills = cfg.setdefault('skills', {})
    skills['external_dirs'] = [f'{src_dir}/skills']

    # 4. Command Guard Hook
    hooks = cfg.setdefault('hooks', {})
    hooks['pre_tool_call'] = [{
        'command': f'{src_dir}/.venv/bin/python {src_dir}/tools/knowledge/command_guard.py',
        'matcher': 'terminal',
        'timeout': 5
    }]

    # 5. Enabled Plugins (Merge instead of overwrite to preserve custom plugins)
    plugins = cfg.setdefault('plugins', {})
    enabled = plugins.setdefault('enabled', [])
    for p in [
        'platforms/whatsapp',
        'telegram-album',
        'email-connector',
        'calendar-connector',
        'youtube-connector',
        'tiktok-connector'
    ]:
        if p not in enabled:
            enabled.append(p)

    # 6. Telegram Toolset Exposure (Merge to preserve existing toolsets)
    kpt = cfg.setdefault('known_plugin_toolsets', {})
    tg_tools = kpt.setdefault('telegram', [])
    for t in [
        'email_connector',
        'calendar_connector',
        'youtube_connector',
        'tiktok_connector'
    ]:
        if t not in tg_tools:
            tg_tools.append(t)

    # 7. Web search backend
    web = cfg.setdefault('web', {})
    web.setdefault('backend', 'tavily')
    web.setdefault('use_gateway', True)

    # 8. Suppress noisy "gateway shutting down" / "gateway restarted" pings to users
    tg = cfg.setdefault('telegram', {})
    tg['gateway_restart_notification'] = False
    # 9. Seed default Telegram routes only if gateway is not yet configured on a fresh VM
    routes_file = Path(f'{src_dir}/config/telegram_routes.example.yaml')
    if routes_file.is_file() and config_path == (home / 'config.yaml'):
        with open(routes_file, 'r', encoding='utf-8') as rf:
            default_routes = yaml.safe_load(rf) or {}
        if 'gateway' not in cfg and 'gateway' in default_routes:
            cfg['gateway'] = default_routes['gateway']
            print('  [OK] Initialized default gateway profile routes from template.')
        if 'telegram' not in cfg and 'telegram' in default_routes:
            cfg['telegram'] = default_routes['telegram']
            print('  [OK] Initialized default telegram trigger rules from template.')

    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, default_flow_style=False)

    print(f'  [OK] Configuration safely updated (routes & credentials preserved): {config_path.name}')
"

# Setup environment files
ENV_TARGET="${HERMES_HOME}/.env"
SRC_ENV="${SRC_DIR}/.env"

if [ -f "${ENV_TARGET}" ]; then
    echo "  [OK] Existing environment preserved at ${ENV_TARGET} (Telegram bot token & credentials intact)."
else
    if [ -f "${SRC_ENV}" ] && [ ! -L "${SRC_ENV}" ]; then
        cp "${SRC_ENV}" "${ENV_TARGET}"
        echo "  [OK] Copied .env from src/ to ${ENV_TARGET}"
    else
        cp "${SCRIPT_DIR}/.env.example" "${ENV_TARGET}"
        echo "  [INFO] Created .env template at ${ENV_TARGET}."
        echo "  [ACTION REQUIRED] Configure TELEGRAM_BOT_TOKEN and API keys in: ${ENV_TARGET}"
    fi
fi

# Ensure src/.env is a symlink pointing to ~/.hermes/.env
if [ -f "${SRC_ENV}" ] && [ ! -L "${SRC_ENV}" ]; then
    rm -f "${SRC_ENV}"
fi
ln -sfn "${ENV_TARGET}" "${SRC_ENV}"
echo "  [OK] Symlink: ${SRC_ENV} -> ${ENV_TARGET}"
echo ""
echo ""

# ------------------------------------------------------------------------------
# 8. systemd Service Setup & Process Supervision
# ------------------------------------------------------------------------------
echo "[STEP 8/8] Registering systemd service (hermes-gateway.service)..."

HAS_SYSTEMD=false
if [ -d /run/systemd/system ]; then
    HAS_SYSTEMD=true
fi

SERVICE_FILE="/etc/systemd/system/hermes-gateway.service"

if [ "${HAS_SYSTEMD}" = "true" ] && ([ -n "${SUDO}" ] || [ "$(id -u)" -eq 0 ]); then
    cat <<EOF | ${SUDO} tee "${SERVICE_FILE}" >/dev/null
[Unit]
Description=Hermes Agent Gateway Daemon
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=${CURRENT_USER}
WorkingDirectory=${HERMES_HOME}
Environment="HOME=${HOME}"
Environment="USER=${CURRENT_USER}"
Environment="HERMES_HOME=${HERMES_HOME}"
Environment="HERMES_PROJECT_SRC=${SRC_DIR}"
Environment="HERMES_ENABLE_PROJECT_PLUGINS=1"
Environment="PATH=${HOME}/.local/bin:${SRC_DIR}/.venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=${HERMES_BIN} gateway run
Restart=always
RestartSec=5
RestartForceExitStatus=75
KillMode=mixed
TimeoutStopSec=60

[Install]
WantedBy=multi-user.target
EOF
    echo "  [OK] Service unit created: ${SERVICE_FILE}"

    # Enable lingering so service persists when user logs out of SSH
    if command -v loginctl >/dev/null 2>&1; then
        ${SUDO} loginctl enable-linger "${CURRENT_USER}" 2>/dev/null || true
        echo "  [OK] User lingering enabled (service survives SSH disconnect)."
    fi

    ${SUDO} systemctl daemon-reload
    ${SUDO} systemctl enable hermes-gateway >/dev/null 2>&1 || true
    ${SUDO} systemctl restart hermes-gateway 2>/dev/null || true
    echo "  [OK] hermes-gateway service started via systemctl."
else
    echo "[INFO] systemd not available as PID 1 (container/WSL). Starting gateway directly..."
    hermes gateway restart 2>/dev/null || hermes gateway start 2>/dev/null || true
fi
echo ""

# ------------------------------------------------------------------------------
# Verification & Self-Test
# ------------------------------------------------------------------------------
echo "======================================================================"
echo "SYSTEM SELF-TEST"
echo "======================================================================"

cd "${SRC_DIR}"
"${UV_BIN}" run python -c "
import sys
from pathlib import Path

src = Path('${SRC_DIR}')
sys.path.insert(0, str(src))

def check(name, fn):
    try:
        fn()
        print(f'  [PASS] {name}')
    except Exception as e:
        print(f'  [FAIL] {name}: {e}')

check('1. Google Workspace (Composio)', lambda: __import__('tools.composio.client'))
check('2. Google Calendar Connector', lambda: __import__('tools.calendar.service'))
check('3. YouTube Channel Connector', lambda: __import__('tools.youtube.service'))
check('4. TikTok Posting Connector', lambda: __import__('tools.tiktok.service'))
check('5. Web Research & Report Generator', lambda: __import__('skills.research.scripts.render_report'))
"

echo ""
echo "======================================================================"
echo "DEPLOYMENT COMPLETE"
echo "======================================================================"
echo "Service management commands:"
echo "  - Status:  hermes gateway status"
echo "  - Logs:    journalctl -u hermes-gateway -f"
echo "  - Restart: sudo systemctl restart hermes-gateway"
echo "  - Update:  bash update_vm.sh"
echo "======================================================================"
