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
