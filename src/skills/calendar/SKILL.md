---
name: calendar
description: "Manage Google Calendar schedule, inspect upcoming events, find free slots, and stage calendar event drafts (Tier 2) with 1-tap confirmation."
version: 0.1.0
author: Hermes project team
license: MIT
platforms: [windows, linux, darwin]
metadata:
  hermes:
    category: calendar
    tags: [calendar, schedule, events, meetings, free-slots]
---

# Google Calendar Integration & Schedule Management

## Overview

Manage meetings, appointments, and daily agendas from Telegram with strict privacy boundaries, automatic timezone handling (ICT / Asia/Ho_Chi_Minh default), and Tier 2 approval discipline.

## Capabilities

1. **Agenda Lookup & Event Listing (`calendar_list_events`):**
   - Query events for today, tomorrow, or a custom time range (e.g. `time_min`, `time_max`, `query`).
   - Supports filtering by specific account via `account_email` (e.g. `'work@company.com'` or `'personal@gmail.com'`).
   - Returns event titles, start/end times, locations, and attendee lists.

2. **Event Inspection (`calendar_get_event`):**
   - Retrieves full details of a specific event using its `event_id`.
   - Returns attendee RSVPs, Google Meet video link, and description.

3. **Rescheduling & Updating Events (`calendar_update_event`):**
   - Use whenever user asks to reschedule (dời lịch), move time, update location, change title, or edit attendees of an existing event.
   - Accepts `event_id` (REQUIRED), `start_time`, `end_time`, `summary`, `location`, `description`, `attendees`, and `account_email`.
   - Uses patch semantics: only specified fields are modified, other event attributes remain untouched.

4. **Canceling & Deleting Events (`calendar_delete_event`):**
   - Use whenever user asks to cancel, remove, or delete a calendar event.
   - Accepts `event_id` (REQUIRED), `calendar_id`, and `account_email`.

5. **Direct Event Creation (`calendar_create_event`):**
   - Directly schedules and commits an event to Google Calendar when user explicitly issues a direct booking request without requesting review.
   - Accepts `summary`, `start_time`, `end_time` (or `duration_minutes`), `location`, `description`, `attendees`, and `account_email`.

6. **Tier 2 Event Drafting (`calendar_create_draft_event`):**
   - Stages an event draft with title, start/end time, description, location, attendees, and target `account_email`.
   - Computes an idempotency key to prevent accidental duplicate bookings.
   - Returns a `draft_id` and formatted summary for user review.

7. **Event Confirmation (`calendar_confirm_event`):**
   - Once user confirms via Telegram 1-tap approval or chat confirmation ("ok", "đồng ý"), commits the draft to Google Calendar.
   - Uses the draft's target `account_email` to commit to the exact requested Google account.
   - Returns verified Google Event ID and Google Calendar URL as machine-verifiable evidence.

8. **Free Slot Discovery (`calendar_find_free_slots`):**
   - Discovers available contiguous time windows on a given date (e.g. `2026-09-04`).
   - Bounded by working hours (09:00 - 18:00 ICT default) and existing busy events.
   - Filterable by minimum meeting duration (default 30 minutes) and target `account_email`.

9. **Connection Status (`calendar_status`):**
   - Checks connection status and enumerates all linked Google accounts.

## Operating Rules

- **Native Tools Only:** Always use the registered tools `calendar_list_events`, `calendar_get_event`, `calendar_create_event`, `calendar_create_draft_event`, `calendar_confirm_event`, `calendar_update_event`, `calendar_delete_event`, `calendar_find_free_slots`, `calendar_status`. Do NOT invoke terminal Python scripts, `google_workspace.py`, or legacy external tools.
- **Reschedule Workflow:** When user says "dời lịch X sang 14h-14h30":
  1. If event ID is not known, call `calendar_list_events` with query to locate the event and obtain its `event_id`.
  2. Call `calendar_update_event(event_id=..., start_time="...", end_time="...", account_email=...)`.
  3. Confirm the updated time clearly with user.
- **Tier 2 Draft-Before-Commit:** When user asks to draft, propose, or stage a meeting, use `calendar_create_draft_event` and wait for confirmation before calling `calendar_confirm_event`.
- **Multi-Account Routing:** If user specifies an email or has multiple connected mailboxes, pass `account_email` to route operations to the correct calendar.
- **Privacy & Host Identity:** Calendar access is strictly DM-only per user; requests in group chats redirect to DM.
- **Working Hours & Lookahead:** Calendar operations are bounded by configured policy (maximum 30 days lookahead, 15 to 480 minutes duration).
- **Timezone Awareness:** All times format cleanly in local ICT (UTC+7) when presenting to users.
