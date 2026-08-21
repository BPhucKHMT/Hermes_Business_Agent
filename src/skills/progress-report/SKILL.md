---
name: progress-report
description: Record Protein Bar Flow A updates, tasks, and unsent follow-up drafts with exact approval and verified report output.
---
# Progress Report
Use only in deterministically routed `protein-bar` profile.
1. Resolve every field required by the selected operation and registered target. Domain tools return typed missing-field outcomes; the presentation layer asks one concise, localized question for the highest-priority missing field, then stops.
2. Any unresolved required field creates zero source event, task, proposal, report mutation, outbound action, or KB sync. Never use retained knowledge to invent an unconfirmed current fact.
3. Record a source only after required fields are resolved. Preview only facts supported by the current source or cited current evidence. Do not broaden scope to adjacent entities or workstreams.
4. Follow-up is always unsent. Never call an outbound tool.
5. Canonical mutation is Tier 2. Require proposal-specific approval. Generic `ok`, silence, timeout, denial, expiry, or replay is not approval.
6. After report read-back verification, create one durable Knowledge Base sync request. Upload only verified output to registered workspace source path, run text indexer, and query back exact revision. Never upload draft, rejected, or unverified content.
7. Current progress questions read verified SQLite state first. Use exact workspace/source-path Azure evidence for citation and history. If Azure is older, answer current state and disclose `Knowledge sync pending`; never repeat stale evidence as current truth.
8. Never accept paths or document coordinates from model/user payload. Registry owns targets.
9. Apply versioned output, reopen, verify, then emit `MEDIA:<absolute-path>` only when file exists.
10. Missing target, evidence, approval, report verification, or Azure query-back means corresponding step is not done. Progress may be verified while knowledge sync remains pending.
11. Keep proposal scope minimal. An update cannot change or summarize unrelated entities or workstreams unless explicitly requested and supported by current evidence.
Unsupported: Gmail, Notion, WhatsApp, XLSX/Sheets, scheduler, DOCX without approved report fixture, and supplier sending.
