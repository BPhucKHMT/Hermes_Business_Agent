# Hermes Progress

## Harness Status

- Phase: H005 complete; next feature not yet activated.
- Scope delivered: manual Telegram evidence-grounded research V1 under `src/`; cron and Gmail remain deferred.
- Workspace: `C:\Hermes-Business-Agent`.
- Git remote: `https://github.com/BPhucKHMT/Hermes_Business_Agent.git`.
- WIP limit: 1; current active count: 0.

## Completed

- H001–H004 — `passing` with recorded independent evidence.
- H005 — `passing` at `2026-08-12T07:13:00Z` from user acceptance plus runtime evidence review.
- Complex Telegram flow passed: brief/confirmation, iterative search/read, cited executive brief, native HTML attachment, and evidence-based follow-up.
- Persistence flow passed: temporary default, explicit `save`, fresh-session `load`, manual `track`, intent-only `watch`, `delete`, then `not found`.
- Canonical `dossier.json` drives replaceable safe HTML; future PPTX must read dossier data, not parse HTML.
- Temporary and durable artifacts live under `src/.runtime/research/`; generated reports no longer pollute `src/` root.
- Layer 1 and Layer 2 passed after workspace rename; `feature-list.json` is valid.

## Operational State

- Workspace renamed from `C:\Hermes agent` to `C:\Hermes-Business-Agent`.
- Operator config now uses `C:/Hermes-Business-Agent/src` and `C:/Hermes-Business-Agent/src/skills`.
- Config backup: `%LOCALAPPDATA%\hermes\config.yaml.20260812T070312Z.bak`.
- Installed Hermes source under `%LOCALAPPDATA%\hermes\hermes-agent` remains unchanged.
- Gateway must be started by operator after workspace rename.

## Git State

- New clean history published to `origin/main`; head before this handoff update: `d66d288`.
- Commit author is only `BPhucKHMT <23521208@gm.uit.edu.vn>`; no AI/co-author metadata.
- `docs/` is local-only and Git-ignored by user request. It is not available to fresh clones.
- `.claude/`, `.h005*.json`, and `src/.runtime/` are local-only and ignored.
- Local branch `backup/pre-clean-history` preserves old history and must not be pushed.

## Blockers

- None for H005.
- No H006 entry exists yet; do not start implementation before defining behavior, verification Layers 1–3, dependency on H005, and moving only H006 to `active`.

## Next Action

1. Start a fresh planning session and read startup files in the order required by `AGENTS.md`.
2. Select the next requirement from `requirement_customer.md`; PPTX/deck generation from canonical `dossier.json` is the current candidate.
3. Add H006 as `not_started`, define acceptance gates, then move it to `active` while keeping WIP=1.
4. Keep HTML renderer replaceable; do not make PPTX depend on parsing HTML.

## Handoff Notes

- `feature-list.json` is state authority; all defined features currently pass.
- Runtime instructions remain English and portable; repository engineering records may be Vietnamese.
- Never commit secrets, tokens, customer PII, runtime dossiers, local usage files, or `docs/`.
