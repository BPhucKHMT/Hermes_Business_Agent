from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any, Dict


@dataclass(frozen=True)
class WorkingHours:
    start: str
    end: str


@dataclass(frozen=True)
class CalendarPolicy:
    schema_version: int
    default_timezone: str
    working_hours: WorkingHours
    max_lookahead_days: int
    max_event_duration_minutes: int
    min_event_duration_minutes: int
    max_list_results: int
    scopes: tuple[str, ...]

    def validate_event_time_window(self, start_time: datetime, end_time: datetime) -> None:
        if end_time <= start_time:
            raise ValueError("end_time_must_be_after_start_time")
        duration_minutes = (end_time - start_time).total_seconds() / 60.0
        if duration_minutes < self.min_event_duration_minutes:
            raise ValueError(f"event_duration_too_short_minimum_{self.min_event_duration_minutes}_minutes")
        if duration_minutes > self.max_event_duration_minutes:
            raise ValueError(f"event_duration_too_long_maximum_{self.max_event_duration_minutes}_minutes")

    def validate_lookahead(self, start_time: datetime, now: datetime | None = None) -> None:
        current = now or datetime.now(timezone.utc)
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        max_future = current + timedelta(days=self.max_lookahead_days)
        if start_time > max_future:
            raise ValueError(f"lookahead_window_exceeded_maximum_{self.max_lookahead_days}_days")


def load_calendar_policy(path: Path | str) -> CalendarPolicy:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("invalid_calendar_policy")
    if data.get("schema_version") != 1:
        raise ValueError("unsupported_policy_schema_version")
    wh = data.get("working_hours", {})
    return CalendarPolicy(
        schema_version=int(data["schema_version"]),
        default_timezone=str(data.get("default_timezone", "Asia/Ho_Chi_Minh")),
        working_hours=WorkingHours(start=str(wh.get("start", "09:00")), end=str(wh.get("end", "18:00"))),
        max_lookahead_days=int(data.get("max_lookahead_days", 30)),
        max_event_duration_minutes=int(data.get("max_event_duration_minutes", 480)),
        min_event_duration_minutes=int(data.get("min_event_duration_minutes", 15)),
        max_list_results=int(data.get("max_list_results", 50)),
        scopes=tuple(data.get("scopes", ())),
    )
