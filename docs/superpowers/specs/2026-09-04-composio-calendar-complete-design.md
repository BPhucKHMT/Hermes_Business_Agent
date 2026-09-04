# Design Spec: Complete Composio Google Calendar Integration

**Date:** 2026-09-04  
**Status:** Proposed  
**Author:** AI Engineering Agent  
**Topic:** End-to-End Composio Calendar Integration, Multi-Account Targeting, Reschedule/Update/Delete Operations, and Legacy Clean Cutover

---

## 1. Problem Statement & Objectives

### 1.1 Observed Defects
1. **Inability to Reschedule or Update Events:** In live Telegram testing, when the user asked *"bạn dời lịch ở đây từ 14h đến 14h30 đi"*, the agent searched for tools and replied that the system lacked any update/reschedule capability.
2. **Missing `account_email` in Draft Staging:** `CALENDAR_CREATE_DRAFT_EVENT_SCHEMA` did not accept `account_email`. When creating a draft for a specific account (e.g. `baophuc1204vn@gmail.com`), the account target was lost, causing the event to fail creation or route to the default account.
3. **Draft Confirmation Did Not Persist to Google Calendar:** When confirming drafts, the legacy service invoked raw HTTP calls with invalid bearer tokens (`ca_...` connection IDs) instead of delegating execution to Composio SDK.
4. **Lack of Deletion & Get Event Tools:** The connector lacked tools for canceling/deleting events and fetching specific event details.
5. **Obsolete Legacy Code:** Remnants of legacy SQLite OAuth and raw Google REST callers remained in the codebase instead of unifying fully onto Composio.

### 1.2 Core Objectives
1. **100% Native Composio Tool Slugs:** Utilize Composio's verified Google Workspace actions (`GOOGLESUPER_PATCH_EVENT`, `GOOGLESUPER_UPDATE_EVENT`, `GOOGLESUPER_CREATE_EVENT`, `GOOGLESUPER_DELETE_EVENT`, `GOOGLESUPER_EVENTS_GET`, `GOOGLESUPER_EVENTS_LIST`, `GOOGLESUPER_FIND_FREE_SLOTS`).
2. **Full Calendar Capability Suite:**
   - List & search events (`calendar_list_events`)
   - Get single event details (`calendar_get_event`)
   - Direct create & Draft-before-commit create (`calendar_create_event`, `calendar_create_draft_event`, `calendar_confirm_event`)
   - Reschedule & Update existing event (`calendar_update_event`)
   - Cancel & Delete event (`calendar_delete_event`)
   - Free/busy slot discovery (`calendar_find_free_slots`)
   - Multi-account connection status (`calendar_status`)
3. **Universal Multi-Account Support:** All tools accept `account_email` and dynamically resolve the connection target via `resolve_account_target`.
4. **Clean Cutover & Purge:** Remove obsolete raw Google OAuth REST logic and ensure 100% test suite pass rate across all 18 repository test suites.

---

## 2. Architecture & Component Interfaces

### 2.1 Composio Calendar Tools (`src/tools/composio/calendar_tools.py`)
Provides host-bound, multi-account isolated helper functions:
- `composio_calendar_list_events(telegram_user_id, calendar_id, account_email, time_min, time_max, query, limit)`
- `composio_calendar_get_event(telegram_user_id, event_id, calendar_id, account_email)`
- `composio_calendar_create_event(telegram_user_id, summary, start_datetime, duration_minutes, end_datetime, description, location, attendees, calendar_id, account_email)`
- `composio_calendar_patch_event(telegram_user_id, event_id, calendar_id, account_email, start_time, end_time, summary, description, location, attendees)`
- `composio_calendar_delete_event(telegram_user_id, event_id, calendar_id, account_email)`
- `composio_calendar_find_free_slots(telegram_user_id, date_str, duration_minutes, calendar_id, account_email)`

### 2.2 Plugin Registration (`src/.hermes/plugins/calendar-connector/`)
Registered tools exposed to the Telegram LLM:
1. `calendar_list_events`: List upcoming events with optional time range and query.
2. `calendar_get_event`: Fetch specific event details by `event_id`.
3. `calendar_create_event`: Directly create an event.
4. `calendar_create_draft_event`: Stage a Tier 2 event draft (now stores `account_email`).
5. `calendar_confirm_event`: Confirm and commit a staged draft.
6. `calendar_update_event`: Reschedule or modify an existing event (`start_time`, `end_time`, `summary`, `location`, `description`, `attendees`).
7. `calendar_delete_event`: Cancel and delete an existing event.
8. `calendar_find_free_slots`: Inspect open meeting windows.
9. `calendar_status`: Inspect all connected Google accounts.

### 2.3 Draft Contract Update (`src/tools/calendar/contracts.py` & `store.py`)
- Update `EventDraft` dataclass to include `account_email: Optional[str] = None`.
- Update `CalendarStore` SQLite schema to store `account_email TEXT` with automatic column migration (`ALTER TABLE event_drafts ADD COLUMN account_email TEXT`).

---

## 3. Data Flow & Execution Sequences

### 3.1 Reschedule Flow ("Dời lịch")
1. User: *"bạn dời lịch ở đây từ 14h đến 14h30 đi"*
2. Bot calls `calendar_list_events` (or uses existing event ID in context): finds event `prhvidj4in6ql77bunrl0act58`.
3. Bot calls `calendar_update_event(event_id="prhvidj4in6ql77bunrl0act58", start_time="2026-09-04T14:00:00+07:00", end_time="2026-09-04T14:30:00+07:00", account_email="baophuc1204vn@gmail.com")`.
4. Composio executes `GOOGLESUPER_PATCH_EVENT` with `account="ca_ksR5CZdrvhZr"`.
5. Google Calendar updates event start/end timestamps.
6. Bot reports updated details with Google Calendar link.

### 3.2 Draft-Before-Commit Flow ("Tạo lịch")
1. User: *"Tạo lịch họp chiều nay"*
2. Bot calls `calendar_create_draft_event(summary="Project web", start_time="...", end_time="...", account_email="baophuc1204vn@gmail.com")`.
3. Bot presents staged draft: *"Mình đã tạo bản nháp... Bạn xác nhận nhé?"*
4. User: *"ok"*
5. Bot calls `calendar_confirm_event(draft_id="...")`.
6. Connector retrieves draft, reads stored `account_email="baophuc1204vn@gmail.com"`, and calls `composio_calendar_create_event` with target account.
7. Event is committed on Google Calendar and verified.

### 3.3 Delete Flow ("Hủy / Xóa lịch")
1. User: *"Hủy lịch Project web"*
2. Bot calls `calendar_delete_event(event_id="...", account_email="baophuc1204vn@gmail.com")`.
3. Composio executes `GOOGLESUPER_DELETE_EVENT` with `account="ca_ksR5CZdrvhZr"`.
4. Bot confirms event was removed from calendar.

---

## 4. Verification & Testing Strategy
1. **Unit Tests:**
   - Expand `tests/google_calendar/test_composio_calendar.py` and `tests/test_composio_calendar.py` to cover `patch_event`, `delete_event`, `get_event`, `create_event`, and `confirm_event` with `account_email`.
2. **Layer 1 & Layer 2 Gating:**
   - Ensure `tests/verify_calendar.py` and `tests/verify_composio.py` pass 100%.
   - Ensure all 18 repository test suites maintain 100% pass rate.
3. **Live Composio Verification:**
   - Verify create, patch, get, and delete on real connected account `baophuc1204vn@gmail.com`.
