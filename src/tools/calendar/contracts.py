from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json


class EventDraftStatus(str, Enum):  # noqa: UP042 -- preserve legacy Enum string behavior
    DRAFT = "draft"
    APPROVED = "approved"
    COMMITTED = "committed"
    CANCELLED = "cancelled"


class CalendarConnectionStatus(str, Enum):  # noqa: UP042 -- preserve legacy Enum string behavior
    CONNECTED = "connected"
    RECONNECT_REQUIRED = "reconnect_required"
    REVOKED = "revoked"


@dataclass(frozen=True)
class CalendarEvent:
    event_id: str
    calendar_id: str
    summary: str
    description: str
    location: str
    start_time: str
    end_time: str
    html_link: str
    status: str = "confirmed"
    attendees: tuple[str, ...] = ()
    is_all_day: bool = False


@dataclass(frozen=True)
class EventDraft:
    draft_id: str
    idempotency_key: str
    principal_id: str
    calendar_id: str
    summary: str
    description: str
    location: str
    start_time: str
    end_time: str
    attendees: tuple[str, ...]
    created_at: str
    status: EventDraftStatus = EventDraftStatus.DRAFT
    committed_event_id: str | None = None
    account_email: str | None = None


@dataclass(frozen=True)
class FreeSlot:
    start_time: str
    end_time: str
    duration_minutes: int


@dataclass(frozen=True)
class CalendarConnection:
    connection_id: str
    principal_id: str
    email: str
    calendar_id: str
    calendar_name: str
    status: CalendarConnectionStatus = CalendarConnectionStatus.CONNECTED
    created_at: str = ""
    updated_at: str = ""


@dataclass(frozen=True)
class EventVerification:
    verified: bool
    event_id: str
    html_link: str
    observed_at: str


def compute_draft_idempotency_key(
    principal_id: str,
    calendar_id: str,
    summary: str,
    start_time: str,
    end_time: str,
    account_email: str | None = None,
) -> str:
    """Build a stable draft key, including an explicit account target when set."""
    payload = {
        "calendar_id": calendar_id.strip(),
        "end_time": end_time.strip(),
        "principal_id": principal_id.strip(),
        "start_time": start_time.strip(),
        "summary": summary.strip().lower(),
    }
    normalized_account = account_email.strip().casefold() if account_email else ""
    if normalized_account:
        payload["account_email"] = normalized_account
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
