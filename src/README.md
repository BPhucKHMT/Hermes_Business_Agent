# Hermes Runtime Workspace

This directory is the sole source of Hermes project instructions and persistent
context. Its parent contains the engineering harness and is not runtime context.
This boundary does not restrict task execution: Hermes may use external resources
for explicit user requests when operator permissions allow it.

## Connect Hermes

Set `terminal.cwd` to this directory and add its `skills` directory to
`skills.external_dirs` in `%LOCALAPPDATA%\hermes\config.yaml`:

```yaml
terminal:
  cwd: <absolute path to this workspace>

skills:
  external_dirs:
    - <absolute path to this workspace>/skills

plugins:
  enabled:
    - telegram-album
```

Use the supported native config bridge for the non-secret project flags:
`hermes config set HERMES_PROJECT_SRC <absolute-src-path>` and
`hermes config set HERMES_ENABLE_PROJECT_PLUGINS 1`. These uppercase
top-level scalar keys are bridged into the Hermes process environment; they are
runtime source/opt-in flags, not SDK secrets. This opts into trusted code under
`.hermes/plugins/`; never enable project plugins from an untrusted workspace.
Restart Hermes after changing either setting.

### Local Google mode (explicit opt-in)

For a customer-owned, single-user CLI/Desktop installation, run the bootstrap
with `--local` from this directory:

```text
Windows: setup.cmd --local
Linux:   chmod +x setup.sh && ./setup.sh --local
```

This calls `tools.composio.local_owner.ensure_local_owner` and creates the
installation binding at `.runtime/google/local-owner.json` only during setup.
Repeated setup keeps the same owner. It uses supported Hermes CLI commands to
set this workspace as `terminal.cwd`, preserve and extend
`skills.external_dirs`, set `HERMES_PROJECT_SRC`, opt into project plugins, and
enable the email and calendar connectors. The supported CLI updates only
operator configuration; it does not modify native Hermes core/AppData
installation files or the managed virtual environment, and it does not require
Telegram.

Provision `COMPOSIO_API_KEY` in the native Hermes operator environment after
setup (`%LOCALAPPDATA%\hermes\.env` on Windows, or the equivalent Hermes
operator `.env` elsewhere). Never print, commit, or place that key in this
workspace. Set Desktop's **Default project directory** to this deployed
directory as well; Desktop's saved directory and the project-plugin opt-in are
separate settings. Restart Desktop or the gateway after changing them.

Use `/connect-google` to authorize Gmail and Calendar, then
`/mail-status`, `/calendar-status`, and the read/search tools to inspect data.
Gmail supports search, thread inspection, drafting, replying, and sending. Calendar writes retain the native approval boundary.
Provider failures and missing connections are errors, not successful results.

The owner is installation-bound and shared by CLI/Desktop across business
profiles; workspace and RAG authorization remains profile/workspace-scoped.
Telegram identities are never auto-linked. Missing owner binding retains
gateway caller behavior, while malformed binding fails closed. Local mode is
not a shared backend or multi-user service; each installation must be
provisioned separately.

### Zalo Bot Platform: private text chat (H016)

The opt-in `zalo-platform` plugin uses the official **Bot Platform**, not Zalo
OA or a personal-account bot. It feeds private text messages into the normal
Hermes gateway, authorization, profile routing, and session pipeline.

Install with the same Hermes interpreter/environment that runs the gateway.
`httpx` is already a Hermes dependency; no Zalo SDK or additional service is
required. The host must support `PluginContext.register_platform` and the native
`BasePlatformAdapter` lifecycle/credential-lock helpers.

From this deployed directory, copy the plugin into the **gateway owner's**
operator home. Do not install a second polling instance in each business profile.

Windows PowerShell (default installation):

```powershell
$HermesHome = Join-Path $env:LOCALAPPDATA "hermes"
Copy-Item -Recurse -Force ".hermes/plugins/zalo-platform" "$HermesHome/plugins/"
hermes plugins enable zalo-platform --no-allow-tool-override
hermes config set platforms.zalo.enabled true
```

Linux (use the actual service user's `HERMES_HOME`):

```bash
export HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
mkdir -p "$HERMES_HOME/plugins"
cp -R .hermes/plugins/zalo-platform "$HERMES_HOME/plugins/"
hermes plugins enable zalo-platform --no-allow-tool-override
hermes config set platforms.zalo.enabled true
```

If the existing deployment already symlinks `$HERMES_HOME/plugins` to this
workspace's `.hermes/plugins`, **skip the copy**. Pulling source updates refreshes
the plugin through that link; enablement and credentials remain operator-owned.
For a copied installation, repeat the copy after updating source.

Privately edit the native operator `.env` and set `ZALO_BOT_TOKEN` to the token
from Zalo Bot Creator. Do not put it in this workspace, shell command history,
screenshots, Git, or shared logs. For pairing, both `ZALO_ALLOW_ALL_USERS` and
`GATEWAY_ALLOW_ALL_USERS` must be unset/false, and global allowlists must not
grant unintended users access. Do not change global policy without reviewing
its effect on existing channels.
The plugin refuses to start if an existing webhook is configured; it never
deletes or replaces one automatically.

Restart the existing gateway using its service manager (do not start a second
poller), then send a private message to the bot. When native access policy
requires pairing, approve the returned code locally:

```text
hermes pairing approve zalo <PAIRING_CODE>
```

Only approve the code from your own conversation. Send two successive text
messages after approval and verify both replies and conversation continuity.
Alternatively configure `ZALO_ALLOWED_USERS` with approved Zalo sender IDs.
Zalo identities are not linked to Telegram or the local CLI/Desktop owner.

Native global authorization is honored, not overridden by this plugin.
With `GATEWAY_ALLOW_ALL_USERS=true` and no restricting allowlist, anyone who can
message the bot can invoke Hermes without pairing. The local operator explicitly
selected retaining this open policy; that choice is not a safe production
default and should be revisited before VPS rollout.

**Scope and deployment limits:**

- Text-only private conversations. Groups, images, voice, and documents are not
  supported by this adapter. There is no `sendFile`/`sendDocument` API.
- Long replies are split to the official 2,000-character limit.
- Polling needs outbound HTTPS only and runs on Windows or Linux. Zalo recommends
  it for local/development use; production VPS rollout needs a separately
  configured public HTTPS webhook deployment. Webhook mode is not implemented
  in this milestone. Do not claim guaranteed delivery across polling outages.
- Stop the Windows poller before enabling the same token on Linux. Native locks
  prevent duplicate pollers on one host, not across two machines.
- A send timeout may mean the server already accepted the message. The adapter
  reports failure rather than blindly resending a whole response.
- End-to-end acceptance requires real Zalo messages, restart, and a Telegram
  regression check; mocked transport checks alone are insufficient.

Official references: [API/authentication](https://bot.zapps.me/docs/call-api/),
[getUpdates limitations](https://bot.zapps.me/docs/apis/getUpdates/),
[sendMessage](https://bot.zapps.me/docs/apis/sendMessage/),
[webhook setup](https://bot.zapps.me/docs/apis/setWebhook/).

### Optional: Langfuse Tracing Plugin (`langfuse-observer`)

> **Feature Status:** Pending verification. No credentials bundled.

- **Opt-in Project Plugin:** `langfuse-observer` is located in `.hermes/plugins/langfuse-observer`. Requires `HERMES_ENABLE_PROJECT_PLUGINS=1` in the operator environment.
- **Mutual Exclusivity:** Never enable `langfuse-observer` together with the native `observability/langfuse` exporter.
- **Interpreter Requirement:** The `langfuse` SDK must be installed directly in the host Hermes runtime interpreter, not in `src/.venv`. SDK installation is an operator prerequisite step and is not run automatically.
- **Plugin Management:** Use documented Hermes CLI commands only:
  ```text
  hermes plugins list
  hermes plugins enable langfuse-observer
  hermes plugins disable langfuse-observer
  ```
- **Privacy & Dashboard:** Tracing exports to an existing operator-only private dashboard on Langfuse Cloud Hobby (no public share links). When enabled and verified, real Telegram and WhatsApp messages and tool inputs/outputs are captured after client-side redaction and truncation (`sanitized` capture mode); pattern-based filtering is not a DLP guarantee.
- **Retention & Operational Constraints:** Langfuse Cloud Hobby provides a 30-day data access window (not automated deletion). Automated alerts (e.g. Telegram alert delivery) are deferred; operators monitor export health manually. Trace verification requires real channel readback from persisted observations on the Cloud dashboard.

## Python Tool Runtime

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) on the host, then bootstrap the locked Python 3.12 environment and Chromium once after each deployment update:

```text
Windows: setup.cmd
Linux:   chmod +x setup.sh && ./setup.sh
```

Do not copy or commit `.venv`; uv recreates it from `.python-version`, `pyproject.toml`, and `uv.lock`. Skills invoke project tools with `uv run --frozen python ...`, so their interpreter and dependencies do not depend on the Python used by Hermes itself. Operator setup owns dependency and browser installation; chat-driven agents must not run `uv sync`, modify the lockfile, or install packages.


Tavily research uses one operator secret. On Windows, place TAVILY_API_KEY in
%LOCALAPPDATA%\hermes\.env; use the equivalent Hermes operator/profile env on
other platforms. Do not store credentials in this workspace or login via flags.
`tavily`; the official CLI reads the same environment variable:

```text
hermes config set web.search_backend tavily
hermes config set web.extract_backend tavily
```
Start a new Hermes session with this workspace configured. Use `/hermes-project` for capability routing, `/research` for public-web evidence or current-response document analysis, and `/hermes-azure-rag` when approved documents must persist beyond the current response or a question uses retained company knowledge. Durable attachments go to Azure and must not fall back to generic memory or OCR.

All bot users share the fixed `internal` knowledge group in V1. The CLI does
not accept access groups from chat. Every user may search and manage documents;
delete still requires explicit confirmation of the exact source path.

Research keeps ordinary runs in session only. Durable dossiers require an
explicit `save`, `track`, or `watch` request; V1 records watch intent but does
not schedule it. Optional deep-research providers, scheduled research, DOCX,
and PDF delivery are not project capabilities until separately verified.
Gmail and Calendar are available only after explicit Google setup/connection;
this workspace provides no outbound Gmail capability.

## Ownership

- This `AGENTS.md` is Hermes runtime context.
- Each skill is a directory containing `SKILL.md`.
- Create `scripts/`, `references/`, or `templates/` only inside skills that need them.
- MCP requires `mcp_servers` in global configuration and a separate feature verifier.
- Advertise a capability only after its implementation and verifier exist.

## Email Intake & Commands (H009)

- `/connect_gmail` (`/connect_email`, `/connect_mail`): OAuth2 Google connection link (DM only).
- `/mail_status` (`/email_status`): Check connected mailbox accounts and connection IDs.
- `/disconnect_gmail <id>` (`/disconnect_email <id>`): Disconnect linked mailbox.
- `/share_mailbox <id> <chat_id>`: Propose sharing mailbox with Telegram group.
- `/email_grant <req_id> approve|deny`: Operator decision on mailbox sharing.
- Natural language queries trigger `email_search` and `email_get_thread` automatically.
