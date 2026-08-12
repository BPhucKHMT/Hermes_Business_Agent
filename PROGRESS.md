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
- Batch 2 commit `ba9e784` added secret-free Azure config and injected HTTP client boundary.
- Added deterministic structure-aware extraction/chunking: TXT/Markdown headings and lines, HTML text, CSV headers/rows, PDF pages with deterministic OCR fallback, PPTX slides, and XLSX sheets/rows/cell ranges.
- DOCX fails actionable because `python-docx` is not installed; runtime does not claim support yet.
- Added channel-neutral ingestion orchestration: validate access groups, extract, chunk, embed, upload pending generation, verify complete chunk-ID set, atomically activate manifest, then delete prior generation.
- Offline fixtures prove deterministic chunk IDs/locators, PDF OCR routing, PPTX/XLSX parsing, unchanged idempotency, replacement cleanup, and failed activation preservation.

## Operational State

- Python runtime is 3.9.13. Installed parsers: `pypdf`, `python-pptx`, `openpyxl`, BeautifulSoup/stdlib HTML support. `python-docx` absent.
- Azure SDK packages are not installed; current Azure boundary uses injected stdlib transport.
- Production Hermes CWD remains deployed `src/`; installed Hermes source remains unchanged.
- `docs/` remains local-only and Git-ignored; implementation does not depend on it.

## Blockers

- DOCX support owner: implementation/operator dependency decision. Unblock condition: approve/use installed `python-docx` or add it explicitly, then add a real DOCX fixture.
- Layer 3 owner: operator/user. Unblock condition: approved Azure resources/credentials, approved synthetic or customer corpus, and approved Telegram test chat.
- Customer acceptance owner: user. Unblock condition: real approved documents plus 10 KB questions and 5 task runs.

## Next Action

1. Commit Task 5 extraction/ingestion checkpoint.
2. Next batch implements Task 6 hybrid retrieval request, manifest-snapshot generation filters, and `EvidenceResult` mapping with fake Search/embedding clients.
3. Do not claim DOCX support until parser and fixture pass.
4. Do not move H006 to `passing`; independent verifier owns that transition after Layer 3.

## Handoff Notes

- `feature-list.json` is state authority; H006 is the only active feature.
- Runtime instructions must stay English and portable.
- Never commit secrets, tokens, customer PII, runtime documents, local usage files, or `docs/`.
