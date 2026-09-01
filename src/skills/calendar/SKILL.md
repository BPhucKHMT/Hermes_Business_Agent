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
   - Query events for today, tomorrow, or a custom time range (e.g. `time_min`, `time_max`).
   - Returns event titles, start/end times, locations, and attendee lists.

2. **Free Slot Discovery (`calendar_find_free_slots`):**
   - Discovers available contiguous time windows on a given date (e.g. `2026-09-01`).
   - Bounded by working hours (09:00 - 18:00 ICT default) and existing busy events.
   - Filterable by minimum meeting duration (default 30 minutes).

3. **Tier 2 Event Drafting (`calendar_create_draft_event`):**
   - Stages an event draft with title, start/end time, description, location, and attendees.
   - Computes an idempotency key to prevent accidental duplicate bookings.
   - Returns a `draft_id` and formatted summary for user review.

4. **Event Confirmation (`calendar_confirm_event`):**
   - Once user confirms via Telegram 1-tap approval or chat confirmation, commits the draft to Google Calendar.
   - Returns verified Google Event ID and Google Calendar URL as machine-verifiable evidence.

5. **Connection Status (`calendar_status`):**
   - Checks connection status and primary calendar details.

## Operating Rules

- **Native Tools Only:** Always use the registered tools `calendar_list_events`, `calendar_find_free_slots`, `calendar_create_draft_event`, `calendar_confirm_event`, `calendar_status`. Do NOT invoke terminal Python scripts, `google_workspace.py`, or legacy external tools.
- **Tier 2 Draft-Before-Commit:** Never create or overwrite calendar events without staging a draft and presenting details to the user for explicit confirmation.
- **Privacy & Host Identity:** Calendar access is strictly DM-only per user; requests in group chats redirect to DM.
- **Working Hours & Lookahead:** Calendar operations are bounded by configured policy (maximum 30 days lookahead, 15 to 480 minutes duration).
- **Timezone Awareness:** All times format cleanly in local ICT (UTC+7) when presenting to users.
