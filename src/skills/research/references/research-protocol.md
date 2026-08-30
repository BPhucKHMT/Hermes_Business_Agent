# Research Protocol

## Brief

For competitor, market, and due-diligence research, present and confirm:

- decision/question and audience;
- entities, geography, segment, time horizon, and exclusions;
- subquestions and evidence needed;
- confirmed `official_domain` when investigating specific brands;
- output and persistence mode;
- time, source, and provider limits (`research_policy.json`).

A timeout, silence, or unrelated reply is not confirmation.

## Acquisition Ladder & Execution

1. **Discovery Search:** Use Tavily Search to discover candidate URLs and terminology. Search snippets are discovery aids only, not verified evidence.
2. **Extraction:** Fetch raw markdown with Tavily Extract (basic first, advanced for JavaScript SPAs).
3. **Site Mapping & Crawling:** For public multi-page documentation or catalogues, run bounded `tvly map` (≤50 URLs) or `tvly crawl` (≤20 pages, depth ≤2).
4. **Rendered Browser Inspection:** When extraction is incomplete on public JavaScript applications, open a clean, unauthenticated Hermes Browser session.
5. **First-Party Public-Data Discovery:**
   - Use `agent-browser network requests --type xhr,fetch` and `agent-browser network request <requestId>` in capture-only mode.
   - Restrict to endpoints matching the confirmed `official_domain` exactly or as a direct subdomain.
   - Reject any request carrying auth tokens, API keys, signatures, sessions, or PII.
   - Reject mutation/cart/booking/checkout endpoints.
   - Never replay or mutate requests in this release.
   - Clean up raw logs/HAR after normalizing permitted response data.
6. **Alternative Direct Sources:** Query official press releases, regulatory filings, public RSS feeds, or public PDF documents.
7. **Access Limitation:** If sources remain inaccessible or incomplete, record `access_status: "inaccessible"` or `"incomplete"` and proceed with gap analysis.

## Rendered Browser Interaction Contract

Use the pinned `agent-browser@0.35.1`; do not add a second CDP/browser runtime.
Every browser run is a clean, unauthenticated, public-only session constrained to
the confirmed official domain.
Every `agent-browser` invocation carries the same fresh
`--session <research-run-id> --pin-tab --allowed-domains
"<official_domain>,*.<official_domain>" --content-boundaries --max-output 50000`
boundary. Close that session explicitly at the end. Do not use `--profile`,
`--state`, `--restore`, `--auto-connect`, authentication commands, or a cloud
browser provider; those can import user state or bypass the clean public session.

1. Start with `agent-browser read <url>` or Tavily extraction. Escalate only when
   the required evidence depends on rendered JavaScript or interaction.
2. After navigation, run `agent-browser wait --load networkidle`; for a required
   late-rendered control, run `agent-browser wait <selector>`. These are the
   pinned tool's equivalents of `wait_for_network_idle` and `wait_for_element`.
3. Use `agent-browser snapshot -i --json` as the accessibility tree and select
   elements by accessible ref. Use a screenshot only as a fallback when layout,
   imagery, canvas, or a missing accessibility node makes structure insufficient.
4. Use `agent-browser tab list --json` before opening a tab. Reuse a matching tab,
   label any tab created for the run, and close it with `agent-browser tab close`
   during cleanup. This supplies `current_tab`, `list_tabs`, and `switch_tab`
   lifecycle semantics without another browser dependency.
5. After each browser action that changes page state, verify it with a targeted
   observation (`snapshot`, `get`, URL, or network request detail) before using
   the result as evidence. Re-snapshot after clicking before reusing element refs.
6. For multi-step browser acquisition, bound the step trace with
   `agent-browser trace start` and `agent-browser trace stop <temporary-path>`.
   The run ledger records action, result, duration, error, and retained evidence
   artifact. Delete raw traces, HAR, screenshots, and network logs after permitted
   evidence is normalized and fingerprinted.
7. On timeout or stale refs, take one fresh targeted observation and retry the
   same action once. Then stop with the failure taxonomy below; do not switch to
   login, replay captured requests, weaken the domain boundary, or improvise a
   second browser controller.

## Evidence Model (Schema v2)

For each source retain:
- `id`, `title`, `publisher`, `url` (or `file_provenance`), `retrieved_at` (RFC 3339 UTC), `access_status`, `classification`, `independence`, `acquisition_method`, `freshness` (`live`, `provider-cache`, `snapshot`, `unknown`), and `fingerprint`.

For each evidence record retain:
- `id`, `source_id`, `kind` (`text` or `structured`), `value`, and `fingerprint`.
- Optional: `visible_page_url`, `data_endpoint`, `location_context`, `observed_at`.

For each claim retain:
- `id`, `type` (`fact`, `source-assertion`, `inference`, `recommendation`, `unknown`), `text`, `confidence`, `confidence_rationale`, `evidence_ids`, `counter_evidence_ids`.
- Every factual material claim requires at least one verified evidence ID.

## Grounded Citation Verification

Use bundled `grounded-citations` to verify exact text excerpts and the v2 store validator to verify canonical structured JSON fragments. Tavily Research output is classified as `candidate` and cannot support a factual material claim without direct source verification.

## Stop and Failure Conditions

Stop at the first condition reached:
- **Coverage:** required questions have supported answers.
- **Saturation:** new queries repeat known findings.
- **Budget Ceiling:** time, calls, or byte limits defined in `src/config/research_policy.json` reached.
- **Access Boundary:** evidence unavailable without unsupported authentication, paywalls, or private access.

Failure taxonomy: `provider_unavailable`, `rate_limited`, `waf_interstitial`, `authentication_required`, `incomplete_extraction`, `timeout`, `unsafe_url`.
Partial research must list completed scope, missing evidence, impact on confidence, and a next action.
