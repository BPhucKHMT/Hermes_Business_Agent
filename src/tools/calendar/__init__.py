"""Calendar tool package for Hermes Agent."""

from tools.calendar.contracts import (
    CalendarConnection,
    CalendarConnectionStatus,
    CalendarEvent,
    EventDraft,
    EventDraftStatus,
    EventVerification,
    FreeSlot,
    compute_draft_idempotency_key,
)
from tools.calendar.google_calendar import GoogleCalendarClient
from tools.calendar.policy import CalendarPolicy, load_calendar_policy
from tools.calendar.service import CalendarService
from tools.calendar.store import CalendarStore

__all__ = [
    "CalendarConnection",
    "CalendarConnectionStatus",
    "CalendarEvent",
    "CalendarPolicy",
    "CalendarService",
    "CalendarStore",
    "EventDraft",
    "EventDraftStatus",
    "EventVerification",
    "FreeSlot",
    "GoogleCalendarClient",
    "compute_draft_idempotency_key",
    "load_calendar_policy",
]
