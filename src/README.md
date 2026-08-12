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
```

Start a new Hermes session with this workspace configured. Use
`/hermes-project` for capability routing or `/research` for evidence-grounded
manual research over public web sources and user-supplied documents.

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
