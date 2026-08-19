# Hermes Progress

## Harness Status

- Phase: H006 Azure-managed RAG active; Azure TXT/PDF ingestion, hybrid retrieval, Telegram album override, and lifecycle routing pass offline. Telegram Layer 3 remains.
- Workspace: `C:\Hermes-Business-Agent` on `main`; old isolated worktree remains but is not current source of truth.
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
- Fixed live Azure SDK 11.6 compatibility: preserve native Blob soft-delete discriminator and construct `SearchIndexer` explicitly because wrapper `from_dict` drops required fields.
- Fixed Blob ACL metadata to JSON-array format required by `jsonArrayToStringCollection` and corrected custom metadata source names.
- Provisioned approved Azure containers, index, datasources, skillsets and indexers.
- Synthetic TXT E2E processed 1 item with zero failures/errors/warnings; hybrid retrieval returned the 37-day fact for `internal` and no evidence for an unauthorized group.
- Synthetic PDF E2E processed 1 item with zero failures/errors/warnings; Layout retrieval returned the 91-day fact with `source_path` and `page_number: 1`.
- Deleted both synthetic Blobs; native soft-delete propagation reduced Search document count to 0.
- Offline verifier proves source routing, Blob metadata, Azure SDK resource serialization, indexer trigger/status, hybrid text plus vector query, access filter and EvidenceResult mapping.
- Added `/knowledge` runtime skill for authorized search, grounded citations, conflict disclosure, and confirmed document lifecycle.
- Added fixed shared `internal` access for all bot users; chat and CLI cannot choose or remove the Azure ACL group.
- Added trusted project-local `telegram-album` platform override. Album arrivals register before download; dispatch waits for received in-flight siblings with a bounded maximum wait.
- Added regression coverage for 3, 5, and 10-file slow albums with one caption and exactly one agent event.
- Replaced phrase-oriented skill routing with current-response versus durable lifecycle boundaries, three positive and three negative examples, and retained-document follow-up ownership.
- Added Windows UTF-8 CLI output handling and a subprocess regression for Vietnamese JSON.
- Added retained-knowledge image/file delivery contract: verify a gateway-visible file, emit an unwrapped standalone `MEDIA:<absolute-path>`, distinguish recreated diagrams, and never claim failed delivery.
- Replaced the rejected fixed website recipe with an adaptive crawl-session protocol. Hermes browser actions remain agent-owned; deterministic code owns public URL validation, same-origin enforcement, resource ledgers, event provenance, capture binding, and Azure mutation boundaries.
- Added strict operator policy at `src/config/website_policy.json` using wall-clock, transferred-byte, asset-byte, and no-progress ceilings. Production code and runtime skill contain no page-count, depth, or fixed-scroll policy.
- Replaced ad hoc discovery/capture manifests with policy-bound `web-start`, `web-observe`, `web-finalize`, and `web-ingest` commands. Policy tampering, replayed events, unknown parents, private redirects, cross-origin capture, budget overruns, unbound captures, and arbitrary session paths fail closed.
- Updated `/hermes-azure-rag` so clear durable URL intent authorizes autonomous adaptive ingestion. It chooses installed browser capabilities from rendered observations and asks again only for risky boundaries, credential needs, budget expansion, or retained-content removal.
- Existing website Blob generation code remains connected. Real adaptive Hermes orchestration, exact Search readiness, image Azure resources, refresh, and delete verification still require completion/Layer 3 proof.
- Replaced direct Playwright executor with Crawl4AI 0.9.2 behind existing trusted crawl boundary. Hermes still owns public-target validation, same-origin frontier, convergence, budgets, provenance, artifact binding, and Azure lifecycle.
- Added uv project runtime pinned to Python 3.12 with cross-platform `uv.lock`; skills use `uv run --frozen`, independent of Hermes' Python runtime. One Crawl4AI browser is reused across each whole-site session.
- Fixed Crawl4AI's false anti-bot result for WebGL SPAs by removing only `--disable-gpu`, `--disable-gpu-compositing`, and `--disable-software-rasterizer` through a project-owned `BrowserManager`; direct reproduction proved these flags caused `Error creating WebGL context` and an empty React root.
- Added generic safe disclosure capture through Crawl4AI's awaited `before_retrieve_html` hook. Only enabled `button[type="button"][aria-controls][aria-expanded]` controls are clicked; exact live question/answer pairs are validated, appended to Markdown, recorded in the artifact manifest, and digest-bound.

## Verification

- `python tests/verify_knowledge.py --layer 1` — pass, 2026-08-13T09:08:32Z, exit 0.
- `python tests/verify_knowledge.py --layer 2` — pass, 2026-08-13T09:08:32Z, exit 0; expected SDK subtype warning remains.
- `python tests/verify_research.py --layer 1` — pass, 2026-08-13T09:08:32Z, exit 0.
- `python tests/verify_research.py --layer 2` — pass, 2026-08-13T09:08:32Z, exit 0.
- `%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\python.exe tests/verify_telegram_album.py` — pass, 2026-08-13T09:09:05Z, exit 0.
- Plugin manager discovery with project opt-in asserted registry `telegram` owner is `telegram-album` — pass, 2026-08-13T09:09:14Z, exit 0.
- `python -m json.tool feature-list.json` and `git diff --check` — pass, 2026-08-13T09:09:14Z, exit 0.
- Live Azure proof remains: TXT/PDF allowed retrieval, unauthorized no-evidence, PDF page 1, and soft-delete count 0.
- Live evidence is implementer-local, not independent verifier evidence. H006 stays `active`.
- `python tests/verify_knowledge.py --layer 1` — pass, 2026-08-15T18:01:19Z, exit 0.
- `python tests/verify_knowledge.py --layer 2` — pass, 2026-08-15T18:01:19Z, exit 0; image upload regression, OCR resource serialization, adaptive session, refresh diff, readiness and absence checks pass; expected SDK subtype warnings remain.
- `python tests/verify_research.py --layer 1` and `--layer 2` plus `git diff --check` — pass, 2026-08-15T18:01:24Z, exit 0.
- Live Azure provision — pass, 2026-08-15T17:51:03Z, exit 0; text and image containers/datasources/skillsets/indexers provisioned.
- Live synthetic website generation — pass, 2026-08-15T18:00:25Z, exit 0: text and PNG uploaded; fresh text/image indexer runs succeeded; exact readiness returned 1/1; query returned `page_text` and `image_ocr` evidence with marker `7429`; Blob delete propagated and Search absence returned true.
- First live attempt exposed stale-success polling; fixed by binding readiness waits to the submitted run. Delete completion now polls the actual Search-absence boundary because Azure can coalesce adjacent indexer submissions.
- Installed Hermes adaptive browser orchestration and Telegram delivery remain the only unverified product boundary.
- Telegram test at 2026-08-15T18:04Z exposed two failures: durable URL was converted to `titanai_services.md` and sent through generic `upload/index`; retained follow-up silently reread the live URL after global retrieval missed the requested facet.
- Fix adds exclusive durable-URL lifecycle routing, explicit prohibition on silent web/browser fallback, website provenance in `EvidenceResult`, one bounded multi-query KB repair, and mandatory `website_id`/legacy `source_path` continuity across follow-ups.
- Live scoped query at 2026-08-15T18:16:40Z, exit 0, returned exactly three `titanai_services.md` chunks and no unrelated document evidence. It also proved legacy retained data lacks project-level details and website provenance, so compliant answer must report insufficiency rather than reread or invent.
- Fresh final gates at 2026-08-15T18:17:18Z: knowledge Layer 1/2, research Layer 1/2, all knowledge Python compilation, and `git diff --check` pass, exit 0.
- `uv lock --check` and `uv run --frozen python -m compileall -q tools/knowledge` — pass, 2026-08-17T03:29:03Z, exit 0.
- `uv run --frozen python ../tests/verify_knowledge.py --layer 1` and `--layer 2` — pass, 2026-08-17T03:31:08Z, exit 0; expected Azure SDK subtype warnings only.
- `uv run crawl4ai-doctor` — pass, 2026-08-17T03:29:25Z, exit 0; Crawl4AI 0.9.2 rendered `https://crawl4ai.com` with Chromium headless.
- Live `uv run --frozen python tools/knowledge/knowledge.py web-crawl "https://example.com"` — pass, 2026-08-17T03:31:08Z, exit 0; trusted session, validated capture, one observed URL and one semantic state.
- `uv run --frozen python ../tests/verify_research.py --layer 1`, `--layer 2`, and `git diff --check` — pass, 2026-08-17T03:31:24Z, exit 0; line-ending warnings only.
- Live Titan Crawl4AI `web-crawl https://titanai.space/#faq` — pass, 2026-08-17T04:18:11Z, exit 0; session `0998e249-6e43-4347-b499-ad64c4f10fa1`, 1 canonical page, 7 disclosure answers, 1,807 answer characters, trusted artifacts, and validated generation `gen-79143d283e144166`.
- Live Titan `web-ingest` — pass, 2026-08-17T04:18:32Z, exit 0; Blob upload succeeded, `knowledge-text-indexer` succeeded, exact generation readiness returned 1/1.
- Live Titan `web-verify` — pass, 2026-08-17T04:18:48Z, exit 0; status `ready`, page `page-d321e39a5f981bcb7472`, no missing page IDs.
- Two generation-scoped Azure searches for project cost and outsourcing model — pass, 2026-08-17T04:19:03Z, exit 0; returned FAQ answer content with exact `website_id`, generation, page ID, `https://titanai.space/` citation, and no warnings.
- Final `uv lock --check`, knowledge Layer 1/2, and `git diff --check` — pass, 2026-08-17T04:19:40Z, exit 0; expected SDK subtype and line-ending warnings only. Gateway restarted successfully at PID 37656.

## Blockers

- Telegram E2E owner: user/operator plus independent verifier. Direct Crawl4AI and Azure generation/search boundaries now pass; unblock final product proof with a fresh Telegram durable-site request against gateway PID 37656.
- Customer acceptance owner: user. Unblock with approved documents, 10 KB questions and 5 task runs.
- Website Layer 3 independent evidence remains required. Implementer-local Titan crawl, ingest, verify, and scoped retrieval do not authorize moving H006 to `passing`.

## Next Action

1. In approved Telegram chat, query the retained Titan FAQ and confirm answer plus canonical citation from generation `gen-79143d283e144166`; no delete authorization is needed.
2. Independently verify exact deletion confirmation semantics: generic `ok` must not execute deletion. Do not delete the active Titan generation solely for this check.
3. Run remaining approved image OCR and safe refresh/delete Layer 3 scenarios if H006 acceptance still requires them.
4. Independent verifier records command, UTC timestamp, exit status, and result; only that verifier may move H006 to `passing`.

## Handoff Notes

- `feature-list.json` remains state authority; H006 stays `active`, not `passing`, with no independent H006 evidence.
- Current source of truth is `main` at `C:\Hermes-Business-Agent`; `.worktrees/h006-azure-rag` is stale and must not be edited.
- Runtime code/config stays under deployed `src/`; production CWD is deployed `src`.
- Azure resources are provisioned and empty after earlier synthetic cleanup; local `src/.env` is Git-ignored and must never be printed or committed.
- Expected Azure SDK 11.6 warning about `NativeBlobSoftDeleteDeletionDetectionPolicy` remains handled.
- Wide uncommitted H006 changes predate and include this session. Do not reset/revert unrelated work.
- Adaptive website files: `src/config/website_policy.json`, `src/tools/knowledge/policy.py`, `web.py`, `knowledge.py`, `storage.py`, `indexing.py`, `clients.py`, Azure resources, `src/.env.example`, `src/skills/hermes-azure-rag/SKILL.md`, and `tests/verify_knowledge.py`.
- Azure image OCR pipeline, exact-generation readiness, refresh diff/confirmation, and Search-backed delete are implemented and live Azure tested. Multimodal description remains optional and unconfigured; image OCR is the verified visual path.
- No login, CAPTCHA, paywall, credentialed, or private-network crawling is supported.
- Python tools are an uv project pinned to Python 3.12. Operator installs uv and runs `setup.cmd`/`setup.sh`; agents use `uv run --frozen` and never mutate environment or lockfile.
- Crawl4AI 0.9.2 is the trusted renderer/extractor. Project-owned browser manager preserves WebGL; one headless Chromium session is reused for each site; Hermes remains policy/frontier/provenance authority.
- Titan active Azure generation is `gen-79143d283e144166` for `website-55198994edd0927f15ee`; validated local source is `src/.runtime/knowledge/web-sessions/0998e249-6e43-4347-b499-ad64c4f10fa1.validated.json`.
- Undetected/Patchright mode was researched but is not enabled: trusted evidence showed no anti-bot block, only WebGL-disabled launch flags. Use undetected mode only after real block evidence and operator-provisioned browser dependencies.
- H006 remains `active` until fresh Hermes/Telegram Layer 3 and independent verifier evidence.

## 2026-08-17 scope-aware crawl and retained-image handoff

- Added explicit required crawl scope: `--scope page|site`. `page` captures one canonical page and ignores child frontier; `site` follows the complete safe same-origin frontier with related-content ordering. URL fragments such as `#faq` normalize without limiting page content.
- Relevant images now use semantic `figure`/`figcaption` or meaningful `alt`; logos, icons, avatars, sprites, and small decoration are excluded. Downloads revalidate public redirect targets, enforce MIME/byte ceilings, stream bounded data, retain digest-named files under runtime root, and bind SHA-256 metadata into the trusted artifact.
- Split resource accounting into `content_asset_bytes` (50 MiB) and `screenshot_bytes` (20 MiB). Root page keeps audit screenshot; site child pages do not capture screenshots by default.
- Remaining owner/blocker: operator must run a new Telegram conversation for Layer 3; independent verifier must record command, UTC timestamp, exit status, and result before moving H006 to `passing`.

## 2026-08-17 Telegram Layer 3 and Azure operations

- Fresh Telegram session `20260817_143752_58011e46` successfully executed the official `uv run --frozen` workflow after two operator environment fixes: expose uv to Git Bash at `C:/Users/ADMIN/bin/uv`, then strip Hermes-inherited `PYTHONPATH` in the operator uv shim so project `.venv` packages cannot be shadowed by Hermes runtime packages. No Hermes upstream files or runtime venv were modified.
- Telegram crawled one Anthropic page, uploaded page text plus eight retained image assets, and ran `web-ingest`/`web-verify`. Text readiness passed 1/1. Image readiness reached 4/8, so Layer 3 remains partial rather than passing.
- Azure image indexer diagnostic is authoritative: without a billable Foundry/Cognitive Services resource, built-in AI enrichment is limited to 20 documents per indexer per day. `knowledge-image-indexer` stopped with `transientFailure` after the free quota was exhausted. The four missing image documents remain retained in Blob; no curl/live-web fallback is allowed or needed.
- The latest partial generation is `gen-e7e414eaef0c4eb5`, validated session `879bbc7a-b263-4651-8c9c-f55d3d532678`, website `website-b19f62aeb044f9fe741a`, page `page-ffc229d83891918f8206`. Missing assets include the coding-agent diagram `asset-f4d05f5e5cfd0b86980e`.
- Cost Management showed USD 31.92 of USD 31.93 total from Azure Cognitive Search between August 13 and 17. Search compute is billed continuously while the paid service exists; stopping gateway/indexers does not stop that charge. Free tier migration is an operator architecture/deployment decision and was not applied.
- Bot inferred `page` scope from a single article link instead of asking the ambiguous-scope question. This is a remaining Layer 3 UX defect against the approved policy; do not mark H006 passing until corrected and independently verified.
- H006 remains `active`. Unblock conditions: restore image readiness 8/8 through quota reset or approved billable enrichment, fix ambiguous-scope prompting, run a fresh Telegram E2E, and obtain independent verifier evidence.

## 2026-08-17 retained-knowledge source routing

- Fresh Telegram query `1 project ở Titan AI thường cần nhiêu tiền` incorrectly selected public web search even though Titan evidence was retained. Root cause was source selection before the RAG skill: the RAG no-fallback contract was correct once selected, but the coordinator lacked ordered first-turn routing for retained public sources.
- Root routing now uses first-match precedence: explicit source, retained continuity, durable lifecycle, live/current web signals, supplied-input transforms, stable general knowledge, then retained-knowledge candidates. A fresh session does not reduce KB priority, and retained candidates include public websites, articles, media, entities, products, projects, prices, policies, and processes that could have been ingested.
- A bounded KB attempt now means the original query plus at most two short query variants in one repair command. Evidence must cover the requested facet. Remaining `no_evidence` or wrong-facet results report insufficiency and require explicit user consent before live-web research; version/effective-date conflicts remain explicit.
- TDD evidence: new Layer 1 routing assertions failed before skill changes at 2026-08-17T09:04:43Z, then passed at 2026-08-17T09:07:28Z. Full regression gates passed at 2026-08-17T09:07:50Z: uv lock, knowledge Layer 2, research Layer 1/2, Telegram album, compileall, and `git diff --check`, exit 0; expected Azure SDK subtype and line-ending warnings only.
- H006 remains `active`. Static contract tests do not prove model tool choice. Unblock this routing slice with fresh Telegram tool traces for retained hit, no-evidence/wrong-facet consent gate, explicit live query, stable general knowledge, and transform-only prompts.

## 2026-08-18 Image indexer disabled (quota throttling fix)

- Azure image indexer (`knowledge-image-indexer`) was blocking crawl pipeline due to Azure Cognitive Services free-tier quota exhaustion (20 docs/day). Indexer entered `transientfailure` and retried indefinitely, stalling the entire `web-ingest` flow.
- Added `HERMES_IMAGE_INDEXER` env var (default `true`). Set to `false` in `src/.env` to disable image asset uploads and image indexer runs without removing any code.
- Changed files: `src/tools/knowledge/knowledge.py` (4 gate points), `src/tools/knowledge/storage.py` (early return when `image_container=None`), `src/.env`, `src/.env.example`, `src/skills/hermes-azure-rag/SKILL.md` (note in Document Lifecycle), `tests/verify_knowledge.py` (Layer 1 env set + Layer 2 None-container test case).
- All 4 verification gates re-run and confirmed pass at 2026-08-18T04:56:49Z, exit 0: knowledge Layer 1/2, research Layer 1/2; expected Azure SDK subtype warning only.
- Gateway restarted to pick up new env var. `layout` and `text` indexers remain active and sufficient for all text-based knowledge workflows.
- To re-enable image indexing: set `HERMES_IMAGE_INDEXER=true` in `src/.env` and restart gateway. No code changes needed.

## 2026-08-19 Project Hermes v2 Build Doc assimilation

- Read and analyzed full specification from `docs/Project_Hermes_v2_Build_Doc.docx` (August 2026, prepared by Klaus), which supersedes the initial 2-week intern brief.
- Updated `requirement_customer.md` to reflect the comprehensive AI Chief of Staff & Sub-Agent Fleet vision: 3 isolated business workspaces (Protein Bar [doors open 8 Dec 2026], Client Projects, TITAN AI), 5-layer logical isolation, 13 sub-agent fleet, 4 autonomy tiers (Tier 0-3), machine-verifiable evidence layer, proactive engine & ADHD support, 5-layer memory architecture, and 6+2 week rollout plan.
- Updated `DECISIONS.md` with durable architectural decisions D014 (Single agent with 5-layer workspace isolation vs 3 separate bots), D015 (Workspace priority rollout order: Protein Bar > Client Projects > TITAN AI), D016 (4-tier autonomy with no silent money movement), D017 (Independent machine-verifiable evidence layer), and D018 (Layered memory architecture & Obsidian vault).
- Updated `AGENTS.md` Reference Map to include `docs/Project_Hermes_v2_Build_Doc.docx`.
- Verified H002 requirements assertions in `feature-list.json`: `requirements verification: PASS`.
- All verification layers re-confirmed: knowledge Layer 1/2, research Layer 1/2, `python -m json.tool feature-list.json`, and `git diff --check`.

## 2026-08-19 Protein Bar Workspace Scaffold & Azure RAG Isolation

- Implemented the first fully isolated business workspace (`protein-bar`) grounded in Klaus's authentic documents (`protein_bar_master_plan.docx`, `protein_bar_budget_plan.xlsx`, `Protein Cafe.xlsx`).
- Added `--workspace <tag>` CLI argument and blob metadata support in `storage.py` and `knowledge.py`.
- Added OData filter `search.ismatch('<workspace>', 'source_path')` in `retrieval.py` for scoped multi-workspace search without index schema modifications. Fixed DOCX page_number mapping (`page_number=None`) to strictly satisfy `contracts.py` invariant.
- Updated `src/skills/hermes-azure-rag/SKILL.md` with workspace isolation guidance.
- Created `protein-bar` Hermes profile via CLI (`hermes profile create protein-bar --clone`) with `terminal.cwd=src` and local skills directory, plus authentic `SOUL.md` persona enforcing Tier 2 Draft-Only landlord policy and 8 Dec 2026 opening date.
- Uploaded all 3 authentic files to Azure AI Search layout pipeline; Layout indexer succeeded with zero errors.
- Verified positive scoped search (`--workspace protein-bar` returns relevant master plan and setup budget evidence) and negative cross-workspace isolation (`--workspace titan-ai` returns `no_evidence` with 0 chunks).
- Created interactive HTML workflow dashboard at `docs/plan/protein_bar_workflow.html`.
- Verification gates passed: `verify_knowledge.py --layer 1` (exit 0) and `--layer 2` (exit 0). Added D019 to `DECISIONS.md`.

