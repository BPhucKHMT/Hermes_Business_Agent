# Tavily-First Research Capability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade `src/skills/research` into a complete Tavily-first quick, deep, and official-site research capability with verified evidence, dynamic public-data acquisition, and no new provider or crawler implementation.

**Architecture:** Tavily is the only hosted search/extract/crawl/research provider. Hermes owns routing, browser acquisition, evidence verification, dossier lifecycle, and reporting; official `tvly` and `agent-browser` CLIs own provider and browser mechanics. Existing Crawl4AI/Azure remains exclusive to explicit durable website ingestion.

**Tech Stack:** Hermes Agent v0.20.4, Python 3.12 stdlib, `tavily-cli==0.1.6`, `agent-browser@0.35.1`, bundled `grounded-citations` 1.1.0, existing Crawl4AI 0.9.2, JSON, HTML, Telegram.

## Global Constraints

- Execute only after no existing feature is `active`; H009 is active at plan creation and blocks implementation.
- Revoke the Tavily key disclosed in chat; supply its replacement only through `%LOCALAPPDATA%\hermes\.env` as `TAVILY_API_KEY`.
- Never place secrets in Git, command arguments, logs, fixtures, reports, or Telegram.
- Do not add Firecrawl, Exa, Parallel, Camofox, another browser provider, a provider wrapper, crawler, retry framework, or research-agent framework.
- Do not add Tavily or provider SDKs to `src/pyproject.toml` or mutate `src/uv.lock`.
- Pin `tavily-cli==0.1.6` and `agent-browser@0.35.1`; changing either version requires compatibility-fixture replay.
- Session research must not invoke Azure mutation, `web-ingest`, or the Crawl4AI knowledge lifecycle.
- Execute in an isolated Git worktree created at execution time; never mix H010 commits with the current H009 working tree.
- First-party public-data acquisition is capture-only, unauthenticated, same confirmed official domain, and read-only in effect.
- Production routing contains no The Coffee House endpoint, selector, count, or product name.
- Preserve unrelated H009, Protein Bar, operator-config, and untracked user changes.
- Follow TDD: Layer 1 before Layer 2; Layer 2 before Layer 3.
- Only an independent verifier may transition the feature to `passing`.

---

## Pre-execution Gate

Run from repository root:

```bash
python -c "import json; d=json.load(open('feature-list.json', encoding='utf-8')); a=[f['id'] for f in d['features'] if f['state']=='active']; assert not a, f'active feature blocks research implementation: {a}'"
```

Expected before execution: exit `0`. At plan creation this intentionally fails with H009 active. Do not change H009 state merely to bypass the gate; continue only after H009 reaches a legitimate `blocked` or independently verified `passing` state.

---

### Task 1: Activate the Research Upgrade Feature

**Files:**
- Modify: `feature-list.json`
- Modify: `PROGRESS.md`

**Interfaces:**
- Consumes: repository feature-state contract and WIP limit 1.
- Produces: one new active feature, `H010`, covering only the approved Tavily-first research design.

- [ ] **Step 1: Verify the pre-execution gate**

Run the gate command above.

Expected: exit `0`, with no active feature.

- [ ] **Step 2: Add H010 as `not_started`**

Add this feature object after H009:

```json
{
  "id": "H010",
  "title": "Hermes performs Tavily-first research over dynamic official sites",
  "behavior": "From Telegram, Hermes performs quick, deep, and official-site public-web research using Tavily plus clean-session browser acquisition, verifies material claims against exact text or structured evidence, produces cited session-scoped reports, and routes only explicit durable website intent to the existing Azure knowledge lifecycle.",
  "verification": {
    "layer_1": "uv run --frozen python ../tests/verify_research.py --layer 1",
    "layer_2": "uv run --frozen python ../tests/verify_research.py --layer 2",
    "layer_3": "fresh Hermes process and approved Telegram chat complete the Tavily-first research release scenarios"
  },
  "state": "not_started",
  "evidence": null,
  "blocked": null,
  "depends_on": ["H005"]
}
```

- [ ] **Step 3: Validate JSON and WIP before activation**

Run:

```bash
python -m json.tool feature-list.json
python -c "import json; d=json.load(open('feature-list.json', encoding='utf-8')); assert sum(f['state']=='active' for f in d['features']) == 0"
```

Expected: both exit `0`.

- [ ] **Step 4: Transition H010 `not_started → active` and update handoff**

Change only H010 state to `active`. Add a concise `PROGRESS.md` entry naming the spec, plan, scope, WIP owner, and external prerequisite: rotated Tavily credential in the operator environment.

- [ ] **Step 5: Revalidate WIP**

Run:

```bash
python -c "import json; d=json.load(open('feature-list.json', encoding='utf-8')); a=[f['id'] for f in d['features'] if f['state']=='active']; assert a == ['H010'], a"
```

Expected: exit `0`.

- [ ] **Step 6: Commit the state transition**

```bash
git add feature-list.json PROGRESS.md
git commit -m "chore(research): activate Tavily-first research"
```

---

### Task 2: Pin and Verify Official Operator Tools

**Files:**
- Modify: `src/setup.cmd`
- Modify: `src/setup.sh`
- Modify: `src/README.md`
- Modify: `tests/verify_research.py`

**Interfaces:**
- Consumes: operator-installed `uv`, npm, and Hermes global environment.
- Produces: `tvly` 0.1.6 and `agent-browser` 0.35.1 commands available from deployed `src` CWD; no project dependency or second credential store.

- [ ] **Step 1: Add failing Layer 1 assertions**

Extend `layer_1()`:

```python
setup_cmd = (ROOT / "src/setup.cmd").read_text(encoding="utf-8")
setup_sh = (ROOT / "src/setup.sh").read_text(encoding="utf-8")
readme = (ROOT / "src/README.md").read_text(encoding="utf-8")
for text in (setup_cmd, setup_sh):
    assert "tavily-cli==0.1.6" in text
    assert "agent-browser@0.35.1" in text
assert "%LOCALAPPDATA%\\hermes\\.env" in readme
assert "TAVILY_API_KEY" in readme
assert "tvly login --api-key" not in readme
```

- [ ] **Step 2: Run Layer 1 and confirm RED**

From `src`:

```bash
uv run --frozen python ../tests/verify_research.py --layer 1
```

Expected: FAIL because setup/docs do not contain the pinned tool contract.

- [ ] **Step 3: Extend operator setup using official installers only**

Append before the existing browser doctors.

`src/setup.cmd`:

```bat
uv tool install tavily-cli==0.1.6 || exit /b 1
call npm install -g agent-browser@0.35.1 || exit /b 1
call agent-browser install || exit /b 1
```

`src/setup.sh`:

```bash
uv tool install tavily-cli==0.1.6
npm install -g agent-browser@0.35.1
agent-browser install
```

Do not add either package to the project lockfile.

- [ ] **Step 4: Document one-store authentication and backend selection**

Add to `src/README.md`:

```text
Tavily research uses one operator secret. On Windows, place TAVILY_API_KEY in
%LOCALAPPDATA%\hermes\.env; use the equivalent Hermes operator/profile env on
other platforms. Do not run `tvly login --api-key` and do not place the key in
this workspace. Configure `web.search_backend` and `web.extract_backend` to
`tavily`; the official CLI reads the same environment variable.
```

Document these non-secret commands:

```bash
hermes config set web.search_backend tavily
hermes config set web.extract_backend tavily
tvly --version
agent-browser --version
```

- [ ] **Step 5: Run Layer 1 and operator-tool smoke checks**

```bash
uv run --frozen python ../tests/verify_research.py --layer 1
tvly --version
agent-browser --version
agent-browser network requests --help
```

Expected: Layer 1 PASS; exact versions 0.1.6 and 0.35.1; network help exits `0`. Authentication checks report only success/failure, never the key.

- [ ] **Step 6: Commit tool setup**

```bash
git add src/setup.cmd src/setup.sh src/README.md tests/verify_research.py
git commit -m "build(research): pin Tavily and browser tools"
```

---

### Task 3: Add Research Policy and Native Routing

**Files:**
- Create: `src/config/research_policy.json`
- Modify: `src/skills/research/SKILL.md`
- Modify: `src/skills/research/references/research-protocol.md`
- Modify: `src/skills/research/references/source-quality.md`
- Modify: `src/skills/research/references/report-contract.md`
- Modify: `src/AGENTS.md`
- Modify: `tests/verify_research.py`

**Interfaces:**
- Consumes: official `tvly`, native Hermes web/browser tools, `grounded-citations`, and existing H005/H006 routing.
- Produces: deterministic Quick, Deep, and Site Intelligence modes plus machine-readable per-run ceilings.

- [ ] **Step 1: Add failing policy and routing assertions**

Add to `layer_1()`:

```python
policy_path = ROOT / "src/config/research_policy.json"
assert policy_path.is_file()
policy = json.loads(policy_path.read_text(encoding="utf-8"))
assert policy == {
    "schema_version": 1,
    "quick": {"search_calls": 2, "extract_calls": 2, "extract_urls": 5,
              "browser_navigations": 1, "source_bytes": 2097152, "seconds": 120},
    "deep": {"research_runs": 1, "research_model": "mini", "status_polls": 60,
             "search_calls": 2, "extract_urls": 10, "browser_navigations": 3,
             "network_responses": 10, "source_bytes": 2097152, "seconds": 900},
    "site": {"map_calls": 1, "map_urls": 50, "crawl_calls": 1,
             "crawl_pages": 20, "crawl_depth": 2, "extract_calls": 2,
             "extract_urls": 5, "browser_navigations": 2,
             "network_requests": 50, "network_responses": 10,
             "response_bytes": 5242880, "seconds": 300},
    "temporary_bytes": 20971520,
    "pro_requires_confirmation": True
}
contract = "\n".join(
    path.read_text(encoding="utf-8")
    for path in [SKILL, *sorted((SKILL.parent / "references").glob("*.md"))]
).lower()
for phrase in ("quick", "deep", "site intelligence", "tvly research",
               "capture-only", "official_domain", "grounded-citations"):
    assert phrase in contract
for forbidden in ("firecrawl", "camofox", "captcha solver"):
    assert forbidden not in contract
```

Keep historical mentions only if required to state an explicit prohibition; adjust the assertion to target runnable instructions, not prose citations.

- [ ] **Step 2: Run Layer 1 and confirm RED**

```bash
uv run --frozen python ../tests/verify_research.py --layer 1
```

Expected: FAIL on missing `research_policy.json` and routing text.

- [ ] **Step 3: Create exact policy**

Write `src/config/research_policy.json` with the object asserted above, formatted as stable UTF-8 JSON.

- [ ] **Step 4: Rewrite the skill around existing tools**

In `SKILL.md`, preserve persistence and report delivery, then add:

```text
Quick: native Tavily search/extract → verified cited answer.
Deep: tvly research mini/pro → reopen load-bearing sources → gap pass → dossier.
Site Intelligence: Tavily extract/map/crawl → clean browser capture → first-party
structured evidence. A provider HTTP 200 with missing requested evidence is
`incomplete`, not success.
```

Add `grounded-citations` to related skills. Name the exact CLI command shapes and exit behavior from the approved spec. State that `pro` requires explicit confirmation.

- [ ] **Step 5: Add deterministic public-data and lifecycle policy**

In `research-protocol.md`, copy the approved capture-only rules, official-domain confirmation, same-domain restriction, sensitive-request rejection, URL validation, cleanup, and no replay/parameter mutation.

In `source-quality.md`, define `live`, `provider-cache`, `snapshot`, `unknown`, location-sensitive pricing, and one-primary-source versus two-independent-source sufficiency.

In `report-contract.md`, require acquisition method, freshness, exact evidence, location context, coverage gaps, and stop reason.

In `src/AGENTS.md`, keep current-response research on `/research`; retain/ingest website intent remains `/hermes-azure-rag`; ambiguous “save this” asks which object to save.

- [ ] **Step 6: Run Layer 1 GREEN**

```bash
uv run --frozen python ../tests/verify_research.py --layer 1
python -m json.tool config/research_policy.json
```

Expected: both PASS.

- [ ] **Step 7: Commit policy and routing**

```bash
git add src/config/research_policy.json src/skills/research src/AGENTS.md tests/verify_research.py
git commit -m "feat(research): define Tavily-first research modes"
```

---

### Task 4: Cut Over the Canonical Dossier to Evidence Schema v2

**Files:**
- Modify: `src/skills/research/scripts/research_store.py`
- Modify: `tests/verify_research.py`

**Interfaces:**
- Consumes: version-1 dossiers and normalized text/JSON source fragments.
- Produces:
  - `normalize_text(value: str) -> bytes`
  - `canonical_json(value: object) -> bytes`
  - `fingerprint(value: bytes) -> str`
  - `validate_first_party_endpoint(official_domain: str, endpoint: str) -> None`
  - `validate_dossier(data: dict) -> None` for schema v2
  - `archive_legacy_dossiers(workspace: Path) -> list[str]`

- [ ] **Step 1: Replace the test fixture with a valid v2 dossier**

Use this shape in `fixture()`:

```python
source_text = "Tavily publishes a web research API."
source_fingerprint = "sha256:" + __import__("hashlib").sha256(
    source_text.encode("utf-8")
).hexdigest()
return {
    "schema_version": 2,
    "dossier_id": "tavily-research-2026",
    "session_id": "telegram-research-session",
    "mode": mode,
    "question": "How should Hermes research the public web?",
    "scope": "Tavily-first public research",
    "created_at": "2026-08-27T00:00:00Z",
    "updated_at": "2026-08-27T00:00:00Z",
    "executive_answer": "Use Tavily with direct evidence verification.",
    "sources": [{
        "id": "s1", "title": "Tavily Research", "publisher": "Tavily",
        "retrieved_at": "2026-08-27T00:00:00Z",
        "url": "https://docs.tavily.com/documentation/api-reference/endpoint/research",
        "access_status": "read", "classification": "primary",
        "independence": "vendor", "acquisition_method": "tavily-extract",
        "freshness": "unknown", "fingerprint": source_fingerprint
    }],
    "evidence": [{
        "id": "e1", "source_id": "s1", "kind": "text",
        "value": source_text, "fingerprint": source_fingerprint
    }],
    "claims": [{
        "id": "c1", "type": "fact",
        "text": "Tavily publishes a web research API.",
        "evidence_ids": ["e1"], "counter_evidence_ids": [],
        "confidence": "high", "confidence_rationale": "Direct documentation."
    }],
    "contradictions": [], "gaps": [], "unknowns": [], "next_questions": [],
    "method": "Opened primary documentation.", "limitations": []
}
```

- [ ] **Step 2: Add RED cases**

Add assertions for:

```python
bad = fixture(); bad["evidence"] = []
expect_error(lambda: store.validate_dossier(bad), "missing evidence")

bad = fixture(); bad["evidence"][0]["value"] = "changed"
expect_error(lambda: store.validate_dossier(bad), "fingerprint")

bad = fixture(); bad["sources"][0]["classification"] = "candidate"
expect_error(lambda: store.validate_dossier(bad), "candidate")

expect_error(
    lambda: store.validate_first_party_endpoint(
        "thecoffeehouse.com", "https://analytics.example.net/menu"
    ),
    "first-party",
)
```

Create a temporary v1 saved dossier and assert `archive_legacy_dossiers()` moves it to `legacy-v1` without inventing evidence.

- [ ] **Step 3: Run Layer 2 and confirm RED**

```bash
uv run --frozen python ../tests/verify_research.py --layer 2
```

Expected: FAIL because schema-v2 functions do not exist.

- [ ] **Step 4: Implement deterministic normalization**

Add imports: `hashlib`, `unicodedata`, and `urlsplit`.

```python
def normalize_text(value: str) -> bytes:
    text = unicodedata.normalize("NFC", value).replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in text.split("\n")).encode("utf-8")


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def fingerprint(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()
```

Validate text evidence against `fingerprint(normalize_text(value))`; structured evidence against `fingerprint(canonical_json(value))`. Reject text over 4,000 characters and structured evidence over 65,536 canonical bytes.

- [ ] **Step 5: Implement evidence and claim validation**

Build `source_ids`, `evidence_ids`, and `claim_ids` separately. Evidence references sources; claims reference evidence—not source IDs. Reject candidate-classified source evidence for factual material claims.

```python
missing = (set(claim.get("evidence_ids", [])) |
           set(claim.get("counter_evidence_ids", []))) - evidence_ids
if missing:
    raise ValueError(f"missing evidence references: {sorted(missing)}")
```

- [ ] **Step 6: Implement first-party and legacy cutover**

```python
def validate_first_party_endpoint(official_domain: str, endpoint: str) -> None:
    domain = official_domain.lower().strip(".")
    host = (urlsplit(endpoint).hostname or "").lower().strip(".")
    if not domain or not host or (host != domain and not host.endswith("." + domain)):
        raise ValueError("data endpoint is not first-party")
```

`archive_legacy_dossiers()` scans `saved/*/dossier.json`; for schema 1, atomically moves the complete dossier directory to the same safe name under `legacy-v1` (for example, `saved/firecrawl-2026` becomes `legacy-v1/firecrawl-2026`). Add CLI command `migrate-v1`. Do not synthesize evidence.

- [ ] **Step 7: Run Layer 2 GREEN**

```bash
uv run --frozen python ../tests/verify_research.py --layer 2
```

Expected: PASS.

- [ ] **Step 8: Commit schema cutover**

```bash
git add src/skills/research/scripts/research_store.py tests/verify_research.py
git commit -m "feat(research): require canonical evidence records"
```

---

### Task 5: Render Verified Evidence and Provenance

**Files:**
- Modify: `src/skills/research/scripts/render_report.py`
- Modify: `tests/verify_research.py`

**Interfaces:**
- Consumes: validated schema-v2 dossier.
- Produces: safe HTML whose claim links resolve through evidence to sources and whose evidence cards show acquisition, freshness, endpoint, timestamp, and location context.

- [ ] **Step 1: Add failing report assertions**

After rendering `fixture()`, assert:

```python
for value in (
    "Tavily publishes a web research API.",
    "tavily-extract",
    "unknown",
    "2026-08-27T00:00:00Z",
):
    assert value in html
assert "[e1]" in html
```

Add an XSS case with evidence value `<img src=x onerror=alert(1)>` and assert it is escaped and no active tag/handler exists.

- [ ] **Step 2: Run Layer 2 and confirm RED**

```bash
uv run --frozen python ../tests/verify_research.py --layer 2
```

Expected: FAIL because renderer still treats claim evidence IDs as source IDs and omits evidence cards.

- [ ] **Step 3: Resolve claim → evidence → source**

At the start of `render_html()`:

```python
sources = {item["id"]: item for item in dossier["sources"]}
evidence = {item["id"]: item for item in dossier["evidence"]}
```

For each claim evidence ID, resolve `evidence[id]["source_id"]`, then link the source URL. Never index `sources` directly by evidence ID.

- [ ] **Step 4: Render bounded evidence cards safely**

Render escaped evidence value, acquisition method, freshness, retrieval time, optional visible-page URL, optional data endpoint, and optional location context. Keep existing CSP-free static HTML: no script, iframe, form, remote JavaScript, or event handlers.

- [ ] **Step 5: Run Layer 2 GREEN**

```bash
uv run --frozen python ../tests/verify_research.py --layer 2
```

Expected: PASS.

- [ ] **Step 6: Commit renderer update**

```bash
git add src/skills/research/scripts/render_report.py tests/verify_research.py
git commit -m "feat(research): render verified evidence provenance"
```

---

### Task 6: Add Reproducible Site-Intelligence Fixtures

**Files:**
- Create: `tests/fixtures/research/coffee_house_menu_sanitized.json`
- Create: `tests/fixtures/research/coffee_house_menu_expected.json`
- Create: `tests/fixtures/research/manifest.json`
- Modify: `tests/verify_research.py`

**Interfaces:**
- Consumes: one clean-session public menu response captured during implementation.
- Produces: deterministic fixture and complete expected projection; production code remains brand-agnostic.

- [ ] **Step 1: Capture only the naturally observed public response**

Use a new unauthenticated `agent-browser` session. Start text HAR capture, navigate to the confirmed official ordering page, perform only public UI actions needed to reveal the product listing, stop HAR, and select the unique same-domain JSON response matching the approved generic menu-candidate rule.

Do not replay a request or submit an address. Delete raw HAR after sanitization.

- [ ] **Step 2: Create a bounded sanitized fixture**

Keep capture metadata and a representative category/product structure. The fixture must contain no headers, cookies, tokens, account values, addresses, analytics records, or unrelated responses. Its shape is:

```json
{
  "visible_page_url": "https://order.thecoffeehouse.com/product-listing",
  "official_domain": "thecoffeehouse.com",
  "observed_at": "2026-08-27T00:00:00Z",
  "location_context": "default unauthenticated context; no branch selected",
  "response": {
    "menu": [
      {
        "id": 92,
        "name": "Món Mới Phải Thử",
        "products": [
          {
            "id": "699eafedbde92e0012ac3304",
            "name": "Pizza Tomyum Hải Sản",
            "price": 59000,
            "options": [
              {"name": "Size", "items": [{"id": "4144", "name": "Vừa", "price": 59000}]}
            ]
          }
        ]
      }
    ]
  }
}
```

The test fixture may contain real public product values; production routing may not.

- [ ] **Step 3: Write the complete expected projection**

`coffee_house_menu_expected.json` lists every category, product, option, and price present in the sanitized fixture. `manifest.json` records fixture SHA-256, source type, sanitized fields, and capture date.

- [ ] **Step 4: Add failing fixture tests**

Add a pure test helper inside `tests/verify_research.py` that recursively projects all category/product/option records from the fixture. Assert exact equality with the expected JSON, unique IDs, nonempty names, integer non-negative prices, and first-party-domain validity.

Also assert production skill/scripts contain none of:

```python
("api.thecoffeehouse.com", "699eafedbde92e0012ac3304", "Pizza Tomyum Hải Sản")
```

- [ ] **Step 5: Run Layer 2**

```bash
uv run --frozen python ../tests/verify_research.py --layer 2
```

Expected: PASS after the complete expected projection is present.

- [ ] **Step 6: Commit fixtures and contract coverage**

```bash
git add tests/fixtures/research tests/verify_research.py
git commit -m "test(research): cover dynamic official menu evidence"
```

---

### Task 7: Verify Tavily Deep-Research and Failure Contracts

**Files:**
- Create: `tests/fixtures/research/tavily_search_success.json`
- Create: `tests/fixtures/research/tavily_research_candidate.json`
- Create: `tests/fixtures/research/tavily_failure.json`
- Modify: `tests/verify_research.py`
- Modify: `src/skills/research/SKILL.md`
- Modify: `src/skills/research/references/research-protocol.md`

**Interfaces:**
- Consumes: official `tvly --json` output and exit-code contract.
- Produces: compatibility fixtures proving provider output remains candidate material until independently verified.

- [ ] **Step 1: Capture sanitized CLI fixtures**

With the rotated key available only in the operator environment, run bounded public test queries:

```bash
printf '%s' 'Tavily Research API official documentation' | tvly search - --depth basic --max-results 5 --json
```

Save the no-wait output to `.runtime/research/temporary/provider-contract/request.json`, then poll the validated ID without hand-editing it:

```bash
mkdir -p .runtime/research/temporary/provider-contract
printf '%s' 'How does Tavily Research work? Use only docs.tavily.com.' | tvly research - --model mini --no-wait --json > .runtime/research/temporary/provider-contract/request.json
python -c \"import json,subprocess; p='.runtime/research/temporary/provider-contract/request.json'; rid=json.load(open(p, encoding='utf-8'))['request_id']; subprocess.run(['tvly','research','poll',rid,'--timeout','600','--json'], check=True)\"
```

Save sanitized outputs under `tests/fixtures/research/`; remove request/account metadata not required by the contract. Create `tavily_failure.json` from a synthetic documented exit-4 shape, not a real credential failure containing sensitive output.

- [ ] **Step 2: Add RED assertions for candidate isolation**

Build a dossier whose only source is `classification: candidate` from Tavily Research and whose factual claim points to it. Assert `validate_dossier()` rejects it. Then add a verified direct-source evidence record and assert the dossier passes.

Assert skill/protocol text names all failure outcomes: invalid input, auth, API, timeout, malformed/empty JSON, partial-result preservation, and no custom retry.

- [ ] **Step 3: Run Layer 1 and Layer 2**

```bash
uv run --frozen python ../tests/verify_research.py --layer 1
uv run --frozen python ../tests/verify_research.py --layer 2
```

Expected: both PASS.

- [ ] **Step 4: Commit provider compatibility fixtures**

```bash
git add tests/fixtures/research src/skills/research tests/verify_research.py
git commit -m "test(research): pin Tavily provider contracts"
```

---

### Task 8: Run Release Verification and Hand Off to Independent Verifier

**Files:**
- Modify: `PROGRESS.md`
- Modify only by independent verifier after all gates pass: `feature-list.json`

**Interfaces:**
- Consumes: completed H010 implementation and approved operator environment.
- Produces: Layer 1/2 evidence, fresh Telegram Layer 3 evidence, and an honest handoff; implementer leaves H010 `active`.

- [ ] **Step 1: Run static/schema gates**

From `src`:

```bash
uv lock --check
uv run --frozen python ../tests/verify_research.py --layer 1
uv run --frozen python -m compileall -q skills/research
```

Expected: all exit `0`. If Layer 1 fails, stop; do not run Layer 2.

- [ ] **Step 2: Run artifact behavior gates**

```bash
uv run --frozen python ../tests/verify_research.py --layer 2
uv run --frozen python ../tests/verify_knowledge.py --layer 1
uv run --frozen python ../tests/verify_knowledge.py --layer 2
uv run --frozen python ../tests/verify_progress.py --layer 1
uv run --frozen python ../tests/verify_progress.py --layer 2
```

Expected: all exit `0`; only previously documented Azure SDK subtype warnings are acceptable. If Layer 2 fails, stop; do not run Layer 3.

- [ ] **Step 3: Verify operator tools without revealing secrets**

```bash
tvly --version
agent-browser --version
tvly auth --json
```

Expected: pinned versions and authenticated status. Redact the entire output if it unexpectedly contains credential material.

- [ ] **Step 4: Run fresh Telegram Quick scenario**

Ask one current, bounded public fact. Verify Tavily source retrieval, direct evidence, citation, no unnecessary dossier, and one final response.

- [ ] **Step 5: Run fresh Telegram Deep scenario**

Run a bounded competitor comparison with a confirmed brief. Verify one mini research run, reopened load-bearing sources, at least one gap/contradiction pass, candidate isolation, exact evidence, chat brief, safe HTML report, and temporary lifecycle.

- [ ] **Step 6: Run The Coffee House Site Intelligence scenario**

From a fresh unauthenticated browser session, verify:

```text
Tavily extraction is marked incomplete when menu/price evidence is absent.
The official domain is confirmed.
One qualifying naturally observed menu response is selected without endpoint-name logic.
Every returned category/product/variant/price is projected or has an explicit skip reason.
No address, branch mutation, replay, auth, or user cookie is used.
Every reported price has structured evidence, retrieval time, and default-context disclosure.
Raw HAR/request artifacts are removed.
```

- [ ] **Step 7: Run negative and lifecycle scenarios**

Verify:

```text
Different-domain data endpoint → rejected.
Authenticated/private request → rejected.
Quota/API failure → actionable partial result with preserved evidence.
“Save this research” → H005 saved dossier.
“Retain this website as knowledge” → H006 route and confirmation boundary.
Ambiguous “save this” → one clarification and no mutation.
Fresh session cannot load an unsaved dossier.
```

- [ ] **Step 8: Record implementer evidence and handoff**

Update `PROGRESS.md` with exact commands/events, UTC timestamps, exit statuses, results, remaining operator limitations, and the independent verifier request. Keep H010 `active`.

- [ ] **Step 9: Commit implementation handoff**

```bash
git add PROGRESS.md
git commit -m "docs(research): record Tavily research verification"
```

- [ ] **Step 10: Independent verifier gate**

A separate verifier repeats Layer 1 → Layer 2 → Layer 3, reviews citation entailment and browser evidence, records evidence, and only then transitions H010 `active → passing` in `feature-list.json`.
