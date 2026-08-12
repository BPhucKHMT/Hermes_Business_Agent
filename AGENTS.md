# Hermes Engineering Harness

## Scope and Context Boundary

Root `C:/Hermes agent` is the coding workspace. Files outside `src/` support planning, implementation, verification, and handoff; they are not production Hermes context.

`src/` is the complete production project root, wherever this repository is deployed. Hermes runtime configuration must use operator-supplied deployment paths and may connect only to paths under the deployed `src/` directory.

Production contract:

- Hermes CWD is deployed `src/`, never repository root.
- `src/AGENTS.md` owns production runtime context. `.hermes.md` is forbidden.
- Chatbot assets, skills, tools, MCP servers, scripts, templates, and runtime-owned files stay under `src/`.
- Production Hermes must not read or depend on root `AGENTS.md`, `CLAUDE.md`, `PROGRESS.md`, `DECISIONS.md`, `feature-list.json`, `requirement_customer.md`, or `docs/`.
- Coding agents work from repository root, read root harness, and may modify `src/` only through approved features.
- Do not modify Hermes runtime installation; do not commit operator config or runtime secrets.

## Session Startup Workflow

Read in order: `CLAUDE.md` → `DECISIONS.md` → `requirement_customer.md` → `PROGRESS.md` → `feature-list.json`.
Repository is source of truth; chat memory is not state.
Read this contract before updating project state.

## Working Rules

Choose work only from `feature-list.json`.
Keep WIP limit at 1: at most one feature may be `active`.
Record blockers in `PROGRESS.md` with owner and unblock condition.
Do not refactor or optimize before core behavior verification.
Do not mark `passing` without independent verifier evidence.

## Required Artifacts

`CLAUDE.md` defines behavioral policy.
`AGENTS.md` defines project workflow and verification gates.
`feature-list.json` owns machine-readable feature state.
`PROGRESS.md` owns session handoff, checks, blockers, and next action.
`DECISIONS.md` owns durable rationale and revisit conditions.
`requirement_customer.md` owns customer goals, requirements, guardrails, acceptance criteria, and unresolved questions.

## Feature State Contract

Valid states: `not_started`, `active`, `blocked`, `passing`.

Allowed transitions:

- `not_started → active`
- `active → blocked`
- `blocked → active`
- `active → passing`

`not_started → passing` is forbidden.
Only an independent verifier may move a feature to `passing`.
Passing evidence must include command, UTC timestamp, exit status, and result.

## Definition of Done

A feature is done only when acceptance behavior is met, applicable three layers pass,
and state is `passing` with independent verifier evidence.
Update progress and decisions when needed.
Clean task artifacts and leave a readable handoff.

## Three-Layer Verification

Run verification in order:

1. Layer 1: static or schema checks.
2. Layer 2: artifact behavior checks.
3. Layer 3: system-boundary checks.

If Layer 1 fails, do not run Layer 2. If Layer 2 fails, do not run Layer 3.
Harness-only checks do not prove product or runtime behavior.

## End-of-Session Workflow

Verify work, then update state.
Update handoff and decisions.
Clean temporary material.
Confirm a fresh session can follow startup order and continue safely.

## Reference Map

- `docs/Harness.docx`
- `docs/Hermes Project.docx`
- `docs/Tổng quan các tính năng chính của Hermes Agent.docx`
