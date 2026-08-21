# Coding Memory

This file guides coding agents working from repository root. It is engineering-harness context only. Hermes production runtime under `src/` must not read or depend on it.

## Solve Systems, Not Examples

- Diagnose root cause and affected boundary before changing code.
- Fix invariant, contract, schema, state transition, or enforcement point governing the whole problem class.
- Do not patch each observed prompt, entity, filename, phrase, workspace, or test case separately.
- Do not encode example wording as domain behavior when a typed reason/code can represent the condition.
- Keep examples in tests and fixtures, not permanent production policy.

## Generalization Gate

Before adding any rule or branch, answer:

1. What problem class does this solve?
2. Which invariant was missing or violated?
3. Does the change work across entities, languages, phrasings, workspaces, and equivalent workflows?
4. Is this better enforced in typed code, validation, policy, registry, or a state machine than in prose?
5. Would the rule still make sense if the triggering example disappeared?

If answers are unclear, stop and redesign. Do not add the patch.

## Evidence-Driven Changes

- Reproduce unexpected behavior and trace data across component boundaries before fixing it.
- Add the smallest failing test for the general invariant, then implement the minimum fix.
- Test representative equivalence classes and boundaries, not only the incident string.
- A test using one example must prove behavior through generic outputs or typed states, not exact incidental wording unless wording is the contract.
- Verify regressions and system boundaries before claiming completion.

## Architecture Preferences

- Prefer one authoritative data path over parallel prompt-only and code-only workflows.
- Prefer typed outcomes such as `missing_entity`, `missing_date`, or `approval_required` over hard-coded natural-language responses in domain logic.
- Render user-facing language at the presentation boundary using context and locale.
- Put safety-critical constraints in enforceable code or policy; prose may explain them but must not be the only guard.
- Keep current state, pending state, retained knowledge, and synthetic test data separate.
- Synthetic fixtures must never become production business truth.

## Scope Discipline

- Make the smallest coherent change that fixes the root cause.
- Do not broaden one workstream because nearby data exists.
- Do not invent abstractions for hypothetical future cases, but do not accept case-specific conditionals as substitutes for a proper invariant.
- Remove obsolete special cases when introducing a general mechanism.
- Preserve unrelated user changes and repository contracts.

## Review Check

Reject a change when it:

- names a specific incident entity without a domain requirement;
- matches one sentence or prompt paraphrase;
- hard-codes a fixture path or test value into production behavior;
- adds another prose rule where an execution boundary should enforce behavior;
- makes tests pass while leaving alternate phrasing or equivalent inputs broken;
- duplicates state or bypasses the canonical workflow.

Accept only when root cause, general invariant, enforcement point, and verification evidence are explicit.
