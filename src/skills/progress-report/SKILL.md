---
name: progress-report
description: Record workspace progress through registered business documents, native Hermes Kanban and Cron, and the existing Azure knowledge lifecycle.
version: 0.3.0
---

# Native Progress and Project Management

Use only after deterministic routing to a named workspace profile. Chat is the
interface, not authoritative state. Business documents own their domains,
Hermes Kanban owns operational task state, Cron owns schedules, and Azure AI
Search is an asynchronous retrieval projection only.

## Safety Invariants

- Do not send customer PII to third-party tools in prompts.
- Do not expose or store secrets, tokens, API keys, `.env` values, operator
  configuration, or backups.
- Landlord communication remains draft-only.
- Payments, transfers, money movement, and legal signing remain human-only.
- External sends remain disabled. Create drafts only; never call an outbound
  send tool.
- Denial, timeout, silence, or no response is never approval.
- No evidence means not done. Report unverified work as pending or failed.
- Never modify installed Hermes Agent source or managed runtime.

## Domain Owner Resolution

Resolve the requested data domain through the current Hermes Project document
role registry. Typical roles include `progress_report`, `supplier_tracker`,
`budget`, `project_plan`, and `operational_tasks`; these names do not bind a
specific filename or format.

1. Require exactly one registered owner for every requested business domain.
2. Never infer an owner from a filename, extension, nearby file, chat history,
   retained memory, or Azure search result.
3. If an owner is missing or ambiguous, Ask exactly one short clarification question
   for the most important missing owner and perform no mutation,
   Kanban creation, Cron creation, draft, or Azure operation.
4. Resume the suspended request after the user supplies the missing owner.
   Re-resolve every owner before writing; do not treat the reply as approval
   for unrelated actions.
5. Create a new artifact only when the user explicitly approves it and no
   authoritative owner already exists for that domain.

`operational_tasks` resolves to the workspace's bound Hermes Kanban board.
Other roles resolve to the artifact and native format skill registered by the
operator. The user never needs to provide a CLI command or filesystem path.

## Intent Separation

### Planning Intent

For operational updates or planning requests, update the requested
business domain and/or create a native Kanban planning card (`hermes kanban create`).
Do NOT store solely in ephemeral session `todo` scratchpad — session todo is lost across separate chat turns.
Use `triage: true` only after fresh-runtime evidence proves that representation remains
discoverable and non-dispatching. Planning intent creates no Cron job.

### Reminder Intent

Create or reuse a native Cron one-shot job only when the user asks to be
reminded at a time. Reference the stable Kanban task ID or business-record ID.
Do not draft or send a follow-up unless separately requested.

### Follow-Up Intent

Create or reuse the linked Cron job and prepare an unsent draft. External send
remains disabled, including after the Cron job wakes. Landlord drafts remain
draft-only permanently.

### General Operational Queries

When asked about current progress, blockers, or supplier status in subsequent turns:
1. First list Kanban tasks (`hermes kanban list`) or inspect registered domain trackers in `docs/` or `workspaces/`.
2. Read specific cards (`hermes kanban show <id>`) or tracker files to answer the user.
3. Fallback to Azure RAG search (`hermes-azure-rag`) for broader historical context.
4. Agent is permitted to use all available Hermes built-in tools and skills (file, code execution, web) as needed.

## Read-Before-Write and Read-Back

1. Resolve owners and capture current evidence.
2. Write requested business artifact domains in deterministic role order.
3. Read back each changed artifact immediately.
4. Create or reuse the Kanban operational task.
5. Create or reuse Cron only when scheduling intent exists.
6. Project only verified changed documents through `hermes-azure-rag`.

Use the registered native skill for DOCX, XLSX, Google Sheets, Google Docs, or
Notion. Preserve the existing artifact structure, stable record identifiers,
formulas, and unrelated content. Never modify a source fixture in place.

Record revision evidence non-invasively where the configured format supports
it: DOCX custom property/comment, XLSX hidden audit sheet/comment, Google Sheet
reserved audit column/sheet, Notion reserved property, or Markdown front matter
or HTML comment. Do not add visible machine markers solely for Azure search.
If metadata is not retrievable, verify by format-native read-back plus a
source-attributable content/version/hash.

## Kanban Operational Contract

Use only native model-facing tools exposed to the routed profile:
`kanban_create`, `kanban_list`, `kanban_show`, `kanban_comment`,
`kanban_block`, and `kanban_complete`.

Store `waiting_on`, `waiting_since`, `last_contact`, `next_action`,
`record_id`, and an optional Cron reference in a stable structured task-body
block or append-only comment. Do not claim arbitrary-field filtering: use a
bounded list of model-listable statuses followed by `kanban_show`.

## Serial Replay and Concurrent Delivery

- Derive a deterministic `idempotency_key` from workspace, source event,
  business record, and action. Serial replay must reuse the existing card and
  artifact revision.
- Native idempotency is not assumed to be concurrent exactly-once. On
  concurrent duplicate delivery, detect duplicate correlations, preserve one
  canonical task/revision, reconcile duplicates through the proven native
  event boundary, and report the result.
- Never claim exactly-once creation without fresh runtime evidence.

## Supplier / Task-List Update Pattern
Use this when the user reports a supplier delay or asks to add something
to "next week's to-do". For operational Excel-tracked workspaces:

1. Do not create a Kanban card for simple workbook log updates unless
   the user explicitly asks for follow-up/scheduling.
2. Update the authoritative workbook (Task Breakdown / Milestones) first:
   append a row with the delay, owner, dependency, status=At risk, and
   verification/notes.
3. Verify with `xlsx_read.py --csv --sheet <sheet> --out <csv>` and tail
   the CSV to confirm the new row landed.
4. Give the user a short, structured Vietnamese operational summary
   (Top 3 today, next 14-day deadlines, waiting-on-them, done, pending
   approvals) — do not narrate the file edits in detail.
5. For supplier delays in weekly plans, place the item in the supplier
   block of the current or next week, and mention ETA confirmation,
   inventory impact, and substitution protocol explicitly.

## Azure Projection

After a changed business document passes read-back, reuse the existing
`hermes-azure-rag` lifecycle from deployed `src/`:

```text
uv run --frozen python tools/knowledge/knowledge.py upload "<verified-file>" --source-path "workspaces/protein-bar/<role>/<stable-name>.<ext>" --workspace protein-bar
uv run --frozen python tools/knowledge/knowledge.py index
uv run --frozen python tools/knowledge/knowledge.py status
uv run --frozen python tools/knowledge/knowledge.py search "<revision-evidence-query>" --source-path "workspaces/protein-bar/<role>/<stable-name>.<ext>" --workspace protein-bar
```

The role and stable path come from the registry, never user/model path input.
Capture artifact size, upload latency, index latency, and source-attributable
revision evidence. Kanban-only changes perform no Azure upload or index run.

## Cold-Session Query Routing

For a cold session with no prior chat context:

1. Read operational status from the bound Kanban board using bounded
   `kanban_list` plus `kanban_show`.
2. Read narrative or business-record context from the registered domain owner.
3. Use available conversation history, past session searches, and exact workspace-scoped Azure evidence for searchable document knowledge and multi-turn context continuity.

Do not use live web search for internal operational state unless the user explicitly requests it.

## Partial Failure Matrix

- Owner resolution fails: mutate nothing and ask one clarification.
- Artifact write fails: mark that domain not updated and do not project it.
- Read-back mismatches: mark that domain not updated and stop dependent steps.
- Artifact verified, Kanban fails: report artifact success and task failure.
- Kanban succeeds, requested Cron fails: report task success and schedule
  failure.
- Azure fails or remains stale: keep the verified authoritative update and
  report `Knowledge sync pending` or failed.
- Kanban-only success does not depend on Azure.

Independent requested domains may continue only when no unsafe dependency
exists. Never roll back a verified authoritative write because a later Kanban,
Cron, or Azure operation fails. Report the exact status of each requested
domain, task, schedule, draft, and projection.

## Layer 3 Release Gates

Layer 1 and Layer 2 cannot prove native runtime behavior. An independent
verifier must use a fresh Hermes process and approved Telegram route to prove:

- Telegram profile exposes required Kanban tools and the correct project/board.
- A planning card is model-readable and dispatcher observation proves no worker starts.
- Serial replay reuses state; concurrent duplicate delivery is either singular
  or detected and reconciled without an exactly-once claim.
- A cold session with no prior chat context restores waiting and next-action
  state from authoritative owners.
- Reminder/follow-up behavior passes Cron list and manual run while sending
  nothing.
- Ambiguous owner clarification resumes safely.
- Document, Kanban, Cron, and Azure failures produce the stated partial result.
- Exact revision evidence is visible after Azure indexing.
- Adversarial wrong-workspace retrieval and mutation return no foreign data and
  create no foreign side effect.

If any native surface is unavailable or fails these gates, stop and record the
exact capability gap before proposing the smallest adapter. Do not replace
missing runtime evidence with a local mock, invented SQLite schema, or prompt
claim.
