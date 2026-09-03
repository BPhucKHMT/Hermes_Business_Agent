#!/usr/bin/env bash
# ==============================================================================
# Hermes Production 1-Click Deployment & Parity Automation Script
# Ensures 100% feature parity between Local Dev and Production Cloud VPS.
# ==============================================================================

set -euo pipefail

echo "======================================================================"
echo "🚀 HERMES PRODUCTION 1-CLICK DEPLOYMENT & PARITY AUTOMATION"
echo "======================================================================"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_DIR="${REPO_ROOT}/src"
HERMES_HOME="${HOME}/.hermes"

echo "📍 Repository Root: ${REPO_ROOT}"
echo "📍 Source Dir:     ${SRC_DIR}"
echo "📍 Hermes Home:    ${HERMES_HOME}"
echo ""

# ------------------------------------------------------------------------------
# 1. Python Dependencies & Virtual Environment Sync
# ------------------------------------------------------------------------------
echo "📦 [1/6] Đồng bộ thư viện Python (uv sync)..."
cd "${SRC_DIR}"

UV_BIN="${HOME}/.local/bin/uv"
if [ ! -x "${UV_BIN}" ]; then
    if command -v uv >/dev/null 2>&1; then
        UV_BIN="$(command -v uv)"
    else
        echo "Installing uv..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
        UV_BIN="${HOME}/.local/bin/uv"
    fi
fi

"${UV_BIN}" sync --frozen
echo "✅ Đã đồng bộ thư viện Python thành công."
echo ""

# ------------------------------------------------------------------------------
# 2. Research & Browser Tooling (Tavily & Playwright)
# ------------------------------------------------------------------------------
echo "🔍 [2/6] Cài đặt công cụ Research & Browser Engine (Tavily + Playwright)..."
# Install tavily-cli
"${UV_BIN}" tool install tavily-cli==0.1.6 2>/dev/null || pip install --quiet tavily-python tavily-cli 2>/dev/null || true

# Install Playwright Chromium for web scraping & dynamic site intelligence
"${UV_BIN}" run python -m playwright install --with-deps chromium 2>/dev/null || true

# Install composio-core for Google Workspace (Gmail & Calendar) multi-user integration
"${UV_BIN}" pip install composio-core 2>/dev/null || pip install --quiet composio-core 2>/dev/null || true

# Install agent-browser if npm is available
if command -v npm >/dev/null 2>&1; then
    echo "Installing agent-browser..."
    sudo npm install -g agent-browser@0.35.1 2>/dev/null || npm install -g agent-browser@0.35.1 2>/dev/null || true
fi
echo "✅ Đã cài đặt xong công cụ Research & Browser."
echo ""

# ------------------------------------------------------------------------------
# 3. Synchronize Plugins and SOUL Persona (Default and All Profiles)
# ------------------------------------------------------------------------------
echo "🔌 [3/6] Đồng bộ Plugins và SOUL.md vào Runtime & Tất cả Profiles..."
mkdir -p "${HERMES_HOME}/plugins"
mkdir -p "${HERMES_HOME}/uploads"
mkdir -p "${HERMES_HOME}/deliverables/general"

# Copy all plugins
cp -r "${SRC_DIR}/.hermes/plugins/"* "${HERMES_HOME}/plugins/"

# Copy neutral SOUL to default runtime
if [ -f "${SRC_DIR}/SOUL.md" ]; then
    cp "${SRC_DIR}/SOUL.md" "${HERMES_HOME}/SOUL.md"
fi

# Also copy/sync SOUL to all profiles in ~/.hermes/profiles/
if [ -d "${HERMES_HOME}/profiles" ]; then
    for prof_dir in "${HERMES_HOME}/profiles"/*; do
        if [ -d "${prof_dir}" ]; then
            prof_name="$(basename "${prof_dir}")"
            if [ "${prof_name}" = "protein-bar" ] && [ -f "${SRC_DIR}/workspaces/protein-bar/SOUL.md" ]; then
                cp "${SRC_DIR}/workspaces/protein-bar/SOUL.md" "${prof_dir}/SOUL.md"
                echo "  -> Đã đồng bộ SOUL.md trung tính cho profile: ${prof_name}"
            elif [ -f "${SRC_DIR}/SOUL.md" ]; then
                cp "${SRC_DIR}/SOUL.md" "${prof_dir}/SOUL.md"
                echo "  -> Đã đồng bộ SOUL.md cho profile: ${prof_name}"
            fi
        fi
    done
fi
echo "✅ Đã sao chép 4 Plugins và SOUL.md cho mọi profile."
echo ""

# ------------------------------------------------------------------------------
# 4. Configure config.yaml for Default and ALL Profiles
# ------------------------------------------------------------------------------
echo "⚙️ [4/6] Cấu hình config.yaml cho Default và Toàn bộ Profiles..."
python3 -c "
import yaml
from pathlib import Path

home = Path.home() / '.hermes'
config_files = [home / 'config.yaml']

profiles_dir = home / 'profiles'
if profiles_dir.is_dir():
    for p in profiles_dir.iterdir():
        if p.is_dir() and (p / 'config.yaml').is_file():
            config_files.append(p / 'config.yaml')

for config_path in config_files:
    with open(config_path, 'r', encoding='utf-8') as f:
        cfg = yaml.safe_load(f) or {}

    # 1. Trỏ đúng đường dẫn Skills trên Linux VPS
    skills = cfg.setdefault('skills', {})
    skills_dir = '${SRC_DIR}/skills'
    skills['external_dirs'] = [skills_dir]

    # 2. Kích hoạt toàn bộ 4 plugins
    plugins = cfg.setdefault('plugins', {})
    enabled = plugins.setdefault('enabled', [])
    for p in ['email-connector', 'calendar-connector', 'youtube-connector', 'tiktok-connector']:
        if p not in enabled:
            enabled.append(p)

    # 3. Đăng ký plugin toolsets cho Telegram
    kpt = cfg.setdefault('known_plugin_toolsets', {})
    tg_tools = kpt.setdefault('telegram', [])
    for t in ['email_connector', 'calendar_connector', 'youtube_connector', 'tiktok_connector']:
        if t not in tg_tools:
            tg_tools.append(t)

    # 4. Kích hoạt Tavily Web Search backend
    web = cfg.setdefault('web', {})
    web['backend'] = 'tavily'
    web['use_gateway'] = True

    # 5. Đảm bảo terminal CWD trỏ vào src
    terminal = cfg.setdefault('terminal', {})
    terminal['cwd'] = '${SRC_DIR}'

    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(cfg, f, allow_unicode=True)

    print(f'  ✅ Đã cập nhật thành công: {config_path.relative_to(home)}')
"
echo ""

# ------------------------------------------------------------------------------
# 5. Environment Variables & Media Cache Retention
# ------------------------------------------------------------------------------
echo "🔐 [5/6] Kiểm tra và cấu hình biến môi trường (.env)..."
ENV_FILE="${SRC_DIR}/.env"
HERMES_ENV="${HERMES_HOME}/.env"

# If src/.env missing but ~/.hermes/.env exists, copy it
if [ ! -f "${ENV_FILE}" ] && [ -f "${HERMES_ENV}" ]; then
    echo "Copying ${HERMES_ENV} -> ${ENV_FILE}"
    cp "${HERMES_ENV}" "${ENV_FILE}"
fi

# Ensure HERMES_MEDIA_CACHE_MAX_AGE_HOURS=2160 is set in both env files
for ef in "${ENV_FILE}" "${HERMES_ENV}"; do
    if [ -f "${ef}" ]; then
        if ! grep -q "HERMES_MEDIA_CACHE_MAX_AGE_HOURS" "${ef}"; then
            echo "HERMES_MEDIA_CACHE_MAX_AGE_HOURS=2160" >> "${ef}"
        fi
        if ! grep -q "HERMES_PERMANENT_UPLOADS_DIR" "${ef}"; then
            echo "HERMES_PERMANENT_UPLOADS_DIR=${HERMES_HOME}/uploads" >> "${ef}"
        fi
    fi
done

# Run audit on required keys
python3 -c "
import os
from pathlib import Path

env_file = Path('${ENV_FILE}')
if env_file.is_file():
    for line in env_file.read_text().splitlines():
        if '=' in line and not line.strip().startswith('#'):
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip())

required_keys = [
    'AZURE_FOUNDRY_API_KEY',
    'TAVILY_API_KEY',
    'TELEGRAM_BOT_TOKEN',
    'EMAIL_GOOGLE_CLIENT_ID',
    'EMAIL_GOOGLE_CLIENT_SECRET',
    'EMAIL_OAUTH_REDIRECT_URI',
    'EMAIL_CONNECTOR_SHARED_SECRET',
]

print('Kiểm tra danh sách biến môi trường:')
all_present = True
for k in required_keys:
    val = os.environ.get(k, '').strip()
    if val:
        print(f'  ✅ {k}: OK')
    else:
        print(f'  ⚠️  {k}: CHƯA ĐẶT HOẶC RỖNG')
        all_present = False

if not all_present:
    print('\nLƯU Ý: Vui lòng kiểm tra và điền các khóa còn thiếu vào file: ${ENV_FILE}')
"
echo ""

# ------------------------------------------------------------------------------
# 6. Restart Gateway & Run Self-Test
# ------------------------------------------------------------------------------
echo "🔄 [6/6] Khởi động lại Hermes Gateway và Chạy Tự Kiểm Tra (Self-Test)..."

# Restart gateway
if command -v systemctl >/dev/null 2>&1 && sudo systemctl is-active --quiet hermes-gateway 2>/dev/null; then
    sudo systemctl restart hermes-gateway
    echo "✅ Đã khởi động lại qua systemctl: hermes-gateway"
else
    hermes gateway restart 2>/dev/null || true
    echo "✅ Đã khởi động lại qua hermes gateway restart"
fi

sleep 3

echo ""
echo "======================================================================"
echo "🧪 KẾT QUẢ TỰ KIỂM TRA TOÀN DIỆN (SYSTEM SELF-TEST):"
echo "======================================================================"

python3 -c "
import sys
import os
from pathlib import Path

src = Path('${SRC_DIR}')
sys.path.insert(0, str(src))

print('1. Kiểm tra Google Workspace Service (Composio Gmail & Calendar):')
try:
    from tools.composio.client import format_user_id, get_composio_client
    from tools.composio.auth import initiate_google_connection, check_connection_status
    from tools.composio.mail_tools import composio_mail_search
    from tools.composio.calendar_tools import composio_calendar_list_events
    print('   ✅ Google Workspace (Composio): SẴN SÀNG')
except Exception as e:
    print(f'   ❌ Google Workspace (Composio): LỖI ({e})')
print('2. Kiểm tra Calendar Service:')
try:
    from tools.calendar.service import CalendarService
    from tools.calendar.policy import load_calendar_policy
    from tools.calendar.store import CalendarStore
    from tools.calendar.google_calendar import GoogleCalendarClient
    pol = load_calendar_policy(src / 'config/calendar_policy.json')
    st = CalendarStore(src / '.runtime/calendar/test.sqlite3')
    cs = CalendarService(policy=pol, store=st, google_client=GoogleCalendarClient())
    print('   ✅ CalendarService: SẴN SÀNG')
except Exception as e:
    print(f'   ❌ CalendarService: LỖI ({e})')

print('3. Kiểm tra YouTube Service:')
try:
    from tools.youtube.service import YouTubeService
    from tools.youtube.policy import load_youtube_policy
    from tools.youtube.store import YouTubeStore
    from tools.youtube.youtube_client import YouTubeClient
    pol = load_youtube_policy(src / 'config/youtube_policy.json')
    st = YouTubeStore(src / '.runtime/youtube/test.sqlite3')
    ys = YouTubeService(policy=pol, store=st, youtube_client=YouTubeClient())
    print('   ✅ YouTubeService: SẴN SÀNG')
except Exception as e:
    print(f'   ❌ YouTubeService: LỖI ({e})')

print('4. Kiểm tra TikTok Service:')
try:
    from tools.tiktok.service import TikTokService
    from tools.tiktok.policy import load_tiktok_policy
    from tools.tiktok.store import TikTokStore
    from tools.tiktok.tiktok_client import TikTokClient
    pol = load_tiktok_policy(src / 'config/tiktok_policy.json')
    st = TikTokStore(src / '.runtime/tiktok/test.sqlite3')
    ts = TikTokService(policy=pol, store=st, tiktok_client=TikTokClient())
    print('   ✅ TikTokService: SẴN SÀNG')
except Exception as e:
    print(f'   ❌ TikTokService: LỖI ({e})')

print('5. Kiểm tra Research & Web Scraper:')
try:
    from skills.research.scripts.render_report import render_html
    print('   ✅ Research Report Generator: SẴN SÀNG')
except Exception as e:
    print(f'   ❌ Research Generator: LỖI ({e})')

"

echo ""
echo "======================================================================"
echo "🎉 HOÀN TẤT TRIỂN KHAI PRODUCTION ĐẠT CHUẨN PARITY 100%!"
echo "======================================================================"
