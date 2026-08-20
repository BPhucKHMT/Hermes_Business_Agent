# Hermes Business Agent

Production workspace and engineering harness for a Hermes-powered business agent.
Current verified pilot routes one Telegram forum topic to an isolated Protein Bar
profile and retrieves workspace-scoped evidence from Azure AI Search.

Read [`ARCHITECTURE.md`](ARCHITECTURE.md) before changing deployment topology.

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
