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

- Batch 1 commit `5a29a5b` added `EvidenceResult`, path contracts, and atomic manifest generation lifecycle.
- Added secret-free `src/.env.example` Azure deployment contract.
- Added dependency-free injectable Azure HTTP boundary for Python 3.9: strict HTTPS/config validation, timeout, bounded retries/backoff, `Retry-After`, sanitized error codes, and no response-body leakage.
- Search query uses only query key; mutation uses admin key.
- Fake transport covers success, timeout, 401/403, 400, 429, 5xx, retry exhaustion, invalid JSON, credential separation, and secret redaction.

## Operational State

- Python runtime is 3.9.13; Azure SDK packages are not installed. Task 4 uses stdlib transport rather than adding dependencies.
- Production Hermes CWD remains deployed `src/`.
- Installed Hermes source under `%LOCALAPPDATA%\hermes\hermes-agent` remains unchanged.
- `docs/` remains local-only and Git-ignored; implementation must not depend on it at runtime.

## Blockers

- None for offline Tasks 5–8.
- Layer 3 owner: operator/user. Unblock condition: approved Azure resources/credentials, approved synthetic or customer corpus, and approved Telegram test chat.
- Customer acceptance owner: user. Unblock condition: real approved documents plus 10 KB questions and 5 task runs.

## Next Action

1. Commit Task 4 Azure boundary checkpoint.
2. Next batch implements Task 5 extraction/chunking/ingestion with proved format fixtures; do not claim formats lacking installed parser support.
3. Keep Azure service payloads behind current injected client and test with fake transport before live resources.
4. Do not move H006 to `passing`; independent verifier owns that transition after Layer 3.

## Handoff Notes

- `feature-list.json` is state authority; H006 is the only active feature.
- Runtime instructions must stay English and portable.
- Never commit secrets, tokens, customer PII, runtime documents, local usage files, or `docs/`.
