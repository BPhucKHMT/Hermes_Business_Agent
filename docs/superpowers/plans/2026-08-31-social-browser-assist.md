# Social Browser Assist Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Facebook personal-profile pilot that prepares a text or single-image post in a dedicated logged-in browser, stops before Publish, and verifies the post only after the human publishes it.

**Architecture:** A pinned `browser-harness==0.1.10` process is isolated behind a project-owned `SafeBrowserGateway`; Hermes receives manifest-bound prepare/status tools, never raw CDP, JavaScript, coordinate clicks, or terminal actions. A fixed Facebook adapter drives reversible UI states, while a SQLite ledger owns idempotency, handoff status, and evidence.

**Tech Stack:** Python 3.12 standard library, `browser-harness==0.1.10`, SQLite, Hermes standalone plugin API, pytest, deterministic local HTML fixtures.

## Global Constraints

- H010 must transition `active -> blocked` with an owner and unblock condition before H012 transitions `not_started -> active`; WIP limit remains one.
- H010 public research behavior and files are off-limits except feature/progress state.
- Hermes never clicks Facebook Post/Publish/Schedule/Send or another terminal action.
- The human clicks the final Publish control in the visible browser.
- `BH_TELEMETRY=0`; Browser Use Cloud is prohibited.
- Browser cookies, passwords, profile exports, CDP credentials, and tokens remain outside Git and Telegram.
- Raw CDP, arbitrary JavaScript, arbitrary Python, shell, coordinate click, and runtime helper writes are not exposed through the Hermes tool surface.
- Only Facebook text and one-image preparation are implemented. YouTube and TikTok remain absent.
- No login, MFA, CAPTCHA, checkpoint, or account-chooser automation.
- Every mutation is restart-safe and idempotent.
- Only an independent Layer 3 verifier may move H012 to `passing`.

---

## File Map

### Production

- `src/config/social_browser_policy.json` — versioned platform/action/UI-label policy with terminal-action deny rules.
- `src/tools/social_browser/contracts.py` — immutable manifests, statuses, operations, observations, and results.
- `src/tools/social_browser/policy.py` — policy loading, account/origin/action/media validation.
- `src/tools/social_browser/store.py` — SQLite schema, state transitions, idempotency, evidence rows.
- `src/tools/social_browser/harness.py` — fixed-template subprocess bridge to `browser-harness`; no user-authored code execution.
- `src/tools/social_browser/gateway.py` — allowed browser operations and terminal-action enforcement.
- `src/tools/social_browser/facebook.py` — Facebook-only state machine and semantic UI mapping.
- `src/tools/social_browser/service.py` — prepare/status/verify orchestration.
- `src/tools/social_browser/cli.py` — local operator smoke and verifier commands.
- `src/tools/social_browser/__init__.py` — package marker and public exports.
- `src/.hermes/plugins/social-browser-assist/plugin.yaml` — standalone plugin manifest.
- `src/.hermes/plugins/social-browser-assist/schemas.py` — typed Hermes tool schemas.
- `src/.hermes/plugins/social-browser-assist/client.py` — in-process service client construction.
- `src/.hermes/plugins/social-browser-assist/plugin_tools.py` — caller-bound prepare/status handlers.
- `src/.hermes/plugins/social-browser-assist/__init__.py` — tool registration and caller guard.
- `src/skills/social-browser-assist/SKILL.md` — routing, human handoff, stop conditions, and evidence contract.
- `src/setup.cmd`, `src/setup.sh` — pinned `browser-harness` installation.
- `src/.env.example` — secret-free CDP endpoint/account-label examples.

### Verification

- `tests/social_browser/test_contracts.py`
- `tests/social_browser/test_policy.py`
- `tests/social_browser/test_store.py`
- `tests/social_browser/test_harness.py`
- `tests/social_browser/test_gateway.py`
- `tests/social_browser/test_facebook.py`
- `tests/social_browser/test_service.py`
- `tests/social_browser/test_plugin.py`
- `tests/fixtures/social_browser/facebook_composer.html`
- `tests/fixtures/social_browser/facebook_published.html`
- `tests/verify_social_browser.py`

### State and handoff

- `feature-list.json`
- `PROGRESS.md`

---

### Task 1: Release the WIP Slot and Activate H012

**Files:**
- Modify: `feature-list.json`
- Modify: `PROGRESS.md`

**Interfaces:**
- Consumes: H010 current state and repository four-state transition contract.
- Produces: H010 `blocked` with external verifier owner; H012 `active` with Layer 1/2/3 commands.

- [ ] **Step 1: Add H012 as `not_started`**

Add after H010:

```json
{
  "id": "H012",
  "title": "Hermes prepares personal Facebook posts for human publication",
  "behavior": "From an approved Telegram caller, Hermes prepares a text or single-image post in a dedicated logged-in Facebook browser profile, verifies account/content/media/audience, stops before Publish, and records a post URL only after the human publishes.",
  "verification": {
    "layer_1": "python tests/verify_social_browser.py --layer 1",
    "layer_2": "uv run --frozen python ../tests/verify_social_browser.py --layer 2",
    "layer_3": "independent verifier uses a dedicated personal Facebook test account to prove prepare-only handoff, human Publish, read-back evidence, idempotency, and blocker paths"
  },
  "state": "not_started",
  "evidence": null,
  "blocked": null,
  "depends_on": ["H008"]
}
```

- [ ] **Step 2: Validate the state file before transitions**

Run:

```bash
python -m json.tool feature-list.json
```

Expected: exit 0; H010 remains the sole active feature.

- [ ] **Step 3: Record and apply the H010 blocker**

Set H010 to `blocked` with:

```json
"blocked": "Implementation and Layer 1/2 are complete. Owner: operator plus independent verifier. Unblock when the seven approved Telegram research scenarios are run against a fresh Hermes process and evidence is recorded."
```

Append the same owner and unblock condition to `PROGRESS.md`.

- [ ] **Step 4: Transition H012 to active**

Set only H012 to `active`. Add a WIP assertion to the validation command:

```bash
python -c "import json; d=json.load(open('feature-list.json', encoding='utf-8')); a=[f['id'] for f in d['features'] if f['state']=='active']; assert a == ['H012'], a"
```

Expected: exit 0.

- [ ] **Step 5: Commit state activation**

```bash
git add feature-list.json PROGRESS.md
git commit -m "chore(state): activate Facebook browser pilot"
```

### Task 2: Define Contracts and Fail-Closed Policy

**Files:**
- Create: `src/tools/social_browser/__init__.py`
- Create: `src/tools/social_browser/contracts.py`
- Create: `src/tools/social_browser/policy.py`
- Create: `src/config/social_browser_policy.json`
- Test: `tests/social_browser/test_contracts.py`
- Test: `tests/social_browser/test_policy.py`

**Interfaces:**
- Produces: `RunStatus`, `BrowserOperation`, `SocialActionManifest`, `BrowserObservation`, `PreparationResult`, `SocialBrowserPolicy`, `load_policy(path)`, `create_manifest(...)`, and validation functions used by every later task.

- [ ] **Step 1: Write contract RED tests**

```python
from pathlib import Path
import pytest
from tools.social_browser.contracts import RunStatus, create_manifest


def test_manifest_idempotency_is_content_addressed(tmp_path: Path):
    media = tmp_path / "post.png"
    media.write_bytes(b"image")
    first = create_manifest("facebook-personal", "klaus", "Hello", [media], "friends")
    second = create_manifest("facebook-personal", "klaus", "Hello", [media], "friends")
    assert first.idempotency_key == second.idempotency_key
    assert first.status is RunStatus.REQUESTED


def test_manifest_rejects_changed_media_after_hashing(tmp_path: Path):
    media = tmp_path / "post.png"
    media.write_bytes(b"image")
    manifest = create_manifest("facebook-personal", "klaus", "Hello", [media], "friends")
    media.write_bytes(b"changed")
    with pytest.raises(ValueError, match="media_digest_mismatch"):
        manifest.verify_media()
```

- [ ] **Step 2: Write policy RED tests**

```python
import pytest
from tools.social_browser.policy import load_policy


def test_policy_denies_terminal_and_raw_operations(policy_path):
    policy = load_policy(policy_path)
    for action in ("publish", "post", "schedule", "send", "raw_cdp", "javascript", "coordinate_click", "shell"):
        assert not policy.allows_operation("facebook-personal", action)


def test_policy_accepts_only_facebook_origin(policy_path):
    policy = load_policy(policy_path)
    policy.require_origin("facebook-personal", "https://www.facebook.com/")
    with pytest.raises(PermissionError, match="origin_not_allowed"):
        policy.require_origin("facebook-personal", "https://example.com/")
```

- [ ] **Step 3: Run RED tests**

Run:

```bash
uv run --frozen python -m pytest ../tests/social_browser/test_contracts.py ../tests/social_browser/test_policy.py -q
```

Expected: collection fails because the package does not exist.

- [ ] **Step 4: Implement immutable contracts**

Use `Enum`, frozen dataclasses, SHA-256, NFC/LF normalization, resolved paths, and `hmac.compare_digest` for media verification. Define exactly:

```python
class RunStatus(str, Enum):
    REQUESTED = "requested"
    PREPARING = "preparing"
    READY_FOR_HUMAN = "ready_for_human"
    PUBLISHED = "published"
    BLOCKED_LOGIN = "blocked_login"
    BLOCKED_ACCOUNT_MISMATCH = "blocked_account_mismatch"
    BLOCKED_CHALLENGE = "blocked_challenge"
    FAILED_UI_DRIFT = "failed_ui_drift"
    EXPIRED = "expired"
    CANCELLED = "cancelled"

class BrowserOperation(str, Enum):
    OPEN = "open"
    OBSERVE = "observe"
    ACTIVATE_CONTROL = "activate_control"
    FILL = "fill"
    UPLOAD = "upload"
    CLOSE = "close"

@dataclass(frozen=True)
class SocialActionManifest:
    run_id: str
    idempotency_key: str
    platform: str
    account_label: str
    text: str
    media: tuple[MediaItem, ...]
    audience: str
    created_at: str
    expires_at: str
    status: RunStatus = RunStatus.REQUESTED

@dataclass(frozen=True)
class BrowserObservation:
    url: str
    title: str
    account_label: str
    accessible_nodes: tuple[AccessibleNode, ...]
    warning_codes: tuple[str, ...] = ()

@dataclass(frozen=True)
class PreparationResult:
    run_id: str
    status: RunStatus
    account_label: str
    text_digest: str
    media_digests: tuple[str, ...]
    audience: str
    evidence_paths: tuple[str, ...]
```

- [ ] **Step 5: Implement the JSON policy**

```json
{
  "schema_version": 1,
  "browser_harness_version": "0.1.10",
  "telemetry": false,
  "cloud": false,
  "max_screenshot_bytes": 2097152,
  "evidence_ttl_seconds": 86400,
  "platforms": {
    "facebook-personal": {
      "origins": ["https://www.facebook.com"],
      "audiences": ["friends", "only-me"],
      "allowed_operations": ["open", "observe", "activate_control", "fill", "upload", "close"],
      "terminal_names": ["post", "publish", "schedule", "send", "đăng", "xuất bản", "lên lịch", "gửi"],
      "composer_names": ["what's on your mind?", "bạn đang nghĩ gì?"],
      "max_text_chars": 63206,
      "max_media_files": 1
    }
  }
}
```

`load_policy()` rejects unknown top-level keys, schema versions, empty origins, telemetry/cloud true, missing terminal names, and overlap between allowed and terminal operations.

- [ ] **Step 6: Run GREEN tests and commit**

```bash
uv run --frozen python -m pytest ../tests/social_browser/test_contracts.py ../tests/social_browser/test_policy.py -q
git add src/tools/social_browser src/config/social_browser_policy.json tests/social_browser/test_contracts.py tests/social_browser/test_policy.py
git commit -m "feat(social): add manifest and action policy"
```

### Task 3: Add Restart-Safe SQLite Ledger

**Files:**
- Create: `src/tools/social_browser/store.py`
- Test: `tests/social_browser/test_store.py`

**Interfaces:**
- Consumes: `SocialActionManifest`, `RunStatus`.
- Produces: `SocialBrowserStore(path)`, `create_or_get(manifest)`, `transition(run_id, expected, target, failure_code=None)`, `add_evidence(...)`, and `get_run(run_id)`.

- [ ] **Step 1: Write RED state-transition tests**

```python
import pytest
from tools.social_browser.contracts import RunStatus
from tools.social_browser.store import SocialBrowserStore


def test_duplicate_manifest_returns_existing_run(store, manifest):
    first = store.create_or_get(manifest)
    second = store.create_or_get(manifest)
    assert first.run_id == second.run_id


def test_published_requires_verified_identifier(store, manifest):
    store.create_or_get(manifest)
    store.transition(manifest.run_id, RunStatus.REQUESTED, RunStatus.PREPARING)
    store.transition(manifest.run_id, RunStatus.PREPARING, RunStatus.READY_FOR_HUMAN)
    with pytest.raises(ValueError, match="verified_post_id_required"):
        store.transition(manifest.run_id, RunStatus.READY_FOR_HUMAN, RunStatus.PUBLISHED)
```

- [ ] **Step 2: Run RED test**

```bash
uv run --frozen python -m pytest ../tests/social_browser/test_store.py -q
```

Expected: import failure for `store`.

- [ ] **Step 3: Implement schema and transition guard**

Create tables with `PRAGMA foreign_keys=ON`, WAL mode, unique idempotency key, parameterized SQL, and a transaction around compare-and-set transitions. Permit only the transitions in the design spec. Require `verified_post_id` for `READY_FOR_HUMAN -> PUBLISHED`.

- [ ] **Step 4: Run GREEN test and commit**

```bash
uv run --frozen python -m pytest ../tests/social_browser/test_store.py -q
git add src/tools/social_browser/store.py tests/social_browser/test_store.py
git commit -m "feat(social): add idempotent action ledger"
```

### Task 4: Build the Fixed-Template Harness Bridge and Safety Gateway

**Files:**
- Create: `src/tools/social_browser/harness.py`
- Create: `src/tools/social_browser/gateway.py`
- Test: `tests/social_browser/test_harness.py`
- Test: `tests/social_browser/test_gateway.py`

**Interfaces:**
- Consumes: `BrowserOperation`, `BrowserObservation`, `SocialBrowserPolicy`.
- Produces: `BrowserHarnessRunner.run(operation, payload) -> dict` and `SafeBrowserGateway` methods `open`, `observe`, `activate_control`, `fill`, `upload`, `close`.

- [ ] **Step 1: Write RED bridge tests**

```python

def test_runner_uses_fixed_templates_without_user_code(fake_subprocess, runner):
    runner.run(BrowserOperation.OBSERVE, {"session": "run-1"})
    command = fake_subprocess.last_command
    stdin = fake_subprocess.last_stdin
    assert command == ["browser-harness"]
    assert "exec(" not in stdin
    assert "eval(" not in stdin
    assert "raw_code" not in stdin


def test_runner_forces_telemetry_off(fake_subprocess, runner):
    runner.run(BrowserOperation.OBSERVE, {"session": "run-1"})
    assert fake_subprocess.last_env["BH_TELEMETRY"] == "0"
    assert "BROWSER_USE_API_KEY" not in fake_subprocess.last_env
```

- [ ] **Step 2: Write RED gateway tests**

```python
import pytest


def test_gateway_denies_terminal_accessible_name(gateway):
    with pytest.raises(PermissionError, match="terminal_action_denied"):
        gateway.activate_control(node(role="button", name="Post"))


def test_gateway_denies_raw_operations(gateway):
    for operation in ("raw_cdp", "javascript", "coordinate_click", "shell"):
        with pytest.raises(PermissionError, match="operation_not_allowed"):
            gateway.dispatch(operation, {})
```

- [ ] **Step 3: Run RED tests**

```bash
uv run --frozen python -m pytest ../tests/social_browser/test_harness.py ../tests/social_browser/test_gateway.py -q
```

- [ ] **Step 4: Implement fixed scripts**

`harness.py` owns one static script per `BrowserOperation`. Payload enters through a base64-encoded JSON environment variable, is decoded as data, and is never concatenated into Python source. Use `subprocess.run` with an argv list, no shell, UTF-8, bounded timeout, bounded stdout, and a sanitized environment containing `BH_TELEMETRY=0`, `BH_AGENT_WORKSPACE`, and the configured CDP endpoint.

- [ ] **Step 5: Implement gateway enforcement**

Before any action, require allowed platform, origin, operation, current adapter state, and accessible role/name. Normalize terminal names with Unicode NFC plus casefold. The only internal coordinate calculation is AX backend node to box center inside the fixed bridge; callers never supply coordinates.

- [ ] **Step 6: Run GREEN tests and commit**

```bash
uv run --frozen python -m pytest ../tests/social_browser/test_harness.py ../tests/social_browser/test_gateway.py -q
git add src/tools/social_browser/harness.py src/tools/social_browser/gateway.py tests/social_browser/test_harness.py tests/social_browser/test_gateway.py
git commit -m "feat(social): enforce safe browser action gateway"
```

### Task 5: Implement the Facebook Prepare-Only Adapter

**Files:**
- Create: `src/tools/social_browser/facebook.py`
- Create: `tests/fixtures/social_browser/facebook_composer.html`
- Create: `tests/fixtures/social_browser/facebook_published.html`
- Test: `tests/social_browser/test_facebook.py`

**Interfaces:**
- Consumes: `SafeBrowserGateway`, `SocialActionManifest`, `BrowserObservation`.
- Produces: `FacebookPersonalAdapter.prepare(manifest) -> PreparationResult` and `verify_published(manifest) -> str | None`.

- [ ] **Step 1: Create deterministic fixtures**

The composer fixture must include:

```html
<button aria-label="Bạn đang nghĩ gì?">Open composer</button>
<div role="dialog" aria-label="Create post">
  <div role="textbox" contenteditable="true" aria-label="Post text"></div>
  <input type="file" accept="image/*">
  <span aria-label="Audience">Friends</span>
  <button aria-label="Post">Post</button>
</div>
```

The published fixture includes the exact text digest marker and a canonical post link such as `https://www.facebook.com/test-account/posts/123456789`.

- [ ] **Step 2: Write RED adapter tests**

```python

def test_prepare_stops_before_post(adapter, manifest, fake_gateway):
    result = adapter.prepare(manifest)
    assert result.status is RunStatus.READY_FOR_HUMAN
    assert "Post" not in fake_gateway.activated_names
    assert fake_gateway.filled_text == manifest.text


def test_account_mismatch_stops_before_fill(adapter, manifest, fake_gateway):
    fake_gateway.account_label = "wrong-account"
    result = adapter.prepare(manifest)
    assert result.status is RunStatus.BLOCKED_ACCOUNT_MISMATCH
    assert fake_gateway.filled_text is None


def test_ui_drift_retries_once(adapter, manifest, fake_gateway):
    fake_gateway.fail_observations = 2
    result = adapter.prepare(manifest)
    assert result.status is RunStatus.FAILED_UI_DRIFT
    assert fake_gateway.observation_count == 2
```

- [ ] **Step 3: Run RED tests**

```bash
uv run --frozen python -m pytest ../tests/social_browser/test_facebook.py -q
```

- [ ] **Step 4: Implement explicit state machine**

Use states `VERIFY_ACCOUNT`, `OPEN_COMPOSER`, `FILL_TEXT`, `UPLOAD_MEDIA`, `VERIFY_PREVIEW`, `HANDOFF`. At each state, validate origin and account. Read audience; do not change it in the Facebook pilot. Require the manifest audience to match the observed value. Never request or activate the terminal control.

- [ ] **Step 5: Run GREEN tests and commit**

```bash
uv run --frozen python -m pytest ../tests/social_browser/test_facebook.py -q
git add src/tools/social_browser/facebook.py tests/fixtures/social_browser tests/social_browser/test_facebook.py
git commit -m "feat(social): prepare Facebook posts for human publish"
```

### Task 6: Orchestrate Prepare, Status, and Read-Back Verification

**Files:**
- Create: `src/tools/social_browser/service.py`
- Create: `src/tools/social_browser/cli.py`
- Test: `tests/social_browser/test_service.py`

**Interfaces:**
- Consumes: policy, store, gateway, Facebook adapter.
- Produces: `SocialBrowserService.prepare(request)`, `status(run_id)`, `verify_after_human(run_id)` and CLI commands `prepare`, `status`, `verify`, `cleanup`.

- [ ] **Step 1: Write RED service tests**

```python

def test_prepare_persists_before_browser(service, store_spy, request):
    service.prepare(request)
    assert store_spy.calls[0] == "create_or_get"
    assert store_spy.calls[1] == "transition:requested->preparing"


def test_verify_without_post_keeps_ready_for_human(service, prepared_run):
    result = service.verify_after_human(prepared_run.run_id)
    assert result.status is RunStatus.READY_FOR_HUMAN


def test_verify_with_post_id_marks_published(service, prepared_run, adapter):
    adapter.published_id = "https://www.facebook.com/test-account/posts/123456789"
    result = service.verify_after_human(prepared_run.run_id)
    assert result.status is RunStatus.PUBLISHED
    assert result.verified_post_id.endswith("123456789")
```

- [ ] **Step 2: Run RED tests**

```bash
uv run --frozen python -m pytest ../tests/social_browser/test_service.py -q
```

- [ ] **Step 3: Implement orchestration and CLI**

The service persists before browser access, maps typed exceptions to blocker statuses, writes evidence only after digest validation, and always closes/detaches in `finally`. `cleanup` removes expired screenshots/traces but never deletes the ledger row.

- [ ] **Step 4: Run GREEN tests and commit**

```bash
uv run --frozen python -m pytest ../tests/social_browser/test_service.py -q
git add src/tools/social_browser/service.py src/tools/social_browser/cli.py tests/social_browser/test_service.py
git commit -m "feat(social): orchestrate human-publish handoff"
```

### Task 7: Expose Narrow Hermes Tools and Runtime Skill

**Files:**
- Create: `src/.hermes/plugins/social-browser-assist/plugin.yaml`
- Create: `src/.hermes/plugins/social-browser-assist/schemas.py`
- Create: `src/.hermes/plugins/social-browser-assist/client.py`
- Create: `src/.hermes/plugins/social-browser-assist/plugin_tools.py`
- Create: `src/.hermes/plugins/social-browser-assist/__init__.py`
- Create: `src/skills/social-browser-assist/SKILL.md`
- Modify: `src/AGENTS.md`
- Test: `tests/social_browser/test_plugin.py`

**Interfaces:**
- Produces Hermes tools `social_prepare_facebook_post`, `social_browser_status`, and `social_verify_facebook_post`.

- [ ] **Step 1: Write RED plugin tests**

```python

def test_plugin_exposes_only_narrow_tools(fake_context):
    register(fake_context)
    assert set(fake_context.tools) == {
        "social_prepare_facebook_post",
        "social_browser_status",
        "social_verify_facebook_post",
    }
    forbidden = {"browser_cdp", "browser_js", "browser_click", "social_publish"}
    assert forbidden.isdisjoint(fake_context.tools)


def test_prepare_requires_dm_and_approved_caller(plugin, group_context):
    response = plugin.prepare(group_context, valid_request())
    assert response["error"]["code"] == "dm_required"
```

- [ ] **Step 2: Run RED tests**

```bash
uv run --frozen python -m pytest ../tests/social_browser/test_plugin.py -q
```

- [ ] **Step 3: Implement schemas and registration**

The prepare schema accepts `account_label`, `text`, optional one-element `media_paths`, and audience `friends|only-me`. It has no `publish`, `auto_publish`, raw URL, raw selector, code, or coordinates field. Reuse the host-owned caller context pattern from `email-connector`; prepare is DM-only and caller-bound.

- [ ] **Step 4: Write runtime skill**

The skill routes explicit Facebook preparation requests, states that the user must be at the visible browser, requires a preview handoff, and treats `ready_for_human` as incomplete. It forbids YouTube/TikTok claims until their future features exist.

- [ ] **Step 5: Run GREEN tests and commit**

```bash
uv run --frozen python -m pytest ../tests/social_browser/test_plugin.py -q
git add src/.hermes/plugins/social-browser-assist src/skills/social-browser-assist src/AGENTS.md tests/social_browser/test_plugin.py
git commit -m "feat(social): register prepare-only Facebook tools"
```

### Task 8: Install, Verify, and Leave Layer 3 Handoff

**Files:**
- Modify: `src/setup.cmd`
- Modify: `src/setup.sh`
- Modify: `src/.env.example`
- Create: `tests/verify_social_browser.py`
- Modify: `PROGRESS.md`

**Interfaces:**
- Produces reproducible install, Layer 1/2 gates, operator configuration contract, and precise Layer 3 blocker evidence.

- [ ] **Step 1: Add pinned installation**

Windows:

```bat
uv tool install browser-harness==0.1.10 || exit /b 1
```

POSIX:

```bash
uv tool install browser-harness==0.1.10
```

Add only placeholders to `src/.env.example`:

```dotenv
BH_TELEMETRY=0
BH_AGENT_WORKSPACE=/absolute/path/to/deployed/src/.hermes/browser-harness-workspace
SOCIAL_BROWSER_CDP_URL=http://127.0.0.1:9222
SOCIAL_BROWSER_FACEBOOK_ACCOUNT_LABEL=replace-with-visible-account-label
```

- [ ] **Step 2: Write Layer 1 verifier**

Layer 1 validates file presence, JSON policy, version pins, telemetry/cloud prohibition, exact three-tool plugin surface, H012 active/WIP=1, and absence of terminal/raw operations from schemas.

- [ ] **Step 3: Write Layer 2 verifier**

Layer 2 runs every `tests/social_browser/test_*.py` file in an isolated runtime directory and checks the Facebook fixture journey end to end.

- [ ] **Step 4: Prove RED then GREEN**

Run Layer 1 before completing setup and observe the expected missing pin failure. Finish setup, then run in order:

```bash
python tests/verify_social_browser.py --layer 1
cd src && uv run --frozen python ../tests/verify_social_browser.py --layer 2
```

Expected: both exit 0.

- [ ] **Step 5: Run regression gates**

```bash
cd src && uv run --frozen python ../tests/verify_research.py --layer 1
cd src && uv run --frozen python ../tests/verify_research.py --layer 2
cd src && uv run --frozen python -m compileall -q tools/social_browser .hermes/plugins/social-browser-assist
git diff --check
```

Expected: exit 0; known unrelated warnings only.

- [ ] **Step 6: Run the local smoke**

With a deterministic fixture transport, run:

```bash
cd src && uv run --frozen python tools/social_browser/cli.py prepare --fixture ../tests/fixtures/social_browser/facebook_composer.html --account-label test-account --text "Hermes social browser fixture" --audience friends
```

Expected JSON: `status=ready_for_human`, exact account/text/audience, and no publish operation.

- [ ] **Step 7: Record the real Layer 3 blocker or evidence**

If the operator has not configured the dedicated profile/CDP endpoint, record H012 as `blocked` with owner `operator plus independent verifier` and unblock conditions: manual login to the dedicated Facebook test account, explicit CDP endpoint, visible browser access, and approval to run the two live prepare scenarios. Do not claim live Facebook success.

If prerequisites exist, run the approved Layer 3 sequence from the design spec. The implementer records evidence but does not move H012 to `passing`; an independent verifier owns that transition.

- [ ] **Step 8: Commit verification and handoff**

```bash
git add src/setup.cmd src/setup.sh src/.env.example tests/verify_social_browser.py PROGRESS.md
git commit -m "test(social): verify Facebook human-publish boundary"
```
