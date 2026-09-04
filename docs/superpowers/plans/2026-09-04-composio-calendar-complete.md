# Complete Composio Google Calendar Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement full-featured Google Calendar capabilities (get, list, direct create, draft+confirm create, reschedule/patch, update, delete, free-busy, multi-account targeting) using native Composio actions while removing legacy raw Google REST OAuth code.

**Architecture:** Single source of truth via Composio v3 SDK (`googlesuper` / `googlecalendar` toolkits). Host-bound isolation via Telegram user IDs. Universal account target resolution (`resolve_account_target`). Draft persistence in SQLite storing `account_email`. Clean fallback between `GOOGLESUPER_*` and `GOOGLECALENDAR_*` slugs.

**Tech Stack:** Python 3.11/3.12, Composio SDK v3, SQLite3, Pytest.

## Global Constraints
- **Zero Raw OAuth HTTP / Ports:** Do not bind ports 8765/8766 or issue direct Google REST API tokens; all calendar calls route via Composio.
- **Dynamic Multi-Account:** All tools accept `account_email` and map to valid account connection IDs; never hardcode emails.
- **100% Verification Parity:** All 18 repository test suites across Layer 1 and Layer 2 must pass 100%.

---

### Task 1: Expand `src/tools/composio/calendar_tools.py`
Add `composio_calendar_get_event`, `composio_calendar_patch_event`, and `composio_calendar_delete_event`.

**Files:**
- Modify: `src/tools/composio/calendar_tools.py`
- Test: `tests/google_calendar/test_composio_calendar.py`

- [ ] **Step 1: Write failing tests in `tests/google_calendar/test_composio_calendar.py`**
- [ ] **Step 2: Run pytest to verify tests fail**
- [ ] **Step 3: Implement functions in `src/tools/composio/calendar_tools.py`**
- [ ] **Step 4: Run pytest to verify tests pass**
- [ ] **Step 5: Commit changes**

---

### Task 2: Persist `account_email` in EventDraft Contracts & SQLite Store
Update `EventDraft` dataclass and `CalendarStore` to store `account_email`.

**Files:**
- Modify: `src/tools/calendar/contracts.py`
- Modify: `src/tools/calendar/store.py`
- Test: `tests/google_calendar/test_store.py`

- [ ] **Step 1: Write failing test in `tests/google_calendar/test_store.py`**
- [ ] **Step 2: Run pytest to verify failure**
- [ ] **Step 3: Add `account_email` to `EventDraft` and update `CalendarStore` migration & queries**
- [ ] **Step 4: Run pytest to verify pass**
- [ ] **Step 5: Commit changes**

---

### Task 3: Expose & Register All Calendar Tools in Plugin
Register `calendar_get_event`, `calendar_create_event`, `calendar_update_event`, `calendar_delete_event` alongside existing tools in `calendar-connector`.

**Files:**
- Modify: `src/.hermes/plugins/calendar-connector/calendar_schemas.py`
- Modify: `src/.hermes/plugins/calendar-connector/calendar_plugin_tools.py`
- Modify: `src/.hermes/plugins/calendar-connector/plugin.yaml`
- Modify: `src/.hermes/plugins/calendar-connector/__init__.py`
- Test: `tests/verify_calendar.py`

- [ ] **Step 1: Add schemas for `calendar_get_event`, `calendar_create_event`, `calendar_update_event`, `calendar_delete_event`**
- [ ] **Step 2: Add handlers in `calendar_plugin_tools.py`**
- [ ] **Step 3: Register tools in `__init__.py` and `plugin.yaml`**
- [ ] **Step 4: Run `verify_calendar.py --layer 1` and `--layer 2`**
- [ ] **Step 5: Commit changes**

---

### Task 4: Update Calendar Skill Documentation
Update `src/skills/calendar/SKILL.md` to instruct the LLM on tool selection for listing, getting, direct creating, drafting, rescheduling/updating, and deleting events.

**Files:**
- Modify: `src/skills/calendar/SKILL.md`
- Test: `tests/verify_calendar.py --layer 1`

- [ ] **Step 1: Update `SKILL.md` with concrete tool descriptions and example user prompts**
- [ ] **Step 2: Verify Layer 1 assertions pass**
- [ ] **Step 3: Commit changes**

---

### Task 5: Clean Up Legacy OAuth Remnants in `src/tools/calendar/`
Ensure `src/tools/calendar/` delegates all execution to Composio without raw OAuth fallbacks.

**Files:**
- Modify: `src/tools/calendar/google_calendar.py`
- Modify: `src/tools/calendar/service.py`
- Test: `tests/verify_calendar.py`

- [ ] **Step 1: Clean raw token refreshing code and point to Composio**
- [ ] **Step 2: Verify `verify_calendar.py` layer 1 and layer 2 pass**
- [ ] **Step 3: Commit changes**

---

### Task 6: Full Verification Across All 18 Test Suites & Live Calendar
Run all 18 repository test suites and perform live verification on the connected accounts.

- [ ] **Step 1: Run all 18 verification suites**
- [ ] **Step 2: Run live verification script for create, patch, and delete**
- [ ] **Step 3: Sync plugin to `%LOCALAPPDATA%\hermes\plugins\` and restart Gateway**
