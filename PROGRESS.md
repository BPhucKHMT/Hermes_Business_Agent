# Hermes Progress

## Harness Status

- Phase: H006 Azure-managed RAG active; offline E2E implementation passes Layers 1–2.
- Workspace: isolated worktree `C:\Hermes-Business-Agent\.worktrees\h006-azure-rag` on `feature/h006-azure-rag`.
- WIP limit: 1; H006 is only active feature.

## Completed

- H001–H005 remain `passing` with recorded evidence.
- D013 supersedes app-owned D012 after official Azure feature research.
- Removed handwritten parser, chunker, embedding orchestration, generation manifest, raw HTTP and retry code.
- Added official Azure Blob/Search SDK clients.
- Added two managed ingestion paths:
  - Layout-supported PDF/DOCX/PPTX/XLSX/HTML to Blob, Document Intelligence Layout Skill, embedding and index projection.
  - TXT/Markdown/CSV to Blob cracking, Text Split Skill, embedding and index projection.
- Added resource definitions for one vector index, two data sources, two skillsets and two indexers.
- Added CLI for `provision`, `upload`, `delete`, `index`, `status`, and `search`.
- Offline verifier proves source routing, Blob metadata, indexer trigger/status, hybrid text plus vector query, access filter and EvidenceResult mapping.

## Verification

- `python tests/verify_knowledge.py --layer 1` — pass, 2026-08-13.
- `python tests/verify_knowledge.py --layer 2` — pass, 2026-08-13.
- `python tests/verify_research.py --layer 1` — pass, 2026-08-13.
- `python tests/verify_research.py --layer 2` — pass, 2026-08-13.
- `python -m json.tool feature-list.json` and `git diff --check` — pass, 2026-08-13.
- Evidence is implementer-local, not independent verifier evidence. H006 stays `active`.

## Blockers

- Azure Layer 3 owner: operator/user. Unblock by copying `src/.env.example` to `src/.env`, filling approved Storage, Search and Azure OpenAI resources, and enabling Blob soft delete before first indexer run.
- Layout Skill owner: operator/Azure region. Unblock when provisioning succeeds on approved Search tier/region and attached billable Foundry resource behavior is confirmed.
- Citation fidelity owner: verifier. Unblock by indexing synthetic files and inspecting real page/format locator output.
- Telegram E2E owner: user/operator. Unblock with approved bot chat after Azure E2E passes.
- Customer acceptance owner: user. Unblock with approved documents, 10 KB questions and 5 task runs.

## Next Action

1. User fills `src/.env` locally without sharing secrets in chat.
2. Run CLI provisioning and synthetic upload/index/status/search.
3. Fix only errors proven by Azure response; do not add custom parser fallback.
4. Wire verified lifecycle into Hermes knowledge skill and approved Telegram chat.
5. Independent verifier runs Layer 3 before H006 can become `passing`.

## Handoff Notes

- `feature-list.json` remains state authority.
- Runtime code/config stays under deployed `src/`; local plan under ignored `docs/` is not runtime dependency.
- Never commit `.env`, Azure keys, Telegram tokens, customer PII or source documents.
