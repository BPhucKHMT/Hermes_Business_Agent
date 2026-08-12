# Hermes Progress

## Harness Status

- Phase: H005 evidence-grounded research implementation.
- Scope: manual Telegram research V1 under `src/`; cron and Gmail deferred.
- Git: initialized at project root.
- WIP limit: 1.

## Current Work

- H005 — `active`.
- Plan: `docs/plan/research_agent.md`.
- Latest approved Telegram research session: `20260811_172604_40cdbf34`.
- Root cause confirmed: initial HTML directive was backtick-wrapped and intentionally ignored by the gateway parser; retry exposed an unverified streaming-delivery boundary.
- `2026-08-12`: added project-owned regression contract requiring an existing report and a bare final `MEDIA:<absolute-path>` line; no Hermes installation source changed.
- `2026-08-12`: implemented canonical dossier validation, atomic temporary/saved storage, `save`/`track`/`watch`/`load`/`delete`/TTL cleanup, and replaceable safe HTML rendering under `src/.runtime/research/`. Removed generated reports from `src/` root.
- Current step: run fresh inbound Telegram research and persistence lifecycle verification.

## Baseline Verification

- Verified at: `2026-08-10T10:00:08Z`.
- Layer 1: exit `0`.
- Layer 2: exit `0`.
- Layer 3: exit `0`.

## Completed

- H001 — state `passing`.
- H002 — state `passing`.
- H003 — state `passing`; independent verification `2026-08-11T04:37:23Z`, schema và Layer 1–3 exit `0`.
- H004 — state `passing`; independent verification `2026-08-11T06:22:53Z`, Layer 1–3 exit `0`.

## Blockers

- H005 Telegram HTML attachment Layer 3 — owner: independent verifier. Project-owned contract fix passes Layer 1 and Layer 2. Fresh Hermes one-shot states that the actual directive must be plain text, backticks/code fences are forbidden, and missing files must not emit `MEDIA:`.
- Unblock condition: approved Telegram chat completes a fresh inbound research run; verifier confirms HTML arrives and records gateway upload evidence, command/event, UTC timestamp, exit status, and result.

## Next Action

1. Reload gateway through documented operator mechanism so fresh sessions read updated `src/skills/research`.
2. Send one bounded inbound research request from approved Telegram chat and confirm brief when requested.
3. Verify final raw response ends with bare `MEDIA:<absolute-path>`, report exists, and Telegram receives native HTML document.
4. Record independent Layer 3 evidence; keep H005 `active` until remaining release checklist passes.

## Handoff Notes

- Read according to startup order.
- `feature-list.json` is state authority; H005 is the only active feature.
- H005 passes only after the real Telegram → search → read → evidence → HTML → follow-up → persistence/no-persistence flow receives independent verifier evidence.
- Do not modify `%LOCALAPPDATA%\hermes\hermes-agent`; back up operator `config.yaml` before routing Hermes to deployed `src`.
