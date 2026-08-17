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

Set `HERMES_ENABLE_PROJECT_PLUGINS=1` in the operator environment. This opts into trusted code under `.hermes/plugins/`; never enable project plugins from an untrusted workspace. Restart Hermes after changing either setting.

## Python Tool Runtime

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) on the host, then bootstrap the locked Python 3.12 environment and Chromium once after each deployment update:

```text
Windows: setup.cmd
Linux:   chmod +x setup.sh && ./setup.sh
```

Do not copy or commit `.venv`; uv recreates it from `.python-version`, `pyproject.toml`, and `uv.lock`. Skills invoke project tools with `uv run --frozen python ...`, so their interpreter and dependencies do not depend on the Python used by Hermes itself. Operator setup owns dependency and browser installation; chat-driven agents must not run `uv sync`, modify the lockfile, or install packages.

Start a new Hermes session with this workspace configured. Use `/hermes-project` for capability routing, `/research` for public-web evidence or current-response document analysis, and `/hermes-azure-rag` when approved documents must persist beyond the current response or a question uses retained company knowledge. Durable attachments go to Azure and must not fall back to generic memory or OCR.

All bot users share the fixed `internal` knowledge group in V1. The CLI does
not accept access groups from chat. Every user may search and manage documents;
delete still requires explicit confirmation of the exact source path.

Research keeps ordinary runs in session only. Durable dossiers require an
explicit `save`, `track`, or `watch` request; V1 records watch intent but does
not schedule it. Optional deep-research providers, scheduled research, Gmail,
DOCX, and PDF delivery are not project capabilities until separately verified.

## Ownership

- This `AGENTS.md` is Hermes runtime context.
- Each skill is a directory containing `SKILL.md`.
- Create `scripts/`, `references/`, or `templates/` only inside skills that need them.
- Secrets belong in `%LOCALAPPDATA%\hermes\.env`, not this workspace.
- MCP requires `mcp_servers` in global configuration and a separate feature verifier.
- Advertise a capability only after its implementation and verifier exist.
