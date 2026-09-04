---
name: calendar
description: "Use when inspecting schedules, creating, modifying, rescheduling, or canceling Google Calendar events, finding free slots, or managing connected Google accounts across platforms."
version: 1.0.0
author: Hermes Engineering Team
license: MIT
platforms: [windows, linux, darwin]
metadata:
  hermes:
    category: calendar
    tags: [calendar, schedule, events, meetings, free-slots, reschedule]
---

# Google Calendar Schedule Management

## Overview

Executive Schedule Coordinator for Hermes Agent. Provides full-lifecycle Google Calendar operations—agenda querying, direct booking, Tier 2 draft-before-commit staging, patch-semantic rescheduling, event cancellation, and availability discovery—with strict multi-account isolation and local timezone handling (ICT / Asia/Ho_Chi_Minh, UTC+7).

---

## When to Use

Apply this skill whenever the user conversation touches scheduling, availability, or calendar management:

- **Schedule & Agenda Inspection:** Querying daily agendas, upcoming meetings, or inspecting details of specific events.
- **Event Scheduling (Direct or Staged):** Booking appointments, scheduling syncs, holding calendar blocks.
- **Event Rescheduling & Modification:** Shifting meeting hours, postponing, advancing, changing location, updating summaries, or altering attendee rosters.
- **Event Cancellation:** Removing or canceling scheduled events.
- **Availability Discovery:** Scanning free slots within business hours (09:00–18:00 ICT) before proposing meeting times.
- **Connection Audit:** Inspecting active Google accounts or diagnosing multi-account connectivity.

---

## Tool Catalog & Interface Contracts

| Registered Tool | Primary Purpose | Key Parameters | Return Contract |
| :--- | :--- | :--- | :--- |
| `calendar_list_events` | Query events within time bounds or by text search | `time_min`, `time_max`, `query`, `limit`, `account_email` | `{"ok": true, "result": {"events": [...], "count": N, "active_account": str}}` |
| `calendar_get_event` | Fetch comprehensive single event details | `event_id` (REQUIRED), `calendar_id`, `account_email` | `{"ok": true, "result": {"event": {...}, "active_account": str}}` |
| `calendar_create_event` | Directly commit an event without staging | `summary`, `start_time`, `end_time`, `location`, `attendees`, `account_email` | `{"ok": true, "result": {"status": "confirmed", "event_id": str, "html_link": str}}` |
| `calendar_create_draft_event` | Stage a Tier 2 draft event awaiting review | `summary`, `start_time`, `end_time`, `location`, `attendees`, `account_email` | `{"ok": true, "result": {"draft": {"draft_id": str, "account_email": str, ...}}}` |
| `calendar_confirm_event` | Commit a staged draft upon user approval | `draft_id` (REQUIRED) | `{"ok": true, "result": {"status": "confirmed", "event_id": str, "html_link": str}}` |
| `calendar_update_event` | Reschedule or patch event attributes | `event_id` (REQUIRED), `start_time`, `end_time`, `summary`, `location`, `account_email` | `{"ok": true, "result": {"status": "updated", "event_id": str, "event": {...}}}` |
| `calendar_delete_event` | Remove / cancel an event from calendar | `event_id` (REQUIRED), `calendar_id`, `account_email` | `{"ok": true, "result": {"status": "deleted", "deleted": true, "event_id": str}}` |
| `calendar_find_free_slots` | Discover open windows within working hours | `date` (YYYY-MM-DD), `duration_minutes`, `account_email` | `{"ok": true, "result": {"slots": [...], "count": N}}` |
| `calendar_status` | Enumerate connected Google accounts | None | `{"ok": true, "connected_accounts": [...], "calendars": [...]}` |

---

## Execution Lifecycles

### Lifecycle A: Event Reschedule & Attribute Modification Protocol
Used when moving meeting times, postponing/advancing schedules, changing venues, or editing summaries of existing calendar items:

1. **Event Resolution:**
   - If `event_id` is already verified in conversational context, proceed immediately to step 2.
   - If `event_id` is unknown, call `calendar_list_events` with `query` and relevant date bounds (`time_min`, `time_max`) on the target `account_email` to locate the target event and capture its unique `event_id`.
2. **Patch-Semantic Mutation:**
   - Call `calendar_update_event` with `event_id`, updated timestamps in ISO 8601 (e.g. `start_time="2026-09-04T14:30:00+07:00"`, `end_time="2026-09-04T15:00:00+07:00"`), and target `account_email`.
   - Only supply fields that require alteration; untouched fields remain intact via Composio patch semantics.
3. **Verification & Delivery:**
   - Formulate confirmation stating updated localized time window (in ICT / UTC+7), event title, and the verified Google Calendar / Meet link.

---

### Lifecycle B: Tier 2 Staged Booking Protocol (Draft-Before-Commit)
Default discipline whenever the scheduling request requires preliminary review, confirmation, or staging:

1. **Availability Verification:**
   - Run `calendar_find_free_slots` for the intended date to ensure no collision with existing commitments within working hours (09:00–18:00 ICT).
2. **Draft Staging:**
   - Call `calendar_create_draft_event` providing `summary`, `start_time`, `end_time`, `location`, `attendees`, and explicit `account_email`.
   - Capture `draft_id` and formatted summary from response.
3. **Presentation & Confirmation Gate:**
   - Present staged draft details clearly to the user (title, ICT time, venue, account).
   - Require explicit human consent ("ok", "đồng ý", "xác nhận", "tiến hành").
4. **Final Commitment:**
   - Upon affirmation, invoke `calendar_confirm_event(draft_id=...)`.
   - The connector automatically retrieves the staged draft, extracts its associated `account_email`, and executes creation on Google Calendar.
   - Deliver verified Google Event ID and URL.

---

### Lifecycle C: Direct Booking Protocol (Tier 1 Scheduling)
Applied when the user issues an unambiguous, imperative scheduling command (e.g. *"Đặt lịch họp trực tiếp lúc 15h hôm nay"*):

1. **Direct Execution:**
   - Call `calendar_create_event` with `summary`, ISO 8601 `start_time`, `end_time`, and target `account_email`.
2. **Immediate Confirmation:**
   - Verify `status: confirmed` from tool response and deliver meeting link and event summary.

---

### Lifecycle D: Cancellation Protocol
Applied when canceling, removing, or declining a calendar commitment:

1. Locate `event_id` using `calendar_list_events` if not present in memory.
2. Invoke `calendar_delete_event(event_id=..., account_email=...)`.
3. Confirm event removal from schedule.

---

## Operating Invariants & Guardrails

- **Native Tools Only:** Always use the registered tools `calendar_list_events`, `calendar_get_event`, `calendar_create_event`, `calendar_create_draft_event`, `calendar_confirm_event`, `calendar_update_event`, `calendar_delete_event`, `calendar_find_free_slots`, `calendar_status`. Never execute raw bash Python scripts or attempt direct OAuth flows.
- **Strict DM-Only Privacy:** Calendar operations are restricted to direct messages (`chat_type == "dm"`). Requests originating from group chats, public channels, or multi-user topics must redirect the user to a private DM session without exposing schedule contents.
- **Multi-Account Integrity:** If the user specifies an email address or manages multiple linked accounts, always pass `account_email` to guarantee operations execute on the intended calendar. Never assume an account when the user specifies another.
- **Timezone Grounding:** All internal timestamps pass in ISO 8601 with timezone offset (e.g. `+07:00`). When displaying to users, always format times in local ICT (Vietnam time) format (e.g. `14:30–15:00, ngày 04/09/2026`).
- **Policy Boundaries:** Operations are bounded by configured policy (maximum 30 days lookahead, 15 to 480 minutes duration). Free slot discovery aligns with working hours (09:00–18:00 ICT).
- **Anti-Hallucination Gate:** Never claim an event was created, updated, or deleted without receiving a verified positive response from the corresponding tool.
