# Hermes Progress

## Harness Status

- Phase: H006 Azure Hybrid RAG active; implementation batch 1 covers feature state, contracts, and manifest generation lifecycle.
- Workspace: isolated worktree `C:\Hermes-Business-Agent\.worktrees\h006-azure-rag` on `feature/h006-azure-rag`.
- Git remote: `https://github.com/BPhucKHMT/Hermes_Business_Agent.git`.
- WIP limit: 1; current active count: 1 (`H006`).

## Completed

- H001–H005 — `passing` with recorded independent evidence.
- D012 records the approved app-owned Azure Hybrid RAG architecture.
- H006 defines exact Layer 1–3 verification and depends on H005.
- Existing research Layer 1 and Layer 2 passed before H006 implementation.

## H006 Current Work

- Added structured `EvidenceResult`; retrieval contracts cannot contain a generated answer.
- Added supported relative source-path validation and truthful format locator rules.
- Added atomic manifest writes, stable document IDs, SHA-256 idempotency, pending/active generations, full expected chunk-set activation, prior-generation preservation on failure, and active manifest snapshots.
- Added `tests/verify_knowledge.py` for H006 state, runtime/secret boundaries, contracts, add/idempotency, partial activation rejection, replacement failure, retry, and generation swap.

## Operational State

- Production Hermes CWD remains deployed `src/`.
- Installed Hermes source under `%LOCALAPPDATA%\hermes\hermes-agent` remains unchanged.
- `docs/` remains local-only and Git-ignored; implementation must not depend on it at runtime.

## Blockers

- None for offline Tasks 1–8.
- Layer 3 owner: operator/user. Unblock condition: approved Azure resources/credentials, approved synthetic or customer corpus, and approved Telegram test chat.
- Customer acceptance owner: user. Unblock condition: real approved documents plus 10 KB questions and 5 task runs.

## Next Action

1. Run H006 JSON, Layer 1, then Layer 2 verification; fix only batch 1 failures.
2. Commit Task 1–3 checkpoint.
3. Next session inspects dependencies and implements Task 4 Azure client boundary with fake transport.
4. Do not move H006 to `passing`; independent verifier owns that transition after Layer 3.

## Handoff Notes

- `feature-list.json` is state authority; H006 is the only active feature.
- Runtime instructions must stay English and portable.
- Never commit secrets, tokens, customer PII, runtime documents, local usage files, or `docs/`.
