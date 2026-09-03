# Composio Google Workspace Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the fragile custom local HTTP servers for email and calendar with a unified, production-ready Composio integration supporting strict multi-user data isolation, full Gmail (read/send/draft), and Google Calendar (list/create/manage) functionality.

**Architecture:** A native Python module under `src/tools/composio/` encapsulating Composio Core SDK, enforcing host-bound `user_id = f"telegram_{telegram_user_id}"` to prevent cross-user data leakage, exposing registered tools to Hermes Agent, providing Telegram slash commands (`/connect-google`, `/google-status`, `/disconnect-google`), and verified with comprehensive Layer 1 and Layer 2 tests.

**Tech Stack:** Python 3.11+, `composio-core`, PyYAML, pytest.

## Global Constraints

- Never expose or allow the LLM to choose or override `user_id`. It must always be derived by the host from the caller's verified Telegram ID.
- Never run background HTTP server daemons on local ports (no port 8766/8765 bindings).
- Keep credentials safe in `.env` (`COMPOSIO_API_KEY`), never hardcode secrets.
- All code must pass PEP 8, clean code guidelines, and 100% of existing + new test suites.

---

### Task 1: Environment and Dependency Setup

**Files:**
- Modify: `src/requirements.txt` (or dependency manifest)
- Modify: `src/.env.example`
- Test: Virtual environment check for `composio` import

**Interfaces:**
- Produces: `composio` import available in `src/.venv` and `COMPOSIO_API_KEY` placeholder in configuration.

- [ ] **Step 1: Install `composio-core` in `src/.venv`**
- [ ] **Step 2: Add `COMPOSIO_API_KEY=` to `src/.env.example` and config templates**
- [ ] **Step 3: Verify import and version in virtualenv**

---

### Task 2: Implement Composio Client and Multi-User Auth Engine

**Files:**
- Create: `src/tools/composio/__init__.py`
- Create: `src/tools/composio/client.py`
- Create: `src/tools/composio/auth.py`
- Test: `tests/test_composio_auth.py`

**Interfaces:**
- Produces:
  - `get_composio_client() -> Composio`
  - `format_user_id(telegram_user_id: int | str) -> str`
  - `initiate_google_connection(telegram_user_id: int | str) -> str (auth_url)`
  - `check_connection_status(telegram_user_id: int | str, toolkit: str = "gmail") -> bool`
  - `disconnect_user(telegram_user_id: int | str) -> bool`

- [ ] **Step 1: Write test for client initialization and user ID isolation**
- [ ] **Step 2: Implement `client.py` with singleton/lazy initialization and API key validation**
- [ ] **Step 3: Implement `auth.py` managing multi-user connections**
- [ ] **Step 4: Run unit tests to verify isolation and URL generation**

---

### Task 3: Implement Composio Gmail Toolset

**Files:**
- Create: `src/tools/composio/mail_tools.py`
- Test: `tests/test_composio_mail.py`

**Interfaces:**
- Produces:
  - `composio_mail_search(telegram_user_id: int | str, query: str = "label:inbox", max_results: int = 5) -> dict`
  - `composio_mail_read(telegram_user_id: int | str, thread_id: str) -> dict`
  - `composio_mail_send(telegram_user_id: int | str, recipient: str, subject: str, body: str) -> dict`
  - `composio_mail_create_draft(telegram_user_id: int | str, recipient: str, subject: str, body: str) -> dict`

- [ ] **Step 1: Write test verifying tool inputs and host-enforced `user_id`**
- [ ] **Step 2: Implement `mail_tools.py` wrapping `GMAIL_FETCH_EMAILS`, `GMAIL_SEND_EMAIL`, `GMAIL_CREATE_EMAIL_DRAFT`**
- [ ] **Step 3: Test execution and error handling (unauthenticated vs authenticated)**

---

### Task 4: Implement Composio Google Calendar Toolset

**Files:**
- Create: `src/tools/composio/calendar_tools.py`
- Test: `tests/test_composio_calendar.py`

**Interfaces:**
- Produces:
  - `composio_calendar_list_events(telegram_user_id: int | str, time_min: str = None, time_max: str = None) -> dict`
  - `composio_calendar_create_event(telegram_user_id: int | str, summary: str, start_time: str, duration_minutes: int = 30, description: str = "", attendees: list = None) -> dict`
  - `composio_calendar_find_free_slots(telegram_user_id: int | str, date_str: str) -> dict`

- [ ] **Step 1: Write test verifying calendar operations and attendee formatting**
- [ ] **Step 2: Implement `calendar_tools.py` wrapping `GOOGLECALENDAR_FIND_EVENT`, `GOOGLECALENDAR_CREATE_EVENT`**
- [ ] **Step 3: Test execution with mock responses**

---

### Task 5: Implement Telegram Slash Commands and Gateway Registration

**Files:**
- Create: `src/tools/composio/commands.py`
- Create: `src/skills/google_workspace/skill.yaml` (or tool definitions)
- Test: `tests/test_composio_commands.py`

**Interfaces:**
- Produces:
  - `/connect-google` command handler
  - `/google-status` command handler
  - `/disconnect-google` command handler
  - Tool registration so LLM can call Gmail & Calendar tools dynamically

- [ ] **Step 1: Write test for command handlers**
- [ ] **Step 2: Implement `commands.py` generating friendly markdown Telegram messages**
- [ ] **Step 3: Register commands and tools with Hermes Gateway dispatch**

---

### Task 6: Implement Verification Suite and Production Setup Parity

**Files:**
- Create: `tests/verify_composio.py`
- Modify: `src/setup_production.sh`
- Test: Full 17-suite test run

**Interfaces:**
- Produces:
  - `python tests/verify_composio.py --layer 1`
  - `python tests/verify_composio.py --layer 2`
  - Automatic `pip install composio-core` and verification in `setup_production.sh`

- [ ] **Step 1: Create `tests/verify_composio.py` with static and behavior checks**
- [ ] **Step 2: Update `src/setup_production.sh` to include Composio check in self-test**
- [ ] **Step 3: Run all verification suites to ensure 100% clean passes**
