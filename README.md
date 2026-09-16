/# Hermes Business Agent

Production workspace and engineering harness for a Hermes-powered business agent.
Current verified pilot routes one Telegram forum topic to an isolated Protein Bar
profile and retrieves workspace-scoped evidence from Azure AI Search.


## Windows local — hướng dẫn bàn giao cho khách hàng

**Trạng thái H017: đang kiểm chứng, chưa phát hành bản cài đặt được nghiệm thu.**
Không dùng hướng dẫn Linux/Docker như bằng chứng rằng Windows đã chạy được.

Máy Windows của khách có thể chạy Hermes Desktop và gateway Telegram/Zalo;
không cần Docker. Máy phải bật, có Internet và không sleep khi cần nhận tin hoặc
chạy nhắc việc. Model, Google, Tavily và Azure vẫn là dịch vụ bên ngoài: chạy
local không có nghĩa là offline hay miễn phí.

### Trước khi bắt đầu

- Nhận release ZIP đã được bên bàn giao kiểm chứng, không tải nhánh phát triển.
- Nhận tài khoản/billing và bí mật qua kênh bảo mật riêng; không gửi password
  Google cho bot hoặc chụp màn hình token.
- Không copy thư mục AppData, `.venv`, `auth.json` hoặc sessions từ máy developer.
- Nếu máy đã có Hermes, nhờ bên bàn giao kiểm tra backup và installation đích
  trước khi chạy setup; không ghi đè môi trường đang sử dụng.

### Bước 1 — cài Hermes chính thức

Mở [trang Hermes chính thức](https://hermes-agent.nousresearch.com/) và dùng bản
cài Windows đã được bên bàn giao chỉ định. Không tự nâng cấp sang bản mới nhất
trong lúc nghiệm thu. Phiên bản/commit phải có trong biên bản kiểm chứng release.

**Đạt khi:** mở được Hermes và gửi một câu chào nhận phản hồi từ model đã chọn.
Nếu báo thiếu tài khoản/model, hoàn thành đăng nhập với bên bàn giao trước.

### Bước 2 — giải nén dự án

Nhấp phải file ZIP → **Extract All / Giải nén tất cả**. Đặt ở một thư mục ổn định,
không chạy trực tiếp trong ZIP và không đặt trong thư mục đồng bộ OneDrive.
Mở thư mục `src`; phải thấy `setup.cmd`, `setup_local.py`, `skills`, `tools`
và `.hermes/plugins/zalo-platform`. Không có Zalo plugin nghĩa là gói bị thiếu.

Không di chuyển hoặc đổi tên thư mục sau cài đặt; cấu hình lưu đường dẫn của nó.

### Bước 3 — kết nối dự án với Hermes

Trong File Explorer đang mở `src`, gõ `cmd` vào thanh địa chỉ rồi nhấn Enter.
Trong cửa sổ xuất hiện, dán:

```bat
setup.cmd --local
```

Chờ quá trình cài thư viện và trình duyệt kết thúc. Khi có `ERROR` hoặc traceback,
dừng lại và gửi thông báo lỗi đã che thông tin riêng tư cho bên bàn giao.
Không tự chạy `pip install` vào Hermes hoặc bỏ qua bước lỗi.

**Đạt khi:** script kết thúc không lỗi và thông báo đã cấu hình local.
Đây chỉ là kết quả bootstrap, chưa chứng minh Telegram/Zalo/Azure hoạt động.
Setup không tự gửi tin, chuyển tài khoản hay khởi động gateway.
### Bước 4 — kết nối dịch vụ của khách

Bên bàn giao cấu hình một lần cùng khách:

| Dịch vụ | Khách làm | Bên bàn giao kiểm tra |
|---|---|---|
| Model/Tavily/Azure | Đăng nhập, xác nhận quyền và chi phí | Secret, model, tài nguyên và truy vấn thật |
| Telegram | Mở bot, thêm vào nhóm được duyệt | Allowlist, topic, profile Protein Bar |
| Zalo | Mở bot và xác nhận tài khoản được phép | Plugin, token, pairing, tin nhắn thật |
| Google | Gõ `/connect-google`, mở link và đồng ý cấp quyền | `/mail-status`, `/calendar-status` và thao tác đọc thật |
| Zalo media (ảnh) | Gửi ảnh dạng URL công khai hoặc ảnh đã nạp Azure | Bucket, quyền SAS và kết quả gửi thật |

Google trên Desktop và trên Telegram/Zalo có danh tính riêng. Kết nối ở một nơi
không tự cấp quyền cho tất cả kênh khác; chỉ kết nối ở các kênh khách muốn dùng.
Không đặt token vào câu chat. Không bật chế độ cho phép tất cả người dùng.

### Bước 5 — nghiệm thu và sử dụng hằng ngày

Khách cùng bên bàn giao kiểm tra:

- Desktop mở đúng thư mục `src` và dùng được tài liệu được cấp quyền.
- Telegram và Zalo trả lời hai tin liên tiếp, giữ đúng hội thoại.
- Topic Protein Bar truy vấn đúng tài liệu, không lộ sang workspace khác.
- Gmail đọc được thư đã chọn; Calendar đọc được lịch đúng tài khoản.
- Ảnh Zalo gửi được dưới dạng URL công khai/SAS hoặc ảnh đã nạp Azure.
- Research trả nguồn; Azure RAG trả citation của tài liệu đã nạp.

Chỉ ghi hoàn thành các mục đã trực tiếp quan sát; không thử gửi email hoặc tạo
lịch thật nếu chưa duyệt dữ liệu. Đóng/ngủ/tắt laptop sẽ ngừng bot.

### Nếu có sự cố
| Hiện tượng | Việc cần làm |
|---|---|
| Không tìm thấy `hermes`, `uv`, `node` hoặc `npm` | Đóng cửa sổ, mở lại sau cài Hermes; còn lỗi thì liên hệ bên bàn giao |
| Google chưa kết nối | Chạy `/connect-google` tại đúng kênh đang sử dụng |
| Bot im lặng | Kiểm tra Internet, máy không sleep và gateway; không chạy thêm bản bot thứ hai |
| Azure không có dữ liệu | Nhờ kiểm tra ingestion và quyền; không bỏ workspace filter |
| Cảnh báo antivirus | Dừng và xác minh installer chính thức; không tắt bảo vệ toàn máy |

Trước khi đổi máy, cập nhật hoặc gỡ Hermes, yêu cầu backup và kế hoạch khôi phục.
Không tự xóa AppData hoặc `.runtime`: chúng có thể chứa công việc và lịch nhắc.
Read [`ARCHITECTURE.md`](ARCHITECTURE.md) before changing deployment topology.

## Claude Code Engineering Workflow

Claude Code uses the same engineering workflow as Antigravity. `.agents/` is the
canonical kit; generated `.claude/` files expose its skills, specialist agents,
and slash workflows through Claude Code discovery.

After cloning, or after changing canonical kit content, run from repository root:

```powershell
.\.agents\scripts\sync-claude-kit.ps1
.\.agents\scripts\verify-claude-kit.ps1
claude
```

Do not edit generated adapters directly. Update `.agents/`, regenerate, and
verify. Project MCP config excludes placeholder credentials; configure required
MCP secrets through operator-owned Claude settings rather than Git.

## What Gets Deployed

Only [`src/`](src) is Hermes production context. Repository-root files are the
engineering harness and must not be used as Hermes working directory.

```text
repository/
├── README.md, ARCHITECTURE.md       operator onboarding
├── AGENTS.md, PROGRESS.md, ...      engineering harness
├── tests/                            verification
└── src/                              deploy this as Hermes workspace
    ├── AGENTS.md                     production runtime policy
    ├── skills/                       Hermes skills
    ├── tools/knowledge/              deterministic Azure tools
    ├── config/                       runtime policy
    ├── setup.cmd / setup.sh          locked environment bootstrap
    ├── pyproject.toml / uv.lock      Python 3.12 runtime
    └── .env.example                  Azure variable template
```

## Prerequisites

Required:

- [Git](https://git-scm.com/)
- a supported [Hermes Agent](https://github.com/NousResearch/hermes-agent) installation
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- a Hermes model/provider credential

For Telegram:

- one bot created with BotFather;
- operator Telegram user ID;
- supergroup/topic IDs when using profile routing.

For retained company knowledge:

- Azure Storage account;
- Azure AI Search service;
- Azure OpenAI embedding deployment compatible with `text-embedding-3-small`.

> Never commit bot tokens, Azure keys, connection strings, operator config,
> profile exports, or application-data backups.

## 1. Install and Configure Hermes Agent

Install Hermes Agent using its official instructions, then verify:

```powershell
hermes --help
hermes setup
hermes config check
```

`hermes` must work before connecting this repository. Do not modify installed
Hermes source or its managed Python environment.

## 2. Clone Repository

```powershell
git clone https://github.com/BPhucKHMT/Hermes_Business_Agent.git
Set-Location Hermes_Business_Agent
```

Linux/macOS:

```bash
git clone https://github.com/BPhucKHMT/Hermes_Business_Agent.git
cd Hermes_Business_Agent
```

## 3. Bootstrap Project Runtime

Windows PowerShell:

```powershell
Set-Location src
.\setup.cmd
```

Linux:

```bash
cd src
chmod +x setup.sh
./setup.sh
```

Setup recreates the locked Python 3.12 environment, installs Chromium, and runs
Crawl4AI doctor. Do not commit or copy `.venv`.

Verify:

```powershell
uv lock --check
uv run --frozen python tools/knowledge/knowledge.py --help
```

## 4. Configure Azure Knowledge Runtime

From `src/`, create local environment file:

```powershell
Copy-Item .env.example .env
```

Linux:

```bash
cp .env.example .env
```

Fill required values in `src/.env`:

```dotenv
AZURE_STORAGE_CONNECTION_STRING=
AZURE_SEARCH_ENDPOINT=
AZURE_SEARCH_ADMIN_KEY=
AZURE_SEARCH_QUERY_KEY=
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small
AZURE_OPENAI_EMBEDDING_MODEL=text-embedding-3-small
AZURE_OPENAI_EMBEDDING_DIMENSIONS=1536
HERMES_IMAGE_INDEXER=false
```

Container, index, skillset, and indexer names already have defaults in
[`src/.env.example`](src/.env.example). Keep image indexing disabled until Azure
AI-enrichment quota/cost is approved.

Provision managed resources:

```powershell
uv run --frozen python tools/knowledge/knowledge.py provision
uv run --frozen python tools/knowledge/knowledge.py status
```

Provisioning creates or updates approved project-owned Azure resources. Review
Azure billing before leaving paid Search resources running.

## 5. Connect Hermes to Deployed `src`

Get absolute `src` path. Example only:

```text
C:/work/Hermes_Business_Agent/src
```

Edit operator-owned Hermes config:

```powershell
hermes config edit
```

Set deployment paths, replacing examples with host paths:

```yaml
terminal:
  cwd: C:/work/Hermes_Business_Agent/src

skills:
  external_dirs:
    - C:/work/Hermes_Business_Agent/src/skills

plugins:
  enabled:
    - telegram-album
```

Set trusted project-plugin opt-in in Hermes operator environment:

```dotenv
HERMES_ENABLE_PROJECT_PLUGINS=1
```

Enable this only for a trusted clone. Hermes runtime CWD remains `src`, never
repository root.

## 6. Create Protein Bar Profile

Inspect profiles first:

```powershell
hermes profile list
```

Create profile only when it does not exist:

```powershell
hermes profile create protein-bar --clone
```

Configure profile CWD and skills to same deployed `src`. Apply Protein Bar
persona/policy according to [`docs/plan/protein_bar.md`](docs/plan/protein_bar.md)
when local docs are available. Do not copy default Telegram token into secondary
profile `.env`; shared token belongs to one gateway adapter.

## 7. Configure Telegram

Run official setup and keep token in operator-owned Hermes state:

```powershell
hermes gateway setup
```

Telegram authorization and trigger config belongs at top-level `telegram`:

```yaml
telegram:
  require_mention: true
  exclusive_bot_mentions: true
  mention_patterns: []
  observe_unmentioned_group_messages: true
```

- Privacy Mode controls which group messages Telegram delivers.
- Disable Privacy Mode or make bot admin when unmentioned context must be visible.
- After changing Privacy Mode, remove and re-add bot.
- `require_mention` keeps ordinary chatter silent.
- Direct replies to bot remain triggers.

Obtain real IDs from Telegram topic links. A link
`https://t.me/c/3835812097/11` maps to chat `-1003835812097`, thread `11`.
Never copy example IDs into another deployment.

Enable deterministic routing with customer values:

```yaml
gateway:
  multiplex_profiles: true
  profile_routes:
    - name: telegram-protein-bar
      platform: telegram
      chat_id: "<actual-supergroup-chat-id>"
      thread_id: "<actual-protein-bar-thread-id>"
      profile: protein-bar
```

Until other profiles exist, ignore their topics explicitly:

```yaml
telegram:
  ignored_threads:
    - "<unrouted-thread-id>"
```

Every routed profile must exist. One shared bot token is configured only by the
default adapter; repeating token in `protein-bar/.env` causes
`duplicate_credential`.

Validate without printing secrets:

```powershell
hermes config check
hermes profile list
```

## 8. Start Gateway

Normal lifecycle:

```powershell
hermes gateway install
hermes gateway restart
hermes gateway status
```

Foreground environments such as WSL, Docker, or Termux:

```bash
hermes gateway run
```

Status must show process running and Telegram connected. After restart, mention
bot in Protein Bar topic and ask it to return current profile.

## 9. Add Protein Bar Documents

Run from `src`. Keep authentic documents outside Git unless publication is
approved:

```powershell
uv run --frozen python tools/knowledge/knowledge.py upload "C:\secure\protein_bar_master_plan.docx" --workspace protein-bar
uv run --frozen python tools/knowledge/knowledge.py index
uv run --frozen python tools/knowledge/knowledge.py search "opening date" --workspace protein-bar
```

Use `--help` on each subcommand before operating if installed CLI differs:

```powershell
uv run --frozen python tools/knowledge/knowledge.py upload --help
```

Retrieval from `--workspace titan-ai` must not return Protein Bar evidence.

## 10. Verify

Run layers in order from repository root:

```powershell
python -m json.tool feature-list.json
python tests/verify_knowledge.py --layer 1
```

Then from `src`:

```powershell
uv run --frozen python ../tests/verify_knowledge.py --layer 2
uv lock --check
```

Do not run Layer 2 after Layer 1 failure. Layer 3 requires real Telegram and
Azure boundaries:

1. New unmentioned topic message produces no typing/reply.
2. Mention in Protein Bar topic resolves `protein-bar`.
3. RAG answer cites authentic Protein Bar document.
4. Cross-workspace query returns `no_evidence`.
5. Gateway restart preserves route.
6. Independent verifier records UTC timestamp, command/event, exit status, and result.

Feature state remains `active` until independent evidence permits `passing`.

## 11. Gmail & Email Intake (Feature H009)

Hermes supports multi-user private and shared Gmail inspection with zero-trust privacy isolation, PKCE OAuth2 flow, and host-bound Telegram authorization.

### Email Slash Commands (Telegram DM)

| Command | Aliases | Description |
| :--- | :--- | :--- |
| `/connect_gmail` | `/connect_email`, `/connect_mail`, `/connect-gmail` | Generate a secure Google OAuth2 link to connect a private Gmail account (DM only). |
| `/mail_status` | `/email_status`, `/mail-status`, `/email-status` | View connected mailboxes (masked addresses like `u***@gmail.com`), status, and connection IDs. |
| `/disconnect_gmail <id>` | `/disconnect_email <id>`, `/disconnect-gmail` | Disconnect and revoke an authenticated Gmail account. |
| `/share_mailbox <id> <chat_id>` | `/share-mailbox` | Propose sharing a personal or business mailbox with a Telegram group/topic. |
| `/email_grant <req_id> approve\|deny` | `/email-grant` | Operator command to approve or reject a mailbox sharing request. |

### Natural Language Email Queries (No Slash Required)

Once connected, you can chat with Hermes using standard natural language (Vietnamese / English):

- *"Hôm nay có email nào mới không bot?"*
- *"Tìm email từ đối tác gửi báo giá hợp đồng trong tuần này"*
- *"Tóm tắt nội dung chuỗi email gần nhất về dự án"*
- *"Kiểm tra trạng thái kết nối hòm thư của tôi"*

Hermes autonomously invokes the underlying tools (`email_search`, `email_get_thread`, `email_connection_status`) with strict privacy boundaries.

## Zalo Bot Platform Text Chat (H016)

Use the opt-in `src/.hermes/plugins/zalo-platform` platform plugin alongside
Telegram. It uses official Bot Platform APIs and Hermes's existing authorization
and session pipeline; no Hermes engine changes or extra dependencies.

Follow [the Windows/Linux configuration and pairing instructions](src/README.md#zalo-bot-platform-private-text-chat-h016).
Store `ZALO_BOT_TOKEN` only in the gateway owner's operator environment.
The current transport is polling for local development. Linux source deployment
is portable, but production webhook rollout needs public HTTPS and is not part
of this milestone. Do not run Windows and VPS pollers with the same token.

Private text only; no group, voice, image, or document transport. Acceptance is
tracked in H016; only real two-message exchanges plus independent restart and
Telegram verification can establish end-to-end completion.

## Troubleshooting

### Bot replies without mention

Ensure keys are top-level:

```yaml
telegram:
  require_mention: true
```

`messaging.telegram.require_mention` is wrong for installed adapter.

### Mention receives no reply

```powershell
hermes gateway status
hermes logs --since 10m
```

Confirm Telegram is connected, sender/chat is authorized, and message is not in
`ignored_threads`.

### `duplicate_credential`

Remove duplicated Telegram token from secondary profile. Default adapter owns
shared token; `profile_routes` selects secondary runtime.

### Bot cannot read ordinary group context

Disable BotFather Privacy Mode or make bot admin, then remove/re-add bot.

### `uv` not found

Install uv, restart terminal, and verify `uv --version`. Do not substitute
Hermes-managed Python for locked project environment.

### Azure returns `no_evidence`

Check workspace tag, indexer status, source path, and query. Never remove
workspace filter to force a result.

### WhatsApp fails while Telegram works

Adapters are independent. Verify Telegram state directly; do not treat unrelated
WhatsApp bridge error as Telegram routing failure.

## Documentation Map

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — system boundaries and flows.
- [`src/README.md`](src/README.md) — production runtime contract.
- [`src/AGENTS.md`](src/AGENTS.md) — Hermes runtime policy.
- [`AGENTS.md`](AGENTS.md) — engineering workflow.
- [`PROGRESS.md`](PROGRESS.md) — current handoff and blockers.
- [`DECISIONS.md`](DECISIONS.md) — durable architecture decisions.
- [`feature-list.json`](feature-list.json) — machine-readable feature state.
