---
type: project
created: 2026-05-25
updated: 2026-07-12
---

# Project Conventions

## Git Workflow
- Always create a new dedicated branch for major code changes.
- Branch name format should follow: `feature/[task-slug]` or `fix/[bug-slug]`.

## Supported AI platforms (AG Kit)
- `.agents/` is the canonical AG Kit source for Google Antigravity and Gemini-compatible discovery.
- Claude Code is supported through generated thin adapters under `.claude/` plus `.mcp.json` and `CLAUDE.md` routing references.
- Adapters must not duplicate canonical workflow bodies. Unsupported runtime primitives map to safe semantic equivalents or fail closed.
- Do not claim support for other assistants unless the user explicitly expands scope and executable compatibility evidence exists.
