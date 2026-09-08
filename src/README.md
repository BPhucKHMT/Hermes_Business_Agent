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
Gmail remains read-only. Calendar writes retain the native approval boundary.
Provider failures and missing connections are errors, not successful results.

The owner is installation-bound and shared by CLI/Desktop across business
profiles; workspace and RAG authorization remains profile/workspace-scoped.
Telegram identities are never auto-linked. Missing owner binding retains
gateway caller behavior, while malformed binding fails closed. Local mode is
not a shared backend or multi-user service; each installation must be
provisioned separately.

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
