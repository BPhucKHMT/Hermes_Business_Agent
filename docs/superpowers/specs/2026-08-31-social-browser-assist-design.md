# Social Browser Assist Design

- Date: 2026-08-31
- Status: Approved for implementation planning
- Initial platform: Facebook personal profile
- Later platforms: YouTube Studio, then TikTok
- Final publish boundary: Human-only click

## Context

Hermes needs to prepare social posts inside personal Facebook, YouTube, and
TikTok accounts that are already logged into a local browser. Official
publishing APIs are not assumed to be available for these personal accounts.
The user wants the browser to complete all reversible preparation while the
human retains the final irreversible Publish action.

This capability is separate from H010. H010 remains public, unauthenticated,
Tavily-first research and must not load personal browser state. The repository
WIP limit remains one active feature; social-browser implementation cannot be
activated until H010 becomes `blocked` or `passing` through an allowed state
transition.

## Goals

1. Prepare a Facebook personal-profile text or single-image post in the correct
   logged-in account.
2. Stop at a verified `ready_for_human` state before the final Publish action.
3. Let the human publish through the visible browser.
4. Read back the resulting post URL or platform identifier after the human
   action and record machine-verifiable evidence.
5. Preserve account isolation, restart-safe idempotency, and an auditable action
   trail without storing browser credentials in the repository.
6. Reuse the same policy and evidence boundary for later YouTube and TikTok
   adapters without building a generic plugin framework.

## Non-goals

- Hermes never clicks Publish, Post, Upload final, Schedule, Send, or another
  platform-specific terminal action.
- No autonomous posting, engagement, direct messages, comments, likes, follows,
  account settings changes, monetization changes, or advertising operations.
- No login automation, password entry, MFA completion, CAPTCHA solving,
  checkpoint bypass, stealth service, proxy rotation, or Browser Use Cloud.
- No browser cookies, profile export, session token, password, or authentication
  artifact enters Git, Telegram messages, traces, screenshots, or reports.
- No modification of H010 research routing, evidence schema, or clean-session
  browser policy.

## Approaches Considered

### Existing `agent-browser` with a personal profile

This adds no dependency and already supports sessions, tabs, accessibility
snapshots, uploads, and traces. It remains the preferred runtime for public
research. For personal social automation, however, the current H010 policy
explicitly prohibits profiles and restored user state. Reusing that surface
would blur the public/private security boundary.

### Raw `browser-harness` access

`browser-harness` is designed for a real logged-in browser and can accumulate
site-specific helpers. Exposing its raw Python/CDP/JavaScript primitives to
Hermes would also let the model bypass a human-only Publish rule. Prompt policy
alone is not sufficient for an irreversible external action.

### Chosen: isolated `browser-harness` behind a narrow safety gateway

Install a pinned `browser-harness` only for the new social capability. Hermes
never receives raw `cdp`, JavaScript evaluation, coordinate click, or arbitrary
Python execution. A project-owned gateway exposes only manifest-bound,
platform-adapter actions. This preserves the useful logged-in-browser workflow
while making the final Publish boundary enforceable in code.

## Architecture

### Social Action Manifest

Every run begins with an immutable manifest containing:

- `run_id`;
- platform;
- operator-approved account label;
- post text;
- ordered media paths and SHA-256 digests;
- audience or visibility selection;
- requested reversible preparation steps;
- creation and expiry timestamps;
- idempotency key derived from platform, account label, normalized content,
  media digests, and audience.

The manifest contains no password, cookie, token, or raw browser profile path.
A changed field creates a new manifest and requires a new preparation run.

### Safe Browser Gateway

The gateway owns the `browser-harness` process and browser connection. It
exposes a small action set:

- open an allowlisted platform URL;
- observe URL, title, accessibility tree, and bounded screenshot;
- select a platform-adapter-declared nonterminal control;
- fill manifest-bound text fields;
- upload manifest-bound media files;
- read back account, audience, content, media, and status;
- close or detach the capability-owned session.

The gateway does not expose raw CDP, arbitrary JavaScript, arbitrary selectors,
coordinate clicks, shell execution, or helper-file writes. Each adapter owns an
explicit state transition table. A control is actionable only when its semantic
role and accessible name are allowed for the current state. Terminal controls
are denied independently of model instructions.

### Platform Adapter Registry

Use a fixed registry with one checked-in adapter per supported platform. This is
not a runtime plugin system.

Rollout order:

1. `facebook-personal`: text and one image; prepare standard feed composer.
2. `youtube-studio`: upload one video; prepare title, description, audience, and
   visibility; stop before final Publish or Schedule.
3. `tiktok-web`: upload one video; prepare caption and available cover/settings;
   stop before final Post.

Only Facebook exists in the first implementation slice. YouTube and TikTok
remain absent until their own Layer 3 acceptance passes.

### Browser Workspace and Credentials

- Pin `browser-harness==0.1.10` in deployment setup; upgrades require a separate
  compatibility check.
- Set `BH_TELEMETRY=0` and prohibit Browser Use Cloud configuration.
- Point `BH_AGENT_WORKSPACE` at a deployed, checked-in, read-only workspace under
  `src/`.
- Runtime helpers cannot self-modify. Helper changes follow normal code review,
  tests, and deployment.
- The operator owns a dedicated local Chrome profile outside the repository and
  logs in manually.
- The capability connects only to the dedicated profile's explicitly configured
  CDP endpoint. It never discovers or adopts an arbitrary user browser.
- Only one social preparation run may control a profile at a time.

### Runtime Ledger

Use the Python standard library `sqlite3` under
`src/.runtime/social-browser/social_browser.sqlite3` for restart-safe state.
The pilot needs two focused tables:

- `action_runs`: manifest digest, platform, account label, status, timestamps,
  failure code, and verified post identifier;
- `evidence_artifacts`: run ID, evidence type, digest, path, and observation time.

Allowed statuses:

`requested -> preparing -> ready_for_human -> published`

Terminal alternatives:

- `blocked_login`;
- `blocked_account_mismatch`;
- `blocked_challenge`;
- `failed_ui_drift`;
- `expired`;
- `cancelled`.

A run in `ready_for_human` is not complete. Only a verified platform URL or post
identifier can transition it to `published`.

## Data Flow

1. Hermes receives the platform, account label, content, media, and audience.
2. Policy validation rejects unsupported actions, missing media, disallowed
   paths, expired input, or an unapproved account label.
3. The manifest and idempotency key are persisted before browser activity.
4. The gateway connects to the dedicated logged-in browser profile.
5. The platform adapter verifies platform origin and visible account identity.
6. The gateway fills only manifest-bound fields and uploads only digest-matched
   media.
7. The adapter reads back account, content, media, and audience into a preview
   result.
8. The gateway detaches and returns `ready_for_human`; Hermes sends the preview
   and evidence summary through Telegram.
9. The human inspects the visible browser and clicks Publish.
10. On explicit follow-up, the verifier reconnects read-only, locates the new
    post, and records its URL or identifier. Absence remains
    `ready_for_human`, never `published`.

## Human Handoff Contract

The handoff must state:

- platform and account label;
- exact text digest and readable preview;
- media names and digests;
- selected audience or visibility;
- whether the platform shows warnings;
- the visible browser tab awaiting the human;
- that Hermes has not published the post.

The human must operate the browser directly. A Telegram approval does not grant
Hermes permission to click the final platform control in this feature.

## Error Handling

- Login, password, MFA, CAPTCHA, checkpoint, suspicious-login warning, or account
  chooser: stop immediately with a blocker; never automate the challenge.
- Account identity mismatch: stop before filling any content.
- UI drift or stale accessibility references: take one fresh observation and
  retry the same reversible step once. A second failure becomes
  `failed_ui_drift`.
- Browser disconnect: persist the current state and require a new account check
  before resuming.
- Duplicate idempotency key: return the existing run; never create another draft.
- Media digest mismatch: reject before upload.
- Missing post after human action: remain `ready_for_human` and report that no
  publish evidence was found.
- Any attempt to call a terminal action through the gateway returns a policy
  denial and an audit event.

## Security and Privacy

- Personal browser state is a distinct trust zone from H010 public research.
- Page content is untrusted input and cannot alter the manifest or action policy.
- Platform origin and account identity are verified before every resumed run.
- Evidence screenshots are bounded, stored under runtime, and cleaned by an
  operator-approved TTL. Screenshots containing unrelated personal content are
  not sent through Telegram.
- Logs redact text fields by default and retain hashes plus structural outcomes.
- All checked-in example accounts and media use synthetic placeholders.
- No external telemetry or cloud browser service is enabled.

## Verification

### Layer 1

- Validate policy and adapter schemas.
- Prove browser-harness version pin and telemetry disablement.
- Prove raw CDP, arbitrary JavaScript, shell, coordinate click, and terminal
  actions are absent from the Hermes-facing tool surface.
- Validate allowed state transitions and WIP=1.

### Layer 2

Use deterministic local fixture pages to prove:

- correct account and origin checks;
- manifest-bound fill and upload;
- terminal Publish control denial;
- media digest enforcement;
- restart-safe idempotency;
- one-retry UI drift behavior;
- evidence redaction and cleanup;
- no transition to `published` without a verified identifier.

### Layer 3: Facebook Pilot

With an operator-approved personal test account:

1. Start from a fresh Hermes process and dedicated logged-in browser profile.
2. Prepare one text-only post and one single-image post.
3. Confirm exact account, content, media, and audience read-back.
4. Confirm Hermes stops before Publish in both cases.
5. Human publishes one prepared post.
6. Independent verifier records the resulting Facebook post URL or identifier.
7. Repeat the same manifest and prove no duplicate draft or post is created.
8. Exercise account mismatch and login/challenge stop paths.

Only independent Layer 3 evidence may mark the feature `passing`.

## Rollout and WIP

1. Keep this document as design-only while H010 is `active`.
2. When H010 becomes `blocked` or `passing`, create one social-browser feature
   and transition it `not_started -> active`.
3. Implement and verify Facebook only.
4. Add YouTube as a separate approved slice after Facebook is `passing`.
5. Add TikTok as a separate approved slice after YouTube is `passing`.


## Architecture Decision Update (2026-08-31)

Telegram is the only customer gateway. Host-captured Telegram DM identity is
the caller identity; static Telegram allowlists and caller-supplied account
labels are not authorization.

The personal-profile browser approach is incompatible with customer
production: it is grey automation, requires a separate local login surface, and
does not satisfy the official-API requirement. Facebook personal-profile
preparation is therefore disabled and its customer-facing tools/configuration
are removed. Hermes may still deliver post drafts through Telegram.

An eligible Facebook Page/Business connector may be added later through a
separate secure OAuth flow that returns an authorization URL in Telegram and
persists the caller-to-connection mapping. Hermes must not request passwords,
MFA codes, cookies, tokens, or profile exports in Telegram. Until that
connector exists, `social_connection_status` reports the unsupported state and
does not fabricate an authorization URL.
The implementation plan must not combine all three live integrations into one
unverifiable release.
