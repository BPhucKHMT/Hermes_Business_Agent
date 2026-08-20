# Hermes Decisions

## D001 — Root harness precedes runtime

- Date: 2026-08-10
- Status: accepted
- Context: Root needs operating contract and state before runtime work.
- Decision: This task creates no runtime, source, or integration.
- Consequences: Runtime behavior remains out of scope.
- Revisit when: runtime plan receives approval.

## D002 — Git lives at project root

- Date: 2026-08-10
- Status: accepted
- Context: Harness, docs, and future source need one checkpoint boundary.
- Decision: Git repository belongs at project root.
- Consequences: Root owns harness, docs, and future source history.
- Revisit when: project scope requires repository split.

## D003 — Artifacts have separate ownership

- Date: 2026-08-10
- Status: accepted
- Context: Policy, workflow, state, handoff, and rationale have different consumers.
- Decision: `CLAUDE.md` holds policy; `AGENTS.md` workflow; `feature-list.json` state; `PROGRESS.md` handoff; `DECISIONS.md` rationale.
- Consequences: State changes stay machine-readable and handoffs stay concise.
- Revisit when: artifact responsibilities overlap or conflict.

## D004 — WIP=1 and verifier-gated passing

- Date: 2026-08-10
- Status: accepted
- Context: One active item limits context drift; completion needs independent proof.
- Decision: Use four-state machine with WIP=1; independent checker controls `passing`.
- Consequences: Implementers keep features active until verifier records evidence.
- Revisit when: verified workflow needs controlled parallel work.

## D005 — Runtime Hermes context is deferred

- Date: 2026-08-10
- Status: accepted
- Context: Runtime design has separate approval and scope.
- Decision: Defer runtime directory, prompt files, skills, MCP, scripts, and config integration to later plan.
- Consequences: Root remains harness-only.
- Revisit when: runtime plan receives approval.

## D006 — Customer requirements remain implementation-neutral

- Date: 2026-08-10
- Status: accepted
- Context: `docs/Hermes Project.docx` mixes customer outcomes with proposed architecture, vendors, credits, and schedule.
- Decision: `requirement_customer.md` captures customer goals, behaviors, guardrails, acceptance criteria, feature dependencies, and unresolved questions while excluding proposed implementation choices.
- Consequences: Future feature plans use a stable Vietnamese requirements baseline without inheriting unapproved technology choices.
- Revisit when: customer approves changed requirements or resolves an open question.

## D007 — `src` isolates Hermes runtime context

- Date: 2026-08-11
- Status: accepted
- Context: Repository root chứa engineering harness cho coding. Hermes runtime không được biết hoặc phụ thuộc artifact ngoài `src`.
- Decision: `src/AGENTS.md` is runtime context; operator config points `terminal.cwd` and `skills.external_dirs` inside deployed `src/`. Skills do not read or reference parent directories. Do not create empty MCP, script, template, or context directories.
- Consequences: Root `AGENTS.md`, state và plan chỉ phục vụ engineering. Hermes receives a self-contained workspace under `src`; other capabilities still require features and independent verifiers.
- Revisit when: Runtime needs another self-contained artifact under `src` or a verified integration.

## D008 — Runtime documentation is portable

- Date: 2026-08-11
- Status: accepted
- Context: Absolute developer-machine paths and Vietnamese runtime instructions block deployment portability and broader operator use.
- Decision: Runtime-owned Markdown is English-only and refers to configured current workspace or placeholders, never a repository-specific absolute path. `src` is the sole source of project instructions and persistent Hermes context, but this does not restrict user-requested task execution outside `src` when operator permissions allow it.
- Consequences: Operators must supply deployment paths in their local `config.yaml`; documentation remains valid after relocation. Hermes may use external resources for explicit tasks without importing them as instructions or implicit context.
- Revisit when: Hermes supports a stable workspace-root variable in configuration.

## D009 — Research is evidence-first with explicit persistence

- Date: 2026-08-11
- Status: accepted
- Context: Research must understand and communicate evidence, not summarize search snippets; durable storage must remain user-controlled.
- Decision: H005 uses an independently functional Hermes-native search/read/gap-analysis loop. Optional deep-research providers supply candidate findings only. Material claims require opened-source evidence and citations. Research remains session-scoped unless the user explicitly requests `save`, `track`, or `watch`; V1 stores watch intent but does not run cron. Telegram delivers a brief plus HTML report; cron and Gmail are separate future work.
- Consequences: Native behavior and provider-disabled E2E are release gates. Report delivery does not imply durable storage. Operator config may point Hermes to deployed `src` after backup, but installed Hermes source and secrets remain untouched.
- Revisit when: A provider is selected, a second capability needs shared source policy, or scheduled email research starts.

## D010 — Clean public history excludes local documents

- Date: 2026-08-12
- Status: accepted
- Context: The user requested a new public repository history without prior contributor metadata and without the local `docs/` directory.
- Decision: Publish a clean grouped history to `origin/main` using the configured human Git identity. Keep `docs/`, runtime dossiers, local usage records, and editor-agent state Git-ignored. Preserve old history only in local `backup/pre-clean-history`; never push that branch.
- Consequences: Fresh clones receive harness, runtime skills, tests, and durable state, but not local plans or source documents. `PROGRESS.md`, `feature-list.json`, and `DECISIONS.md` must carry all required handoff context.
- Revisit when: The user explicitly chooses safe documents for publication.

## D011 — Renderers consume canonical dossiers

- Date: 2026-08-12
- Status: accepted
- Context: HTML is a temporary delivery format and PPTX is the likely next capability.
- Decision: `dossier.json` remains canonical; HTML and future PPTX are replaceable derived renderers. A renderer must not parse another renderer's output.
- Consequences: Research evidence, citations, confidence, persistence, and lifecycle stay independent from presentation format.
- Revisit when: The canonical dossier schema needs a versioned migration.

## D012 — Azure Hybrid RAG uses one incremental ingestion core

- Date: 2026-08-12
- Status: superseded by D013
- Context: Initial design prioritized deterministic locators and generation activation before proving Azure managed ingestion.
- Decision: Project-owned extraction, chunking, embedding, Search push, and generation manifest were selected.
- Consequences: Early implementation duplicated supported Azure services and SDK behavior.
- Revisit when: Never; D013 replaces this decision after official Azure feature research.

## D013 — Azure owns Knowledge Base ingestion and retrieval primitives

- Date: 2026-08-13
- Status: accepted
- Context: Azure AI Search supports Blob indexers, Document Intelligence Layout Skill, Text Split Skill, Azure OpenAI Embedding Skill, Index Projections, integrated query vectorization, hybrid RRF retrieval, and soft-delete propagation. Handwritten parsing, chunking, embedding orchestration, HTTP retries, and generation manifests duplicate managed capabilities without evidence that Hermes needs custom behavior.
- Decision: Use Azure-managed ingestion and classic hybrid retrieval. Hermes only validates Telegram/folder operations, uploads or deletes Blobs with access metadata, triggers and observes the indexer, maps Search results to `EvidenceResult`, and owns answer/citation policy. Use official Azure SDKs. Keep Semantic Ranker optional and Agentic Retrieval deferred. Treat Layout Skill availability and locator fidelity as Layer 3 gates.
- Consequences: Delete app-owned parser, chunker, embedding loop, raw Azure HTTP client, and manifest lifecycle. Azure resource definitions become source-controlled behavior. Do not claim exact format locators or production readiness before real region/tier and corpus verification.
- Revisit when: Azure E2E proves a required format or locator unavailable, real evaluation proves classic hybrid insufficient, or production identity requires Managed Identity migration.

## D014 — Single Agent Instance Serving Three Workspaces

- Date: 2026-08-19
- Status: accepted
- Context: Project Hermes v2 serves three distinct businesses (Protein Bar, Client Projects, TITAN AI) plus HQ/Unsorted. A choice existed between deploying three separate bots or a single unified agent with logical isolation.
- Decision: Run a single Hermes Agent instance serving all three workspaces with five enforced isolation layers in code: 1) Channel/contact binding before inference, 2) Ask-don't-guess when ambiguous, 3) Scoped subagent retrieval in code, 4) Mandatory `workspace` field on all state records, and 5) 20-prompt adversarial context-bleed audit.
- Consequences: Unified morning brief, cross-business prioritisation, single decision-debt queue, unified preference/style store, and one deployment footprint. Context bleed is prevented by structural enforcement rather than prompt politeness.
- Revisit when: Hard legal separation or partner divestiture requires physically separated instances.

## D015 — Workspace Priority Rollout Order

- Date: 2026-08-19
- Status: accepted
- Context: Building 13 sub-agent capabilities across 3 businesses requires a disciplined rollout sequence to avoid stalled parallel work.
- Decision: Prioritize workspaces in strict order: 1) Protein Bar (hard unmovable opening date: 8 Dec 2026, highest time-sensitivity for suppliers, lease, and licensing), 2) Client Projects (live external revenue and client commitments, e.g. TWJ app), 3) TITAN AI (richest content and agency operations, onboards after core engine is proven).
- Consequences: Core engine (routing, memory, daily sync, approval gate, verifier) is proven first on Protein Bar before onboarding subsequent workspaces. Runtime Top-3 scoring weights Protein Bar highest until 8 Dec 2026.
- Revisit when: Protein Bar launch gate completes on 8 Dec 2026.

## D016 — Four-Tier Autonomy System with Zero Silent Money Movement

- Date: 2026-08-19
- Status: accepted
- Context: LLM agents acting in operational business contexts risk catastrophic errors if allowed unbounded external actions.
- Decision: Enforce four autonomy tiers in the action executor: Tier 0 (Silent/Internal), Tier 1 (Do & Report in brief), Tier 2 (Draft & Approve via 1-tap Telegram/dashboard), Tier 3 (Human Only). All external communications, invoices, bookings, and landlord negotiations start at Tier 2. Landlord negotiations remain permanently draft-only. Money movement, payments, and legal signing are permanently Tier 3 (Hermes never moves money). Trust graduation to Tier 1 requires ≥95% unedited approval rate over 2+ weeks (≥10 volume) with instant demotion on any error.
- Consequences: Safe automation envelope. High-risk actions cannot be bypassed by prompt injection or model hallucination.
- Revisit when: Operator updates the approved tier matrix.

## D017 — Multi-Level Independent Machine-Verifiable Evidence Layer

- Date: 2026-08-19
- Status: accepted
- Context: LLM agents frequently suffer from false-completion hallucination (claiming "done" without executing or verifying the actual external state).
- Decision: No action is marked "done" without machine-verifiable evidence declared up-front (Gmail message ID, Calendar event ID, Notion block ID, PDF URL, execution ID, PNR). A deterministic verifier separate from the executing agent checks evidence against the target system via API. "No evidence = not done" with one retry then human escalation. End-of-day reconciliation diffs claimed actions against reality, and 10% daily spot-checks run continuously.
- Consequences: Eliminates silent failure. State DB and dashboard maintain an objective reliability scoreboard.
- Revisit when: Target third-party systems deprecate read APIs or require webhook-only verification.

## D018 — Layered Memory Architecture and Obsidian-Compatible Vault

- Date: 2026-08-19
- Status: accepted
- Context: Relying solely on chat history or a single database creates context drift and opaque state.
- Decision: Implement a 5-layer memory architecture: 1) Native platform memory (MEMORY.md/USER.md), 2) Small structured state DB (9 tables: workspaces, contacts, tasks, threads, events, approvals, evidence, ledger, audit_log), 3) Per-workspace file-based KB, 4) Human-readable Obsidian-compatible Markdown vault synced to Drive+Git (Klaus can read/edit directly), and 5) Preference/style store updated by diffing draft edits.
- Consequences: High continuity across sessions ("where were we on X"), total auditability, and resilience against platform loss.
- Revisit when: Workspace document corpus exceeds file-retrieval latency thresholds and justifies vector migration.

## D019 — Multi-Workspace Isolation via Azure AI Search Tagging and Hermes Profiles

- Date: 2026-08-19
- Status: accepted
- Context: Project Hermes v2 requires strict isolation between Protein Bar, Client Projects, and TITAN AI to prevent cross-business context bleeding and confidential data leakage.
- Decision: Enforce isolation across the entire stack:
  1) Runtime Profile Layer: Dedicated profile created via `hermes profile create <workspace> --clone` with custom `SOUL.md` persona, rules, and `terminal.cwd` pointing to `src/`.
  2) Blob Storage Layer: Documents stored under `<workspace>/<filename>` hierarchy with `workspace=<tag>` metadata.
  3) Search Retrieval Layer: `knowledge.py` and `retrieval.py` accept `--workspace <tag>` and apply `search.ismatch('<tag>', 'source_path')` additive OData filter.
- Consequences: 100% data isolation proven: searches scoped to `protein-bar` retrieve authentic Master Plan / Budget chunks, while cross-workspace queries (`titan-ai`) return `no_evidence` (0 chunks).
- Revisit when: New workspaces (e.g. Client Projects, TITAN AI) are onboarded.

## D020 — One Telegram Gateway Routes Topics to Isolated Profiles

- Date: 2026-08-20
- Status: accepted
- Context: One Telegram bot must serve isolated business workspaces without LLM intent selecting a security boundary. Installed Hermes supports `gateway.profile_routes`, but unmatched sources fall back to default and duplicate platform credentials fail fast.
- Decision: Run one Telegram bot token through one gateway-owned default adapter. Enable multiplexing and route approved `(platform, chat_id, thread_id)` tuples to installed isolated profiles. Secondary routed profiles must not configure the shared Telegram credential. Use top-level `telegram.require_mention: true` with `observe_unmentioned_group_messages: true`; ordinary group chatter may supply context but cannot execute. Ignore unmapped business topics until their real profiles and policies exist. Keep Azure `--workspace` filtering as defense-in-depth after profile selection.
- Consequences: Protein Bar topic `(-1003835812097, 11)` deterministically selects `protein-bar`; TITAN AI topic `5` and General topic `1` stay ignored in the pilot. One session namespace, persona, memory, tools, and fixed RAG workspace apply after routing. Direct replies to bot remain official mention-gate triggers. Operator config and credentials remain local and uncommitted.
- Revisit when: A real Client Projects/TITAN profile is approved, Telegram membership differs enough to require separate groups, or hard legal separation requires separate tokens/gateways.

