# Tavily-First Research Capability Design

**Date:** 2026-08-27  
**Status:** Approved design; implementation not started  
**Scope:** Upgrade `src/skills/research` without changing Hermes Agent core or the durable Azure knowledge lifecycle

## 1. Problem

The existing research skill defines a sound evidence workflow but does not reliably acquire data from large official websites. Search and HTML extraction often return only landing-page content when the actual public data is loaded by a JavaScript application. A blocked or incomplete source can therefore collapse the whole run or push the agent toward stale secondary sources.

The Coffee House is the release-driving example. Advanced Tavily extraction of its official product-listing URL returned only the landing page, while a normal browser session loaded the menu from the company's first-party public API. That API response contained categories, products, descriptions, variants, toppings, availability fields, and prices.

Research quality also needs to approach GPT/Gemini-style web research: explicit planning, multiple acquisition attempts, iterative gap analysis, source verification, citations, progress reporting, and a decision-ready report.

## 2. Decision

Use **Tavily as the only hosted search, extraction, crawl, and research provider** and compose it with capabilities already present in Hermes:

- Tavily Search, Extract, Map, Crawl, and Research through the official Tavily CLI;
- Hermes-native `web_search` and `web_extract` configured to Tavily;
- Hermes Browser plus the official `agent-browser` request log for public JavaScript applications and first-party public-data discovery;
- bundled `grounded-citations` for source and exact-evidence verification;
- existing `research_store.py` and `render_report.py` for canonical dossier lifecycle and report delivery;
- existing Crawl4AI/Azure workflow only for explicitly durable website ingestion.

Do not add Firecrawl, Exa, Parallel, Camofox, another browser provider, a custom crawler, a provider abstraction, or a research-agent framework.

## 3. Goals

1. Answer quick live-web questions with verified citations.
2. Produce deep, multi-source reports for market, competitor, supplier, location, and due-diligence research.
3. Recover public menu, pricing, catalogue, promotion, and product data from official JavaScript applications when normal extraction is incomplete.
4. Prefer first-party structured data over stale secondary summaries.
5. Continue a run when one source is inaccessible; report the resulting coverage gap.
6. Keep ordinary research session-scoped and preserve the existing explicit `save`, `track`, and `watch` semantics.
7. Use one operator-managed Tavily credential outside the repository.
8. Preserve the H005/H006 boundary: session research never mutates Azure Blob Storage or Azure AI Search.

## 4. Non-goals

- Bypassing authentication, paywalls, CAPTCHA, robots controls, or explicit access restrictions.
- Defeating Cloudflare challenges through fingerprint evasion or residential proxies.
- Hardcoding APIs or selectors for The Coffee House or another brand.
- Mirroring entire websites during ordinary research.
- Treating Tavily Research output as verified evidence without source review.
- Adding scheduled competitor monitoring in this change.
- Changing Hermes Agent installation source or core browser implementation.
- Adding Tavily or other provider SDKs to `src/pyproject.toml`.

## 5. Existing Components to Reuse

| Component | Existing owner | Reuse |
|---|---|---|
| Research policy and routing | `src/skills/research/SKILL.md` | Extend with modes and acquisition ladder |
| Research lifecycle | `src/skills/research/scripts/research_store.py` | Extend the canonical source/evidence contract |
| HTML delivery | `src/skills/research/scripts/render_report.py` | Render evidence and acquisition provenance |
| Citation verification | Hermes bundled `grounded-citations` | Verify retrieved URLs and exact evidence spans |
| Web search/extract | Hermes native web tools | Configure Tavily as both backends |
| Full Tavily capability | Official `tvly` CLI | Search, extract, map, crawl, and research with JSON output |
| Dynamic pages | Hermes Browser plus official `agent-browser network` commands | Render public apps and inspect XHR/fetch request and response details |
| Durable website lifecycle | `src/tools/knowledge/**` | Remain exclusive to explicit retain/ingest intent |

### 5.1 Supported Tool Contract

Pin operator tooling to `tavily-cli==0.1.6` and `agent-browser@0.35.1` for the first release. Upgrades require replaying the JSON/exit-code fixtures before rollout.

The validated baseline is Hermes Agent `v0.20.4` at installed commit `ab173e26d2aa0300f22f5a5944c0284d732cfa8f`, bundled `grounded-citations` `1.1.0`, repository baseline `41c3ef5cb0565358ed0c771f3c8d50da89d9770d`, and Crawl4AI `0.9.2` from `src/uv.lock`. Implementation records the effective versions before Layer 1; any mismatch requires compatibility fixtures to pass before use.


The research skill invokes the official CLI through Hermes Terminal; it does not add a provider wrapper. User-supplied research text goes through standard input, not shell interpolation. Supported command shapes are:

```text
tvly search - --depth basic|advanced --max-results 5|10 --json
tvly extract <validated-url> --extract-depth basic|advanced --json
tvly map <validated-url> --max-depth 2 --limit 50 --json
tvly crawl <validated-url> --max-depth 2 --limit 20 --timeout 150 --json
tvly research - --model mini|pro --no-wait --json
tvly research status <validated-request-id> --json
tvly research poll <validated-request-id> --timeout 600 --json
```

The CLI owns HTTP, retries, polling, and provider response parsing. Hermes owns tool selection, bounded arguments, conversion of returned JSON into the canonical dossier, and truthful handling of process results. Exit `0` with valid nonempty JSON is success. Documented exits `2`, `3`, and `4`, any other nonzero exit, signal termination, terminal timeout, empty output, or malformed JSON are failures. Partial output from a failed process is retained only as diagnostic metadata and never becomes evidence.

Provider output is written only under the active temporary research directory. The existing store validator, not a new adapter, accepts or rejects the dossier assembled from that output.

## 6. Research Modes

### 6.1 Quick

Use for a bounded current fact or comparison that does not require a full report.

```text
web_search
→ select direct sources
→ web_extract
→ verify source support
→ concise cited answer
```

A quick run does not create a dossier unless the user asks for a report or persistence.

### 6.2 Deep

Use for competitor scans, market analysis, supplier/location comparisons, and due diligence.

```text
confirm brief
→ run Tavily Research mini/pro
→ collect candidate report and source list
→ reopen load-bearing sources
→ acquire missing primary evidence
→ run contradiction and gap pass
→ verify evidence and citations
→ build canonical dossier
→ deliver chat brief and HTML report
```

Default to `mini`. Use `pro` only for genuinely multi-domain work, an explicit exhaustive request, or a failed mini run whose identified gaps justify the higher cost.

### 6.3 Site Intelligence

Use when the requested evidence is expected on a named official website: menus, prices, catalogues, product variants, promotions, store listings, or service packages.

```text
Tavily Extract advanced
→ Tavily Map/Crawl when several public pages matter
→ Hermes Browser when rendered content remains incomplete
→ first-party public-data discovery
→ structured evidence normalization
```

Incomplete extraction is a failure state even when the provider returns HTTP 200.

## 7. Acquisition Ladder

For every material source, stop at the first route that returns sufficient evidence:

1. **Tavily Search** — URL discovery and terminology only; snippets are not material evidence.
2. **Tavily Extract** — full content from selected URLs.
3. **Tavily Map/Crawl** — bounded multi-page acquisition on a named public site.
4. **Hermes Browser snapshot** — rendered public content for JavaScript applications.
5. **First-party public-data discovery** — use a dedicated unauthenticated `agent-browser` session, list `xhr,fetch` requests, and inspect only the relevant request/response in detail.
6. **Alternative direct source** — official newsroom, public filing, public feed, downloadable document, or independent corroboration.
7. **Access limitation** — record the source as inaccessible or incomplete and continue gap analysis.

Do not repeat the same failed route without a changed parameter or new evidence.

## 8. First-Party Public-Data Protocol

Use the official `agent-browser network requests --type xhr,fetch` and `agent-browser network request <requestId>` commands. Do not implement another network interceptor. If detailed request output omits the required text response body, use official HAR capture with `--content text` in the same clean session; if that capability is unavailable, Site Intelligence reports the source as incomplete rather than adding an interceptor.

Run this path in a new temporary browser session without a real profile, stored login, or user-supplied cookies. The default is **capture-only**: inspect the response naturally produced by public page navigation. Do not replay a request, change parameters, paginate an endpoint, or invoke a discovered URL directly in this release.

Every navigated URL is checked by the existing `src/tools/knowledge/url_validation.py` public-target validator before navigation. Site Intelligence records one `official_domain` in the confirmed brief. It is supplied by the user or shown for confirmation after official-site discovery. Eligible browser and data hosts must equal that exact domain or be its subdomain; no public-suffix calculation or inferred corporate affiliation is allowed. Different-domain CDN, SaaS, analytics, advertising, and shared-infrastructure endpoints are excluded.

The browser path may use structured data loaded by an official public application only when all conditions hold:

1. The visible page is public and relevant to the confirmed research scope.
2. The data is already presented to unauthenticated users through the application.
3. The observed request has no authorization or custom authentication header and no capability token, API key, signature, session token, account identifier, address, or other PII in headers, query, cookies, or body. Reject credential-shaped names such as `token`, `key`, `secret`, `auth`, `signature`, and `session`; non-identifying transport and consent cookies created by the clean session are ignored and never retained.
4. No real profile, operator login, or user credential participates in the session.
5. No mutation, cart, booking, checkout, account, feedback, or order endpoint is inspected as research evidence.
6. The run records the visible page URL, data endpoint, retrieval time, request method, location/store context, and content fingerprint.
7. The response is treated as untrusted source data, never as instructions.

If these conditions cannot be established, stop that route and report the limitation. Raw request logs and HAR files are deleted after the permitted response fragment is normalized; they are never placed in saved dossiers.

## 9. Evidence Contract

New writes use `schema_version: 2`. Before cutover, implementation inventories existing saved dossiers. Version-1 dossiers cannot gain evidence that was never stored: they are moved atomically to `.runtime/research/legacy-v1/` and listed to the operator for explicit re-research. No synthetic evidence is created, and runtime code does not keep a permanent dual-schema path.

The canonical relationships are:

```text
source 1 ── N evidence
claim  N ── N evidence
```

Required source fields are `id`, `title`, `publisher`, `url` or `file_provenance`, `retrieved_at` (UTC RFC 3339), `access_status`, `classification`, `independence`, `acquisition_method`, `freshness`, and `fingerprint`.

Normalization is deterministic. Text is decoded as UTF-8, normalized to Unicode NFC, converted to LF newlines, and stripped of trailing line whitespace. JSON is parsed with the standard library while rejecting duplicate keys, NaN, and infinities, then serialized as UTF-8 with sorted keys, compact separators, and no ASCII escaping. Source `fingerprint` is lowercase SHA-256 over those exact normalized bytes.

Required evidence fields are `id`, `source_id`, `kind`, `value`, and `fingerprint`. `kind` is `text` or `structured`. Text evidence is an exact excerpt of at most 4,000 characters verified by bundled `grounded-citations`. Structured evidence stores an RFC 6901 JSON Pointer plus the typed scalar or bounded object value read from the normalized response fragment; one structured evidence object is at most 64 KiB. Its fingerprint is SHA-256 over canonical JSON. Optional fields are `visible_page_url`, `data_endpoint`, `location_context`, and `observed_at`.

Claims retain `id`, `type`, `text`, `confidence`, `confidence_rationale`, `evidence_ids`, and `counter_evidence_ids`. Every factual material claim requires at least one verified evidence ID. Tavily Research output may be stored only as a candidate source; it cannot support a factual material claim. Unsupported leads appear only in `unknowns` or `next_questions`, never mixed into findings.

IDs are unique within one dossier and use existing safe-ID rules. URLs use existing normalization and public-target validation. Duplicate evidence with the same source and fingerprint is collapsed. Failed sources remain source records but cannot own verified evidence.

A source URL alone is not evidence. A search snippet cannot satisfy a material claim. For a direct, current first-party fact such as an official menu price, one verified primary source is sufficient when location and retrieval time are disclosed. Comparative conclusions and recommendations require two independent sources or an explicit single-source limitation.

### 9.1 Citation Verification Contract

Each run loads bundled `grounded-citations` and points its `sources.py` commands at a task-local ledger inside the temporary research directory. Retrieval registers the canonical URL before drafting. Text evidence is attached with `quote --from <normalized-source-file>` and must pass `verify --evidence`; structured evidence is verified by the version-2 dossier validator against its canonical JSON fragment and fingerprint. The generated report must pass citation-ID and source-list verification before delivery.

Failure of either verifier prevents the affected claim from entering `key_findings`. The claim may move to `unknowns` with the failed-verification reason or be removed.

## 10. Research Quality Loop

A deep run completes these stages:

1. Confirm question, decision, audience, geography, time horizon, exclusions, and deliverable.
2. Decompose the brief into subquestions and required evidence.
3. Run Tavily Research and/or focused search.
4. Acquire direct evidence using the acquisition ladder.
5. Map claims to supporting and counter evidence.
6. Evaluate directness, authority, independence, freshness, method, and incentive.
7. Run at least one gap/contradiction iteration.
8. Stop on coverage, saturation, budget, or an explicit access boundary.
9. Verify citation IDs and evidence spans.
10. Build and render the canonical dossier.

The final answer separates fact, source assertion, inference, recommendation, and unknown.

Progress uses the existing research-skill contract: one start message after scope confirmation, one meaningful acquisition/gap checkpoint for a deep run, and one final or actionable partial-result message. No new progress event system is added.

## 11. Cost Policy

Tavily currently provides 1,000 free API credits per month without requiring a credit card. Credit use is provider-owned and may change; operator documentation links the current pricing page rather than treating current values as a permanent guarantee.

`src/config/research_policy.json` owns per-run ceilings. Initial defaults are:

- Quick: at most 2 search calls, 2 extract calls covering 5 URLs total, one browser navigation, 2 MiB per source, and 120 seconds.
- Deep: one Tavily Research `mini` run, one request ID with at most 60 status polls at the documented 10-second interval, 2 follow-up search calls, 10 extracted verification URLs, 3 browser navigations, 10 inspected network responses, 2 MiB per source, and 900 seconds.
- Site Intelligence: one map call returning at most 50 URLs, one crawl call covering at most 20 pages to depth 2, 2 extract calls covering 5 URLs, 2 browser navigations, 50 listed network requests, 10 inspected text responses, 5 MiB total captured response text, and 300 seconds before an actionable partial result.
- Every mode has a 20 MiB temporary-artifact ceiling. `pro` requires explicit user confirmation naming the higher-cost mode.

Basic search/extract is the default. Advanced extract runs first only for a source already characterized as JavaScript-rendered; otherwise it follows an incomplete basic result. Every CLI call has one provider-owned attempt. Authentication, quota, API, malformed-output, signal, and terminal-timeout failures do not trigger a custom retry loop. The first reached call, byte, or wall-clock ceiling stops new acquisition, preserves accumulated evidence, and records the exact stop reason.

## 12. Credential Boundary

The Tavily credential is an operator secret and must not appear in Git, project documents, tests, logs, reports, command arguments, or Telegram messages.

The key disclosed during design discussion must be revoked and replaced before implementation. On Windows, the replacement key is supplied only through `%LOCALAPPDATA%\hermes\.env` as `TAVILY_API_KEY`; equivalent deployments use the Hermes operator/profile secret environment. Do not run `tvly login --api-key`, which would create a second credential store. Hermes native Tavily tools and the CLI consume the same environment variable. Verification may report only present/absent and successful/failed authentication.

## 13. Data and Lifecycle Boundaries

- Temporary dossiers: `.runtime/research/temporary/<session-id>/`.
- Explicitly saved dossiers: `.runtime/research/saved/<dossier-id>/`.
- Tavily intermediate JSON and sanitized browser fragments: the active temporary research directory only.
- Existing safe-ID, atomic-write, and cleanup behavior in `research_store.py` remains authoritative. Crash leftovers are removed by the existing temporary TTL cleanup; saved dossiers are never TTL-cleaned.
- Browser/API evidence is normalized into the dossier; raw cookies, headers, request logs, and HAR files are deleted immediately after normalization.
- Freshness maps conservatively: naturally observed browser data is `live`; a provider result is `provider-cache` only when Tavily declares caching, otherwise `unknown`; archives are `snapshot`.
- “Save this research/report/dossier” saves an H005 dossier. “Retain/ingest this website as knowledge” routes to H006. Ambiguous “save this” asks one object clarification before any mutation.
- Ordinary research never calls `web-ingest`, Azure indexers, or Blob mutation.
- Explicit durable website intent continues to route to `hermes-azure-rag` and the existing Crawl4AI/Azure lifecycle.

## 14. Failure Handling

Classify failures as:

- provider unavailable;
- quota or rate limit;
- not found;
- inaccessible/WAF challenge;
- authentication required;
- JavaScript required;
- incomplete extraction;
- timeout;
- unsafe URL;
- unsupported content;
- stale or location-ambiguous evidence.

Each failed source remains visible in the method/coverage report. Failure of one provider route does not erase acquired evidence or imply that no evidence exists.

## 15. Planned File Changes

1. `src/skills/research/SKILL.md`
   - add Quick, Deep, and Site Intelligence routing;
   - define Tavily CLI/native tool use;
   - define the acquisition ladder and H005/H006 boundary.
2. `src/skills/research/references/research-protocol.md`
   - add public-data protocol, quality loop, failure taxonomy, and budgets.
3. `src/skills/research/references/source-quality.md`
   - add live/cache/snapshot and location-sensitive evidence treatment.
4. `src/skills/research/references/report-contract.md`
   - require acquisition and evidence provenance in reports.
5. `src/skills/research/scripts/research_store.py`
   - validate evidence records and material claim references.
6. `src/skills/research/scripts/render_report.py`
   - render exact evidence, acquisition method, freshness, and location context.
7. `tests/verify_research.py`
   - add contract and behavior coverage.
8. `src/config/research_policy.json`
   - own deterministic per-run time, call, source, crawl, and model ceilings.
9. Operator setup documentation already owning installation/configuration
   - pin the official Tavily and agent-browser CLI versions outside the project environment;
   - configure native Hermes Tavily search/extract backends;
   - document one-store credential provisioning and non-sensitive verification.

No production provider wrapper or crawler file is added.

## 16. Verification Strategy

### Layer 1 — Static and contract

- skill routing and safety text exists;
- pinned CLI invocation fixtures and `research_policy.json` validate;
- no forbidden provider dependency or hardcoded brand endpoint exists;
- dossier schema rejects missing evidence spans, invalid fingerprints, and invalid claim references;
- every public target routes through the existing URL validator;
- secret-shaped values and unsafe URLs are rejected;
- H005 contains no Azure mutation command.

### Layer 2 — Artifact behavior

Fixtures cover:

- static source;
- search snippet rejected as evidence;
- JavaScript page with incomplete extraction;
- a sanitized structured-menu fixture captured from the release-driving public application;
- first-party public JSON evidence and disallowed third-party/ambiguous hosts;
- capture-only request policy and raw network-artifact cleanup;
- blocked source with independent alternative;
- provider authentication/quota/API failure with partial-result preservation;
- location-sensitive pricing;
- Tavily Research candidate that cannot become factual evidence before verification;
- schema-version cutover and saved-dossier migration;
- safe HTML rendering of untrusted excerpts;
- temporary and saved lifecycle behavior.

### Layer 3 — Fresh runtime

From a fresh Hermes process and approved Telegram chat:

1. Quick current-fact run.
2. Deep multi-source competitor report.
3. The Coffee House official menu and pricing run.
4. Provider quota/failure degradation.
5. Negative authenticated/private API scenario.
6. Follow-up using the same evidence model.
7. Temporary no-persistence and explicit save behavior.

An independent verifier records commands or events, UTC timestamp, exit status, and observed result before changing feature state to `passing`.

## 17. The Coffee House Release Scenario

Prompt intent: research the current official menu and prices.

The first release never submits an address or selects a branch. It uses the application's default unauthenticated context and labels that context exactly as observed.

From naturally observed allowed-domain `xhr`/`fetch` text responses, a menu candidate must parse as JSON and contain a collection of objects with stable identifiers, names, and numeric price fields. Exactly one qualifying response is required. Zero candidates yields `incomplete`; multiple candidates yield `ambiguous_response` and no menu claim. The implementation does not choose by endpoint name.

Required behavior:

- discover the official ordering application;
- detect that ordinary extraction is incomplete;
- use a clean public rendered-browser session and capture naturally observed first-party data;
- parse every category and product returned by the selected menu response, preserving every returned price/variant field or recording an explicit skip reason;
- require nonempty categories and products, stable unique IDs, typed non-negative integer VND prices, and evidence links for every reported price;
- include retrieval timestamp and the exact branch/store context supplied by the response; if none is selected, say so rather than inventing one;
- disclose that availability and prices may vary by branch or location;
- cite the visible official application and its first-party data source;
- avoid stale third-party menu blogs as the primary source;
- contain no The Coffee House endpoint, selector, count, or product name in production routing code.

Layer 2 stores `tests/fixtures/research/coffee_house_menu_sanitized.json`, a bounded redacted capture with its SHA-256 and capture metadata, plus `coffee_house_menu_expected.json` containing the complete expected normalized projection. Layer 3 uses live structural invariants rather than fixed product names or counts, so normal menu changes do not invalidate the test.

## 18. Rollout

1. Rotate the exposed Tavily credential.
2. Install the pinned official Tavily CLI and expose the replacement key only through the Hermes operator environment.
3. Verify `tvly search`, `extract`, `map`, `crawl`, and `research --json` from deployed `src` CWD without exposing the key.
4. Verify pinned `agent-browser` request-log and text-HAR behavior in a clean temporary session; lack of response-body support blocks Site Intelligence rather than authorizing custom interception.
5. Configure Hermes native web search/extract to Tavily.
6. Inventory and migrate saved version-1 dossiers, then cut over to schema version 2.
7. Implement schema and skill changes test-first.
8. Run Layer 1 and Layer 2.
9. Run the fresh Telegram Layer 3 scenarios, including a clean-session public API discovery case.
10. Obtain independent verifier evidence.

Implementation cannot become the active feature while another feature remains `active` under the repository WIP limit.

## 19. Acceptance Summary

The capability is complete when Hermes can conduct quick and deep cited research, continue through source failures, recover structured public data from official JavaScript applications without hardcoded site logic, produce a verified dossier/report, preserve session/durable boundaries, and pass the The Coffee House and multi-source Telegram scenarios with independent evidence.
