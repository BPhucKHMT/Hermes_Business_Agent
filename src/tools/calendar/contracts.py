from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from typing import Any, Optional
from uuid import uuid4


class EventDraftStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    COMMITTED = "committed"
    CANCELLED = "cancelled"


class CalendarConnectionStatus(str, Enum):
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
    committed_event_id: Optional[str] = None


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
) -> str:
    payload = {
        "calendar_id": calendar_id.strip(),
        "end_time": end_time.strip(),
        "principal_id": principal_id.strip(),
        "start_time": start_time.strip(),
        "summary": summary.strip().lower(),
    }
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
