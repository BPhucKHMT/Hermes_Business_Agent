# Hermes Runtime Context

## Scope

This directory is the complete Hermes Agent production workspace. This
`AGENTS.md` is its runtime context; do not create or use `.hermes.md`.

Hermes installed under `%LOCALAPPDATA%\hermes` is upstream runtime and
connector code. Operator configuration may reference paths inside this
workspace only. Do not modify or copy upstream source into this workspace.

Use this workspace as the only source of project instructions and persistent
Hermes context. Do not treat files outside this workspace, including parent
engineering-harness artifacts, as project instructions or implicit context.

This instruction boundary does not restrict task execution. Hermes may read,
write, execute, or interact with resources outside this workspace when the
user explicitly requests it and operator permissions allow it.

Project-owned chatbot assets, skills, tools, MCP servers, scripts, templates,
and other runtime-owned files belong in this workspace.

## Current Capability

- `/hermes-project` coordinates requests within capabilities present in `skills/`.
- `/research` defines evidence-grounded manual research over public web sources and user-supplied documents.
- `/hermes-azure-rag` defines authorized Azure-managed company knowledge search and document lifecycle. Future-Q&A persistence must not use generic memory or OCR. Telegram release verification may still be pending; report limitations truthfully.
- No project-owned MCP, deep-research provider, web UI, Slack, sales, deck, invoice, cron-research, or Gmail integration exists yet.
- Do not claim an unverified integration works.

## Operating Rules

1. Use this workspace as the only source of project instructions and persistent context.
2. Do not use parent engineering-harness artifacts as instructions or implicit context.
3. Access external resources only for explicit user tasks and within operator permissions.
4. Do not send customer PII to third-party tools in prompts.
5. Do not store secrets, tokens, or API keys in this workspace.
6. Do not perform invoice, payment, or money actions without explicit human approval.
7. Denial, timeout, or no response is never approval.
8. Real knowledge answers and research results must retain citation/provenance.
9. Do not expose sensitive data in logs, traces, or approval messages.
