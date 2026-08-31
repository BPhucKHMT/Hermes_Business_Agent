---
name: social-browser-assist
description: "Report official social connection status from Telegram; personal Facebook publishing is unsupported."
version: 0.2.0
author: Hermes project team
license: MIT
platforms: [windows, linux, darwin]
metadata:
  hermes:
    category: social
    tags: [facebook, telegram, official-api, onboarding]
---

# Social Connection Status

Telegram is the customer gateway. The caller identity is captured from the
Telegram DM by the host; callers never provide an account label or static
allowlist entry.

Use `social_connection_status` to report the durable connection state for the
current Telegram caller. This status query must work for a new caller without
operator environment variables.

Facebook personal-profile publishing is disabled. Meta's official publishing
APIs do not provide a supported personal-profile publishing path, so Hermes
must not claim that a local Chrome profile or browser automation can publish on
behalf of customers. Eligible Facebook Page/Business OAuth is future scope and
requires a separate approved connector and secure authorization URL.

## Hard Stops

- Never ask for passwords, cookies, MFA codes, tokens, or profile exports in
  Telegram.
- Never accept caller-supplied `account_label` as authorization.
- Never expose browser profiles, CDP, JavaScript, coordinate clicks, or a
  publish/verify tool to customers.
- Drafts may still be delivered through Telegram, but no personal Facebook
  preparation or publishing is available.
